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
