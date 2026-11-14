# Phase 7A verification · 14 November 2026

## Starting point and source review

Clean `main` at `b2f2dfaaa032e908a3e5dd3672ecb18dfe877264` (working tree changes for this slice). Both Plan v4 files were tracked at that revision. No applicable `AGENTS.md` was found. Compared the canonical app with the Phase 6 handoff and `87a7aea` implementation and traced the regressions described for `93991e5` through the current sources.

- Release. An unset ledger selected a canonical research adapter that constructed approved-looking provenance and served data without checking the pinned manifest. Hotspot, model comparison and road-class routes bypassed the verifier. The page also rendered hard-coded candidate totals. Removed those paths and the now-unused adapter. D7 payloads still require the exact manifest, a named and dated external approval, and byte verification. The separate legacy frequency router retains its own approval gate and unavailable behavior.
- Workspace. Missing bearer credentials could select the first stored account. The guest endpoint could issue an ordinary session token for that account. Removed both paths, retired previously issued tokens, and reserved the legacy open identity. Existing account holders sign in again. Stored records and owner IDs require no schema change. Protected endpoints continue with their existing owner-scoped lookups.
- Public routes. Root is the investigation, `/methods` works independently of D7, and `/road-safety` handles loading, structured unavailability, transport failure and retry. The verified record reuses Phase 6 charts, tables and checked downloads. Table identity and hashes must match provenance before the page renders figures. The calculator keeps `/illustrative-scenario`. The signed-in workspace moves to `/analyser`. Protected URLs retain their destination through sign-in.
- Methods. Checked wording against Plan v3, the D7 dictionary, v6 source and reproduction notes, the [WPRDC cumulative resource](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/2c13021f-74a9-4289-a1e5-fe0472c89881) and [PennDOT’s coding notice](https://crashinfo.penndot.pa.gov/PCIT/). The project references point to the Phase 6 revision. Their public reachability could not be confirmed from this environment.

## Changed paths

Under `EDAgent_Completed_Extension/EDAgent/`

- Release serving in `backend/app/api/v1/endpoints/overview.py` and removal of `backend/app/services/canonical_road_safety.py`.
- Workspace authorization in `backend/app/api/v1/endpoints/auth.py`, `backend/app/core/deps.py` and `backend/app/core/security.py`. Regression checks in `backend/tests/test_overview.py`, `test_end_to_end.py` and `test_security_api.py`.
- Routes and layouts in `frontend/index.html`, `frontend/src/App.tsx` and `frontend/src/components/layout/` (`PublicLayout.tsx`, `ReleaseStatus.tsx`, `public.css`, `Sidebar.tsx` and `TopHeader.tsx`).
- Pages in `frontend/src/pages/` (`InvestigationPage.tsx`, `MethodsPage.tsx`, `RoadSafetyPage.tsx`, `InterventionPage.tsx`, `HomePage.tsx` and `LoginPage.tsx`). Request and session handling in `frontend/src/services/roadSafetyService.ts`, `frontend/src/services/apiClient.ts` and `frontend/src/context/AuthContext.tsx`. Browser checks in `frontend/tests/road-safety-smoke.mjs`.

## Local verification

Windows, Python 3.13.7, Node 22.16.0, Vite 5.4.21, Playwright 1.60.0 and Chromium 148.0.7778.96. The API used disposable SQLite, temporary storage, and a mock provider. Installed declared dependencies into `.repro/phase7a/deps` for this run.

| Check | Command and result |
| --- | --- |
| Canonical backend | From `backend`, `python -m pytest -o addopts= -q --timeout=30 tests`. 194 passed, including exact D7 approval, unavailable artifacts, independent calculator, anonymous denial, previous token rejection and two-owner isolation. |
| Road-safety repository suite | From the root, `python -m pytest -o addopts= -q -rs --timeout=45 --basetemp .repro/phase7a/root-suite-rerun tests`. 140 passed and 9 existing legacy-artifact skips. The first run hit a Windows rename permission error in a temporary publication fixture. The suite passed in a fresh directory. |
| Focused backend | `python -m pytest -o addopts= -vv --timeout=25 tests/test_overview.py tests/test_interventions.py tests/test_security_api.py tests/test_end_to_end.py::test_report_and_export_isolation`. 103 passed. |
| Frontend | From `frontend`, `node node_modules/typescript/bin/tsc -b` and `npm run build`. Build emits the existing Vite chunk-size warning. |
| Browser | `node tests/road-safety-smoke.mjs`. Passed at 390, 768 and 1440 px for public routes, headings, landmark and live status, keyboard skip link, Methods anchors, direct refresh, history, slow loading, the client deadline, unavailable and transport states, mixed-identity refusal and recovery. Checked 200% CSS zoom at 768 px and inspected desktop and phone layouts. |
| Synthetic approved API and browser | `python -m tests.serve_overview_fixture` on 8016, proxied by Vite on 5377. Invented rows, verified CSV, SVG, explicit nulls and zeros, keyboard table access, hypothetical arithmetic, invalid input, stale calculation and real-site refusal passed. |
| Real candidate, closed gate | Loopback FastAPI on 8017 through Vite on 5378, archive `.repro/v3-d7-2-a`, empty external test ledger. HTTP 503 with structured null release data at desktop and phone widths. Signed-in deep-link return, analyser entry and refresh, synthetic CSV upload, manual analysis, PDF download and JSON profile export passed. |
| Candidate archive integrity | `Get-FileHash` plus SHA-256 checks against each manifest. Both archived candidates match `ec9def348fc67561f7ee2a5c7b3307a7db42b6e8832d7df7cc04252b87e70a82` and all 19 listed outputs in each match. |
| Compose configuration | `docker compose -p edagent-phase7a -f docker-compose.yml -f docker-compose.staging.yml config --quiet` passed using disposable inputs. `docker info --format '{{.ServerVersion}}'` could not connect to Docker Desktop’s Linux engine. |

Set `PYTHONPATH` to the local backend dependencies and `.repro/geodeps` for the app suite. For the root suite, also include `src`, set `PROVISIONAL_STAGE=.repro/v3-phase3-verified-a` and `DESCRIPTIVE_STAGE=.repro/v3-d7-2-a/descriptive_release`. On Windows the test commands used a writable workspace `TEMP` and `TMP`. The existing Phase 6 handoff describes the fixture and staging entry points. Supply local ports through `FIXTURE_URL` and `STAGING_URL`, and the local Playwright and browser through `PLAYWRIGHT_MODULE` and `CHROMIUM_EXECUTABLE`.

Evidence is local under `.repro/phase7a/screenshots/`. Public index, Methods, unavailable record and transport screenshots have desktop, tablet and narrow variants. `public-{desktop,tablet,narrow}.zip` holds the Playwright traces. The `fixture-*` figures use invented values. The `staging-pending-*` images show the real candidate behind a closed gate on loopback.

## Release acceptance still open

Browser checks exercised the accessibility tree and keyboard. Reader comprehension, assistive-technology sessions with participants and science-editor sign-off remain open. The intended HTTPS origin, deployed image and mounted ledger, same-origin routing, migration and rollback evidence, and operational account-boundary checks require the deployment owner. Before exposing the analyser, verify signing-key configuration and retained account ownership. Keep the genuine D7 decision pending until its designated reviewer records approval for the exact hash. Keep a rollback image with both repaired boundaries verified on that host. Before promotion, rehearse reverting to that image with the gate closed.

The smallest 7B increment is the annual count and selected-year coordinate and field coverage, tied to one verified identity across the chart, accessible table, caption and CSV. Rehearse changed release identity and withdrawal before promoting that path on the intended HTTPS host.
