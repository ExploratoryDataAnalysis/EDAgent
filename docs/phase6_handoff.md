# Phase 6 Road Safety Overview handoff

The `v3-phase6` branch starts at `71376b3`, the merge of Phase 5 PR #10. Both `6d01d2a` and `0d136f3` are ancestors. The application lives in `EDAgent_Completed_Extension/EDAgent`.

## Application and API

- `/road-safety` opens the public Overview shell. A verified release supplies totals, annual trends, separate severity coding eras, coordinate and field coverage, the clipped county grid, findings and downloads. The charts have keyboard-accessible tables. The grid has an image description, mapping denominators and a cell-count CSV.
- `/illustrative-scenario` displays six `REFERENCE_ONLY` treatment references from `GET /api/v1/interventions/evidence`. It sends hypothetical inputs to `POST /api/v1/interventions/scenarios` using schema `"1"`, decimal strings and a common crash type and period. The server supplies the display rounding and refusal codes.
- `/` remains the entry to the authenticated general analyser and links to Road Safety Overview. The existing dataset `/overview` remains part of the analyser.

All Overview API routes are `GET` under `/api/v1/road-safety/overview`.

| Path | Response |
| --- | --- |
| `/provenance` | Verified scope, source and output SHA-256 hashes, run ID, bundle identity, table inventory and grid coverage. |
| `/tables/{table_id}` | Original typed rows in bundle order. The response supplies row key fields, units, ratio columns, denominator populations, caveat captions and row annotations keyed by zero-based row index. Period bounds on individual rows take precedence over the table span. |
| `/tables/{table_id}/metrics/{column}` | One metric, selected by the complete row key as query parameters. The response includes period, geography, units, counts behind any ratio, coverage, caveats and the value state. |
| `/downloads/{table_id}` | Original checked CSV bytes and a download filename. |
| `/assets/{name}` | Checked `county_boundary.geojson`, `county_grid.svg` or `descriptive_release_data_dictionary.md` bytes with provenance headers and a link to `/provenance`. |

Table IDs are `county_periods`, `severity_composition`, `coordinate_coverage`, `field_coverage_by_year`, `source_missingness`, `historical_grid`, `severity_associations` and `findings`. See the [D7 dictionary](descriptive_release_data_dictionary.md#phase-6-road-safety-overview-api-contract) for their row keys and interpretation. For example, `/tables/county_periods/metrics/known_severity_percent_of_reported?period_grain=year&period_start=2024&period_end=2024` selects the 2024 share. Null observations retain their `UNKNOWN` or `UNAVAILABLE` state and reason. The 2024 illumination count of zero is a measured count. The reported population is 248,810 and the polygon-screened mapped population is 238,281. Serious/fatal values spanning the 2016 coding boundary stay null. The 2024 recording rows show valid hours for 387 of 10,228 reports and populated illumination for 0 of 10,228.

All Overview reads check the release kind, supported schema and scope, pinned manifest SHA-256, external approval and checksums. Downloads and typed reads consume the verified artifact bytes. Missing, pending, mismatched, changed and unsupported releases return HTTP 503 with `detail.code=OVERVIEW_UNAVAILABLE` and null `detail.data` and `detail.approval_state`. Responses use `Cache-Control: no-store`. The legacy `/frequency` routes retain their existing gates. The retrospective finding is a review-only scope note with public inference unavailable.

## Stage with Compose and PostgreSQL

The real candidate is `v3-d7-2`, schema `1`. The manifest SHA-256 is `ec9def348fc67561f7ee2a5c7b3307a7db42b6e8832d7df7cc04252b87e70a82`. Both verified builds in `.repro/v3-d7-2-{a,b}/descriptive_release/` have this hash. The [D7 approval record](phase3_phase4_review_status.md) documents the outstanding decision.

Use the existing PostgreSQL schema and local file storage. The staging override uses named volumes for PostgreSQL, uploads and exports. The backend mounts only the release root and an external ledger read-only. A dedicated release root has `descriptive_release/manifest.json` and its declared outputs. Keep the ledger outside the release root and out of Git. An empty JSON object is suitable for a local pending-approval demo. Docker binds only the frontend on loopback and proxies `/api/v1` to the backend on the private Compose network. The loopback demo uses HTTP. An external staging URL still requires an agreed host and HTTPS ingress. Vite Preview is used for this local staging verification.

From `EDAgent_Completed_Extension/EDAgent`, configure the following in the shell or in a deployment-controlled Compose env file outside the checkout. Use a unique random signing key and a matching database password and URL. The staging demo used PostgreSQL 16, port `5178`, and `LLM_PROVIDER=mock`.

| Variable | Value |
| --- | --- |
| `POSTGRES_PASSWORD` | Staging PostgreSQL secret. |
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<password>@postgres:5432/<database>` with URL-encoded credentials as needed. Default user and database are `postgres` and `edagent`. |
| `SECRET_KEY` | Random staging signing secret of at least 32 characters. |
| `D7_RELEASE_ROOT` | Absolute path to the root containing the real `descriptive_release` directory. |
| `D7_APPROVAL_LEDGER` | Absolute path to the external approval ledger file. |
| `STAGING_PORT` | Optional local port, default `5173`. |

```powershell
docker compose -p edagent-phase6-final -f docker-compose.yml -f docker-compose.staging.yml config --quiet
docker compose -p edagent-phase6-final -f docker-compose.yml -f docker-compose.staging.yml up --build -d
docker compose -p edagent-phase6-final -f docker-compose.yml -f docker-compose.staging.yml exec backend alembic current
docker compose -p edagent-phase6-final -f docker-compose.yml -f docker-compose.staging.yml exec backend alembic check
docker compose -p edagent-phase6-final -f docker-compose.yml -f docker-compose.staging.yml exec backend sha256sum /run/edagent/road-safety/descriptive_release/manifest.json
```

When the designated reviewer approves these exact bytes, the external JSON ledger needs a `descriptive_release` entry with `decision: APPROVED`, the genuine `reviewer` name, ISO `date`, and the exact `manifest_sha256` above. Recreate the backend container after replacing the host ledger file so the file bind sees the new bytes. Then verify provenance, population reconciliation and the approved artifacts before Phase 7 sign-off.

## Reproduce checks

From the repository root, with the existing road-safety dependencies and verified input paths on Windows.

```powershell
$env:PYTHONPATH = 'src;.repro/geodeps'
$env:PROVISIONAL_STAGE = '.repro/v3-phase3-verified-a'
$env:DESCRIPTIVE_STAGE = '.repro/v3-d7-2-a/descriptive_release'
python -m pytest -o addopts= -q tests/test_descriptive_release.py
python -m pytest -o addopts= -q -rs tests
```

From the canonical backend directory with its dependencies installed.

```powershell
$env:PYTHONPATH = 'C:/Darshan/EDAgent/src;C:/Darshan/EDAgent/.repro/geodeps'
python -m pytest -o addopts= -q tests/test_overview.py tests/test_interventions.py
python -m pytest -o addopts= -q tests
python -m tests.serve_overview_fixture
```

The last command starts a disposable synthetic backend on port `8016`. Its manifest pin is overridden only in the local test process. The fixture and ledger are generated in a temporary directory. Backend and frontend image builds exclude their test directories. In a separate shell from `frontend`, run the following.

```powershell
npm ci
npm run build
$env:VITE_PROXY_TARGET = 'http://127.0.0.1:8016'
node node_modules/vite/bin/vite.js --port 5177 --strictPort
```

Use Playwright with Chromium installed in a test environment. In another frontend shell, run `node tests/road-safety-smoke.mjs`. Set `PLAYWRIGHT_MODULE` to the Playwright module URL if it lives outside the frontend's module search path. Optional `CHROMIUM_EXECUTABLE` selects an installed browser. Set `STAGING_URL` to the local Compose URL to check pending approval and the authenticated analyser. `SMOKE_OUTPUT` writes PNG evidence to the given directory.

## Verification record · 2026-11-13

| Check | Result |
| --- | --- |
| Frozen D7 artifact suite using the real candidate | 9 passed. |
| Repository road-safety suite with verified Phase 3 and D7 paths | 140 passed, 9 existing skips for unapproved legacy artifacts. |
| Focused Overview API and intervention tests | 82 passed, including synthetic approved reads, exact-hash mismatch, pending decision, missing and altered bytes, nulls, release replacement during a request and legacy isolation. |
| Canonical backend suite | 192 passed. Backend pytest runs reported one Starlette TestClient deprecation warning. |
| Frontend dependency install and production build | `npm ci` installed 386 packages. The production build passed with Vite's chunk-size warning. |
| Synthetic browser integration | Chromium passed at 1440 px and 390 px. Checked keyboard navigation, chart data alternatives, SVG load, explicit null and zero rendering, decimal-string submission, validation, stale and delayed responses, and the actual refusal of a request carrying site context. |
| Real-artifact local Compose staging | Verified the mounted manifest SHA-256. PostgreSQL migrated to `0001 (head)` and `alembic check` found no new upgrade operations. At both viewport widths, the real Overview displayed the approval/verification state and returned HTTP 503 with null data. The illustrative calculator ran against the staged API. The analyser completed sign-in, CSV upload, analysis, and PDF report generation and download. |

Local browser evidence is in `.repro/phase6-browser/screenshots/`. `fixture-overview-{desktop,narrow}.png` and `fixture-calculator-{desktop,narrow}.png` use invented test rows. `staging-pending-{desktop,narrow}.png` records the mounted real bundle's unavailable state. The smoke script reproduces the checks and screenshots.

**Technical integration passed.** The synthetic fixture exercised verified serving and both new workspaces. **Local staging passed.** Compose, PostgreSQL, migrations, the real bundle's unavailable response and the analyser workflow were verified on loopback. **Public Overview readiness is pending.** A designated reviewer still needs to record a named, dated `APPROVED` decision for the exact `v3-d7-2` manifest above. External HTTPS staging and final release sign-off remain for the agreed deployment and Phase 7.
