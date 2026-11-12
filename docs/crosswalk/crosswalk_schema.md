# Roadway Crosswalk Schema & Data Dictionary

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 3 — Module C  
**Date:** November 2026  
**Status:** Approved & Implemented  

---

## 1. Overview

This document specifies the exact schema, field constraints, nullability rules, and enumerations for the EDAgent roadway crosswalk dataset (`CrosswalkRecord`) and the underlying stable physical site registry (`SiteRecord`).

---

## 2. Crosswalk Record Schema (`CrosswalkRecord`)

Every crash record in the analytical universe receives exactly one `CrosswalkRecord`. This record links the crash incident to its validated physical roadway location while strictly enforcing the **One-Primary-Site Rule**.

### 2.1 Field Definitions

| Field Name | Type | Nullable | Enum / Format | Description |
|---|---|---|---|---|
| `crash_id` | Integer | No | Int64 (e.g. `2005001001`) | Unique PennDOT Crash Record Number (CRN). |
| `crash_year` | Integer | Yes | 1997–2026 | Calendar year of crash occurrence. |
| `primary_site_id` | String | Yes | `INT:...` or `SEG:...` | **Stable Project-Level Site ID**. Non-null if and only if `match_status == MATCHED`. Strictly `None` if `AMBIGUOUS` or `UNMATCHED`. |
| `site_type` | String | No | `SiteType` | Categorization of matched location: `INTERSECTION`, `SEGMENT`, or `UNMATCHED`. |
| `road_class` | String | No | `RoadClass` | Functional classification: `INTERSTATE`, `STATE_ROUTE`, `COUNTY_ROAD`, `LOCAL_STREET`, `RAMP`, `UNKNOWN`. |
| `match_method` | String | No | `MatchMethod` | Methodological stage that resolved or rejected the match: `EXACT_LRS`, `INTERSECTION_JUNCTION`, `SEGMENT_SPATIAL_SNAP`, `AMBIGUOUS_CONFLICT`, `AMBIGUOUS_MULTI_CANDIDATE`, `UNMATCHED_DISTANCE`, `UNMATCHED_MISSING`, `UNMATCHED_OUT_OF_BOUNDS`. |
| `match_status` | String | No | `MatchStatus` | Resolution status: `MATCHED`, `AMBIGUOUS`, `UNMATCHED`. |
| `match_confidence` | String | No | `MatchConfidence` | Categorical confidence level: `HIGH`, `MEDIUM`, `LOW`, `NONE`. |
| `candidate_site_count` | Integer | No | Non-negative integer | Count of potential candidate sites evaluated during matching. |
| `secondary_candidates` | List[Dict] | No | JSON array of `CandidateSite` | Audit trail of secondary or competing candidate sites (especially populated for ties). |
| `snap_distance_meters` | Float | Yes | Metric float, rounded to 2 decimals | Distance in meters from decoded crash coordinates to matched site centroid/centerline. |
| `source_reference_id` | String | Yes | E.g. `PENNDOT_RMS_...` or `AC_CENTERLINE_...` | Authoritative source reference ID of the matched roadway asset. |
| `coordinate_validation_status` | String | No | `VALID`, `WARNING`, `CONFLICT`, `INVALID`, `MISSING` | Provenance status propagated from Phase 3 Module B coordinate validation. |
| `crosswalk_version` | String | No | Semantic version (`1.0.0`) | Pipeline version generating this crosswalk record. |

---

## 3. Enumeration Specifications

### 3.1 `SiteType`
- `INTERSECTION`: Multi-roadway junction or intersection node.
- `SEGMENT`: Directional or bidirectional roadway link/corridor.
- `UNMATCHED`: No physical site assigned.

### 3.2 `RoadClass`
- `INTERSTATE`: Federal Interstate highway (e.g., I-76, I-79, I-376).
- `STATE_ROUTE`: Pennsylvania State Route (e.g., SR 28, SR 51, SR 8).
- `COUNTY_ROAD`: Allegheny County maintained roadway.
- `LOCAL_STREET`: Municipal or local public roadway.
- `RAMP`: Interchange access or egress ramp (e.g., PennDOT 8000-series routes).
- `UNKNOWN`: Unclassified roadway.

### 3.3 `MatchMethod`
- `EXACT_LRS`: Stage 1 match using official PennDOT County + Route + Segment numbers.
- `INTERSECTION_JUNCTION`: Stage 2 match using approach street names within $\le 30.48$ m catchment.
- `SEGMENT_SPATIAL_SNAP`: Stage 3 orthogonal snapping to centerline within $\le 50.0$ m with street name corroboration.
- `AMBIGUOUS_CONFLICT`: Stage 4 gating due to Police DMS vs. State Decimal coordinate discrepancy $>500$ m.
- `AMBIGUOUS_MULTI_CANDIDATE`: Stage 4 tie between two or more equidistant candidates ($\le 2.0$ m diff) with equal corroboration.
- `UNMATCHED_DISTANCE`: Stage 5 rejection because nearest roadway is $>50.0$ m or lacks attribute agreement.
- `UNMATCHED_MISSING`: Stage 5 rejection due to missing crash coordinates and absence of State Route LRS.
- `UNMATCHED_OUT_OF_BOUNDS`: Stage 5 rejection due to crash coordinates outside project/county boundaries.

### 3.4 `MatchStatus`
- `MATCHED`: Successfully resolved to exactly 1 primary site ID.
- `AMBIGUOUS`: Evidence indicates multiple conflicting sites or contradictory inputs; primary site is `None`.
- `UNMATCHED`: Insufficient physical or spatial evidence; primary site is `None`.

### 3.5 `MatchConfidence`
- `HIGH`: Definitive match (Stage 1 LRS or verified dual-approach intersection $\le 30.48$ m).
- `MEDIUM`: Strong match (single-approach intersection or segment snap $\le 25$ m).
- `LOW`: Bounded spatial snap (segment snap 25–50 m with partial token match).
- `NONE`: Ambiguous or unmatched.

---

## 4. Stable Site Record Schema (`SiteRecord`)

Entities registered in the authoritative `SiteRegistry` maintain the following schema:

| Field Name | Type | Description |
|---|---|---|
| `site_id` | String | Unique deterministic identifier (`INT:{muni}:{str1}:{str2}` or `SEG:{co}:SR{rte}:{seg}`). |
| `site_type` | String | `INTERSECTION` or `SEGMENT`. |
| `canonical_name` | String | Standardized human-readable label (e.g., `CRAFT AVE & FORBES AVE (Pittsburgh)`). |
| `municipality_code` | String | 5-digit PennDOT municipal code (e.g., `02101`). |
| `municipality_name` | String | Optional municipality name (e.g., `Pittsburgh`). |
| `road_class` | String | Classification from `RoadClass`. |
| `street_names` | List[String] | Normalized list of participating street names. |
| `centroid_lat` | Float | Decimal latitude of site centroid/midpoint. |
| `centroid_lon` | Float | Decimal longitude of site centroid/midpoint. |
| `source_reference_ids`| List[String] | Official source feature keys and reference identifiers. |
| `version` | String | Registry format version (`1.0.0`). |

---

## 5. JSON Serialization Examples

### 5.1 Resolved Intersection Match
```json
{
  "crash_id": 2005002002,
  "crash_year": 2019,
  "primary_site_id": "INT:02101:CRAFT AVE:FORBES AVE",
  "site_type": "INTERSECTION",
  "road_class": "LOCAL_STREET",
  "match_method": "INTERSECTION_JUNCTION",
  "match_status": "MATCHED",
  "match_confidence": "HIGH",
  "candidate_site_count": 1,
  "secondary_candidates": [],
  "snap_distance_meters": 2.15,
  "source_reference_id": "INT_REF_02101_001",
  "coordinate_validation_status": "VALID",
  "crosswalk_version": "1.0.0"
}
```

### 5.2 Ambiguous Coordinate Conflict Gated
```json
{
  "crash_id": 2007016949,
  "crash_year": 2021,
  "primary_site_id": null,
  "site_type": "UNMATCHED",
  "road_class": "LOCAL_STREET",
  "match_method": "AMBIGUOUS_CONFLICT",
  "match_status": "AMBIGUOUS",
  "match_confidence": "NONE",
  "candidate_site_count": 0,
  "secondary_candidates": [],
  "snap_distance_meters": null,
  "source_reference_id": null,
  "coordinate_validation_status": "CONFLICT",
  "crosswalk_version": "1.0.0"
}
```
