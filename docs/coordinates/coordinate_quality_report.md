# Phase 3 — Module B: Coordinate Quality & Validation Report

**Project:** EDAgent Road-Safety Analytics  
**Phase:** Phase 3 — Roadway Crosswalk and Geographic Integration  
**Module:** Module B — GPS Decoding and Coordinate Validation  
**Document:** Empirical Coordinate Quality Report & Baseline Audit  
**Baseline Dataset:** WPRDC Allegheny County Crash Data (2004–2024, 248,810 records)  

---

## 1. Executive Summary

This report establishes the empirical quality, completeness, and spatial agreement of coordinates across the complete 21-year historical baseline of Allegheny County crash records (2004–2024). 

Using the verified `GPSDecoder` and `CoordinateValidator` modules developed in Phase 3 Module B, every crash record is evaluated against:
1. **Mathematical validity:** Format syntax, degree/minute/second domains, and placeholder detection.
2. **Geographic boundaries:** Western Pennsylvania regional envelope ($[38^\circ, 43^\circ]\text{N}, [-82^\circ, -78^\circ]\text{W}$) and Allegheny County screening boundary ($[40.10^\circ, 40.75^\circ]\text{N}, [-80.40^\circ, -79.60^\circ]\text{W}$ / Census GEOID 42003 polygon).
3. **Cross-source concordance:** Great-circle Haversine distance between officer-entered GPS coordinates and PennDOT state-route decimal coordinates.

---

## 2. Global Coordinate Coverage & Missingness

Across the 248,810 cumulative records, location fields exhibit distinct completeness characteristics:

| Coordinate Field | Non-Null Count | Missing Count | Missing % | Primary Role & Format |
|---|---|---|---|---|
| `LATITUDE` (Police GPS) | 238,721 | 10,089 | 4.05% | Officer-entered text DMS (`DD MM:SS.ddd`) |
| `LONGITUDE` (Police GPS) | 238,720 | 10,090 | 4.06% | Officer-entered text DMS (`DD MM:SS.ddd`) |
| `DEC_LAT` (State Route) | 238,608 | 10,202 | 4.10% | PennDOT RMS LRS geocoded decimal degrees |
| `DEC_LONG` (State Route) | 238,600 | 10,210 | 4.10% | PennDOT RMS LRS geocoded decimal degrees |
| **Both Sources Available** | **238,517** | **10,293** | **4.14%** | **Eligible for pairwise conflict auditing** |
| **Completely Missing Both** | **10,089** | — | **4.05%** | **Geographically unlocatable records** |

---

## 3. Pairwise Discrepancy & Conflict Analysis

### 3.1 Concordance Distribution (238,517 Comparable Pairs)
When both police DMS text coordinates and State Route decimal coordinates are present, the spatial distance between them is evaluated:

| Metric | Distance Value (Meters) | Distance Value (Miles / Feet) | Interpretation |
|---|---|---|---|
| **Minimum** | 0.00 m | 0.0 ft | Exact coordinate identity |
| **Median (50th percentile)** | **4.16 m** | **13.6 ft** | Sub-lane accuracy; excellent operational concordance |
| **90th percentile** | 18.22 m | 59.8 ft | Within typical intersection curb-to-curb width |
| **95th percentile** | 36.91 m | 121.1 ft | Within standard 100-foot intersection catchment zone |
| **99th percentile** | 398.91 m | 0.25 miles | Approaching road segment boundary |
| **Maximum** | **48,466.70 m** | **30.1 miles** | Severe multi-county spatial displacement |

### 3.2 Conflict Gating ($>500$ Meter Threshold)
- **Total Conflicting Records:** **2,146 pairs** (0.900% of comparable records).
- **Audit Decision:** Records exceeding 500 meters are classified as `ValidationStatus.CONFLICT` and tagged `ValidationFlag.COORDINATE_PAIR_CONFLICT`.
- **Root Cause Taxonomy of the 2,146 Conflicts:**
  1. **Typographical Degree/Minute Errors:** E.g., CRN `2007016949` where police longitude degree was entered as `79° 10'` instead of `79° 45'`, displacing the point 48.47 km eastward into Westmoreland County.
  2. **Interstate / State Route County Line Segment Resets:** E.g., CRN `2005006334` (42.14 km mismatch) where state route referencing mistakenly mapped onto a segment in neighboring Armstrong County.
  3. **Station / Headquarters Geocoding:** Incidents where responding officers recorded the municipal police headquarters address rather than the crash scene.
  4. **Sign / Transposition Errors:** E.g., CRN `2005186033` (41.58 km mismatch) where eastern and western coordinates were transposed.

---

## 4. Temporal Completeness & The 2004–2007 Local Road Gap

The temporal distribution of coordinate completeness reflects historical advances in PennDOT's GIS infrastructure:

```
Year      State Route Dec. OK    Unavailable / Ambiguous    % Missing
---------------------------------------------------------------------
2004              9,552                   2,983               23.8%
2005              9,618                   2,597               21.3%
2006              9,410                   2,337               19.9%
2007             11,539                     699                5.7%
2008             11,550                     308                2.6%
2009             11,489                     188                1.6%
2010             11,116                     204                1.8%
2015             12,706                      29                0.2%
2020              9,854                       9                0.1%
2024             10,198                      30                0.3%
```

> [!NOTE]
> **Historical Coverage Caveat:** Between 2004 and 2006, over 2,000 crashes per year lack geocoded coordinates because PennDOT only mapped State Routes. Longitudinal spatial comparisons must account for this baseline change; an apparent rise in local road crashes after 2007 reflects improved geocoding, not necessarily an increase in actual crashes.

---

## 5. County Screening & Spatial Outliers

Screening the candidate coordinates against the U.S. Census 2024 Allegheny County boundary polygon (GEOID 42003) reveals:
- **Inside County Polygon:** 238,281 records.
- **Outside County Polygon:** **275 records**.
- **Outlier Characteristics:** Points located in bordering counties (Beaver, Butler, Armstrong, Westmoreland, Washington) resulting from highway crashes near county boundary bridges or officer reporting jurisdiction overlap.
- **Policy:** Out-of-county points are retained in the research record but tagged with `ValidationFlag.OUTSIDE_COUNTY_BOUNDARY` and assigned `ValidationStatus.WARNING`. They are excluded from site ranking within Allegheny County.

---

## 6. Traceable Record Schema & Lifecycle Contract

In Module B, each crash incident is structured as a `CoordinateRecord`:

| Field Name | Type | Description |
|---|---|---|
| `crash_crn` | `int` | Primary immutable crash identifier. |
| `crash_year` | `int` | Calendar year of crash (2004–2024). |
| `raw_latitude` | `string` | Untouched police GPS latitude input (e.g. `'40 19:05.530'`). |
| `raw_longitude` | `string` | Untouched police GPS longitude input (e.g. `'79 54:27.197'`). |
| `raw_dec_lat` | `string` | Untouched state decimal latitude input. |
| `raw_dec_long` | `string` | Untouched state decimal longitude input. |
| `decoded_latitude` | `float` | Normalized WGS 84 latitude in decimal degrees. |
| `decoded_longitude` | `float` | Normalized WGS 84 longitude in decimal degrees. |
| `coordinate_source` | `enum` | Primary selected source: `state_route_decimal`, `police_dms`, `none`. |
| `crs` | `string` | Always `"EPSG:4326"`. |
| `decoder_version` | `string` | Code version: `"1.0.0"`. |
| `validation_status` | `enum` | Lifecycle category: `VALID`, `WARNING`, `CONFLICT`, `INVALID`, `MISSING`. |
| `validation_reasons` | `list[enum]` | Explicit audit flags (e.g. `COORDINATE_PAIR_CONFLICT`, `OUTSIDE_COUNTY_BOUNDARY`). |
| `pair_distance_meters`| `float` | Great-circle distance between police and state coordinates. |
| `source_dataset_version`| `string`| Input checksum hash: `"2c13021f-74a9-4289-a1e5-fe0472c89881"`. |

---

## 7. Conclusions & Module C Roadway Crosswalk Prerequisites

With GPS decoding and coordinate validation completed and verified:
1. **Decoder Verified:** The `DD MM:SS.ddd` DMS parser handles all valid police GPS strings with exact mathematical precision.
2. **Conflict Firewall:** The 2,146 conflict records are quarantined from automatic site snapping.
3. **Ready for Crosswalk Engine (Module C):** Validated coordinates can now be projected to Pennsylvania State Plane South (EPSG:2272) for distance-bounded topological snapping against the 82,365 Allegheny County centerline segments (`alleghenycounty_streetcenterlines202610.zip`).
