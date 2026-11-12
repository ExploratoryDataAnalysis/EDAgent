# v6 source and research decisions

## Frozen crash input

- Publisher: Western Pennsylvania Regional Data Center, [Allegheny County
  Crash Data, Cumulative Crash Data](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/2c13021f-74a9-4289-a1e5-fe0472c89881).
- Resource ID: `2c13021f-74a9-4289-a1e5-fe0472c89881`; local filename:
  `data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv`. The resource metadata
  reports data last modified 2025-06-30 and describes the cumulative 2004–2024
  extract. A resource ID alone is not an immutable version: identify this
  snapshot by its SHA-256 and size.
- Frozen SHA-256: `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511`;
  116,560,683 bytes, 248,810 rows and 191 columns. The official CKAN
  [datastore dump](https://data.wprdc.org/datastore/dump/2c13021f-74a9-4289-a1e5-fe0472c89881)
  downloaded for this attempt matched both size and SHA-256. The metadata's
  recommended downstream download returned HTTP 502 on 2026-11-12. The
  checked-in manifest records the earlier source check on 2026-11-11 UTC.
- The CSV is local input, excluded from Git. Do not substitute another version
  under this identity; stop and record a mismatch before analysis.

## Spatial reference and interpretation gates

The notebook uses the [2024 Census county 500k boundary](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip),
selecting Allegheny County GEOID `42003`. The archive downloaded for this
attempt had SHA-256 `da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1`
(case-insensitive hex). The frozen manifest did not record a boundary hash,
so its exact bytes cannot be independently established from that manifest.

Police GPS encoding remains unverified; candidate DMS comparisons are
diagnostic and do not authorize operational coordinate selection. Historical
severity definitions and codebooks still require team attestation. Reported
crashes are not traffic exposure, and the reused 2022–2024 test period is not
fresh external validation. The site-frequency gate remains closed without
approved exposure data. All models and outputs remain review-only and
`NOT_APPROVED_FOR_PRODUCTION`; no reproduction is a promotion or sign-off.

See [the reproduction inventory](v6_reproduction_inventory.md) for the
notebook revision, commands, hashes, comparisons and review status.
