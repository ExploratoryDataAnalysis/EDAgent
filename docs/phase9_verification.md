# Phase 9 verification · 15 November 2026

Started from clean `main` at `53dc033a1f4a53c7ff19e615c1e4301982a8b8ab`, the Phase 8 commit. Scope comes from Plan v4 Phase 9 and the arithmetic and treatment decisions in Plan v3 Phase 5. The calculator uses the existing schema 1 API, Decimal calculations, server rounding, and six `REFERENCE_ONLY` records. The example shares the all-crashes scope and five-year period across the baseline and factor. On a baseline of 40 hypothetical crashes, a factor of 0.80 gives 32.00 and a reduction of 8.00. Bounds of 0.70–0.95 give 28.00–38.00 at the same baseline.

## Changed files

Application paths below are relative to `EDAgent_Completed_Extension/EDAgent`.

- `frontend/src/pages/InterventionPage.tsx` adds the example and keeps one calculation path for example, manual entry, and retry. The page cancels invalidated requests, associates errors with controls, and displays the result directly below the example. Browsing a treatment citation is independent of calculation inputs. The page gives the scenario POST a 15-second deadline.
- `frontend/src/services/apiClient.ts` passes through the existing structured validation details to the form.
- `backend/tests/test_interventions.py` adds the exact example payload and expected counts and bounds to the schema 1 regression suite.
- `frontend/tests/phase9-smoke.mjs` exercises the calculator and D7-closed routes at desktop and phone widths. `frontend/tests/road-safety-smoke.mjs` checks the updated field error and reference browsing behavior and waits for the completed result region.

This report and `docs/phase9_screenshots/` record the verification. The calculator has no share or export path.

## Local commands and results

Commands below use the canonical application. `$run` is a fresh local test directory.

| Check | Command | Result |
| --- | --- | --- |
| Backend from `backend` | `..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -o addopts= -q --basetemp "$run/pytest" tests` | 197 passed. One Starlette TestClient deprecation warning. |
| Frontend from `frontend` | `node node_modules/typescript/bin/tsc -b` | Passed. |
| Frontend from `frontend` | `npm.cmd run build` | Passed. Vite reported the existing warning for the Plotly chunk. |
| Browser from `frontend` | `node tests/phase9-smoke.mjs` | Passed at 390 and 1440 px. Covered the exact example request and result, input precision, keyboard order and focus, live status and alerts, field errors and correction, real-site refusal, pending edit and reset, out-of-order completion, transport retry, neutral and increasing factors, zero baseline, and Investigation and Methods with the D7 gate closed. |
| Shared browser from `frontend` | `node tests/phase8-smoke.mjs` | Passed at 390, 768 and 1440 px with the synthetic release, the gated candidate, and the optional large/partial fixture. The first large-fixture attempt timed out during a concurrent build and passed on the completed build. |
| Shared browser from `frontend` | `node tests/road-safety-smoke.mjs` | Passed at 390, 768 and 1440 px on loopback. Covered public routes and release states, synthetic Overview evidence, calculator validation and refusal, and signed-in analyser upload, analysis, and exports. |
| Working tree | `git diff --check` | Passed. |

Browser runs used loopback HTTP and Playwright Chromium. For Phase 9, run `..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8017` from `backend` with `ENVIRONMENT=test`, `LLM_PROVIDER=mock`, `DATABASE_URL=sqlite+aiosqlite:///<absolute-disposable-db>`, and disposable `LOCAL_STORAGE_PATH` and `EXPORTS_STORAGE_PATH`. Point `ROAD_SAFETY_RELEASE_ROOT` at the absolute path to `.repro/v3-d7-2-a` and `ROAD_SAFETY_APPROVALS` at a disposable file containing `{}`. In `frontend` set `VITE_PROXY_TARGET=http://127.0.0.1:8017` and run `node node_modules/vite/bin/vite.js --port 5178 --strictPort`. For the smoke command, set `STAGING_URL=http://127.0.0.1:5178` and optionally set `SMOKE_OUTPUT` to the screenshot directory. Use `PLAYWRIGHT_MODULE` and `CHROMIUM_EXECUTABLE` to select locally installed test tools. The [Phase 6 handoff](phase6_handoff.md) and [Phase 8 verification](phase8_verification.md) describe the synthetic fixture setup for the shared smoke tests.

## Automated browser evidence

| State | 390 px | 1440 px |
| --- | --- | --- |
| Initial | [Phone](phase9_screenshots/initial-390.png) | [Desktop](phase9_screenshots/initial-1440.png) |
| Worked result | [Phone](phase9_screenshots/result-390.png) | [Desktop](phase9_screenshots/result-1440.png) |
| Invalid factor | [Phone](phase9_screenshots/error-390.png) | [Desktop](phase9_screenshots/error-1440.png) |
| Real-site refusal | [Phone](phase9_screenshots/refusal-390.png) | [Desktop](phase9_screenshots/refusal-1440.png) |

The refusal test adds a forbidden site field to an invented request in transit. It checks the actual API response and confirms the result is absent. Keyboard and live-region checks inspect Chromium’s accessibility tree, focus, and field associations. These checks are automated.

## Reader testing and release

- Reader test pending. Ask participants to run the example, explain the 28.00–38.00 range in their own words, and recover after entering an invalid factor. Look for recognition that the baseline stays fixed and the range comes from entered bounds, with no statistical confidence level. Include an assistive-technology session to hear the result and error announcements.
- Science-editor review of the treatment language and production HTTPS verification remain open. On the intended HTTPS host, verify the calculator route, same-origin scenario POST, refusal, and source links.
- The calculator can ship independently of D7 once its own reviews and HTTPS checks clear. To roll back only the calculator, run `git restore --source=53dc033 -- EDAgent_Completed_Extension/EDAgent/frontend/src/pages/InterventionPage.tsx` from the repository root and rebuild the frontend. Use `road-safety-smoke.mjs` from `53dc033` to exercise the restored calculator. Both calculator versions use schema 1. Recheck the direct route, a manual calculation and real-site refusal with D7 closed.
