# Phase 3 and 4 review status

**Reviewed 2026-11-12. Phase 3 is provisional. Phase 4 is no-go for frequency and blocked for historical screening. Phase 5 is no-go.** No named reviewer decision has been received for any real artifact. Earlier v1.0.0 completion, exposure, concentration and approval claims remain historical. The release gate requires a separately recorded approval for the exact staged manifest.

## Frozen input and reproducibility

The 116,560,683-byte WPRDC CSV at `data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv` verified against the full SHA-256 `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511` in `analysis/outputs/run_manifest.json`. Its 248,810 distinct CRNs cover 2004–2024. Frozen v6 inputs, outputs and assumptions were preserved. The old v1.0.0 audit matched 187,068, marked 5,856 ambiguous and left 55,886 unmatched using crash-derived LRS sites and bounding-box midpoints. That result has no release approval.

Both surviving provisional builds, `.repro/phase3_stage_b` and `.repro/phase3_stage_c`, verified byte-for-byte against their manifests and against each other. Both have 81,957 December 2024 segments, 42,878 endpoint candidates, 2,146 ambiguous conflicts, 246,664 unmatched CRNs, zero exclusions and zero primary assignments. The frozen input count equals the outcome count. The 235,988 nearest line candidates are 233,318 within 10 m, 2,303 over 10 m through 25 m and 367 over 25 m through 50 m. There are 10,114 missing or invalid coordinates and 562 records with a usable point and no candidate within 50 m. Every candidate points to the same snapshot inventory.

| Checkpoint output | SHA-256 |
|---|---|
| `crosswalk.csv` | `0bd33ca777dbc5257361f0a662fc8a5fd03fc86f6fa9f6cde08005d93f8ae750` |
| `site_inventory.csv` | `eb8d4a737fa5d795ac0d0300489243355e9912db74c03ae68ee03b65574c34a0` |
| `network.geojson` | `7c3f7e6419766b6b7d11a52099925d6af43ce3fac83ba75def9c8fdecf66ecd2` |
| `candidate_junctions.csv` | `349b7c1eac6cf04205e141b63f9696e4581645693f9e487e2dd23c1fef8f6caa` |
| `qa_by_year_road_method.csv` | `f5c7c36fea3c93c9c18920e4debd25499c26693eea3ca1cb59f58b5410fd4098` |
| `manifest.json` | `70143952555cc99890ab61eb1357cd68b0fb0e54d63d9fe4a66c0402da84282d` |

## Phase 3 evidence and dispositions

[Phase 3 source inventory](data_sources/phase3_source_inventory.md) and [source pins](../data/reference/phase3_phase4_review_sources.json) record publisher, URL, snapshot or version, verification date, SHA-256, study coverage and restrictions. The archive comparison covers 2006 and one snapshot in each year 2013–2024, plus October 2026 to test revision behavior. County snapshot years 2004–2005 and 2007–2012 lack a pinned county centerline. Snapshot dates and edits leave opening, closure and change dates unresolved within and between years. County addressing lines include local roads, ramps and limited-access facilities as well as non-road classes. The report preserves source FCC/CFCC counts and bounding boxes. Those fields are source classifications with vintages of their own.

PUB 153 (02-24) documents decimal-degree conversion to DMS on p. 21. Its PDF was created February 2025. This supports the published 2024-era reporting convention. The 2018 CRS manual specifies DMS with hundredths for the entry interface. NHTSA's archived 2010 PUB 153 and PennDOT's indexed 2021 revision describe DMS with a decimal seconds component. The 2010 download returned 403 and the old 2021 URL returned HTML. The 2023 PennDOT dictionary describes PennDOT-determined GPS text and decimal-degree fields, with a 404 from the direct download. The available evidence describes reporting and documented export fields at those dates. Year-specific flattened WPRDC field provenance, coordinate-source independence and encoding transitions for 2004–2024 remain unverified. [2010 PUB 153](https://www.nhtsa.gov/sites/nhtsa.dot.gov/files/documents/pa_crash_manual_pub153_sub_11_2010.pdf) · [2018 CRS manual](https://www.pa.gov/content/dam/copapwp-pagov/en/penndot/documents/travelinpa/safety/documents/webmanual.pdf) · [2021 indexed PUB 153](https://www.penndot.pa.gov/TravelInPA/Safety/Documents/PUB_153_9-21.pdf) · [2023 dictionary](https://gis.penndot.gov/gishub/crashZip/Crash%20Data%20Dictionary%2005.2023.pdf) · [current PUB 153](https://www.pa.gov/content/dam/copapwp-pagov/en/penndot/documents/travelinpa/safety/documents/pub153.pdf)

The live PennDOT extract has 5,325 unique county/route/segment keys, directional values B/S/W/N/E/O, 5,323 positive current AADT values, and GIS edit dates from 2025-04-27 through 2026-11-08. Against all frozen crashes it yields 118,828 unique current keys with in-range offsets, 1,851 out-of-range offsets, 250 without usable offsets, 16,190 keys absent from the current extract and 111,691 incomplete keys. A current key and in-range offset do not establish a crash-era assignment. The November 2024 state-road archive is independent of crashes. It has 5,319 unique county 02 route/segment keys and 5,238 lines with a unique orientation against published endpoint coordinates. Publication 23 defines the offset as linear feet from the segment start in increasing segment direction and explains divided-road segment numbering. Archive direction, county, route and segment must agree before projecting an offset; the RMS length is used to place the offset fraction on the endpoint-checked polyline. The review's exploratory 20 m endpoint tolerance accommodates endpoint/generalization discrepancies and withholds cases where both orientations fit. The archive produces 4,252 diagnostic offset locations for 2023, whose crash-era validity remains unproved. All 10,228 frozen 2024 records have empty segment identifiers. No crash-era LRS linkage is established for a releasable scope. [PennDOT LRS](https://www.pa.gov/agencies/penndot/research-planning-and-innovation/roadway-management-testing/location-reference-system) · [Publication 23, ch. 22](https://www.pa.gov/content/dam/copapwp-pagov/en/penndot/documents/public/pubsforms/publications/pub-23/pub%2023-chapter%2022%20.pdf) · [State-road archive](https://www.pasda.psu.edu/download/padot/state/historic/PaStateRoads/)

The segment lineage records shared projected edges, exact geometry, source keys, street names and direction attributes. Unique exact one-to-one correspondence carries a candidate continuity ID, including renumbering candidates. Partial edge containment records possible splits or merges, and changed, missing or conflicting geometry remains unresolved. Older schemas and duplicate or absent keys use a snapshot-scoped row identity. County junction lineage carries an ID where the rounded endpoint and incident segment lineage agree. The December 2024 county snapshot omits the node and Z-level fields present in some other vintages. The exploratory 25 m grouping requires a common road pair or shared ramp feature and pairwise agreement. It yields 42,368 groups including 509 multi-node groups. Same-point and planar crossings are candidate evidence. The separate PennDOT November 2024 at-grade archive has 12,977 county 02 records, including 58 without geometry, with 8,900 distinct nonblank node IDs among mapped records. It identifies official at-grade locations in that vintage. The crosswalk still requires time-valid incident-road identity, topology and crash linkage for any county junction. [County archive](https://www.pasda.psu.edu/download/alleghenycounty/historic/AlleghenyCounty_StreetCenterlines/) · [PennDOT at-grade archive](https://www.pasda.psu.edu/download/padot/state/historic/PA_AtGrade_Intersections/)

Across successive archive comparisons, the review found 375,403 exact segment links, 30,024 renumbering candidates, 105 split candidates and 698 merge candidates. These are link counts, so one feature can contribute in multiple comparisons. The junction lineage has 208,062 links where endpoint and incident lineage agree. The two independent enhanced builds in `.repro/phase3_review_d` and `.repro/phase3_review_e` reproduced the segment and junction lineage, clusters, original checkpoint, county candidate distances, November 2024 grade map and RMS offset candidate files byte-for-byte.

Point-to-line and point-to-junction distances use EPSG:2272 and exactly 1200/3937 metres per US survey foot. The 50 m radius is for candidate review. A production threshold and tie width require a labelled review sample by road class and site type. The tested matcher requires verified coordinates and site effective dates, filters incompatible class, type and direction, requires independent at-grade evidence for intersections, and preserves close geometric ties. When independent LRS is available, an unambiguous LRS candidate must agree with an eligible geometry candidate. An unresolved or conflicting reference withholds the primary. The site matcher has fixture validation and no approved real scope in this checkout.

The 2,146-entry conflict register records both frozen coordinates, nearest snapshot candidates, distances, crash LRS fields, a county-polygon check and one withheld disposition per CRN. The register uses the frozen v6 field label “police candidate.” Its provenance is unverified. Against the frozen v6 boundary source, 2,125 have both points inside, 12 have only the police candidate outside, eight have only the decimal point outside, and one has both points outside. These are diagnostics against the 2024 Census cartographic boundary. Evidence does not resolve which coordinate represents the crash. The review samples include a multi-line candidate, a planar crossing, a multi-node cluster, missing coordinates and historical gaps. CRN `2004000001` is 0.665 m from a snapshot line and is withheld for crash-era validity. CRN `2007016949` is a flagged conflict and retains its two candidate positions. CRN `2004002034` has an offset beyond its current-key segment length. A named reviewer and corroborating dated location evidence remain required for any conflict resolution.

Among 4,161 frozen 2024 intersection-flagged crashes, 2,631 have a PennDOT at-grade snapshot point within 50 m and 1,530 have no candidate. These are junction-distance diagnostics. All are withheld pending verification of incident roads, crash coordinates and timing.

The archived RMS candidate for 2023 CRN `2023086164` is 9,784.767 m from the recorded decimal point. Its key matches route `0019`, segment `0501` in the November 2024 archive. This is a review example of incompatible location evidence across vintages, with no primary assignment.

## Phase 4 evidence and decision

PennDOT's two 2024 permanent-station tables yield 20 published AADT values at four Allegheny stations, 203, 208, 375 and 840, for 2020–2024. The second table supplies 2024 county/route/segment identifiers. Three stations have a unique matching record in the ten-feature TIRe sample. The sample contains station metadata, including station identifier and offset, and no annual volumes. The 2024 location table does not attest unchanged segment identifiers, direction or location for the preceding four years. The live RMS current AADT attribute has no annual observation year in the captured fields. The 20 annual values are retained as station-year evidence, with zero verified links to an eligible site-year. The denominator is unknown, so observed, estimated and missing fractions are unmeasured. The public report restricts use to traffic counts and excludes projected growth. [2024 PennDOT traffic report](https://www.pa.gov/agencies/penndot/about-penndot/results-data/traffic-information/2024-pennsyivania-traffic-data) · [traffic source inventory](traffic_exposure/traffic_source_inventory.md)

The staged panel contract joins exact crosswalk-version site-years to independent full-year eligibility and crash-observation frames. It preserves verified zero, unknown crash observation, attributed crashes in unknown years and missing traffic as separate fields. Traffic requires a positive annual observation, station identity, matching route/segment/direction, compatible site type and AADT measure, and declared observed or estimated status. Duplicate site-years fail validation. Incompatible records and observations outside the eligibility frame are reported. Coverage uses all eligible site-years as denominator by year, class and type. Controlled data verify zero retention and crash reconciliation. A segment's screening measure is attributed crashes per observed kilometre-year using inventory length. Intersections use attributed crashes per observed intersection-year, with no segment length. Only independently observed site-years enter the measures, and the summaries identify the eligible and observed totals. The real crosswalk does not support either measure. A chronological Poisson baseline, negative-binomial challenger and Empirical Bayes are unavailable for this evidence. Severity remains retrospective and requires a separately covered artifact. There is no justified expected baseline for any Phase 5 site/crash-type combination.

## Commands and approval

### Bounded pilot follow-up

The [2023 PennDOT report](https://www.pa.gov/agencies/penndot/about-penndot/results-data/traffic-information/2023-pennsylvania-traffic-data)
provides independently dated station location and AADT tables. Both PDFs are
pinned in the source registry. All four station route/segment keys agree with
the 2024 location table, and all 16 overlapping annual AADT values agree.
The 2023 report also adds four 2019 station-level observations. All 24
station-years remain unlinked to eligible site-years.

| Station and route/segment | 2023 offset candidates using November 2024 RMS | 2024 route-wide geometry candidates, one line / multiple lines within 50 m |
|---|---:|---:|
| 203, PA 65 / 0270 | 2 | 21 / 78 |
| 208, I-376 / 0794 | 7 | 0 / 666 |
| 375, US 22 / 0080 | 0 | 0 / 55 |
| 840, I-279 / 0122 | 3 | 4 / 160 |

The 2024 counts are diagnostics across the full recorded route and do not
locate crashes on the station segment. The review checked all crash types
for segment candidates. No intersection or crash type qualified. The best
candidate for a future pilot is the I-376 station 208 segment in 2023.
Its closest decimal point and independently reconstructed offset are 1.105 m
apart. The calculation uses November 2024 geometry, so the closeness does
not verify 2023 endpoints, alignment or the independence of the crash
coordinate. Station 375's empty result is an unknown crash count. Station 840
has no corresponding record in the local TIRe sample.

For station 208, obtain dated segment endpoints and offset geometry from
PennDOT District 11's RMS/LRS custodian and crash-coordinate lineage and
reporting completeness for the selected crash types from PennDOT's crash data
custodian or WPRDC. Obtain station direction, location and coverage history
from PennDOT's traffic monitoring program. Those records would determine
which matches, observation years, and AADT links can enter a reviewer package.
The other three candidates require the same effective-date and direction
evidence. The frozen crosswalk still accounts for all 248,810 records with
zero primary assignments and no eligible or observed pilot denominator.

Run `python scripts/extract_permanent_aadt.py .repro/source_review --pilot-review .repro/phase3_review_final .repro/phase4_final .repro/pilot_review.json`.
Two runs produced SHA-256
`28d34f61ffe27e2e61681fcb7149e6993118a05a5445e6edaf54fde497f98098`.
The diagnostic pins its input manifests and preserves CRN samples and each
station-year disposition. No pilot artifacts qualify for approval or publication.

### Pipeline reproduction

From the repository root in PowerShell, use `scripts/requirements-provisional.txt` for the geometry environment. The traffic-table extraction used PyMuPDF 1.27.2.3. Staging destinations must be new directories.

```powershell
$env:PYTHONPATH = 'src;.repro/geodeps'
$env:OPENBLAS_NUM_THREADS = '1'
python scripts/verify_review_sources.py
python scripts/extract_permanent_aadt.py .repro/source_review
python scripts/build_crosswalk.py --stage .repro/phase3_review_final
python scripts/assess_traffic_exposure.py --stage .repro/phase4_final/exposure --input .repro/phase3_review_final
python scripts/run_frequency_modelling.py --stage .repro/phase4_final/concentration --input .repro/phase3_review_final
python scripts/generate_concentration_visualizations.py --stage .repro/phase4_final/visualizations --input .repro/phase3_review_final
$env:PROVISIONAL_STAGE = '.repro/phase3_review_final'
python -m pytest -o addopts= -q tests
```

`verify_review_sources.py --fetch` retrieves missing archival files and checks the pinned bytes. For the existing live snapshots, use the two `snapshot_*.py` commands documented by their names. They fetch new vintages from dynamic services. Use a new path or preserve the surviving snapshots before any fresh capture. `build_provisional_crosswalk.py --output <new staging directory>` and `summarize_provisional.py <staging directory>` reproduce the original checkpoint. The new Phase 3 stage preserves the checkpoint manifest and adds a checksummed evidence manifest, line and junction lineage, a conflict register, grade and LRS diagnostics, and QA by year, class, type, reason and distance. Phase 4's three stage manifests pin the Phase 3 manifest and identify the unavailable decision or station review outputs.

| Local stage manifest | Verified SHA-256 |
|---|---|
| `.repro/phase3_review_final/manifest.json` | `ba19132b6d892489382524766e40264dee82deaeeb1058626816d7150c75ecd7` |
| `.repro/phase4_final/exposure/manifest.json` | `16825b324fbb4bf5b82257e3f115caf7dbf6ee219042f102e95a1f148d32c876` |
| `.repro/phase4_final/concentration/manifest.json` | `ee7545e50366287fe4abccc3479f38e1707a58bd323675674ed0587355e39fa1` |
| `.repro/phase4_final/visualizations/manifest.json` | `b0997e72cc0df7e97dfb5ecc6d7c9871438d91b4f727d0d077ca39bd057431d3` |

All four manifests' output hashes were verified. The final Phase 3 build
reproduced 15 of the 17 files from `.repro/phase3_review_e`. The added
county-boundary evidence changed the conflict register and evidence report.
All four real publication probes with the local pending-decision ledger
returned a release refusal and created no publication directory.

For eligible future work, pass an input directory containing an approved `crosswalk/` and, downstream, approved `exposure/` and `concentration/` bundles. Exposure reads `eligibility.csv`, `observation.csv` and `linked_annual_aadt.csv` alongside the bundles. The tests provide controlled schemas. Each publication command accepts `--publish <bundle> --approvals <ledger> --release-root <directory>`. The deployment-controlled JSON ledger sits outside the staged/published bundle. Each product key (`crosswalk`, `exposure`, `concentration`, `visualizations`) maps to a decision with `decision`, `reviewer`, `date` (ISO date), and `manifest_sha256`. `APPROVED` binds the reviewer to the exact manifest bytes, which pin the version, scope, inputs and all output hashes. The manifest must be a `REVIEW_CANDIDATE`; a provisional manifest remains ineligible even if its hash appears in the ledger. Publication verifies the staged bundle and the copy before making the directory visible. For the API set `ROAD_SAFETY_APPROVALS` and `ROAD_SAFETY_RELEASE_ROOT` to the trusted ledger and release root. The API verifies the visualization bundle before serving and rechecks the served bytes. Legacy CSVs, incomplete bundles, missing or pending decisions, mismatches and tampering return unavailable. No real artifact has an approved ledger entry.

## Legacy verification

The complete road-safety suite against the final Phase 3 staging directory
passed **128** tests with **9** historical skips. The backend suite passed
**110** tests in its installed virtual environment, with one TestClient
deprecation warning. The HTTP and publication fixtures exercised the
approved path and missing, pending, provisional, mismatched and tampered
cases. Separate HTTP requests against the real provisional Phase 4 stage
returned 503 for all six protected artifact routes, with the blocked status
and null expected-frequency responses retained.

The previous 117-pass baseline included the API checks. The current collection has 13 legacy HTTP test cases, including the stale-artifact test and duplicated endpoint checks across two test modules. All requested HTTP routes are covered. Nine historical release-artifact tests remain skipped:

| Legacy skip | Current verification |
|---|---|
| Hard-coded traffic coverage metrics | Eligible denominator and observed, estimated and missing fractions in the panel fixture |
| Crash-selected panel structure | Independent full-year frames, never-crashed eligible site-year, unknown and attributed count reconciliation |
| Canonical concentration CSV | Approved fixture with geometry-derived length and separate intersection measure |
| Annual concentration | Fixture annual observed/eligible totals and HTTP response |
| Road-class concentration | Fixture class reconciliation and HTTP breakdown |
| Site-type concentration | Fixture type reconciliation and HTTP breakdown |
| Top sites geographic CSV | Site ranking and approved GeoJSON use inventory site IDs. The old standalone CSV was retired. |
| Top sites GeoJSON | Approved map fixture and unavailable checks on the real provisional bundle |
| Severity CSV export | The API serves an approved retrospective fixture with predictive and causal flags false. Real severity remains withheld. |

The remaining acceptance evidence is dated, independently validated crash-to-road location coverage; at-grade incident-road and continuity evidence for the intended years; independent eligibility and reporting completeness frames; direction-compatible station links with observation years; and a named, dated reviewer decision for the corresponding input and artifact versions. No real approved HTTP artifact was available for verification.
