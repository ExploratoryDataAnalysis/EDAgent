# Phase 3 — Module A: Official Roadway Data and Source Inventory

**Project:** EDAgent Road-Safety Analytics  
**Phase:** Phase 3 — Roadway Crosswalk and Geographic Integration  
**Module:** Module A — Official Roadway Data and Source Research  
**Date:** November 2026  
**Status:** Complete / Verified Research Baseline  

---

## 1. Executive Summary & Repository Assessment

### 1.1 Context and Scope
The EDAgent road-safety analytics initiative extends exploratory data analysis into domain-specific roadway intelligence for Allegheny County, Pennsylvania. As articulated in [Project Plan v2](../../docs/EDAgent_Project_Plan_v2.pdf), the central analytical priority is to bridge police-reported historical crash data (2004–2024) with spatial roadway reference infrastructure to enable reproducible network screening, site attribution, and evidence-informed intervention modeling.

Before any roadway crosswalk, spatial snapping, or site identification can be implemented, authoritative source verification is required. This inventory documents the inspection of the EDAgent codebase, surveys the canonical application and research baseline, inventories all crash location fields, acquires official source codebooks and roadway references, validates coordinate encoding requirements, and calculates cryptographic SHA-256 checksums for all preserved source assets.

### 1.2 Repository Inspection & Architecture
The repository consists of two primary operational domains:

1. **Active Canonical Application (`EDAgent_Completed_Extension/EDAgent/`):**
   - **Backend:** FastAPI (Python 3.11+), Pydantic v2, SQLAlchemy 2 (async SQLite default / PostgreSQL compatible), Alembic migrations, in-process background job runner.
   - **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Plotly.js.
   - **Analytics Engine:** Validated catalogue of 27 statistical, distribution, and modeling tools with deterministic backend execution, strict prompt-grounding validation, and audit ledgers.
   - **API Boundaries:** Defined in [`docs/api_specification.md`](../../docs/api_specification.md) and [`docs/architecture.md`](../../docs/architecture.md). Existing generic endpoints (`/api/v1/datasets`, `/api/v1/analysis`, `/api/v1/reports`, `/api/v1/jobs`) remain unmodified. Domain roadway endpoints will be layered non-destructively in subsequent Phase 3 modules without breaking application API contracts.

2. **Road-Safety Research Baseline (`analysis/`):**
   - **Canonical Research Notebook:** [`analysis/EDA_v6.ipynb`](../../analysis/EDA_v6.ipynb) (version `6.1-targeted-corrections`), encompassing 105 total cells (44 executed code cells).
   - **Frozen Outputs:** Preserved under `analysis/outputs/` (`eda_summary/`, `spatial/`, `model_metrics/`, `model_artifacts/`, and `run_manifest.json`), reflecting the approved baseline execution from 2026-11-11 UTC.
   - **Linage & Reproducibility:** Documented in [`docs/v6_reproduction_inventory.md`](../../docs/v6_reproduction_inventory.md) and [`docs/sources_and_decisions.md`](../../docs/sources_and_decisions.md).

### 1.3 Baseline Crash Dataset Scope Lock
- **Resource Identifier:** WPRDC Resource `2c13021f-74a9-4289-a1e5-fe0472c89881` ([Allegheny County Crash Data](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/2c13021f-74a9-4289-a1e5-fe0472c89881)).
- **Temporal Horizon:** Exactly 2004 through 2024 (21 complete calendar years).
- **Scope Restriction:** The separately published 2025 WPRDC crash resource (`c6bedb17-2d23-49b1-843a-8f6b41e5e5c3`) is explicitly excluded under the Project Plan v2 decision freeze to maintain temporal integrity.
- **Physical Ingestion Checksum:** SHA-256 `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511` (116,560,683 bytes; 248,810 records; 191 columns).
- **Zero Duplication Policy:** Research code directly respects established coordinate cleaning filters and variable role definitions in `EDA_v6.ipynb`.

---

## 2. Inventory of Existing Crash Location Fields

The 2004–2024 cumulative crash dataset contains multiple spatial and roadway context fields collected by responding police officers and augmented by PennDOT linear referencing pipelines. In accordance with Section 4 of `EDA_v6.ipynb` and `analysis/outputs/eda_summary/source_missingness.csv`, the 24 location, coordinate, and roadway classification fields are inventoried below:

| Column Name | Category | Storage Type | Missing Count | Missing % | Semantic Role & Operational Description |
|---|---|---|---|---|---|
| `CRASH_CRN` | Identifier | Integer | 0 | 0.00% | Unique Crash Record Number; immutable key across all reporting tables. |
| `ROADWAY_CRN` | Identifier | Float / Int | 6,158 | 2.47% | Associated Roadway record identifier. |
| `FLAG_CRN` | Identifier | Integer | 0 | 0.00% | Companion FLAG table foreign key. |
| `_id` | Identifier | Integer | 0 | 0.00% | CKAN datastore row identifier. |
| `LATITUDE` | Coordinate (Police) | String / Text | 10,089 | 4.05% | Officer-entered GPS latitude encoded as `DD MM:SS.ddd` (Degrees Minutes:Seconds). |
| `LONGITUDE` | Coordinate (Police) | String / Text | 10,090 | 4.06% | Officer-entered GPS longitude encoded as `DD MM:SS.ddd` (positive magnitude in text; Western hemisphere). |
| `DEC_LAT` | Coordinate (State Route) | Float | 10,202 | 4.10% | PennDOT geocoded decimal latitude (WGS 84 decimal degrees, regional range 40.1–40.7°N). |
| `DEC_LONG` | Coordinate (State Route) | Float | 10,210 | 4.10% | PennDOT geocoded decimal longitude (WGS 84 decimal degrees, regional range -80.4 to -79.6°W). |
| `ROUTE` | Roadway Linear Ref | String / Text | 102,322 | 41.12% | 4-digit State Route number (e.g., `0019`, `0376`, `8001` ramps). Populated for state-maintained roads. |
| `SEGMENT` | Roadway Linear Ref | String / Text | 110,226 | 44.30% | 4-digit roadway segment number (e.g., `0010`, `0410`). Increments by 10; even/odd for divided highways. |
| `OFFSET` | Roadway Linear Ref | String / Text | 96,035 | 38.60% | Distance in feet from beginning of segment to crash site. |
| `ROAD_OWNER` | Roadway Admin | Float / Int | 6,158 | 2.47% | Jurisdiction: 1=Interstate, 2=State highway, 3=County road, 4=Local road/street, 5/6=Turnpike, 7=Private, 9=Unknown. |
| `ROADWAY_COUNTY` | Roadway Admin | Float / Int | 6,157 | 2.47% | PennDOT county code where roadway is situated (02 for Allegheny; may differ on boundary roads). |
| `CRASH_COUNTY` | Geography | Integer | 0 | 0.00% | County code where crash occurred (02 = Allegheny). |
| `DISTRICT` | Geography | Integer | 0 | 0.00% | PennDOT Engineering District (District 11 = Allegheny, Beaver, Lawrence). |
| `MUNICIPALITY` | Geography | Integer | 0 | 0.00% | 5-digit PennDOT municipality code (e.g., 02101 Baldwin Twp, 02108 McCandless, 02301 Pittsburgh). |
| `POLICE_AGCY` | Reporting Agency | Integer | 0 | 0.00% | 5-digit PennDOT reporting police agency code. |
| `STREET_NAME` | Roadway Reference | String / Text | 12,316 | 4.95% | Recorded street or roadway name (subject to spelling, abbreviation, and directional variation). |
| `LOCAL_ROAD` | Roadway Reference | String / Text | 12,418 | 4.99% | Local roadway designation/name for non-state facilities. |
| `RDWY_ORIENT` | Geometry | String / Text | 10,090 | 4.06% | Travel direction of roadway (N, S, E, W, U). |
| `RDWY_SEQ_NUM` | Sequence | Integer | 0 | 0.00% | Roadway sequence number involved in crash (e.g. 3=primary midblock; 3,4=intersection approach). |
| `ADJ_RDWY_SEQ` | Sequence | Float / Int | 35,182 | 14.14% | Adjacent roadway sequence counter. |
| `INTERSECTION` | Junction Indicator | Integer | 1 | 0.00% | Binary indicator: 1 = Intersection crash, 0 = Non-intersection. |
| `NON_INTERSECTION` | Junction Indicator | Integer | 1 | 0.00% | Binary indicator: 1 = Mid-block / non-intersection crash, 0 = Intersection. |
| `INTERSECT_TYPE` | Junction Classification | Integer | 0 | 0.00% | Geometric junction type (00=Midblock, 01=4-way, 02=T, 03=Y, 06/07=Ramp, 08=Crossover, 12=Circle, 13=Roundabout). |
| `RELATION_TO_ROAD` | Spatial Placement | Integer | 0 | 0.00% | Crash position relative to roadway (1=On roadway, 2=Shoulder, 3=Median, 4=Roadside, 5=Outside trafficway, 7=Gore). |
| `LOCATION_TYPE` | Facility Type | Integer | 0 | 0.00% | Special roadway structure (0=Standard, 1=Underpass, 2=Ramp, 3=Bridge, 4=Tunnel, 5=Toll booth, 7=Driveway/parking lot). |
| `SPEED_LIMIT` | Operational Context | Float / Int | 13,336 | 5.36% | Posted speed limit in mph (ranges 15 to 70 mph; 5.36% unrecorded). |
| `LANE_COUNT` | Roadway Profile | Float / Int | 15,007 | 6.03% | Total travel lanes (both directions undivided; single direction divided). |
| `ACCESS_CTRL` | Operational Context | Float / Int | 121,206 | 48.71% | Access control: 1=Full (freeway), 2=Partial (expressway), 3=None (uncontrolled surface street). State roads only. |
| `URBAN_RURAL` | Spatial Context | Integer | 0 | 0.00% | FHWA urban/rural classification (1=Rural, 2=Urban, 3=Small Urban). |

---

## 3. Comprehensive Master Source Registry

The structured source registry is maintained in machine-readable JSON at [`data/reference/source_registry.json`](../../data/reference/source_registry.json) and tabular CSV at [`data/reference/source_registry.csv`](../../data/reference/source_registry.csv). The table below details all investigated, verified, and preserved assets:

| Source ID | Source Name & Publisher | Official URLs | Release Date & Temporal Coverage | CRS & Format | Checksum (SHA-256) & Preserved Path | Verification Status & Limitations |
|---|---|---|---|---|---|---|
| **SRC-001** | **Allegheny County Crash Data (Cumulative 2004–2024 Extract)**<br>Publisher: WPRDC / PennDOT | Landing: [WPRDC Portal](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/2c13021f-74a9-4289-a1e5-fe0472c89881)<br>Dump: [CKAN Datastore](https://data.wprdc.org/datastore/dump/2c13021f-74a9-4289-a1e5-fe0472c89881) | Released: 2025-06-30<br>Coverage: 2004–2024 (Allegheny County) | WGS 84 / NAD 83 Geographic (EPSG:4326)<br>Format: CSV (116.56 MB) | `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511`<br>Path: `data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv` | **Verified canonical baseline** (248,810 rows, 191 columns). Excludes 2025 resource; 2016 injury standard break; exact dates suppressed. |
| **SRC-002** | **PennDOT Crash Data Dictionary (2026 Edition)**<br>Publisher: PennDOT Bureau of Maintenance and Operations | Landing: [PennDOT GIS Hub](https://gis.penndot.pa.gov/gishub/)<br>Download: [Crash_Data_Dictionary_2026.pdf](https://gis.penndot.pa.gov/gishub/crashZip/Crash_Data_Dictionary_2026.pdf) | Released: 2026-01-01<br>Coverage: Statewide PA historical–2026 | N/A (Technical Codebook)<br>Format: PDF (56 pages, 1.18 MB) | `a2836c65883e04ab7d1aae604aec5da767f619b81466405cccb14d28236fc354`<br>Path: `data/reference/codebooks/Crash_Data_Dictionary_2026.pdf` | **Verified authoritative source**. Authoritatively establishes `LATITUDE` / `LONGITUDE` format as `DD MM:SS.ddd` and `DEC_LAT` / `DEC_LONG` as decimal degrees `99.9999`. |
| **SRC-003** | **PennDOT Crash Database Primer (April 2015 Edition)**<br>Publisher: PennDOT Bureau of Highway Safety / WPRDC | Landing: [WPRDC Resource](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/c884d6da-588d-45ec-b029-8aaec8018500)<br>Download: [database-primer-4-15.pdf](https://data.wprdc.org/dataset/3130f583-9499-472b-bb5a-f63a6ff6059a/resource/c884d6da-588d-45ec-b029-8aaec8018500/download/database-primer-4-15.pdf) | Released: 2015-04-15<br>Coverage: Commonwealth of PA / Allegheny County | N/A (Database Primer)<br>Format: PDF (13 pages, 424.6 KB) | `df15ff45bedb73f8cfe87f12f2b3bb131732b8a454b73282a1c60befebceb658`<br>Path: `data/reference/codebooks/database-primer-4-15.pdf` | **Verified authoritative source**. Establishes state route segmenting, 100-ft intersection catchment convention, and local road compilation constraints. |
| **SRC-004** | **PennDOT Crash Database Primer (Current / 2026 Edition)**<br>Publisher: PennDOT GIS Hub | Landing: [PennDOT GIS Hub](https://gis.penndot.pa.gov/gishub/)<br>Download: [crash_database_primer.pdf](https://gis.penndot.pa.gov/gishub/crashZip/crash_database_primer.pdf) | Released: Circa 2024–2026<br>Coverage: Commonwealth of PA | N/A (Database Primer)<br>Format: PDF (12 pages, 600.1 KB) | `f008858c55ec1ff8f005942abd683d1de47e9ab04d3d21afd74a1dad94da748c`<br>Path: `data/reference/codebooks/crash_database_primer_2026.pdf` | **Verified authoritative source**. Updated guidance confirming local road coordinate improvements post-2008. |
| **SRC-005** | **PennDOT Municipality Codes Table (Allegheny County)**<br>Publisher: PennDOT / WPRDC | Landing: [WPRDC Resource](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/fb81a55f-c560-4541-9ad4-7ea7c41f79e7)<br>Download: [municipalitycodes.csv](https://data.wprdc.org/dataset/3130f583-9499-472b-bb5a-f63a6ff6059a/resource/fb81a55f-c560-4541-9ad4-7ea7c41f79e7/download/municipalitycodes.csv) | Released: 2016-03-29<br>Coverage: Allegheny County (130 municipalities) | N/A (Codebook CSV)<br>Format: CSV (131 rows, 3.31 KB) | `8490cb5d4c61ba3fa727f392a2fac2240d1a2509d15f11d8ed550f1562ae2824`<br>Path: `data/reference/codebooks/municipalitycodes.csv` | **Verified authoritative lookup**. Maps 5-digit PennDOT municipality code directly to legal municipal names. |
| **SRC-006** | **PennDOT Police Agency Codes Table (Allegheny County)**<br>Publisher: PennDOT / WPRDC | Landing: [WPRDC Resource](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/057dc1b4-a720-4593-8a0c-02f302b8b817)<br>Download: [policeagencycodes.csv](https://data.wprdc.org/dataset/3130f583-9499-472b-bb5a-f63a6ff6059a/resource/057dc1b4-a720-4593-8a0c-02f302b8b817/download/policeagencycodes.csv) | Released: 2016-03-29<br>Coverage: Allegheny County law enforcement agencies | N/A (Codebook CSV)<br>Format: CSV (131 rows, 3.29 KB) | `80f245bc4efa78c74ba89c9dcc51c47421e00dd3d07d943b7e5b379e900f436a`<br>Path: `data/reference/codebooks/policeagencycodes.csv` | **Verified authoritative lookup**. Maps reporting police agency numeric code to department name. |
| **SRC-007** | **Allegheny County Addressing Street Centerlines**<br>Publisher: Allegheny County GIS Group / PASDA | Landing: [PASDA Dataset 1224](https://www.pasda.psu.edu/uci/DataSummary.aspx?dataset=1224)<br>Download: [alleghenycounty_streetcenterlines202610.zip](https://data.wprdc.org/dataset/34f6668d-130d-4e10-b49b-598c43b83d27/resource/736ee220-d51d-4e3b-874f-10eabb3c4f1b/download/alleghenycounty_streetcenterlines202610.zip) | Released: 2026-10 (Continuous maintenance)<br>Coverage: Allegheny County (82,365 features) | State Plane PA South ftUS (EPSG:2272)<br>Format: Shapefile Archive (19.27 MB) | `f204219e0230f73514718b58c2ba02d1cdef4c4d1a33faca87e2b974b0463502`<br>Path: `data/reference/street_centerlines/alleghenycounty_streetcenterlines202610.zip` | **Verified authoritative reference**. Full county network coverage; contains street names, municipal borders, node topology, and FCC road classes. Reprojection required. |
| **SRC-008** | **Allegheny County Addressing Data Model Specification**<br>Publisher: Allegheny County GIS Group | Landing: [WPRDC Package](https://data.wprdc.org/dataset/allegheny-county-addressing-data-model)<br>Download: [addressing_data_model.pdf](https://www.arcgis.com/sharing/rest/content/items/ffb67d3d8b814b54b299a39de81d03b0/data) | Released: 2026-06-16<br>Coverage: Allegheny County | N/A (Technical Data Model)<br>Format: PDF (27 pages, 811.4 KB) | `bb7ad24567d16f1f313f7a136f8a315080cca5bc20fee1a83d8d1425fa55c6c9`<br>Path: `data/reference/street_centerlines/addressing_data_model.pdf` | **Verified authoritative specification**. Defines attributes for street dictionary, centerlines, address ranges, and unmaintained fields (SPEED). |
| **SRC-009** | **U.S. Census Bureau 2024 County Boundary 500k**<br>Publisher: U.S. Census Bureau | Landing: [Census TIGER/Cartographic](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html)<br>Download: [cb_2024_us_county_500k.zip](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip) | Released: 2024<br>Coverage: National (GEOID 42003 screening) | NAD 83 Geographic (EPSG:4269)<br>Format: Shapefile Archive (11.62 MB) | `da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1`<br>Path: `data/reference/municipal_boundaries/cb_2024_us_county_500k.zip` | **Verified screening polygon source**. Matches exact hash from reproduction baseline; screens crash points within legal county boundaries. |
| **SRC-010** | **PennDOT Roadway Management System (RMSSEG) State Roads**<br>Publisher: PennDOT Bureau of Planning and Research | Landing: [PennDOT PennShare Open Data](https://data-pennshare.opendata.arcgis.com/datasets/pennshare::pennsylvania-state-roads)<br>REST Service: [PASDA PennDOT MapServer](https://mapservices.pasda.psu.edu/server/rest/services/pasda/PennDOT/MapServer/0) | Annual / Continuous Updates<br>Coverage: State-maintained routes statewide | PA State Plane / WGS 84 (EPSG:2272 / EPSG:4326)<br>Format: Esri REST / GeoJSON | Dynamic service (hash generated per snapshot extract) | **Verified compatible reference**. Authoritative segment length, route number, and administrative jurisdiction for state roads. Excludes local municipal roads. |
| **SRC-011** | **PennDOT Publication 153 (Police Officers Crash Report Manual)**<br>Publisher: PennDOT / PSP / PCPA | Historical: `https://www.penndot.pa.gov/TravelInPA/Safety/Documents/Pub153.pdf` | Periodically Revised (2012, 2016, 2020)<br>Coverage: Commonwealth of PA | N/A (Police Training Manual)<br>Format: PDF | Direct URL blocked by PA.gov search portal redirect | **Partially verified / Open documentation blocker**. Direct PDF download blocked; field constraints corroborated via SRC-002 (Data Dictionary 2026). |

---

## 4. Preserved Physical Asset Verification

All source files are stored in `data/reference/`, completely separated from transformed data and frozen outputs. The table below provides the verification record:

```
data/
└── reference/
    ├── codebooks/
    │   ├── Crash_Data_Dictionary_2026.pdf      (1,183,616 bytes | SHA-256: a2836c65883e04ab7d1aae604aec5da767f619b81466405cccb14d28236fc354)
    │   ├── crash_database_primer_2026.pdf      (  600,170 bytes | SHA-256: f008858c55ec1ff8f005942abd683d1de47e9ab04d3d21afd74a1dad94da748c)
    │   ├── database-primer-4-15.pdf            (  424,666 bytes | SHA-256: df15ff45bedb73f8cfe87f12f2b3bb131732b8a454b73282a1c60befebceb658)
    │   ├── municipalitycodes.csv               (    3,318 bytes | SHA-256: 8490cb5d4c61ba3fa727f392a2fac2240d1a2509d15f11d8ed550f1562ae2824)
    │   └── policeagencycodes.csv               (    3,295 bytes | SHA-256: 80f245bc4efa78c74ba89c9dcc51c47421e00dd3d07d943b7e5b379e900f436a)
    ├── coordinates/
    │   └── police_gps_format.json              (      993 bytes | SHA-256: 8886c45e8105556569c942326e71f444eb6c716f3102fca721e5dc8a6b0d62e7)
    ├── metadata/
    │   ├── wprdc_centerline_package_metadata.json (14,441 bytes | SHA-256: 45baf2be5dd04ca9a1b86e3a3a6f93408f55d61b0131b5b9fea07af7b723968c)
    │   └── wprdc_crash_package_metadata.json   (   32,234 bytes | SHA-256: 77c1eb871bf7ea682737d2649591b87b378fb9839e39fc367c8f0252212f45c8)
    ├── municipal_boundaries/
    │   └── cb_2024_us_county_500k.zip          (11,626,066 bytes | SHA-256: da4051717caec55c75e3748c3608c2a3dbde8d1ff401bbaf4f952e3c3fb63ef1)
    ├── street_centerlines/
    │   ├── addressing_data_model.pdf           (  811,455 bytes | SHA-256: bb7ad24567d16f1f313f7a136f8a315080cca5bc20fee1a83d8d1425fa55c6c9)
    │   └── alleghenycounty_streetcenterlines202610.zip (19,275,631 bytes | SHA-256: f204219e0230f73514718b58c2ba02d1cdef4c4d1a33faca87e2b974b0463502)
    ├── source_registry.json                    (   16,246 bytes | SHA-256: ae2d0fc54ef2fa6090d17eed4316c9585fcb0dd0745da5e6dd6300b8990442d3)
    └── source_registry.csv                     (   11,358 bytes | SHA-256: 323769b55ed64dad3d86104b7d2ae3c7d838c500a87e1356151f1d5245554d8c)
```

---

## 5. Next Steps for Crosswalk Development
With the official sources verified and preserved:
1. **Module B (Spatial Matching & Crosswalk Engine):** Deploy topological snapping against the 82,365 preserved centerline segments (`alleghenycounty_streetcenterlines202610.zip`) with reprojection to EPSG:2272.
2. **Coordinate Disagreement Resolution:** Programmatically audit the 2,146 candidate discrepancies using route/segment/offset ground truth.
3. **Crosswalk Artifact Generation:** Construct `crosswalk_crash_site.csv` implementing primary site attribution and confidence tagging.
