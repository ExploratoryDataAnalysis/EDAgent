"""Plan with the provider, compute locally, and explain only from the result."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any, Dict, List

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import sanitize_prompt_data
from app.models.dataset import Dataset
from app.models.session import AnalysisSession
from app.repositories.session_repository import SessionRepository
from app.schemas.analysis import StructuredAnalysisPlan
from app.schemas.chat import ChatKind, ChatResponse
from app.services import analysis_service, dataset_service
from app.services.ai import grounding, prompts
from app.services.ai.context import DatasetContext, build_context
from app.services.ai.llm import LLMError, ai_status, get_llm_client
from app.services.analysis import catalogue, engine
from app.services.analysis.common import AnalysisError, PlanValidationError

logger = logging.getLogger("edagent.chat")

HISTORY_TURNS = 4
# A repair and time spent waiting for a compute slot both count against this deadline.
CHAT_WORK_SECONDS = 45
CHAT_COMPUTE_SECONDS = 30
# The endpoint gives persistence a small margin after the last possible provider call.
CHAT_RESPONSE_SECONDS = 50
_PLAN_FIELDS = set(StructuredAnalysisPlan.model_fields)


# ---------------------------------------------------------------------------
# Parsing model output
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Dict[str, Any]:
    """Require one JSON object, with no surrounding prose."""
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("top-level JSON is not an object")
    return obj


def _map_names(plan: Dict[str, Any], name_map: Dict[str, str]) -> Dict[str, Any]:
    """Maps the (sanitised) column names the model saw back to the real column names."""
    def m(v: Any) -> Any:
        return name_map.get(v, v) if isinstance(v, str) else v

    def mlist(v: Any) -> Any:
        return [m(x) for x in v] if isinstance(v, list) else v

    def mfilter(g: Any) -> Any:
        if not isinstance(g, dict):
            return g
        out = dict(g)
        conds = []
        conditions = g.get("conditions", [])
        if not isinstance(conditions, list):
            return g  # Leave invalid shapes for the schema to reject.
        for c in conditions:
            if isinstance(c, dict) and "conditions" in c:
                conds.append(mfilter(c))
            elif isinstance(c, dict):
                conds.append({**c, "column": m(c.get("column"))})
            else:
                conds.append(c)
        out["conditions"] = conds
        return out

    p = dict(plan)
    for key in ("column", "date_column", "sort_by"):
        if key in p:
            p[key] = m(p[key])
    for key in ("target_columns", "group_by"):
        if key in p:
            p[key] = mlist(p[key])
    if p.get("filters"):
        p["filters"] = mfilter(p["filters"])
    if isinstance(p.get("parameters"), dict):
        p["parameters"] = {k: (mlist(v) if isinstance(v, list) else m(v)) for k, v in p["parameters"].items()}
    return p


def parse_plan(raw_plan: Dict[str, Any], ctx: DatasetContext) -> StructuredAnalysisPlan:
    """Builds a StructuredAnalysisPlan from model JSON; unknown keys are dropped, not trusted."""
    cleaned = {k: v for k, v in raw_plan.items() if k in _PLAN_FIELDS and v is not None}
    # The model may only choose *what* to compute; execution limits come from server settings.
    for forced in ("seed",):
        cleaned.pop(forced, None)
    return StructuredAnalysisPlan.model_validate(_map_names(cleaned, ctx.name_map))


def _problems_from_validation(e: ValidationError) -> List[str]:
    return [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:8]]


# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

def _history_text(turns: List[Any]) -> str:
    if not turns:
        return "(no earlier questions)"
    lines = []
    for t in turns[-HISTORY_TURNS:]:
        q = sanitize_prompt_data(t.user_query, 300)
        lines.append(f"Q: {q}")
        if t.structured_plan:
            lines.append(f"Plan used: {json.dumps(t.structured_plan, default=str)[:900]}")
        if t.result is not None:
            lines.append(f"Computed summary: {sanitize_prompt_data(t.result.summary_text, 300)}")
        elif t.kind != "analysis":
            lines.append(f"(that question ended with: {t.kind})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Messages for the failure modes
# ---------------------------------------------------------------------------

_LLM_MESSAGES = {
    "timeout": "The AI provider took too long to respond, so I could not interpret your question. Please try again in a moment.",
    "rate_limit": "The AI provider is rate-limiting requests right now. Please wait a little and try again.",
    "auth": "The AI provider rejected the server's API key. An administrator needs to check the AI configuration.",
    "token_limit": "The question or dataset description exceeded the model's limits. Try a narrower question.",
    "configuration": "The AI provider rejected the server's settings. An administrator needs to check the provider and model.",
    "unavailable": "The AI provider is temporarily unavailable. Please try again shortly.",
    "bad_response": "The AI provider returned something I could not understand. Please try again.",
}
_MANUAL_HINT = " You can run the analysis in the Analysis Workspace."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _stage(name: str, deadline: float, limit: float):
    started = perf_counter()
    outcome = "ok"
    try:
        now = asyncio.get_running_loop().time()
        if now >= deadline:
            raise TimeoutError
        async with asyncio.timeout_at(min(deadline, now + limit)):
            yield
    except TimeoutError:
        outcome = "timeout"
        raise
    except LLMError as e:
        outcome = e.kind
        raise
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except Exception as e:
        # Exception text can include column names, HTTP destinations or SQL values.
        outcome = type(e).__name__
        raise
    finally:
        logger.log(logging.INFO if outcome == "ok" else logging.WARNING,
                   "chat stage=%s outcome=%s elapsed_ms=%.1f", name, outcome, (perf_counter() - started) * 1000)


async def handle_chat(
    db: AsyncSession,
    session: AnalysisSession,
    dataset: Dataset,
    message: str,
) -> ChatResponse:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + CHAT_WORK_SECONDS
    client = get_llm_client()

    async def finish(kind: ChatKind, reply: str, *, plan=None, result=None, source=None, suggestions=None, err=None, clarify=None, cannot=None) -> ChatResponse:
        async with _stage("save", deadline + CHAT_RESPONSE_SECONDS - CHAT_WORK_SECONDS, CHAT_RESPONSE_SECONDS):
            req = await analysis_service.persist_turn(
                db, session, question=message, kind=kind.value, assistant_message=reply, plan=plan, result=result,
                explanation_source=source, error_message=err,
            )
        return ChatResponse(
            session_id=session.id, request_id=req.id, kind=kind, reply_text=reply,
            is_clarification_needed=kind == ChatKind.CLARIFICATION, clarifying_question=clarify, cannot_answer_reason=cannot,
            analysis_plan=plan, analysis_result=result, suggested_questions=suggestions or [], explanation_source=source,
            ai_configured=client is not None, created_at=req.created_at,
        )

    if client is None:
        logger.info("chat stage=planner outcome=disabled elapsed_ms=0")
        return await finish(ChatKind.AI_UNAVAILABLE, ai_status()["message"] + _MANUAL_HINT, err="disabled")

    async with _stage("prepare", deadline, CHAT_WORK_SECONDS):
        turns = await SessionRepository(db).turns(session.id)
        loaded = await dataset_service.load_for_analysis(db, dataset)
        profile = await dataset_service.get_or_compute_profile(db, dataset)
        ctx = build_context(dataset.name, profile, settings.LLM_MAX_CONTEXT_CHARS)
        system = prompts.PLANNER_SYSTEM.replace("{catalogue}", catalogue.catalogue_for_prompt())
        prompt = prompts.PLANNER_USER.format(
            context=ctx.text, history=_history_text(turns), question=sanitize_prompt_data(message, 2000),
        )

    problems: List[str] = []
    for stage in ("planner", "repair"):
        try:
            async with _stage(stage, deadline, settings.LLM_TIMEOUT_SECONDS):
                raw = await client.complete(system, prompt)
        except (TimeoutError, LLMError) as e:
            category = e.kind if isinstance(e, LLMError) else "timeout"
            return await finish(ChatKind.AI_UNAVAILABLE, _LLM_MESSAGES.get(category, _LLM_MESSAGES["unavailable"]) + _MANUAL_HINT, err=category)

        try:
            async with _stage("validate", deadline, CHAT_WORK_SECONDS):
                obj = extract_json(raw)
                kind = obj.get("type")
                if kind == "clarify":
                    question = obj.get("question")
                    options = obj.get("options", [])
                    if not isinstance(question, str) or not question.strip() or not isinstance(options, list) or not all(isinstance(o, str) for o in options):
                        raise ValueError("The clarification was malformed.")
                    question, options = question[:500], [o[:120] for o in options[:4]]
                elif kind == "cannot_answer":
                    reason = obj.get("reason")
                    if not isinstance(reason, str) or not reason.strip():
                        raise ValueError("The refusal was malformed.")
                    reason = reason[:600]
                elif kind == "plan" and isinstance(obj.get("plan"), dict):
                    plan = parse_plan(obj["plan"], ctx)
                    problems = catalogue.validate_plan(engine.effective_plan(plan, loaded), loaded)
                    if problems:
                        raise PlanValidationError(problems)
                else:
                    raise ValueError("The response did not contain a supported plan or question.")
        except ValidationError as e:
            problems = _problems_from_validation(e)
        except PlanValidationError as e:
            problems = e.errors
        except (ValueError, RecursionError):
            problems = ["The provider response did not match the required format."]
        else:
            if kind == "clarify":
                return await finish(ChatKind.CLARIFICATION, question, suggestions=options, clarify=question)
            if kind == "cannot_answer":
                return await finish(ChatKind.CANNOT_ANSWER, reason + _MANUAL_HINT, cannot=reason)
            break

        # Repair only a received, unusable answer. Never replay a failed provider POST.
        prompt += "\n\n" + prompts.REPAIR_USER.format(
            problems="\n".join(f"- {p}" for p in problems[:8]), previous=raw[:1500],
        )
    else:
        reason = "I could not turn that into a valid analysis: " + " ".join(problems[:3])
        return await finish(ChatKind.CANNOT_ANSWER, reason + _MANUAL_HINT, cannot=reason, err="invalid_plan")

    try:
        async with _stage("compute", deadline, CHAT_COMPUTE_SECONDS):
            result = await analysis_service.run_plan(db, dataset, plan)
            await analysis_service.add_multiple_test_warning(db, session.id, result)
    except (TimeoutError, AnalysisError, PlanValidationError) as e:
        msg = str(e) or "The analysis took too long. Try selecting fewer columns or filtering the dataset."
        return await finish(ChatKind.ERROR, msg + _MANUAL_HINT, plan=plan, err="compute_failed")

    # Computation has finished. Even a slow or rejected explanation must preserve this result.
    source = "fallback"
    scope_first = False
    try:
        async with _stage("explain", deadline, settings.LLM_TIMEOUT_SECONDS):
            raw = await client.complete(
                prompts.EXPLAINER_SYSTEM,
                prompts.EXPLAINER_USER.format(question=sanitize_prompt_data(message, 2000), facts=grounding.result_facts(result)),
                max_tokens=160,
            )
            selection = extract_json(raw)
            # Accept only an exact result reference and a fixed display choice. No provider prose
            # enters the explanation: even a real value can be attached to the wrong metric or unit.
            if (selection.keys() != {"result_id", "focus"} or selection["result_id"] != str(result.id)
                    or selection["focus"] not in ("summary", "scope")):
                raise LLMError("unsupported_explanation", "The provider did not select a supported explanation.")
            scope_first = selection["focus"] == "scope"
            source = "guided"
    except (TimeoutError, LLMError, ValueError, RecursionError):
        pass

    return await finish(
        ChatKind.ANALYSIS, grounding.template_explanation(result, scope_first=scope_first),
        plan=plan, result=result, source=source, suggestions=grounding.suggested_followups(result),
    )
