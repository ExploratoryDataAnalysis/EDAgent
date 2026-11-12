# Road-Site Identification and Crosswalk Specification

**Project:** EDAgent — Road-Safety Analytics  
**Version:** 1.0.0  
**Phase:** Phase 3 — Module C  
**Date:** November 2026  
**Status:** Approved & Verified  

---

## 1. Executive Summary

This specification defines the methodology, data structures, and deterministic algorithms used to establish a stable physical roadway crosswalk between crash incidents and physical road infrastructure in Allegheny County, Pennsylvania.

Historically, safety analytics fail or produce spurious hotspot clusters when crash records are joined loosely to the nearest geometric line feature. This implementation establishes a rigorous, transparent, and reproducible 5-stage matching pipeline grounded in official PennDOT Linear Referencing System (LRS) standards, Allegheny County Street Centerline attributes, and USPS Publication 28 address formatting.

### Key Architectural Invariants
1. **One-Primary-Site Rule**: Every crash record is assigned at most **one primary site ID** (`INT:...` or `SEG:...`). When resolution is ambiguous or evidence is insufficient, `primary_site_id` is strictly `None`. Crashes are never double-counted in primary site-level safety analyses.
2. **Order-Invariance & Determinism**: Intersection and segment identifiers depend entirely on canonical semantic properties (municipality code, alphabetically sorted approach streets, official state route and segment numbers) and do not vary based on dataset row order, platform, or execution run.
3. **Transparent Ambiguity Gating**: Coordinate conflicts exceeding 500 meters (such as the 2,146 documented baseline discrepancy pairs) and equidistant candidate ties are explicitly gated as `AMBIGUOUS`, retaining secondary candidates for auditability.
4. **No Synthetic Data**: Identifiers and references are derived exclusively from verified government sources (PennDOT Crash Data Dictionary 2026, PennDOT Database Primer, Allegheny County GIS Addressing Data Model).

---

## 2. Identifier Architecture

Sites are categorized into two primary physical roadway types: **Intersections** and **Road Segments**.

### 2.1 Intersection Sites (`INT:...`)

An intersection is a physical junction where two or more public roadways converge.

#### Semantic Identifier Format
```text
INT:{municipality_code}:{STREET_1}:{STREET_2}[:{STREET_3}...]
```
- **Municipality Code**: 5-digit PennDOT municipal code (e.g. `02101` for Pittsburgh, `02113` for Penn Hills).
- **Street Names**: Standardized via USPS Pub 28, converted to uppercase, stripped of punctuation, and sorted in ascending alphabetical order.

#### Example
A crash occurring at Forbes Avenue and Craft Avenue in Pittsburgh (`02101`) generates:
```text
INT:02101:CRAFT AVE:FORBES AVE
```
Because approach streets are sorted alphabetically, entering `FORBES AVE & CRAFT AVE` or `CRAFT AVE & FORBES AVE` produces the exact same identifier.

#### Catchment Footprint
- **Default Catchment Radius**: 30.48 meters (100 feet), aligned with standard traffic engineering junction impact zones and PennDOT intersection reporting thresholds.

### 2.2 Road Segment Sites (`SEG:...`)

Road segments represent contiguous directional or bidirectional links of a roadway between physical intersections or official reference markers.

#### A. PennDOT State Route Segments
Governed by PennDOT's Roadway Management System (RMS) Linear Referencing System:
```text
SEG:{county_code}:SR{route_4}:{segment_4}
```
- **County Code**: 2-digit zero-padded FIPS/PennDOT code (`02` for Allegheny County).
- **Route Number**: 4-digit zero-padded route number (e.g., `SR 28` $\to$ `0028`, `I-376` $\to$ `0376`).
- **Segment Number**: 4-digit zero-padded segment marker (e.g., `0010`, `0020`, `0040`).
- **PennDOT Directional Convention**:
  - *Divided Highways*: Even segment numbers (`0010`, `0020`, `0030`) represent Northbound or Eastbound travel; odd segment numbers (`0011`, `0021`, `0031`) represent Southbound or Westbound travel.
  - *Undivided Highways*: Even segment numbers represent both travel directions.

*Example:* `SEG:02:SR0022:0040`

#### B. Allegheny County Centerline Segments
For county and municipal roadways indexed in Allegheny County's GIS Centerline repository:
```text
SEG:AC:{feature_key}
```
- **Feature Key**: Unique roadway centerline identifier (e.g., `RCL100234`).

*Example:* `SEG:AC:RCL100234`

#### C. Local Municipal Road Segments
For non-state local roads referenced by municipal street name and block number:
```text
SEG:{municipality_code}:{STREET_NAME}:{block_or_id}
```

*Example:* `SEG:02101:FIFTH AVE:0100`

---

## 3. Staged Matching Pipeline

Matching is executed through five deterministic stages. Evaluation terminates at the earliest decisive stage.

```mermaid
flowchart TD
    Start([Crash Record Input]) --> CoordGate{Coordinate Quality Gate?}
    CoordGate -- Conflict > 500m --> Stage4A[Stage 4A: AMBIGUOUS_CONFLICT<br/>primary_site_id = None]
    CoordGate -- Out of Bounds --> Stage5C[Stage 5C: UNMATCHED_OUT_OF_BOUNDS<br/>primary_site_id = None]
    CoordGate -- Valid / Missing --> Stage1{Stage 1: Valid PennDOT LRS?<br/>ROUTE + SEGMENT}
    
    Stage1 -- Found in Registry --> MatchLRS[MATCHED: EXACT_LRS<br/>Confidence: HIGH]
    Stage1 -- No LRS --> CheckCoords{Coordinates Available?}
    
    CheckCoords -- No --> Stage5B[Stage 5B: UNMATCHED_MISSING<br/>primary_site_id = None]
    CheckCoords -- Yes --> Stage2{Stage 2: Intersection?<br/>INTERSECTION=1 or Multi-Street}
    
    Stage2 -- Approach match within 30.48m --> MatchInt[MATCHED: INTERSECTION_JUNCTION<br/>Confidence: HIGH / MEDIUM]
    Stage2 -- No / Midblock --> Stage3{Stage 3: Segment Snap?<br/>Distance <= 50m & Name Agreement}
    
    Stage3 -- Single Best Candidate --> MatchSeg[MATCHED: SEGMENT_SPATIAL_SNAP<br/>Confidence: MEDIUM / LOW]
    Stage3 -- Equidistant Multi-Candidate Tie --> Stage4B[Stage 4B: AMBIGUOUS_MULTI_CANDIDATE<br/>primary_site_id = None]
    Stage3 -- Distance > 50m or No Name Match --> Stage5A[Stage 5A: UNMATCHED_DISTANCE<br/>primary_site_id = None]
```

### Stage 1: Exact Reference-Identifier Match (`EXACT_LRS`)
- **Trigger**: Crash record contains valid `ROUTE` and `SEGMENT` fields.
- **Action**: Look up `(county, route_4, segment_4)` directly in the LRS index.
- **Corroboration**: If coordinates are available, validates proximity within segment corridor (allowance $\le 250$ m). If coordinates are missing, exact LRS is accepted because police mile-marker reference is official legal evidence.
- **Confidence**: `HIGH`.

### Stage 2: Validated Intersection Match (`INTERSECTION_JUNCTION`)
- **Trigger**: `INTERSECTION == 1`, `INTERSECT_TYPE > 0`, or composite street names (`FORBES AVE & CRAFT AVE`).
- **Action**:
  1. Parse approach streets and query municipality intersection index.
  2. Perform spatial radius check ($\le 30.48$ m = 100 ft).
  3. Corroborate street names against intersection approach inventory.
- **Confidence**: `HIGH` ($\le 30.48$ m with dual approach agreement), `MEDIUM` ($\le 50$ m or single approach agreement).

### Stage 3: Validated Road-Segment Spatial Match (`SEGMENT_SPATIAL_SNAP`)
- **Trigger**: Midblock crashes with valid decoded coordinates.
- **Action**:
  1. Retrieve registered segment centerlines within 50.0 meters.
  2. Compute orthogonal projection distance from crash point to 2D line segment.
  3. Filter candidates by name or route corroboration (Jaccard token score $\ge 0.5$).
- **Confidence**: `MEDIUM` (distance $\le 25$ m with corroborating name), `LOW` (distance 25 m to 50 m with corroborating name).

### Stage 4: Ambiguous Classification (`AMBIGUOUS_CONFLICT` / `AMBIGUOUS_MULTI_CANDIDATE`)
- **4A (`AMBIGUOUS_CONFLICT`)**: Police DMS coordinates and State Decimal coordinates disagree by $>500$ meters.
- **4B (`AMBIGUOUS_MULTI_CANDIDATE`)**: Multiple roadway candidates are within 2.0 meters of each other with identical corroboration scores (e.g., divided carriageways or overlapping ramp segments).
- **Outcome**: `primary_site_id = None`, `match_status = MatchStatus.AMBIGUOUS`. Tied candidates preserved in `secondary_candidates`.

### Stage 5: Unmatched Classification
- **5A (`UNMATCHED_DISTANCE`)**: Nearest registered roadway is $>50.0$ meters away, or nearby candidates fail attribute corroboration.
- **5B (`UNMATCHED_MISSING`)**: Coordinates are missing and no State Route LRS identifiers exist.
- **5C (`UNMATCHED_OUT_OF_BOUNDS`)**: Coordinates fall outside project/county boundaries.
- **Outcome**: `primary_site_id = None`, `match_status = MatchStatus.UNMATCHED`.

---

## 4. Confidence Tier Definitions

Confidence tiers represent categorical evidence strength:

| Confidence Tier | Description | Typical Conditions |
|---|---|---|
| `HIGH` | Definitive reference match | Official PennDOT State Route + Segment, or intersection match within 30.48 m with multi-approach street verification. |
| `MEDIUM` | Validated spatial snap with strong corroboration | Intersection match within 30–50 m with approach match; or midblock segment snap $\le 25$ m with exact street name match. |
| `LOW` | Distance-bounded spatial snap with partial corroboration | Segment snap 25–50 m with token-level street corroboration. |
| `NONE` | Unresolved, ambiguous, or rejected | Coordinate conflict >500m, multi-candidate tie, missing data, or distance >50m. |

---

## 5. Verification & Acceptance Summary

The crosswalk implementation was verified using the pytest suite across 67 test cases:
- Normalization: 13 tests passed.
- Stable Site Identification: 14 tests passed.
- Crash Site Staged Matching: 9 tests passed.
- One-Primary-Site Invariant: 100% verified across 150 diverse test records.
- Total Suite: **67 passed in 0.40 seconds**.
