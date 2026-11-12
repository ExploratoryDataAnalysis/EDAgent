# Phase 3 and 4 review status

Status: **blocked; not approved for Phase 5**. This supersedes completion and
approval language in the Phase 3 and 4 reports. Those reports are preserved as
the historical record, not evidence of an accepted release.

The v6 input SHA-256 is `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511`.
The Phase 3 audit reproduced the v1.0.0 totals and identical decompressed output
across two builds, but found that LRS sites are inferred from crash records,
spatial matching uses bounding-box midpoints, and no intersections are built.
The released inputs lack a pinned independent route/segment/offset network and
a reconciled historical network. No replacement crosswalk or site inventory is approved.

## Source review, 2026-11-12

* PennDOT Publication 153, current PDF, is preserved at
  `data/reference/codebooks/pub153_current.pdf`, SHA-256
  `cfecb7765e16c7244fff934b7575439c16288f537edd01f3af968ef5ad7c311e`.
  [PennDOT's public manual](https://www.pa.gov/content/dam/copapwp-pagov/en/penndot/documents/travelinpa/safety/documents/pub153.pdf)
  is a statewide police crash-reporting guide; the local PDF metadata is dated
  February 2025. It is not evidence that encoding was unchanged in 2004–2024.
  The previously recorded 2021 URL redirected to a search page on download.
* PASDA's [historical archive](https://www.pasda.psu.edu/download/alleghenycounty/historic/AlleghenyCounty_StreetCenterlines/)
  lists a 2006 snapshot and snapshots in 2013–2024. The December 2024 snapshot
  is preserved at `data/reference/street_centerlines/AlleghenyCounty_StreetCenterlines202412.zip`,
  SHA-256 `8364f54192898cc776560069745db5f5903e9f9afd8a939d3c7dc93081a948af`;
  ZIP integrity was checked. These are Allegheny County centerline snapshots,
  not proof of continuous road existence, at-grade junctions, or stable IDs.
  Coverage between snapshots, missing years, and licence and reuse terms need review.
* PennDOT publishes a dynamic [roadway segments service](https://gis.penndot.pa.gov/gis/rest/services/opendata/roadwaysegments/MapServer/0)
  and [TIRe](https://gis.penndot.pa.gov/TIRe) traffic counts, including
  [local-road counts](https://gis.penndot.pa.gov/ltap/Public/DropIns.aspx).
  Neither a pinned LRS extract nor a linked historical traffic extract has been
  obtained or validated for this study. Service availability does not establish
  coverage for any given site or year; use restrictions and historical versions
  remain to be checked.

The Phase 4 coverage values are hard-coded assumptions, not a TIRe join. The
crash-selected panel omits sites without a crash and uses future crashes to
select training sites. The panel builder now requires independent eligible and
observed site-year frames, neither of which is available in the checkout. There is no verified
site-year AADT extract or approved exposure join. The previous no-go remains a
precautionary restriction, not a measured 0% coverage finding. The concentration
report's nominal lengths, overlapping severity categories and persistence totals
must be corrected and revalidated against an accepted crosswalk.

The release scripts fail closed until those defects and input gaps are resolved.
The old v1.0.0 reports and hashes are not a replacement release. Required before
acceptance: versioned LRS and traffic reference extracts with licences and
historical coverage; geometry-based matching and an intersection inventory;
review of coordinate disagreements; a reviewed eligible network and exposure
join or bounded historical fallback; regenerated artifacts and hashes; and named,
dated reviewer decisions. Reviewer sign-off is absent. The frozen v6 baseline
is unchanged. The API withholds the old concentration outputs pending review.

## Reproduction and current tests

The previous audit's two disposable legacy builds produced 248,810 outcomes:
187,068 matched, 5,856 ambiguous, 55,886 unmatched, including 2,146 withheld
coordinate conflicts; decompressed crosswalks matched. They used the defective
v1.0.0 algorithm and are not a new release. Its year and road-class summaries
reconciled, but assignments lack independent reference validation. No current
artifact or hash is promoted. The four script entry points intentionally fail
closed; they cannot rebuild the required inventory, crosswalk or Phase 4 output.

With `$env:PYTHONPATH='src'` and `$env:OPENBLAS_NUM_THREADS='1'`, the release
gate, unavailable-API dependency, and Phase 3 unit tests passed (80 tests).
The non-API Phase 4 suites yielded 19 passed and nine artifact-dependent
failures; they require absent outputs and still encode old claims. The 12 legacy
API tests were attempted, but their TestClient stalled before a result; they
also expect unreviewed artifacts to be served. The new test checks route
dependencies and metadata, but an HTTP integration run remains outstanding.
All four script commands were invoked and stopped at their release gates.
No reviewer has signed off any replacement. The 2006 and 2013–2024 archives
still need year-by-year network comparison and provenance review. Geometry
matching, grade separation and intersection clustering remain unimplemented.

## Provisional staging run (2026-11-12)

`scripts/build_provisional_crosswalk.py` is a separate, non-release entry point;
the four release scripts remain blocked. Install the pinned packages in
`scripts/requirements-provisional.txt` and set `PYTHONPATH` to those packages
and `src`. Runs with `--output .repro/phase3_stage_b` and `phase3_stage_c`
produced identical output hashes. Outputs remain local staging artifacts:
`site_inventory.csv`, `candidate_junctions.csv`, `network.geojson`,
`crosswalk.csv`, `qa_by_year.csv`, `qa_by_road_class.csv`, `manifest.json`,
and, after `scripts/summarize_provisional.py`, `review_summary.json` and
`qa_by_year_road_method.csv`. The crosswalk SHA-256 is
`0bd33ca777dbc5257361f0a662fc8a5fd03fc86f6fa9f6cde08005d93f8ae750`;
inventory `eb8d4a737fa5d795ac0d0300489243355e9912db74c03ae68ee03b65574c34a0`;
map `7c3f7e6419766b6b7d11a52099925d6af43ce3fac83ba75def9c8fdecf66ecd2`;
junction candidates `349b7c1eac6cf04205e141b63f9696e4581645693f9e487e2dd23c1fef8f6caa`;
joint QA `f5c7c36fea3c93c9c18920e4debd25499c26693eea3ca1cb59f58b5410fd4098`.

The 2024 archive has 81,957 unique FEATURE_KE values and EPSG:2272 geometry
in US survey feet. IDs include the snapshot version and feature key; junction
candidate IDs hash incident segment IDs and rounded endpoint coordinates. IDs
are deterministic for this snapshot, not proven persistent across revisions.
Ramps and divided carriageways remain separate source features; no clustering or
at-grade confirmation is inferred from their geometry. The 42,878 endpoint
junction candidates all require grade and topology review. Geometry crossings
without shared endpoints are not included. Distances use actual polylines in
EPSG:2272, converted from survey feet to metres. The 50 m candidate radius is an
exploratory search limit, not a validated acceptance threshold.

All 248,810 source CRNs appear exactly once: 2,146 frozen conflicts are
`AMBIGUOUS` and 246,664 records are `UNMATCHED`; none has a primary assignment.
Nearest snapshot candidates exist for 235,988 records and all reference a
segment in the inventory; 10,114 lack valid coordinates and 562 have no line
within 50 m. Year, road-class and reason strata reconcile. All assignments are
withheld, including 2024, because temporal validity, route/offset linkage,
intersection evidence and reviewer decisions are not established. The candidate
distances and snapshot road classes are not adjudicated matches. Representative
raw/input checks: CRN 2004000001 has a candidate 0.665 m away but is withheld;
2004000022 has missing coordinates; 2007016949 is a withheld v6 conflict with
route/segment recorded. No reviewer has approved these samples or the output.

`scripts/snapshot_penndot_reference.py` captured 5,325 Allegheny features to
`.repro/penndot_roadwaysegments/segments.geojson` with SHA-256
`7b68dbe432bc66e04d759d15566860592ba39e6ec96184c99cd3d41dcad9fdca`.
5,323 have a positive `CUR_AADT`; it is a live-service snapshot and its AADT
observation year, historical network validity, terms and link to PASDA sites
remain unverified. `.repro/tire_station_sample/sample.json` contains ten
station features (SHA-256 `a183d47cd718e78466df171bbf7b3c8bed7530821777f231e47e12c5795f490e`),
not traffic observations. Neither source provides a reviewed site-year join.
An attempted download of NHTSA's 2010 Pub 153 returned HTTP 403. Historical
encoding, roadway reference validity and the full conflict dispositions require
additional official evidence and human review.

The fixture-based exposure join rejects duplicate site-year records, preserves
zero versus unknown crash counts, leaves missing exposure empty and reports
unmatched observations. It is not a station-to-site join or coverage estimate.
No site/crash-type expected baseline is justified for Phase 5. The complete
test suite with `PROVISIONAL_STAGE=.repro/phase3_stage_b` passed **117** tests;
nine legacy artifact checks were skipped because their v1.0.0 release contract
is unapproved. The 12 formerly stalled HTTP tests executed outside the socket
sandbox with their updated unavailable-state expectations. The four release
commands still stop at their guards. Supported approved-artifact HTTP behavior
cannot be tested because no approval mechanism or accepted artifacts exist.
