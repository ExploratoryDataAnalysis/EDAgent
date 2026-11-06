"""
AI chat orchestration.

    question -> dataset context -> LLM plan (JSON data) -> parse + validate (one repair retry)
             -> clarify / cannot answer / run approved backend tool -> validate result
             -> LLM explanation (numbers checked against the result) or deterministic text

Safety properties (each covered by tests):
* The model returns a *plan*; it never returns code and nothing it says is executed.
* Every column in the plan is validated against the real schema before running.
* Numbers in the prose must be traceable to the computed result, otherwise the deterministic
  explanation is shown instead.
* If the model is missing, slow, rate-limited or broken, the user gets a clear message and the
  rest of the app keeps working.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

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
from app.services.ai.llm import LLMClient, LLMError, ai_status, get_llm_client
from app.services.analysis import catalogue, engine
from app.services.analysis.common import AnalysisError, PlanValidationError

logger = logging.getLogger("edagent.chat")

HISTORY_TURNS = 4
_PLAN_FIELDS = set(StructuredAnalysisPlan.model_fields)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


# ---------------------------------------------------------------------------
# Parsing model output
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Dict[str, Any]:
    """Pulls the JSON object out of a model reply (tolerates fences and stray prose)."""
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    obj = json.loads(cleaned[start : end + 1])
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
        for c in g.get("conditions") or []:
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
            p[key] = mlist(p[key]) or []
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
    "token_limit": "This dataset's description is too large for the AI model's limits, even after shortening. Try a dataset with fewer columns.",
    "unavailable": "The AI provider is temporarily unavailable. Please try again shortly.",
    "bad_response": "The AI provider returned something I could not understand. Please try again.",
}
_MANUAL_HINT = " You can still run any analysis directly from the Workspace, and profiling, charts and reports do not need AI."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def _call_planner(client: LLMClient, system: str, user: str) -> str:
    return await client.complete(system, user, max_tokens=settings.LLM_MAX_TOKENS)


async def handle_chat(
    db: AsyncSession,
    session: AnalysisSession,
    dataset: Dataset,
    message: str,
) -> ChatResponse:
    repo = SessionRepository(db)
    turns = await repo.turns(session.id)
    configured = ai_status()["configured"]

    async def finish(kind: ChatKind, reply: str, *, plan=None, result=None, source=None, suggestions=None, err=None, clarify=None, cannot=None) -> ChatResponse:
        req = await analysis_service.persist_turn(
            db, session, question=message, kind=kind.value, assistant_message=reply, plan=plan, result=result,
            explanation_source=source, error_message=err,
        )
        return ChatResponse(
            session_id=session.id, request_id=req.id, kind=kind, reply_text=reply,
            is_clarification_needed=kind == ChatKind.CLARIFICATION, clarifying_question=clarify, cannot_answer_reason=cannot,
            analysis_plan=plan, analysis_result=result, suggested_questions=suggestions or [], explanation_source=source,
            ai_configured=configured, created_at=req.created_at,
        )

    client = get_llm_client()
    if client is None:
        return await finish(ChatKind.AI_UNAVAILABLE, ai_status()["message"] + _MANUAL_HINT)

    loaded = await dataset_service.load_for_analysis(db, dataset)
    profile = await dataset_service.get_or_compute_profile(db, dataset)
    history = _history_text(turns)
    system = prompts.PLANNER_SYSTEM.replace("{catalogue}", catalogue.catalogue_for_prompt())

    def user_prompt(ctx: DatasetContext) -> str:
        return prompts.PLANNER_USER.format(context=ctx.text, history=history, question=sanitize_prompt_data(message, 2000))

    # --- 1. plan (shrinks the context once if the provider says it is too large) ---
    ctx = build_context(dataset.name, profile, settings.LLM_MAX_CONTEXT_CHARS)
    try:
        try:
            raw = await _call_planner(client, system, user_prompt(ctx))
        except LLMError as e:
            if e.kind != "token_limit":
                raise
            ctx = build_context(dataset.name, profile, settings.LLM_MAX_CONTEXT_CHARS // 3)
            raw = await _call_planner(client, system, user_prompt(ctx))
    except LLMError as e:
        logger.warning("planner call failed: %s", e.kind)
        return await finish(ChatKind.AI_UNAVAILABLE, _LLM_MESSAGES.get(e.kind, _LLM_MESSAGES["unavailable"]) + _MANUAL_HINT, err=e.message)

    # --- 2. interpret + validate, with one repair attempt ---
    plan: Optional[StructuredAnalysisPlan] = None
    problems: List[str] = []
    for attempt in range(2):
        problems = []
        try:
            obj = extract_json(raw)
            kind = obj.get("type")
            if kind == "clarify":
                question = str(obj.get("question") or "Could you clarify what you would like to analyse?")[:500]
                options = [str(o)[:120] for o in (obj.get("options") or [])][:4]
                text = question + ("\n" + "\n".join(f"- {o}" for o in options) if options else "")
                return await finish(ChatKind.CLARIFICATION, text, suggestions=options, clarify=question)
            if kind == "cannot_answer":
                reason = str(obj.get("reason") or "The dataset does not contain what is needed to answer this.")[:600]
                return await finish(ChatKind.CANNOT_ANSWER, reason, cannot=reason, suggestions=[])
            if kind != "plan" or not isinstance(obj.get("plan"), dict):
                raise ValueError("response 'type' must be plan, clarify or cannot_answer")
            candidate = parse_plan(obj["plan"], ctx)
            problems = catalogue.validate_plan(engine.effective_plan(candidate, loaded), loaded)
            if not problems:
                plan = candidate
                break
        except ValidationError as e:
            problems = _problems_from_validation(e)
        except (ValueError, json.JSONDecodeError) as e:
            problems = [f"Invalid response: {e}"]
        if attempt == 0:
            try:
                raw = await _call_planner(client, system, user_prompt(ctx) + "\n\n" + prompts.REPAIR_USER.format(problems="\n".join(f"- {p}" for p in problems), previous=raw[:1500]))
            except LLMError as e:
                return await finish(ChatKind.AI_UNAVAILABLE, _LLM_MESSAGES.get(e.kind, _LLM_MESSAGES["unavailable"]) + _MANUAL_HINT, err=e.message)

    if plan is None:
        # Validation messages are already written for people ("column X not found, did you mean Y?").
        reason = "I could not turn that into a valid analysis: " + " ".join(problems[:3])
        return await finish(ChatKind.CANNOT_ANSWER, reason, cannot=reason, err="; ".join(problems[:5]))

    # --- 3. run the approved backend tool ---
    try:
        result = await analysis_service.run_plan(db, dataset, plan)
    except (AnalysisError, PlanValidationError) as e:
        msg = str(e)
        return await finish(ChatKind.ERROR, msg, plan=plan, err=msg)
    await analysis_service.add_multiple_test_warning(db, session.id, result)

    # --- 4. explanation: model prose if every number is grounded, else deterministic text ---
    source = "llm"
    try:
        prose = (await client.complete(
            prompts.EXPLAINER_SYSTEM,
            prompts.EXPLAINER_USER.format(question=sanitize_prompt_data(message, 2000), facts=grounding.result_facts(result)),
            max_tokens=700,
        )).strip()
        if not prose:
            raise LLMError("bad_response", "empty explanation")
        bad = grounding.ungrounded_numbers(prose, result)
        if bad:
            logger.warning("explanation rejected: ungrounded numbers %s", bad[:5])
            raise LLMError("bad_response", "ungrounded numbers")
    except LLMError:
        prose = grounding.template_explanation(result)
        source = "template"

    return await finish(
        ChatKind.ANALYSIS, prose, plan=plan, result=result, source=source, suggestions=grounding.suggested_followups(result),
    )
