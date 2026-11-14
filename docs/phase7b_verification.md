# Phase 7B verification · 14 November 2026

## Starting point and baseline review

- Baseline: Git commit `a35503b` (`Implemented Phase 7A`) on `main`. Clean working tree prior to Phase 7B edits.
- Applicable guides and plans:
  - `docs/EDAgent_Project_Plan_v4.tex`: Phase 7B workflow, design specifications, and release acceptance criteria.
  - `docs/EDAgent_Project_Plan_v3.tex`: Scientific definitions, exclusions, 2016 coding seam, and Phase 6 evidence.
  - `docs/phase7a_verification.md`: Verification baseline, route boundaries, fail-closed release gate, and browser test structure.
  - `docs/phase6_handoff.md` and `docs/descriptive_release_data_dictionary.md`: Data contracts, table definitions, stable keys, and denominator rules.
- Existing Phase 7A contracts preserved:
  - Strict release verifier: external ledger check, manifest hash verification (`ec9def348fc67561f7ee2a5c7b3307a7db42b6e8832d7df7cc04252b87e70a82`), and structured HTTP 503 fail-closed behavior when ungated.
  - Public route boundaries: root investigation page (`/`), methodology page (`/methods`), verified road-safety record (`/road-safety`), illustrative calculator (`/illustrative-scenario`), and signed-in analyser (`/analyser`).
  - No new data collection or mutation of frozen notebooks or source artifacts.

---

## Changed paths

All modifications reside under `EDAgent_Completed_Extension/EDAgent/`:

1. `frontend/src/components/road-safety/AnnualCrashFigure.tsx` (created):
   - Interactive annual crash-report chart plotting annual police-reported crashes in Allegheny County extract (2004–2024).
   - Selected-year control: native `<select id="selected-year">` with accessible label, full keyboard and touch operability.
   - URL search parameter synchronization: selected year synchronizes with `?year=YYYY`, with graceful fallback to latest year (`2024`) on invalid or missing query parameters, supporting browser back/forward and direct refresh.
   - Selected-year chart highlight: selected year rendered with a prominent marker (`#8D3821`, 14px circle) along the annual trend line (`#0E6059`).
   - Selected-year coverage panel detailing:
     - Extract scope and explicit non-inference caveat: counts reflect only police-reported crashes in the fixed extract; no inference of travel exposure, per-trip risk, site rankings, forecasts, or treatment effects.
     - Coordinate mapping coverage: numerator (mappable crashes), denominator (total county crashes), percentage, unusable coordinate pairs, and crashes outside county boundary.
     - Field coverage: Valid hour coverage (e.g. 2024 low coverage caveat `LOW_2024_HOUR_COVERAGE` [3.78%] vs historical heaping `HOUR_HEAPING`).
     - Field coverage: Populated illumination coverage with strict distinction for observed zero (e.g. 2024 observed zero `NO_2024_ILLUMINATION_COVERAGE` [0 / 10,228], distinct from missing or unavailable data).
     - Severity coverage & 2016 coding seam: 2016+ serious injury and fatal crashes (`crash_fatal_and_serious_count`) and percentage of known vs pre-2016 `Unavailable` with caveat `SEVERITY_CODING_BREAK_2016` (PennDOT KABCO standard transition).
   - Accessible data table:
     - Renders annual series with year, crash count, mapped %, valid hour %, illumination %, serious/fatal count, and serious/fatal %.
     - Interactive and keyboard-operable rows (`role="button"`, `tabIndex={0}`, `aria-selected`, `Enter`/`Space` handlers) that update selected year.
     - Clean display of caveats and null states.
   - Provenance, caption, and export:
     - Scope caption, link to WPRDC cumulative dataset, PennDOT coding notice, and data dictionary accessible without hover or motion.
     - Traceable verified release metadata (release ID, run ID, manifest SHA-256).
     - Verified CSV export link (`/api/v1/overview/tables/county_periods/export.csv?format=csv`) explicitly stating coverage across the full annual series (2004–2024).

2. `frontend/src/services/roadSafetyService.ts` (modified):
   - Added typed data structures: `RowAnnotation`, `RowWithAnnotation<T>`, `Bundle`, `Provenance`, and `OverviewData`.
   - Added `makeStableRowKey(row, keyFields)` helper to bind annotations to canonical compound keys prior to sorting or filtering.
   - Updated `loadOverview` to bind annotations to stable row keys and compute `caveatCaptions`.

3. `frontend/src/pages/InvestigationPage.tsx` (modified):
   - Uses `loadOverview` and mounts `AnnualCrashFigure` with `showFullRecordLink` when release is verified and ready.
   - Renders Phase 7A `ReleaseStatus` and "How the record was assembled" when release is gated or unavailable.

4. `frontend/src/pages/RoadSafetyPage.tsx` (modified):
   - Mounts `AnnualCrashFigure` as the reference annual and coverage section.
   - Maintains total Plotly charts on `/road-safety` at exactly 3 (Annual trend, Severity breakdown, Field coverage matrix) while removing duplicate annual logic.
   - Preserves Crash totals summary cards, Severity composition section, Field coverage section, Historical grid section, and Methodology references.

5. `backend/tests/test_overview.py` (modified):
   - Added `test_phase7b_annual_and_coverage_slice_contract`: verifies annual table schema, 2016 severity seam, 2024 field caveats, and CSV export route.

6. `frontend/tests/road-safety-smoke.mjs` (modified):
   - Extended test suite with Phase 7B assertions: year selection, selected-year coverage metrics and caveats, 2024 observed zero illumination, 2015 severity break, table row click, direct URL `?year=2015`, invalid `?year=9999` fallback, browser back button, annual CSV download headers, and root ready state check across 1440px, 768px, and 390px viewports.

---

## Data tables and stable row keys used

| Table ID | Key fields | Stable row key format | Measures & Denominators | Notes & Caveats |
| --- | --- | --- | --- | --- |
| `county_periods` | `period_grain`, `period_start`, `period_end` | `year:YYYY-01-01:YYYY-12-31` | `crash_count` (total police-reported crash records in Allegheny County extract) | Annual count only; no inference about exposure or rates. |
| `coordinate_coverage` | `period_grain`, `period_start`, `period_end` | `year:YYYY-01-01:YYYY-12-31` | Numerator: `mappable_crashes`; Denominator: `denominator_crashes`; Rate: `coverage_rate`; Also `unusable_pairs_count`, `outside_county_count` | Quantifies geocoding completeness for mapping. |
| `field_coverage_by_year` | `period_start`, `metric_id` | `YYYY-01-01:metric_id` | Numerator: `metric_value`; Denominator: `denominator`; Rate: `coverage_rate` | Evaluates valid hour (`valid_hour`) and illumination (`illumination_code`). In 2024, illumination is observed zero (0 / 10,228). |

---

## Verification commands and results

Environment: Windows 11, Python 3.13.7, Node 22.16.0, Vite 5.4.21, Playwright 1.60.0, Chromium 148.0.7778.96.

| Verification Level | Exact Command | Result |
| --- | --- | --- |
| **Backend test suite** | `cd EDAgent_Completed_Extension\EDAgent\backend`<br>`..\.venv\Scripts\python.exe -m pytest -o addopts= -q tests` | **195 passed, 1 warning in 135.17s** (includes new Phase 7B contract test, all Phase 7A auth/isolation/verifier tests). |
| **Root release & gate suite** | `$env:PYTHONPATH = "src"`<br>`EDAgent_Completed_Extension\EDAgent\.venv\Scripts\python.exe -m pytest -o addopts= -q tests/test_audit_release_gates.py tests/test_descriptive_release.py tests/test_historical_concentration_and_severity.py` | **16 passed, 9 skipped in 2.43s** (0 regressions, expected skips for uninstalled optional network tools). |
| **Frontend type check** | `cd EDAgent_Completed_Extension\EDAgent\frontend`<br>`node node_modules/typescript/bin/tsc -b` | **Passed with 0 errors**. |
| **Frontend production build** | `npm run build` | **Passed** (`vite build` completed successfully, dist artifacts emitted). |
| **Browser smoke test** | `node tests/road-safety-smoke.mjs` | **Passed across 1440px, 768px, and 390px**: verified keyboard navigation, year selection, coverage panel caveats, 2024 observed-zero illumination, 2015 unavailable severity, table row selection, URL search param synchronization, invalid year fallback, browser back-button navigation, CSV download route, and Investigation page integration. |

---

## Visual evidence and artifacts

Stored under `.repro/phase7b/screenshots/`:
- `fixture-root-ready-desktop.png`: Investigation page (`/`) with approved `AnnualCrashFigure` mounted at 1440px.
- `fixture-root-ready-narrow.png`: Investigation page (`/`) with approved `AnnualCrashFigure` mounted at 390px.
- `fixture-overview-desktop.png`: Full `/road-safety` record view with interactive figure, severity composition, and field coverage at 1440px.
- `fixture-overview-narrow.png`: Full `/road-safety` record view at 390px.
- `fixture-calculator-desktop.png`: Calculator route (`/illustrative-scenario`) at 1440px.
- `fixture-calculator-narrow.png`: Calculator route (`/illustrative-scenario`) at 390px.
- `public-index-pending-desktop.png`, `public-index-pending-tablet.png`, `public-index-pending-narrow.png`: Homepage under closed release gate.
- `public-methods-desktop.png`, `public-methods-tablet.png`, `public-methods-narrow.png`, `public-methods-200-percent.png`: Independent methods documentation.
- `public-record-unavailable-desktop.png`, `public-record-unavailable-tablet.png`, `public-record-unavailable-narrow.png`: Road safety record fail-closed under closed gate.
- `public-record-transport-desktop.png`, `public-record-transport-tablet.png`, `public-record-transport-narrow.png`: Road safety record transport failure state.
- Playwright traces: `public-desktop.zip`, `public-tablet.zip`, `public-narrow.zip`.

---

## Verification outcomes

### 1. Local Implementation: PASSED
- The annual crash-report figure and selected-year coverage panel are fully implemented and tied to verified release provenance.
- All edge cases, caveat indicators (2016 severity coding seam, 2024 observed zero illumination, 2024 low hour coverage), accessible keyboard controls, table row selection, URL synchronization, and direct CSV export are verified locally.

### 2. Science Approval: PENDING
- The real D7 candidate release (`v3-d7-2`, SHA-256 `ec9def348fc67561f7ee2a5c7b3307a7db42b6e8832d7df7cc04252b87e70a82`) remains gated (HTTP 503) pending external science editor review and explicit ledger entry.
- Synthetic fixtures with identical schema and verified release structure were used for local automated verification.

### 3. Target Deployment Verification: OPEN
- Target HTTPS hosting, production reverse proxy, domain routing, SSL/TLS, and remote server validation require production deployment credentials and remain open for the deployment owner.

---

## Architectural reuse for Phase 8

Phase 8 (map and severity pages) can directly reuse:
1. **Unified Component Pattern**: `AnnualCrashFigure` co-locates Plotly visualization, accessible data table, explicit scope caveats, and verified CSV export, bound to a single verified release identity.
2. **Stable Row Key Resolution**: The `makeStableRowKey(row, keyFields)` pattern in `roadSafetyService.ts` ensures annotation bindings remain robust against filtering, sorting, or projection changes in Phase 8 site rankings and map layers.
3. **URL State Synchronization**: The `?year=YYYY` query parameter state pattern with default selection and invalid-value fallback provides the exact template for Phase 8 URL state (e.g. `?segment_id=...` or `?severity=...`).
4. **Dual-Route Mounting**: The architecture of mounting the complete interactive record on `/road-safety` and surfacing an approved entry point on `/` (InvestigationPage) with fail-closed release status fallback.
5. **Release Integrity Enforcement**: Reusable verifier guarantees that charts, tables, annotations, and downloads remain bound to one verified release identity without risk of mixed-version client state.
