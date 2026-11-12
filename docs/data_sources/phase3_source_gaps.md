# Phase 3 — Module A: Source Gaps, Coordinate Discrepancies & Research Blockers

> Review update: the statements below that no historical centerline archives
> exist and that the current Pub 153 cannot be obtained are superseded by the
> [source review](../phase3_phase4_review_status.md#source-review-2026-11-12).
> Historical coverage and older police manual versions remain unverified.

**Project:** EDAgent Road-Safety Analytics  
**Phase:** Phase 3 — Roadway Crosswalk and Geographic Integration  
**Module:** Module A — Official Roadway Data and Source Research  
**Document:** Source Gaps, Discrepancies, Blockers, and Unsupported Assumptions  
**Reference:** Project Plan v2 (§12–15), EDA v6 Research Baseline  

---

## 1. Executive Summary

A defensible roadway crosswalk cannot be built on optimistic assumptions. When linking 248,810 police-reported crash records from 2004–2024 to spatial roadway geometry, substantial documentation gaps, historical reporting discrepancies, and geographic misalignments emerge. 

This document provides a rigorous, transparent inventory of all identified source gaps, analyzes empirical coordinate conflicts, documents access blockers, articulates unsupported assumptions that must not be made, and specifies gating prerequisites for Phase 3 Module B (Crash-Site Matching and Crosswalk Engine).

---

## 2. Empirical Coordinate Disagreements (>500m Conflict Analysis)

### 2.1 The Coordinate Conflict Empirical Baseline
In the canonical EDA v6 baseline ([`analysis/outputs/spatial/candidate_coordinate_comparison_summary.csv`](../../analysis/outputs/spatial/candidate_coordinate_comparison_summary.csv)), candidate police DMS coordinates were converted and compared against PennDOT state-route decimal coordinates across the 248,810 cumulative records.

- **Total Comparable Coordinate Pairs:** 238,517 pairs.
- **Median Difference:** 4.16 meters.
- **95th Percentile Difference:** 36.91 meters.
- **99th Percentile Difference:** 398.91 meters.
- **Candidate Pairs with Disagreement > 500 Meters:** **2,146 pairs** (0.900% of comparable records).
- **Maximum Observed Difference:** **48,466.70 meters (48.47 km)**.

### 2.2 Forensic Analysis of Severe Discrepancies
Inspection of [`analysis/outputs/spatial/candidate_coordinate_disagreements_review.csv`](../../analysis/outputs/spatial/candidate_coordinate_disagreements_review.csv) reveals distinct failure modes:

| Crash CRN | Year | Candidate Police Lat/Lon | State Decimal Lat/Lon | Discrepancy (m) | Probable Failure Mechanism |
|---|---|---|---|---|---|
| `2007016949` | 2007 | `40.3914°N, -79.1793°W` | `40.4355°N, -79.7488°W` | 48,466.7 m | **Longitude degree/minute typographical error.** Police coordinates place crash in Westmoreland County near Derry, while state decimal coordinates place it on SR 0022 in Monroeville. |
| `2005006334` | 2004 | `40.4933°N, -79.9006°W` | `40.7848°N, -79.5814°W` | 42,142.9 m | **State Route segment reset across county line.** State coordinates place incident in Armstrong County, outside Allegheny County boundaries. |
| `2005186033` | 2005 | `40.4569°N, -79.7587°W` | `40.4362°N, -80.2493°W` | 41,580.1 m | **Hemisphere / Transposition Error.** Crash occurred in eastern Allegheny County (Penn Hills/Plum), but state decimal coordinates place it west of Pittsburgh International Airport. |
| `2007074747` | 2007 | `40.3725°N, -80.2261°W` | `40.3350°N, -79.7795°W` | 38,071.8 m | **Route number ambiguity.** Cross-county confusion between SR 0051 and local connectors. |
| `2018118761` | 2018 | `40.4725°N, -80.2810°W` | `40.4297°N, -79.8636°W` | 35,639.0 m | **Station / Dispatch Coordinates vs Incident Scene.** Police GPS reflects police station headquarters or dispatch center rather than the physical collision site. |

### 2.3 Operational Decision Policy for Module B
Neither source may be treated as automatically infallible:
1. **Rule of Priority:** On verified State Routes where `ROUTE`, `SEGMENT`, and `OFFSET` match valid physical highway segments, `DEC_LAT`/`DEC_LONG` serve as primary reference because they are anchored to the engineering line network.
2. **Conflict Gating:** Any crash with paired distance $>500$ meters must be assigned `ASSIGNMENT_STATUS = "ambiguous"` and `COORDINATE_CONFLICT = True`. Such records must not be arbitrarily forced onto either roadway segment without manual or algorithmic verification.

---

## 3. Local Road Geocoding Gaps & Temporal Discontinuities

### 3.1 Historical Coverage Gap (2004–2007)
As documented in [`analysis/outputs/spatial/coordinate_coverage_by_year.csv`](../../analysis/outputs/spatial/coordinate_coverage_by_year.csv) and corroborated by the PennDOT Database Primer (2026, Page 9):
- In early crash reporting years (2004–2006), PennDOT did not systematically geocode local municipal roadway crashes.
- **Unavailable / Ambiguous Coordinates by Year:**
  - **2004:** 2,983 crashes (23.8% of yearly total)
  - **2005:** 2,597 crashes (21.3% of yearly total)
  - **2006:** 2,337 crashes (19.9% of yearly total)
  - **2007:** 699 crashes (5.7% of yearly total)
  - **2008:** 308 crashes (2.6% of yearly total)
  - **2015–2024:** Averaging fewer than 35 unavailable records per year (<0.3%).
- **Impact on Analytics:** Historical trend analysis on local municipal roads between 2004 and 2007 will suffer from artificial spatial undercounting unless restricted to state routes or explicitly adjusted for geocoding coverage.

### 3.2 Absence of Linear Referencing on Local Roads
- State roads possess structured LRS keys: County (`02`), 4-digit Route, 4-digit Segment, and 4-digit Offset.
- Local municipal roads contain **no route, no segment, and no offset**. Location depends entirely on `MUNICIPALITY` code and text strings in `STREET_NAME` and `LOCAL_ROAD`.
- Street name text suffers from widespread orthographic variation:
  - Misspellings (e.g. `FORBES AVE`, `FORBES AV`, `FORBS AVE`).
  - Directional inconsistency (e.g. `MAIN ST`, `E MAIN ST`, `EAST MAIN ST`).
  - Redundant suffixes (e.g. `PENN AVENUE AVE`, `MAIN STREET ST`).
  - Dual naming (e.g. legal municipal name vs colloquial name vs historical township route number).

---

## 4. Roadway Reference Data & Centerline Gaps

### 4.1 Temporal Misalignment of Centerline Geometry
- **Preserved Centerline Asset:** Allegheny County Street Centerlines (`alleghenycounty_streetcenterlines202610.zip`), October 2026 snapshot.
- **Temporal Gap:** The reference network reflects the physical roadway alignment, newly constructed developments, and traffic geometries of **late 2026**.
- **Historical Blind Spots:**
  - Roadways realigned, rerouted, or decommissioned between 2004 and 2025 (e.g., Mon-Fayette Expressway SR 0043 extensions, Southern Beltway PA 576 construction, local street vacations).
  - Crashes occurring on historical alignments will fail snap distance thresholds or snap erroneously to adjacent parallel modern roadways.
  - No authoritative 2004–2023 annual historical centerline archives are publicly maintained by Allegheny County.

### 4.2 Coordinate Reference System Discrepancy
- Crash dataset coordinates are provided in **WGS 84 / NAD 83 Geographic Coordinates** (decimal degrees or DMS; EPSG:4326 / EPSG:4269).
- Allegheny County Street Centerlines are projected in **NAD 1983 StatePlane Pennsylvania South FIPS 3702 Feet (EPSG:2272)**.
- **Transformation Requirement:** Direct spatial joining or distance calculations without rigorous CRS reprojection will cause severe dimensional corruption. The crosswalk engine in Module B must project geometries to EPSG:2272 for distance calculations in survey feet and back-project to EPSG:4326 for web mapping.

### 4.3 Unmaintained Attributes in Reference Datasets
- As officially documented in the *Allegheny County Addressing Data Model* (Page 7), the `SPEED` attribute in the county centerline database is **not maintained** and was imported from legacy legacy sources.
- In the crash dataset, `SPEED_LIMIT` has 13,336 missing records (5.36%).
- Centerline speed attributes cannot be used as ground truth for road design or regulatory speed limit analysis.

---

## 5. Traffic Exposure & Network Panel Gaps (The AADT Dilemma)

### 5.1 Lack of Comprehensive Exposure Data
- PennDOT TIRe (Traffic Information Repository) and RMS traffic count layers provide Annual Average Daily Traffic (AADT) for State Routes and select Federal-Aid highways.
- **Local Road Coverage:** Local municipal roads and residential streets have zero systematic AADT coverage.
- **Temporal Mismatch:** AADT is not collected annually at every count station; traffic counts follow 3- to 5-year collection cycles.

### 5.2 Methodological Gating for Count Models
- In accordance with Project Plan v2 (§8, §18), a true crash frequency model (Poisson / Negative Binomial) requires:
  1. A zero-inclusive panel of eligible roadway segments (including segments that experienced **zero crashes** over the observation window).
  2. Defensible traffic exposure offsets ($E_{s,t} = \text{AADT}_{s,t} \times \text{Length}_s \times \text{Days}_t$).
- **Gating Decision:** Because local road AADT is missing and cannot be fabricated without violating scientific integrity, site ranking on local roads must be presented as **historical crash concentration**, not per-vehicle crash rate or causal risk.

---

## 6. Official Documentation Access Blockers

### 6.1 PennDOT Publication 153 (Police Officers Crash Report Manual)
- **Status:** **Partially Blocked / Access Restricted.**
- **Details:** The official PennDOT direct download endpoint (`https://www.penndot.pa.gov/TravelInPA/Safety/Documents/Pub153.pdf`) is currently intercepted by a statewide web server rewrite rule redirecting automated clients to `https://www.pa.gov/search`.
- **Mitigation & Corroboration:**
  - Field definitions, lengths, types, and constraints were corroborated directly from the official **PennDOT Crash Data Dictionary (2026 Edition)** downloaded from PennDOT GIS Hub (`Crash_Data_Dictionary_2026.pdf`).
  - Officer data entry guidelines (Degrees, Minutes, Seconds) were confirmed through federal NHTSA and state police documentation.
  - The inability to archive a virgin byte copy of Pub 153 is documented as an open blocker, but does not prevent exact mathematical modeling of the `DD MM:SS.ddd` encoding.

---

## 7. Unsupported Assumptions Explicitly Prohibited

To preserve scientific rigor, the following assumptions are **strictly prohibited** in all subsequent modules:

1. **Assumption:** *A field named `LATITUDE` contains decimal degrees.*  
   **Reality:** Disproven. Official PennDOT documentation proves `LATITUDE` is text formatted as `DD MM:SS.ddd`.
2. **Assumption:** *Police GPS coordinates and State Route decimal coordinates are interchangeable.*  
   **Reality:** Disproven. 2,146 records exhibit discrepancies $>500$ meters, with differences up to 48.47 km.
3. **Assumption:** *The 2026 centerline network accurately represents roadways in 2004.*  
   **Reality:** Unsupported. Highway construction, re-alignments, and development have altered network topology over the 21-year period.
4. **Assumption:** *All crashes can be precisely pinned to an exact roadway segment.*  
   **Reality:** Unsupported. Non-geocoded historical local road crashes and ambiguous intersections must be categorized as `unmatched` or `ambiguous`.
5. **Assumption:** *A roadway with high raw crash counts is inherently more dangerous than a roadway with few crashes.*  
   **Reality:** False. Raw counts reflect traffic exposure and roadway volume; safety screening must explicitly distinguish between concentration and exposure-adjusted risk.
6. **Assumption:** *Crash Modification Factors (CMFs) from national clearinghouses can be multiplied together or applied generically to local sites.*  
   **Reality:** Prohibited by Project Plan v2 (§20). CMFs are facility- and crash-type specific, and non-causal scenario calculators must disclose all confidence boundaries.

---

## 8. Recommended Next Module: Phase 3 Module B

### Recommended Scope: Crash-Site Matching and Crosswalk Engine
The immediate next stage is to construct the reproducible crosswalk engine that implements:
1. **Topological snapping:** Spatial projection of crash points to EPSG:2272 and nearest-feature matching against `alleghenycounty_streetcenterlines202610.zip` with strict distance cutoffs ($\le 30$ meters for intersections; $\le 50$ meters for midblock segments).
2. **Dual-system reconciliation:** Prioritizing LRS ground truth on State Routes while using normalized street name matching on local roads.
3. **Conflict flagging:** Explicitly isolating the 2,146 coordinate conflict records into an audited exception table.
4. **Stable Site ID Generation:** Generating immutable `SITE_ID` keys separating segments from intersections.
