# EDAgent implementation plan

14 November 2026 · Baseline `main` at `87a7aea` · Proposed work after the Phase 6 handoff

## Decision and scope

Make the Allegheny County investigation the public entry point. Give it a document layout, a bounded question, and evidence readers can trace. Keep the illustrative calculator and general dataset analyser separately identifiable. The first public increment is the investigation, Methods, the existing record route, and a usable hypothetical calculator. The map and evidence pages follow the first verified data slice. Model diagnostics, private guest uploads, and provider features have independent release decisions.

The local checkout matches the short revision named in the audit. The audit records matching candidate bytes and an outstanding external D7 decision at the time of review. Its screenshots establish an unavailable Overview and an untouched calculator form. Its handoff describes prior fixture and loopback staging successes. Establish the current Docker, exact-candidate approval, public HTTPS, and provider state in Phase A. The UX report did not inspect a live populated EDAgent page. This plan was checked against the documents and checkout inventory. It does not record a new deployment, browser run, provider smoke test, or scientific review.

## What the research changes in the audit’s work order

| Research result | Implementation consequence | How the team will tell |
| --- | --- | --- |
| The unavailable Overview is a missing-evidence problem as well as a layout problem. Presentation, useful status copy, and evidence availability affect different outcomes. | Begin deployment diagnosis and editorial prototyping in parallel. Build Methods and a substantive unavailable state. Test the populated experience with controlled fixture data, then rerun against genuinely approved data when available. | Compare orientation with identical unavailable content, test the effect of adding scope separately, then measure finding and caveat comprehension in a populated state. |
| Familiar patterns can support task performance. Community reports of an AI look largely describe combinations of defaults, interchangeable copy, and inconsistent choices. | Use distinct public and workspace layouts. Preserve predictable analyser navigation, field labels, tables, and standard focus behavior. Review public components by the reader question each serves. | Measure route discovery and workspace task completion separately from distinctiveness ratings. |
| Immediate appeal and observed comprehension are different outcomes. Sequencing may affect recall and preference, with mixed evidence for accuracy. | Put one bounded claim, its coverage or denominator, and a source beside the first figure. Compare narrative order before committing to more elaborate presentation. | Score immediate interpretation, source finding, and delayed recall separately. |
| Research supports communicating limitations close to public facts. Its experiments do not validate how EDAgent readers will interpret crash coverage. | Bring unknowns, exclusions, coding changes, and denominator basis into captions and tables. Treat a scientifically misleading interpretation as a release defect. | Ask readers to explain the claim and its limit in their own words and record confidence in wrong answers. |
| A worked example plausibly reduces calculator entry friction. Its epistemic status can still be misread. | Put a one-click invented case before the full form, repeat its status at the result, and test understanding of both the arithmetic and the boundary. | Measure first valid result, recovery from invalid input, and confusion with observed effects or site recommendations. |
| The proposed paper palette, type pairing, illustration, and grid are art-direction hypotheses. | Try two coherent first screens with identical content and state. Choose by reading order, contrast, phone layout, and subject fit. Start with the simplest figure that answers the question. | Keep screenshots, task evidence, and the decision rationale. Collect perceived authorship only after task and quality ratings. |

## Workstream sequence

| Phase | Depends on | Output and decision |
| --- | --- | --- |
| A. Baseline and release readiness | Current checkout and deployment access for live probes | Reproduce the pictured failure or document its verified cause, establish state fixtures, identify exact D7 decision and deployment gaps. |
| B. Reader prototype and validation | Audit, current views, safe Methods text, and A fixtures as available | Decide on public hierarchy, scope wording, navigation, and calculator entry based on reader tasks. Can begin during A. |
| C. Public shell and first evidence slice | A contract and B findings sufficient for the slice | Public root and Methods, verified annual record and coverage, plus trustworthy degraded states. Real findings require approval and public verification. |
| D. Map, severity evidence, and calculator | C shared patterns for map/evidence. Calculator can begin after B | More detailed approved county evidence and an independent hypothetical calculator with a worked example. |
| E. Public release rehearsal and rollout | C, the calculator from D, and genuine D7 approval for live findings | Same-origin HTTPS and browser checks, evidence review, operational rollback, and a decision for each included route. Map and severity can follow if their route checks are still open. |
| F. Analyser onboarding and private guest workflow | C route split. Real county sample depends on D7 | Teaching or approved aggregate sample, then owner-scoped guest uploads, analysis, exports, and retention. |
| G. AI reliability, then optional BYOK | Existing signed-in analyser for early diagnostics. Guest enablement depends on F | Demonstrated provider and grounded analysis path with deterministic recovery. BYOK requires a subsequent privacy and isolation decision. |
| H. Retrospective model review | C release pattern. Separate model derivative approval for any real diagnostics | Method page or synthetic lesson, followed by separately approved aggregate model figures when eligible. Offline reproduction can begin during C. |

Roles below describe responsibility. Assign people in the first planning session. Keep this website plan separate from the existing scientific phase numbers and record D7 and model decisions in their existing release records.

## Phase A · Establish the baseline and prove the release contract

**Owners** Deployment maintainer, science reviewer, and QA.

1. Record deployed revision, build IDs, Compose layers, browser origin, expected API prefix, health, migration revision, candidate bundle ID, and exact manifest SHA-256. Check runtime environment presence and read-only mounts from inside the running service. Diagnose the Overview with the health route, provenance response, each required table, and server-side gate diagnostics. Keep paths, raw errors, and secrets out of public messages.
2. Separate ordinary developer startup from same-origin staging. Verify SPA deep links and refresh, API proxy ordering, forwarded HTTPS at ingress, and correct JSON errors on API failure. Check that browser requests target the deployment origin and use the intended build. Record which checks need the deployment owner’s access.
3. Reuse the existing test fixture for a served release and explicitly label it synthetic wherever anyone could see it. For the real candidate, confirm bundle identity and ask the designated reviewer to record the genuine named, dated decision through the existing external ledger. No review decision is implied by a hash match or successful fixture run.
4. Exercise missing, pending, mismatched, and tampered inputs. Exercise a genuine approved path when available. Verify revocation with a fixture and establish how the production gate handles an approval change across browser state, downloads, caches, and any sample endpoint. Choose a bounded revalidation policy with the release owner. Invalidate visible protected results when the gate closes and prevent cached copies from serving as a fallback.
5. Capture baseline screenshots and network traces for current Overview, calculator, and analyser in each state that can be reproduced. Include fresh session, approved fixture, unavailable, slow and failed requests, and small-screen navigation. Record the exact fixture, browser and viewport with the evidence.

**Code and handoff** `docs/phase6_handoff.md`, `docs/phase3_phase4_review_status.md`, `docs/descriptive_release_data_dictionary.md`, existing Compose files and staging proxy, `backend/app/api/v1/endpoints/overview.py`, `backend/tests/test_overview.py`, `frontend/tests/road-safety-smoke.mjs`, and root release-gate tests. Application paths are relative to `EDAgent_Completed_Extension/EDAgent/` throughout.

**Exit** A second maintainer can reproduce the fixture, identify the real candidate’s actual state, and verify fail-closed behavior. Open approval or hosting dependencies are recorded with an owner and next action. B and C can proceed using fixtures. Live findings stay gated until E.

## Phase B · Validate the first reading path before polishing

**Owners** UX or frontend lead, science reviewer for stimuli, and a facilitator who can score reader answers.

- Create two first-screen studies using identical unavailable copy, links, and data absence. Compare document hierarchy and navigation treatment. Then keep the selected visual structure fixed and compare sparse copy with a useful explanation of scope, evidence status, and Methods. Use neutral methods prose and explicitly labeled fixtures for research sessions while live evidence is unavailable.
- For a populated comparison, hold evidence, wording, selection, and caveats constant while varying ordering and placement. Test a claim with its coverage and source nearby. Show the 2016 coding boundary and give the reader a way to inspect the relevant denominator. Score qualitative answers to a script agreed before sessions.
- Compare the existing calculator entry with the same form plus a prominently hypothetical preset. Separately test whether the public navigation makes the general analyser discoverable while holding the workspace constant.
- Aim for 12–16 formative sessions across public or county readers, civic-data or research readers, and prospective analyser users. Include keyboard or assistive-technology users in this round or a dedicated accessibility round. Counterbalance variants and show each person a manageable subset so one version does not teach the next task. Record order and device.
- Task sequence is orientation and task completion, then comprehension and confidence, then delayed recall and quality, then optionally perceived authorship. Record time, wrong turns, repeated errors, ability to find a source and explain what it supports, and confident misinterpretations. Ask whether no data means zero, whether the map supports site risk, and whether a scenario result is observed or hypothetical.
- Start with an editorial composition, a restrained candidate palette, and legible type. Make illustration, bespoke motion, and additional interactivity contingent on a job they can do. Subject identity can come from the county question, methods, evidence, and captions.

**Exit** Save the variants, brief for every route in C, scoring rubric, observations by task, and selected alternatives. Treat recurring or high-impact scientific misunderstanding, an inaccessible primary action, and a blocked route as defects. Fix and retest affected tasks. The formative sample informs design choice without a population estimate. If recruitment is delayed, engineering can build reversible layout and contract work. Record the remaining reader decisions before committing to high-cost visual or interaction work.

## Phase C · Ship the public document shell and annual record slice

**Owners** Frontend lead, release maintainer, and science editor.

| Route | First increment | Unavailable or deferred state |
| --- | --- | --- |
| `/` | County question, period and source scope, first approved annotated figure, and links to record, Methods, calculator, and analyser | A self-contained account of what was measured and how, where readers can verify scope, and which reviewed results are currently unavailable |
| `/methods` | Source inventory, inclusion, coding periods, missingness, mapping/exposure limits, reproduction and citation guidance | Validated method and source links remain useful without the data API. Availability text reflects actual status evidence. |
| `/road-safety` | Annual count and selected-year coverage, shared chart/table state, local caveat and data/source actions | Retain the deep link. Show a useful explanation and retry. An independent panel error can be recoverable while the common gate and other tables still verify. |
| `/illustrative-scenario` | Preserve route and link it explicitly as hypothetical | Phase D improves the experience. |
| `/analyser` | Clear workspace entry and applicable account sign-in path | Preserve current authenticated workflows and deep links through redirects where needed. |

1. Split the public document shell in `frontend/src/App.tsx` and the layout components. Use readable native scroll, purposeful heading order, landmark navigation, visible focus, and predictable back/forward behavior. Remove version branding from public chrome. Label the analyser by its task, with sign-in instructions at the relevant step. Test unknown routes and direct refresh.
2. Extend `roadSafetyService.ts` to keep the typed release and table metadata, stable row keys, grain, population, unit, ratios, caveats, and run information already supplied. Resolve annotations against original ordering before filtering. Use the public provenance read to establish release identity, verify identity on all responses, and discard aborted or superseded responses. Preserve the existing wire contract where adequate.
3. Define approved, unavailable, loading, transport, and dependent-panel behaviors. A transport error states what the browser actually knows. A failing gate or mismatched release clears protected content across the active view. A panel failure can remain local while other responses still belong to the verified release. No chart, screenshot, static summary, download, or example should backfill protected data on the unavailable path.
4. Use `RoadSafetyPage.tsx`, `PlotlyChart.tsx`, and existing native tables for the first chart. One selected-year state drives chart, table, caption, and shareable selection where supported. Label counts as reports from the fixed extract. Place denominator and coverage on the same reading path. Reconstruct ratios from compatible counts and preserve zero, null, unknown, and unavailable as distinct values.
5. Add a common figure/source pattern with period, geography, population, unit, caveat, approval-aware data link, and a Methods anchor. Release identity and filter metadata accompany numerical exports. Keep charts off the critical path where possible and record baseline load, chart initialization, and selection response on representative phone/throttled settings before adopting budgets.

**Exit** One complete annual-and-coverage path with fixture reconciliation, keyboard-accessible chart alternatives, and responsive screenshots at 1440, 768, and 390 px plus 200% zoom. Approved fixture, unavailable, slow, panel error, mixed release, and stale request paths are covered. Review a direct link, refresh, back navigation, and a transition into the authenticated workspace. Science reviewer checks captions and source mapping. Publish public Methods and the unavailable state independently if deployment and accessibility checks pass.

## Phase D · Add the map, severity evidence, and hypothetical calculator

**D1 · Map and measurement.** Implement `/road-safety/map` using verified `historical_grid` and county boundary assets. GEOID 42003, WGS 84, fixed precision IDs, and the documented 0.001° grid are contract checks. Reconcile visible or downloadable cells to the approved grid and explain exclusions relative to county counts. Clip against the approved boundary. Evaluate offline reviewed geometry if runtime clipping or phone rendering is too costly. Keep the cell table and coverage summary usable when the map fails. Distinguish absent cells from measured zero and describe historical report concentration at cell grain. Include an accessible selection and data fallback. Site ranking, address lookup, routes, individual points, and site-risk readings are outside this surface.

**D2 · Severity and measurement evidence.** Add `/road-safety/evidence` from approved `source_missingness`, `severity_associations`, and existing coverage tables. Begin with 2004–2015 and 2016–2024 panels, known/excluded denominators, and the visible coding seam. Preserve unsupported serious/fatal comparisons as null. Show 2024 valid-hour and illumination constraints beside the relevant chart. Use an effect-size plot with sample size, period, pooling and q treatment as applicable. Give expected-cell limits, underflow, and optional adjusted-model context their proper scope. New joint distributions, adjusted figures, or other changed evidence require the responsible derivative review before public use.

**D3 · Calculator.** Add “Run an invented example” ahead of the full form in `InterventionPage.tsx`. Use the existing backend arithmetic and keep a result with plainly labeled invented inputs, before/after and sensitivity, formula, reset, and guarded reference information. Visibly preserve hypothetical status in the result, share state, and any export. Make errors field-specific, move or announce result focus appropriately, and invalidate outputs when inputs or request scope change. Example reconciliation is 40 × 0.80 = 32.00, a reduction of 8.00, with after range 28.00–38.00 for factors 0.70–0.95. Cover zero baseline, neutral factor, increases, malformed decimals, bounds, stale requests, and real-location or unsupported factor refusals. Reuse `test_interventions.py` and browser smoke. Reference evidence stays distinct from invented arithmetic.

**Exit** D1 passes geometry, coverage, totals, fallback and performance checks. D2 figures, tables, source links and period filters agree with the same manifest and preserve unsupported values. D3 passes numerical and browser regression checks, and a reader can explain the invented output and recover from an input error. Each increment is independently mergeable. Expose only routes with a complete primary task and the relevant review.

## Phase E · Rehearse and release the public investigation

**Owners** Deployment maintainer runs the rehearsal, science reviewer controls evidence approval, and frontend/QA confirms reader paths.

1. Rehearse the currently supported public routes on same-origin HTTPS using the target build and staging data configuration. Verify fresh visits, direct routes, JSON health and API errors, desktop and mobile, keyboard and reduced motion, accessibility and performance findings, the manual analyser entry, and data exports. Reproduce the gate’s unavailable state without relying on a stale cached response.
2. Verify the external decision for the exact real D7 manifest. Reconcile chart, table, and export against the manifest and data dictionary. Include annual/era/county counts, missingness, and map totals for routes being released. Use the audit’s quantities as candidate reconciliation checks only after rechecking the exact artifact. Exercise plausible misreadings, including exposure-normalized rates, causal treatment claims, station counts where evidence is unavailable, and site-level forecasts across relevant output paths.
3. Record reviewer, revision, manifest, build, environment, date, checks, and any routes deferred. Identify operational ownership for failed health, unavailable review data, and feedback. Rehearse rollback of app and release config with supported database compatibility. Withdraw suspect evidence through the approval control and verify the public explanatory state. Previously approved bytes require an applicable current decision and supported bundle compatibility before reactivation.

**Exit** Sign off in the release record with screenshots, route/contract results, and rollback evidence. If approval is pending, release only the verified Methods, status and independent tools as appropriate. Re-run the real-data checks after approval before exposing findings. AI readiness and model lab approval do not gate this rollout.

## Phase F · Open the general analyser in two increments

**First increment.** Add a discoverable analyser entry and a ready-to-run sample using the existing deterministic engine, upload and workspace patterns. An approved county aggregate sample is derived from allowlisted release fields, carries the matching identity, and respects revocation. If ineligible, offer a prominently labeled teaching dataset. Walk through opening the sample, a manual analysis, export, and return to the investigation.

**Second increment.** Implement guest uploads in the existing session and ownership path. Agree guest policy before choosing schema changes: lifetime, size/quota, permitted analysis, job concurrency, explicit clear, and whether conversion to an account is supported. Propagate ownership through file/object storage, datasets, job queues and results, reports, caches, and exports. Define how clear or expiry interacts with running jobs, retries, browser back, and download URLs. Reclaim orphaned files after restart. Keep the signed-in version and deterministic engine interoperable with existing data.

**Code and handoff** `AuthContext.tsx`, `DatasetContext.tsx`, `UploadPage.tsx`, `WorkspacePage.tsx`, existing API client, backend dataset dependencies/repositories and storage, job and export services, relevant migration only if needed. Use the existing ingestion, engine, security and end-to-end suites.

**Exit** Independent guests and signed-in users can complete supported flows. Cross-session dataset/result/export reads fail through normal entry points. Expiry, deletion during active work, quota, restart, cleanup, and existing account history are verified. Guest uploads remain private, and analytics/provider transmission requires its own user-facing policy and appropriate consent.

## Phase G · Verify optional AI, then decide on BYOK

1. Start signed-in diagnostic work early if available. Establish disabled, configured and available states. Use the deployed backend with a fixed harmless canary plus an approved synthetic test dataset for an end-to-end quality check. Check provider/model pairing, runtime config, connectivity, auth, and response validation. Log timings and categories without keys, dataset content, or prompts. A reachable model proves connectivity for that request only.
2. Test planning, deterministic computation, and explanation separately and together. Enforce supported operation/schema validation and session-scoped inputs. Persist or return a reliable computed result even if explanation fails. Generate numerical facts from computed IDs and render their units and scope from the result. Route invalid, unsupported, or overclaiming explanations to a deterministic fallback.
3. Set end-to-end latency and retry budgets from observations. Make disabled, invalid credential, timeout, rate limit, provider failure, malformed output, and unsupported operations actionable. Discard stale results when switching session or dataset, and avoid duplicate intentional computation or charges on ambiguous retries. Surface only observed stages. Keep manual analysis available across modes.
4. Consider BYOK after the provider, discussion of data processing, and session lifecycle are verified. Use an explicit destination/model and request-local credential handling. Use synthetic keys and test transport to check concurrent request isolation, reload/clear or session switching, rejection and logs. Consent identifies what data moves and where. Keep workspace sign-in state intact when an upstream key is rejected.

**Files** Existing `chat.py`, AI configuration, orchestrator/LLM/context/grounding/prompt modules, chat page and clients, `docs/AI_DATA_PROCESSING.md`, and `test_chat_flow.py`.

**Exit** Fixture and real canary evidence, correct deterministic known output, scoped fallback, safe diagnostics and recoverable errors. Enable a provider only for tested environments and permitted workflows. Treat BYOK as a separate go/no-go decision. A public research assistant would need its own approved-fact contract and is deferred.

## Phase H · Retrospective model review and teaching

Use the frozen notebook and model metrics as read-only inputs. Reconcile the task definition, feature timing, cohort, chronological split, AP reference, and calibration metrics offline. Derive aggregate, checksummed web tables with explicit scope and availability. Independently review the derivative exact manifest before exposing any real comparison. Keep browser controls limited to supported cohort, split, model and threshold combinations with stored aggregates. Explain post-event inputs next to those comparisons. No case-level exports, arbitrary inference, site forecasts, production prediction, or legacy API shortcuts.

A Methods page and a deterministic synthetic lesson may precede approval. Show a persistent synthetic label in the lesson, reset, and any shared view. Keep unsupported curves unavailable. Add the endpoint and `/road-safety/models` only when each published state has a complete reader path. Review coding and evaluation details against v3, and compare curves only on equivalent cohorts with visible reference and definitions.

**Exit** Offline reproduction and reconciliation of visible outputs, approved derivative identity for real figures, correct feature timing and cohort explanation, verified refusal boundaries, and deterministic synthetic reset. Preserve the existing scientific constraints for the independent frequency, site and intervention paths.

## Cross-phase review and handoff

| Check | Required evidence |
| --- | --- |
| Scientific integrity | Review scope, time, grain, denominator, missingness, coded eras and allowed inference beside each claim. Reconcile chart, table, download, sample and any explanation with their matching source. |
| Safety of release states | Verified exact approval, tamper/mismatch/withdrawal tests, stable status and cleared stale content, same-origin deployment and rollback. |
| Reader and accessibility | Representative task notes, keyboard and visible focus, screen-reader check for changed controls or status, reduced motion, 200% zoom, chart/table parity and mobile evidence. |
| Regression | Run applicable existing backend, root release tests, TypeScript/build and browser smoke through `.github/workflows/edagent-ci.yml`. Add focused coverage where new behavior creates a regression gap. Report test environment and any unrun live checks. |
| Completion record | PR links, scope, data states, revision/manifest, fixtures, screenshots, commands and outcomes, unresolved external dependencies, and decision owner. |

Use reviewable slices. A first PR can add repeatable stage and gate probes. A second can establish the public shell and useful Methods with an unavailable fixture. Follow with the annual evidence slice and calculator as separate reviews. Each changes one recognizable reader or deployment outcome and carries its own acceptance evidence.

## Decisions to resolve as work starts

| Decision | Owner | Needed by |
| --- | --- | --- |
| Target HTTPS environment and access to observe the real deployment | Deployment owner | A diagnosis and E rehearsal |
| Exact current D7 decision and policy for revalidation and withdrawal | Designated science reviewer and release owner | A status recording and E live data |
| Routes and wording readers can navigate and interpret, and chosen visual direction | Frontend lead and science editor with reader evidence | C public release |
| Guest retention, quotas, deletion, and permitted data processing | Product and backend/privacy owners | F private upload and G provider rollouts |
| Eligible model aggregates and feature timing disclosures | Science reviewer | H model derivative review |

## Inputs

- [EDAgent UX Research: AI-Looking Cues, Genericness, Reader Outcomes, and Pre-Build Decisions](https://chatgpt.com/library?file_id=libfile_217b93b301348191957b9794ab8a96e3)
- [EDAgent-audit.md](https://chatgpt.com/library?file_id=libfile_0cd101eb6b188191ae9378a5b07393c1)
- [EDAgent project plan v3](https://github.com/ExploratoryDataAnalysis/EDAgent/blob/87a7aea/docs/EDAgent_Project_Plan_v3.tex) and [Phase 6 handoff](https://github.com/ExploratoryDataAnalysis/EDAgent/blob/87a7aea/docs/phase6_handoff.md)
