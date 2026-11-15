# Phase 11A verification · 15 November 2026

Started from clean `main` at `aaffeb61db7a0c30cb58950b7297153353409f70` (Phase 10). No applicable `AGENTS.md` was present. The scope follows Plan v4 Phase 11, the Plan v3 analyser and scientific boundaries, the Phase 6 handoff and the Phase 10 identity and ownership rules. This change uses the canonical application in `EDAgent_Completed_Extension/EDAgent`. All new analysis inputs and test credentials are invented.

The teammate report is unverified outside this checkout. In the local backend working directory, the effective settings selected the OpenAI-compatible adapter, model `gemini-3.8-flash`, a custom destination and **no configured key**. Chat was disabled before any provider request. Model compatibility and reachability in the intended environment remain unverified. Phase 6 also ran in mock (disabled) mode; its workspace checks did not prove live chat. The original chat suite passed 17 tests from a disposable snapshot of the starting revision, using the disabled path or scripted model overrides.

| Failure | Evidence and behavior |
| --- | --- |
| Disabled | Observed locally. `/chat/status` reports disabled. Chat has a keyboard-accessible Analysis Workspace link; manual computation requires no provider. |
| Provider rejects credentials | Controlled HTTP 401/403 from the stub become an AI-unavailable chat turn over app HTTP 200. The application token, owned dataset and session remain usable. |
| Provider configuration/transport | Controlled 404, 429, 503, read error and timeout produce distinct guidance where applicable. Each failed completion is attempted once. A received but invalid plan may prompt one repair; no failed POST is replayed. |
| Malformed or unsupported plan | Strict JSON, the existing structured plan schema and the operation catalogue validate the request, including its columns and filters against the owned session's dataset. Unknown operations, malformed filters and invalid aggregation arguments never reach computation. |
| Computation failure | An injected analysis failure and an exhausted work budget produce a recoverable error; the explainer is never called. The existing deterministic engine still handles approved plans. |
| Explanation failure | Controlled malformed provider responses, slow replies, incorrect result identifiers and unsupported claims leave the same computed output and saved result available. The model can select summary or scope first for the exact result ID. Values, named units, row counts, caveats and prose come from the engine and server template. Earlier stored AI-written explanations retain their legacy label. |
| View switched | The browser aborts delivery and replaces its local transcript when the session or dataset changes. The server may still finish or incur billing; a late result belongs only to the original session. |

The signed-in route checks ownership of the session and then of the dataset referenced by that session. It builds provider context from that dataset and recent turns in that session. Only its validated plan reaches the existing deterministic engine. The explainer receives its result ID, operation, scope and row counts with the question. Accepted emphasis choices and fallback both render the same computed facts; neither can introduce independent claims. The result and explanation are saved and restored under the same session. The guest restriction remains on both chat endpoints. The public investigation, calculator and both sample paths retain their independent gates.

## Known result and timings

The uploaded fixture `invented-waits.csv` has one column, `wait_minutes`, with 2, 6, 10 and 14 minutes. `descriptive_stats` should return mean and median 8, min 2, max 14, exact scope, 4 of 4 rows and zero excluded. The signed-in HTTP transport test checks the result table, rendered explanation, dataset/session/request/result bindings and stored turn. The browser fixture repeats the median calculation in the Workspace after provider failure. The overclaim uses values that really occur in the fixture but attaches the wrong metric and unit; no provider claim is rendered.

Representative local Windows timings through the API with `httpx.MockTransport`; upload and sign-in ran before each measurement:

| Case | Prepare | Plan | Validate | Compute | Explain | Save | Request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Accepted emphasis | 5.4 ms | 0.8 ms | 0.1 ms | 4.6 ms | 0.7 ms | 4.7 ms | 30.5 ms |
| Unsupported claim | 5.4 ms | 0.6 ms | 0.1 ms | 5.3 ms | 0.8 ms | 5.2 ms | 32.8 ms |
| Deliberate explanation stall, 100 ms test cap | 6.0 ms | 0.6 ms | 0.1 ms | 4.7 ms | 103.9 ms | 4.4 ms | 134.7 ms |

The local stages are fast compared with provider waits. The initial policy is a 10 s default per provider attempt, a shared 45 s work budget, a 30 s computation cap including the queue, and a 50 s handler target including turn persistence. The browser stops waiting after 55 s. The budget is cooperative: it bounds awaits in the chat handler and delivery in the browser. A CPU thread, database finalization or an upstream POST that was already accepted can outlive the local wait. No automatic transport retries; a successful HTTP reply with an invalid plan can trigger at most one repair within the shared work budget. Reassess the initial limits using the real canary and target proxy timings before enabling provider chat.

Redacted stage evidence: `chat stage=explain outcome=unsupported_explanation elapsed_ms=0.8`; `chat stage=explain outcome=timeout elapsed_ms=103.9`; both are followed by `stage=save outcome=ok`. The actual loopback adapter in Chromium also logged `stage=planner outcome=auth` and `stage=explain outcome=unsupported_explanation`. The chat logger emits fixed stage names, error categories and timings. Configure `edagent.chat` at INFO to collect successful stage timings; keep SQL debug logging off and do not enable provider wire dumps or request-body capture. The chat flow omits provider response bodies and exception text from logs. Tests assert that log messages contain no fixture columns, prompts or invented credentials.

## Verification commands and evidence

The local runs used Windows, Python 3.13, Node 22 and Playwright Chromium. The managed sandbox could not open Python's owner-only temporary directories or spawn esbuild, so the successful runs used the host test permissions with disposable directories. Set `$run` to a fresh writable directory and use it for `TEMP` and `TMP`.

| Location | Command | Evidence |
| --- | --- | --- |
| Snapshot of starting backend | `python -m pytest -p no:cacheprovider -o addopts= -q --tb=short --durations=6 --basetemp "$run/pytest" tests/test_chat_flow.py` | 17 passed. [Log](../.repro/phase11/prechange/chat.log). |
| Canonical backend | `..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -o addopts= -q -s --tb=short --basetemp "$run/pytest" tests` | 221 passed. [Backend log](../.repro/phase11/backend-final/backend.log). |
| Repository root | `EDAgent_Completed_Extension/EDAgent/.venv/Scripts/python.exe -m pytest -p no:cacheprovider -o addopts= -q -rs --tb=short --basetemp "$run/pytest" tests` | 141 passed, 9 expected legacy-release skips. [Log](../.repro/phase11/root/root.log). |
| Frontend | `node node_modules/typescript/bin/tsc -b`; `npm.cmd run build` | Both passed. Existing Vite Plotly size warning. [Final build log](../.repro/phase11/browser-082713590/build.log). |
| Frontend | `node tests/phase11a-smoke.mjs` | Passed at 390 and 1440 px in stub and disabled modes. [Stub log](../.repro/phase11/browser-082713590/phase11a-smoke.log) · [Disabled log](../.repro/phase11/browser-082605529/phase11a-smoke.log) · [Provider error and recovery link at 390 px](../.repro/phase11/browser-082713590/evidence/chat-provider-recovery-390.png) · [Manual median at 390 px](../.repro/phase11/browser-082713590/evidence/chat-manual-median-390.png). |
| Frontend | `node tests/phase10a-smoke.mjs`, `node tests/phase10b-smoke.mjs`, `node tests/phase9-smoke.mjs`, `node tests/phase8-smoke.mjs`, `node tests/road-safety-smoke.mjs` | Passed. Teaching and JSON export, private guest analysis and CSV export, calculator, public pages, signed-in PDF report and JSON profile export. [Teaching](../.repro/phase11/browser-081504/phase10a-smoke.log) · [Guest](../.repro/phase11/browser-081504/phase10b-smoke.log) · [Calculator](../.repro/phase11/browser-081504/phase9-smoke.log) · [Map and evidence](../.repro/phase11/browser-081504/phase8-smoke.log) · [D7 closed and reporting](../.repro/phase11/browser-082215237/road-safety-smoke.log). |
| Repository root | `git diff --check` | Passed. |

For the repository suite, set `PYTHONPATH` to the absolute paths for `src` and `.repro/geodeps`, `PROVISIONAL_STAGE` to `.repro/v3-phase3-verified-a` and `DESCRIPTIVE_STAGE` to `.repro/v3-d7-2-a/descriptive_release`. This checks the archived artifacts without granting a real release decision.

For browser reproduction, use the Phase 10 loopback setup: start the backend from `backend` with `python -m uvicorn app.main:app --host 127.0.0.1 --port 8064 --no-access-log`, disposable SQLite/storage, `ENVIRONMENT=test`, guest creation enabled and the real D7 candidate behind a separate empty ledger. Disable request rate limits only for these disposable smoke runs. Start Vite from `frontend` using `node node_modules/vite/bin/vite.js --port 5494 --strictPort` and `VITE_PROXY_TARGET=http://127.0.0.1:8064`. With `STAGING_URL=http://127.0.0.1:5494`, set the local Playwright/Chromium variables as in the Phase 10 handoff. Run Phase 11A once with `LLM_PROVIDER=mock` and no `CHAT_STUB_PORT`. Then set backend `LLM_PROVIDER=openai`, `LLM_MODEL=loopback-stub`, `LLM_API_KEY=invented-key`, `LLM_BASE_URL=http://127.0.0.1:8065/v1`, restart the backend and run the smoke with `CHAT_STUB_PORT=8065`. The smoke starts its own loopback provider while it runs. For the other browser suites start `python -m tests.serve_overview_fixture` and a second Vite proxy as in Phase 10.

**Changed paths.** Backend `app/api/v1/endpoints/chat.py`, `app/core/config.py`, `app/models/analysis.py`, `app/schemas/chat.py`, `app/services/ai/{grounding,llm,orchestrator,prompts}.py`, `app/services/analysis/catalogue.py` and `tests/test_chat_flow.py`. Frontend `src/pages/ChatPage.tsx`, `src/context/DatasetContext.tsx`, `src/components/chat/ChatMessageBubble.tsx`, `src/services/api.ts`, `src/types/index.ts` and `tests/phase11a-smoke.mjs`. Runtime settings in `.env.example` and `docker-compose.yml`. No database schema or research release change.

## Exit decisions and rollback

| Check | Disposition |
| --- | --- |
| Local integration | Passed through the actual signed-in API and loopback stub, including login continuity, deterministic explanation fallback, guest provider denial, both late reply checks and the browser regressions. |
| Real provider canary | Open. No authorized configured key and intended runtime were available here. In the intended runtime, run one completion through the configured adapter with invented text (`Reply READY. No application data.`), under the configured deadline. Record redacted provider/model, environment, mode, elapsed time and category/outcome. Then repeat the known-result run. |
| Known-result correctness | Passed against the controlled four-row fixture, across accepted and rejected explanations. |
| Reader validation | Automated keyboard task passed at 390 and 1440 px. Ask a participant to recover from a chat failure, find and run Summary statistics for the same dataset, and report the median with units. Record whether they find the link unaided and understand which data and rows were used. Participant and assistive-technology validation remain open. |
| Production verification | Open. Check the intended environment, authorized canary, timeout alignment, operational logging, authentication, public gate and configuration rollback there. No push or deployment in this slice. |
| BYOK eligibility | Not eligible. 11A release evidence and the separate privacy and consent decision are open. See [Phase 11B decision](phase11b_byok_decision.md). |

To roll back provider execution, set `LLM_PROVIDER=mock` in the effective backend environment and restart the backend (recreate the Compose backend so the environment changes take effect). Verify a signed-in `/chat/status` reports disabled, the chat page exposes the Analysis Workspace link, and manual analysis, exports, reports, samples and calculator still run with D7 closed. Preserve the database and storage. No migration, credential transfer or dataset copy is required.
