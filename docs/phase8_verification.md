# Phase 8 verification · 15 November 2026

Work started from a clean `main` at `cdd3b48` (`implemented Phase 7B`). The scope follows Plan v4 and the definitions, exclusions and historical decisions in Plan v3, the audit and the D7 dictionary. The frozen extract, D7 artifacts and genuine approval ledger were left intact.

The exact candidate is `v3-d7-2`, schema 1, run `v6/6.1-targeted-corrections/2026-11-11T03:13:38.038283+00:00`. The candidate at `.repro/v3-d7-2-a/descriptive_release` matches manifest SHA-256 `ec9def348fc67561f7ee2a5c7b3307a7db42b6e8832d7df7cc04252b87e70a82`. Checks use the recorded input and output hashes and compare all released JSON and CSV rows. The fixtures use separate test-only pins and disposable ledgers.

## 8A · County grid and coverage

- `/road-safety/map` uses `historical_grid` and `coordinate_coverage`. The map, caption, keyboard cell lookup, paged table and CSV use the same count and period. The interactive legend bands are 1–4, 5–19, 20–49 and 50+ reports. The approved reference SVG uses its original continuous scale.
- Reconciled **38,332 occupied cells** and **238,281 mapped reports of 248,810 (95.77%)**. The 10,529 unmapped reports comprise 10,254 unusable coordinate pairs (10,232 missing, 10 invalid and 12 placeholders) and 275 usable pairs outside the county. The usable-pair denominator is 238,556.
- Confirmed WGS 84 (EPSG:4326), 0.001° cell sides, and unique longitude and latitude centre IDs at three decimal places. The GeoJSON identifies the 2024 Census county boundary as GEOID 42003. Each occupied rectangle intersects the polygon with positive area. Canvas clips the rectangles to the county, and pointer selection checks the same boundary. The synthetic test samples an in-county and out-of-county pixel within a boundary cell.
- A missing cell has an unavailable count. The map uses full-period aggregate counts of reported crashes. Exposure rates, individual crash locations, annual cell counts and site-level claims are outside the D7 contract.
- Rollback path. Remove the map route, its Overview link and public page title entry. The Phase 7 Overview and Methods keep their existing links and content. For a renderer-specific failure, the verified SVG, keyboard lookup and table can be used on the route while the active release passes verification.

| Artifact | SHA-256 |
| --- | --- |
| `historical_grid.json` | `7042e4554fa64faf786ca036627f8f1adc609f3b7fab8698561bf241721354d6` |
| `historical_grid.csv` | `350cb493d9398245857b981d4daaadbf23199a17519bf545bfbadaf38a87fffa` |
| `coordinate_coverage.json` | `766aeac1582885d5229aea153bc635e82a2d43273321504839472c3d22bc8a6a` |
| `county_boundary.geojson` | `86c85c5af1c37be2825a2e956fef9d592941d043813119c02927d2dcf988ab6b` |
| `county_grid.svg` | `e6cc909e708e524f832c0e01ec6d380dee77f53fd5d445544445a18660cdfff5` |

## 8B · Severity and measurement

- `/road-safety/evidence` presents separate 2004–2015 and 2016–2024 severity panels. The first has **119,187 known and 25,733 excluded of 144,920** reports. The second has **86,357 known and 17,533 excluded of 103,890**. Known groups use the known-severity denominator. Excluded groups use all reports. The 2016 coding change limits the combined serious/fatal measure to the later era (**3,615 of 86,357**, 4.19%).
- The 2024 coverage evidence is **387 valid hours of 10,228** (3.78%) and **0 populated illumination codes of 10,228** (0%). The second count measures recording. Illumination conditions remain unknown. The source missingness control changes the chart, table and caveat together using the selected field’s stable row key.
- All four association rows use **77,476 known-severity reports** from 2016–2023, out of 93,662 reports in that period. The table gives Cramér’s V, tested levels, source levels pooled before testing, the minimum expected count and the BH q-value. The frozen minimum expected counts are all above 5. Collision type has V = 0.2020 and a null q-value flagged for underflow. The figure describes associations within reported crashes. Adjusted effects, joint distributions and imputed comparisons require separately reviewed derivatives.
- Rollback path. Remove the evidence route, its Overview link and public page title entry independently of 8A. Phase 7 annual evidence and Methods remain available through their established routes.

| Artifact | SHA-256 |
| --- | --- |
| `county_periods.json` | `5b64fb5eff5f38fd6e5fb9d8672923fb9a9cf072d42acf4969f33ead8b77d56e` |
| `severity_composition.json` | `784f0f7711ba979cff86f1fa250b9c18d32c0b9c396fb3166b074a8748e85068` |
| `field_coverage_by_year.json` | `675f6c4eb6f90177b76af92d1c1b83817e62a69c46e016c25ed71dfd6248769a` |
| `source_missingness.json` | `cd4992ae9f6097e20f6860095bc7cb039278447d88a916e438f2419e0bc926e1` |
| `severity_associations.json` | `4878c330b256ff06567d90cacafc40fc89be2858d2c70b59f97f84ab1fd21207` |
| `descriptive_release_data_dictionary.md` | `6967abf0aacff18aed926b3c9da156b238011a12b041e461beb60e6b88eefbb6` |

## Changes and release behavior

Application paths below are relative to `EDAgent_Completed_Extension/EDAgent`.

- 8A lives in `frontend/src/pages/CountyGridPage.tsx`. 8B lives in `frontend/src/pages/SeverityEvidencePage.tsx`. `App.tsx`, `PublicLayout.tsx` and `RoadSafetyPage.tsx` register and link each route independently.
- `EvidenceFigure.tsx` provides figure source links, identity and the accessible table reused by the Overview. `roadSafetyService.ts` verifies each table identity and binds annotations to stable keys before view transforms. `ReleaseStatus.tsx` rechecks on focus, when the document becomes visible and every 15 seconds while visible. A failed recheck clears the verified view. Navigation and retries abort the previous request.
- `PlotlyChart.tsx` loads Plotly when a chart mounts so the new routes can skip that payload. The map paints the selected-cell outline separately from the grid, so selection does not repaint all occupied cells.
- `backend/app/api/v1/endpoints/overview.py` accepts a manifest pin for existing CSV and asset endpoints. The verifier checks approval and hashes on each read, and the artifact handler checks bytes again before serving. `backend/app/main.py` exposes the existing identity headers to allowed cross-origin clients. The annual figure, Investigation and Overview also use manifest-bound reads and file links.
- `backend/tests/overview_fixture.py`, `serve_overview_fixture.py`, `test_overview.py` and `frontend/tests/phase8-smoke.mjs` exercise the two slices. The repository-level `tests/test_descriptive_release.py` verifies the candidate geometry, eras, 2024 coverage and association cohort.

## Local checks

Windows, Python 3.13, Node 22.16, Vite 5.4.21 and Playwright Chromium. Python tests used the local app virtual environment and separate workspace temporary directories. The loopback APIs used disposable SQLite and the mock provider.

| Check | Command and result |
| --- | --- |
| Canonical backend | From `backend`, `..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -o addopts= -q --basetemp <fresh-dir> tests`. **196 passed.** One Starlette TestClient deprecation warning. |
| Repository and release | From the root, `EDAgent_Completed_Extension\EDAgent\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -o addopts= -q -rs --basetemp <fresh-dir> tests`. **141 passed, 9 skipped.** The skips concern unapproved legacy artifacts. Set `PYTHONPATH=src;.repro/geodeps`, `PROVISIONAL_STAGE=.repro/v3-phase3-verified-a` and `DESCRIPTIVE_STAGE=.repro/v3-d7-2-a/descriptive_release`. |
| Type check and production build | From `frontend`, `node node_modules/typescript/bin/tsc -b` and `npm.cmd run build`. Both passed. Vite reports a chunk-size warning for the separately loaded Plotly bundle. |
| Phase 7 browser regression | From `frontend`, `node tests/road-safety-smoke.mjs`. Passed the annual figure, Methods, calculator and analyser on loopback. Also checked gated data, invalid and stale calculator requests, sign-in, file upload and export. |
| Phase 8 browser | From `frontend`, `node tests/phase8-smoke.mjs`. **Passed** at 390, 768 and 1440 px, including 200% zoom, keyboard selection and focus, direct refresh, renderer failure, transport retry, mixed identity, late responses and real candidate gate closure. The test withdraws a synthetic release while its fallback is visible and confirms retry after restoring the test decision. |

For local browser reproduction, run `python -m tests.serve_overview_fixture` from `backend` and proxy Vite to it using `VITE_PROXY_TARGET=http://127.0.0.1:8016`. Set `FIXTURE_URL` to that frontend and `STAGING_URL` to the frontend backed by the real candidate with an empty external ledger. For the second fixture, add `OVERVIEW_FIXTURE_PORT=8018`, `OVERVIEW_FIXTURE_LARGE=1` and `OVERVIEW_FIXTURE_PARTIAL=1`. Proxy Vite Preview to it and set `PHASE8_LARGE_URL` to that preview URL. Point `FIXTURE_LEDGER` at the generated **synthetic** ledger to exercise withdrawal and restoration. `SMOKE_OUTPUT` selects the screenshot directory. `PLAYWRIGHT_MODULE` and `CHROMIUM_EXECUTABLE` select locally installed test tooling.

Local images are in `.repro/phase8/screenshots/`. The fixture screenshots contain invented counts. Widths in the filenames are CSS pixels.

| State | Images |
| --- | --- |
| 8A ready and selected | `map-ready-{390,768,1440}.png` |
| 8A renderer failure | `map-renderer-fallback-{390,1440}.png` |
| 8B ready | `evidence-ready-{390,768,1440}.png` |
| 8B partial | `evidence-partial-390.png`. An approved synthetic fixture omits the 2024 illumination coverage row. The table shows unavailable coverage while retaining the valid-hour value. |
| Real candidate gate closed | `map-candidate-gated-{390,768,1440}.png` and `evidence-candidate-gated-{390,768,1440}.png` |
| Reflow at 200% zoom | `reflow-map-200.png` and `reflow-evidence-200.png` |

### 8A phone profile

Production Preview used an approved synthetic grid of 38,332 occupied cells and Chromium’s Pixel 7 emulation at 390 px. CPU throttling was 4× with 70 ms simulated latency, 12.5 Mbps download and 2 Mbps upload. Startup measures navigation through the first painted grid. Selection measures form submit through two animation frames with the selected-cell table verified.

| Run | Before Plotly split and selection overlay | After |
| --- | --- | --- |
| Cold startup / cell selection | 23,453 ms / 536 ms | 7,041 ms / 87 ms |
| Repeat 1 | 8,173 ms / 1,069 ms | 4,775 ms / 48 ms |
| Repeat 2 | 8,301 ms / 1,129 ms | 5,927 ms / 23 ms |

The entry JavaScript went from 5.17 MB to 485 KB before compression. These timings use loopback and invented cells. The real candidate remained gated, and target-device and HTTPS timings remain open.

## Release acceptance

- **Science approval.** Genuine exact-manifest approval and signed caption review are pending. The real candidate was exercised with an empty external ledger on loopback. Public evidence opens only when the exact artifact receives its named, dated decision and the target is verified.
- **Reader validation.** Browser QA exercises keyboard use, focus, reflow and the screen-reader-facing table structure. Participant sessions remain open. For 8A, ask what a selected count means and which reports cannot contribute to it. For 8B, ask whether serious/fatal comparisons can cross 2016 and whether the 2024 fields support time or lighting comparisons.
- **Target HTTPS verification.** Verify the deployed image, external ledger, same-origin routing, verified byte responses and withdrawal on the intended HTTPS origin. Carry forward Phase 7’s signing-key and account-boundary checks, migration and rollback rehearsal, production reference reachability and human accessibility review. No push or deployment was performed.
