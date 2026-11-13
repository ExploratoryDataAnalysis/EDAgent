# Phase 3 — Module A: Roadway Data Dictionary & Field Specifications

> **Superseded scope:** This report records earlier work and decisions. [Project Plan v3](../EDAgent_Project_Plan_v3.pdf) and the [v3 roadmap](../implementation_plan.md#v3-transition-and-roadmap) govern release scope: site-level historical screening, frequency/EB modelling and real-site treatment estimates are out of scope; geographic matches are diagnostic, with zero accepted primary assignments. Earlier claims of approval, mandatory pathways or pending release describe historical proposals, not current authorization.

**Project:** EDAgent Road-Safety Analytics  
**Phase:** Phase 3 — Roadway Crosswalk and Geographic Integration  
**Module:** Module A — Official Roadway Data and Source Research  
**Document:** Roadway Data Dictionary & Coordinate Encoding Specification  
**Authority:** PennDOT Crash Data Dictionary (2026), PennDOT Database Primer (4-15 & 2026), Allegheny County Addressing Data Model  

---

## 1. Overview & Data Architecture

This data dictionary formally specifies all spatial, coordinate, roadway, and intersection fields in the Allegheny County crash data repository. It resolves ambiguous field naming conventions, documents official encoding standards, provides enumerated codebook definitions, and establishes the schema contract for the Phase 3 crash-site crosswalk.

In Pennsylvania crash reporting, records combine two distinct location systems:
1. **Linear Referencing System (LRS):** PennDOT Roadway Management System (RMS) referencing based on `COUNTY`, `ROUTE`, `SEGMENT`, and `OFFSET`, which applies strictly to state-maintained highways.
2. **Geographic Coordinates (GPS & GIS):** Point-based spatial referencing including officer-collected GPS coordinates (`LATITUDE`, `LONGITUDE`) and RMS-geocoded coordinates (`DEC_LAT`, `DEC_LONG`).

---

## 2. Coordinate Encodings & Mathematical Transformations

### 2.1 Police GPS Coordinates (`LATITUDE`, `LONGITUDE`)

> [!IMPORTANT]
> **Authoritative Specification:** Contrary to common initial assumptions that fields labeled `LATITUDE` and `LONGITUDE` contain decimal degrees, the **PennDOT Crash Data Dictionary (2026 Edition, Page 4)** explicitly defines:
> - `LATITUDE`: *"GPS Latitude determined by PennDOT"*, Type: `TEXT`, Length: `12`, Constraints: `DD MM:SS.ddd`
> - `LONGITUDE`: *"GPS Longitude determined by PennDOT (in negative degrees)"*, Type: `TEXT`, Length: `12`, Constraints: `DD MM:SS.ddd`

#### Field Characteristics & Formatting
- **Raw Storage:** Alphanumeric strings formatted as degrees, space, minutes, colon, seconds, and decimal seconds: `DD MM:SS.ddd`.
- **Sample Values (Observed in `analysis/outputs/spatial/police_coordinate_encoding_audit.csv`):**
  - Latitude: `'40 19:05.530'`, `'40 29:18.923'`, `'40 25:07.576'`, `'40 27:40.438'`
  - Longitude: `'79 54:27.197'`, `'80 20:13.631'`, `'80 02:57.719'`, `'80 00:31.456'`
- **Hemisphere Convention:**
  - Latitude degrees represent North latitude (positive).
  - Longitude degrees represent West longitude (negative). The raw string contains positive degrees (e.g. `79` or `80`), and must be negated to yield true Western hemisphere coordinates.
- **Missingness in 2004–2024 Cumulative Extract:**
  - `LATITUDE`: 10,089 missing records (4.05%)
  - `LONGITUDE`: 10,090 missing records (4.06%)

#### Mathematical Conversion to Decimal Degrees
$$\text{Decimal Degrees} = \text{Degrees} + \frac{\text{Minutes}}{60.0} + \frac{\text{Seconds}}{3600.0}$$

For longitude in the Western hemisphere:
$$\text{Decimal Longitude} = -\left(\text{Degrees} + \frac{\text{Minutes}}{60.0} + \frac{\text{Seconds}}{3600.0}\right)$$

#### Regular Expression & Validation Parsing Rule
```regex
^(\d{1,3})\s+(\d{1,2}):(\d{1,2}(?:\.\d+)?)$
```
- **Validation Bounds:**
  - Minutes: $0 \le \text{Minutes} < 60$
  - Seconds: $0 \le \text{Seconds} < 60$
  - Latitude Regional Bounding Box: $38.0^\circ\text{N} \le \text{Lat} \le 43.0^\circ\text{N}$
  - Longitude Regional Bounding Box: $-82.0^\circ\text{W} \le \text{Lon} \le -78.0^\circ\text{W}$

---

### 2.2 State Route Geocoded Decimal Coordinates (`DEC_LAT`, `DEC_LONG`)

- **Authoritative Definition:** PennDOT Crash Data Dictionary (2026, Page 3):
  - `DEC_LATITUDE` (in CSV: `DEC_LAT`): *"Decimal format of the Latitude"*, Type: `NUMBER 2.4`, Constraints: *Latitude expressed in decimal degrees 99.9999*.
  - `DEC_LONGITUDE` (in CSV: `DEC_LONG`): *"Decimal format of the Longitude"*, Type: `NUMBER 2.4`, Constraints: *Longitude expressed in decimal degrees 99.9999*.
- **Data Origin:** Derived by PennDOT's automated Linear Referencing GIS engine by locating the state route segment and foot offset along the digitized state roadway centerline network (RMSSEG).
- **Missingness in 2004–2024 Cumulative Extract:**
  - `DEC_LAT`: 10,202 missing records (4.10%)
  - `DEC_LONG`: 10,210 missing records (4.10%)
- **Validation Bounds:**
  - Latitude: $40.10^\circ\text{N} \le \text{Lat} \le 40.75^\circ\text{N}$
  - Longitude: $-80.40^\circ\text{W} \le \text{Lon} \le -79.60^\circ\text{W}$

---

## 3. Crash Location & Roadway Context Fields

### 3.1 Linear Referencing & Highway Identifiers

#### `ROUTE`
- **Definition:** 4-digit State Route number assigned to PennDOT-maintained roadways.
- **Type:** Text (String), Length: 4.
- **Missingness:** 102,322 records (41.12%).
- **Domain Rules:**
  - Interstate Highways: `0076` (PA Turnpike), `0079`, `0376` (Parkway East/West), `0279`, `0579`.
  - US Highways: `0019`, `0022`, `0030`.
  - State Routes: `0028`, `0051`, `0088`, `0837`, `0885`.
  - Ramps / Interchanges: `8001` through `8999` (unique per interchange within each county).
  - Blank / Null: Local municipal roads, county roads, private roads.

#### `SEGMENT`
- **Definition:** 4-digit segment identifier along a State Route. Segments average approximately one-half mile in length.
- **Type:** Text (String), Length: 4.
- **Missingness:** 110,226 records (44.30%).
- **Domain Rules:**
  - Undivided Highways: Begin at `0010` at county line/origin and increment by 10 (`0010`, `0020`, `0030`, ...) heading North or East.
  - Divided Highways (Separated by median, barrier, or $\ge 4$ ft painted buffer): Uses even/odd segment pairs.
    - Even Segments (`0010`, `0020`, ...): Primary direction (Northbound or Eastbound).
    - Odd Segments (`0011`, `0021`, ...): Opposing direction (Southbound or Westbound).
  - Placeholder: `9999` denotes unknown segment.

#### `OFFSET`
- **Definition:** Linear distance in feet measured from the start of the segment heading in the direction of increasing segment numbers.
- **Type:** Text (String), Length: 4.
- **Missingness:** 96,035 records (38.60%).
- **Domain Rules:** Integer value typically ranging from `0000` to the full length of the segment (usually $\le 2640$ ft). `9999` denotes unknown offset.

#### `ROAD_OWNER`
- **Definition:** Administrative jurisdiction responsible for maintaining the roadway where the crash occurred.
- **Type:** Categorical Code (Integer / Float), Length: 2.
- **Missingness:** 6,158 records (2.47%).
- **Enumerated Codebook:**
  - `1`: Interstate (non-turnpike)
  - `2`: State highway
  - `3`: County road
  - `4`: Local road or street (municipal)
  - `5`: East-West portion of PA Turnpike
  - `6`: Turnpike spur / extension
  - `7`: Private road
  - `9`: Other or Unknown

#### `ACCESS_CTRL`
- **Definition:** Level of highway access control (applicable to state roads).
- **Type:** Categorical Code (Integer / Float), Length: 1.
- **Missingness:** 121,206 records (48.71%).
- **Enumerated Codebook:**
  - `1`: Full Access Control (Freeways / Interstates; ramp access only)
  - `2`: Partial Access Control (Expressways; limited at-grade intersections)
  - `3`: No Access Control (Standard surface streets / unlimited access)

#### `LANE_COUNT`
- **Definition:** Total number of travel lanes. For undivided roadways, includes both directions; for divided highways, counts lanes in the crash direction only.
- **Type:** Integer / Float, Length: 2.
- **Missingness:** 15,007 records (6.03%).

#### `SPEED_LIMIT`
- **Definition:** Posted legal speed limit in miles per hour.
- **Type:** Integer / Float, Length: 2.
- **Missingness:** 13,336 records (5.36%). Plausible domain: 15–70 mph.

---

### 3.2 Street Names & Local Road Reference

#### `STREET_NAME`
- **Definition:** Name of the roadway where the crash occurred as reported by the investigating officer.
- **Type:** Text (String), Length: 50.
- **Missingness:** 12,316 records (4.95%).
- **Normalization Requirements:** Raw street names exhibit variance in abbreviations (`ST`, `STREET`, `RD`, `ROAD`, `AVE`, `AVENUE`, `BLVD`), directional prefixes (`N`, `NORTH`, `S`, `SOUTH`), and duplicate endings (`MAIN ST ST`). Matching to reference centerlines requires standardizing tokens against USPS Publication 28 conventions.

#### `LOCAL_ROAD`
- **Definition:** Local roadway name or route designation (e.g., township route numbers like `T-302` or county designations).
- **Type:** Text (String), Length: 50.
- **Missingness:** 12,418 records (4.99%).

---

### 3.3 Intersection & Geometric Classification

#### `INTERSECTION` & `NON_INTERSECTION`
- **Definition:** Mutually exclusive binary flags indicating whether the crash occurred at a junction or along a mid-block segment.
- **Type:** Integer (0 or 1).
- **Missingness:** 1 record (0.0004%).
- **Rules:**
  - `INTERSECTION = 1`: Crash occurred within 100 feet of an intersection or was legally attributed to junction maneuvers.
  - `NON_INTERSECTION = 1`: Mid-block collision.

#### `INTERSECT_TYPE`
- **Definition:** Geometric configuration of the intersection.
- **Type:** Categorical Code (Integer), Length: 2.
- **Missingness:** 0 records (0.00%).
- **Enumerated Codebook (PennDOT 2026 Dictionary, Page 17):**
  - `00`: Mid-block (Non-intersection)
  - `01`: Four-way intersection
  - `02`: "T" intersection
  - `03`: "Y" intersection
  - `04`: Traffic Circle / Roundabout *(Expired 2018-01-01; see codes 12 and 13)*
  - `05`: Multi-leg intersection ($\ge 5$ approaches)
  - `06`: Ramp End
  - `07`: Ramp Begin
  - `08`: Crossover
  - `09`: Railroad grade crossing
  - `10`: Other
  - `11`: "L" intersection
  - `12`: Traffic Circle
  - `13`: Roundabout
  - `99`: Unknown

#### `RELATION_TO_ROAD`
- **Definition:** Physical location of the initial impact or critical event relative to trafficway lanes.
- **Type:** Categorical Code (Integer), Length: 1.
- **Missingness:** 0 records (0.00%).
- **Enumerated Codebook (PennDOT 2026 Dictionary, Page 17):**
  - `1`: On roadway (Travel lanes)
  - `2`: Shoulder
  - `3`: Median
  - `4`: Roadside (Off trafficway, vehicle traversable area)
  - `5`: Outside trafficway (Area not intended for vehicles)
  - `6`: In parking lane
  - `7`: Gore (Triangular area between highway mainline and ramp)
  - `9`: Unknown

#### `LOCATION_TYPE`
- **Definition:** Distinct facility structure or special roadway feature.
- **Type:** Categorical Code (Integer), Length: 2.
- **Missingness:** 0 records (0.00%).
- **Enumerated Codebook (PennDOT 2026 Dictionary, Page 17):**
  - `0`: Not applicable (Standard surface roadway)
  - `1`: Underpass
  - `2`: Ramp
  - `3`: Bridge / Overpass
  - `4`: Tunnel
  - `5`: Toll Booth
  - `6`: Crossover related
  - `7`: Driveway or Parking Lot
  - `8`: Ramp and bridge
  - `99`: Unknown

---

### 3.4 Jurisdictional & Administrative Codes

#### `MUNICIPALITY`
- **Definition:** 5-digit PennDOT municipality code where the crash occurred. First two digits represent county (`02` = Allegheny); last three digits identify the specific municipality.
- **Type:** Categorical Code (Integer), Length: 5.
- **Missingness:** 0 records (0.00%).
- **Official Lookup:** Fully defined in [`data/reference/codebooks/municipalitycodes.csv`](../../data/reference/codebooks/municipalitycodes.csv) (130 distinct Allegheny County municipalities). Examples:
  - `02101`: Baldwin Township
  - `02108`: McCandless Township
  - `02109`: Mount Lebanon Township
  - `02112`: Penn Hills Township
  - `02301`: City of Pittsburgh
  - `02410`: Monroeville Borough
  - `02454`: McKeesport City

#### `POLICE_AGCY`
- **Definition:** 5-digit PennDOT reporting police agency code.
- **Type:** Categorical Code (Integer), Length: 5.
- **Missingness:** 0 records (0.00%).
- **Official Lookup:** Fully defined in [`data/reference/codebooks/policeagencycodes.csv`](../../data/reference/codebooks/policeagencycodes.csv).

#### `URBAN_RURAL`
- **Definition:** Urban/rural classification of crash site.
- **Type:** Categorical Code (Integer), Length: 1.
- **Missingness:** 0 records (0.00%).
- **Enumerated Codebook:**
  - `1`: Rural
  - `2`: Urban
  - `3`: Small Urban

---

## 4. Roadway Reference Data Dictionary (Allegheny County Centerlines)

Extracted from the official shapefile DBF schema (`data/reference/street_centerlines/alleghenycounty_streetcenterlines202610.zip`) and governed by `addressing_data_model.pdf`:

| Field Name | Type | Width | Description & Domain Rules |
|---|---|---|---|
| `FEATURE_KE` | Character | 20 | Unique primary segment identifier for the centerline feature. Used as join key to street table. |
| `FULL_NAME` | Character | 254 | Full concatenated street name (e.g., `PENN AVE`, `WM PENN HWY`, `MCKNIGHT RD`). |
| `ST_NAME` | Character | 125 | Legal base street name assigned by municipality (e.g., `PENN`, `MCKNIGHT`). |
| `ST_PREFIX` | Character | 2 | Directional prefix preceding street name (`N`, `S`, `E`, `W`). |
| `ST_TYPE` | Character | 5 | Street type suffix defined by USPS Pub 28 (`AVE`, `ST`, `RD`, `BLVD`, `WAY`, `DR`, `LN`). |
| `ST_SUFFIX` | Character | 2 | Directional suffix following street name. |
| `ST_PREMODI` | Character | 50 | Pre-modifier descriptive text. |
| `ST_POSTMOD` | Character | 50 | Post-modifier descriptive text (`EXT`, `CONN`, `OVERPASS`). |
| `LMUNI` | Character | 254 | Legal name of municipality situated on the left side of segment. |
| `RMUNI` | Character | 254 | Legal name of municipality situated on the right side of segment. |
| `LCOUNTY` | Character | 40 | County name on left side (`Allegheny`). |
| `RCOUNTY` | Character | 40 | County name on right side (`Allegheny`). |
| `L_ZIP` / `R_ZIP` | Character | 5 | 5-digit US Postal Service ZIP codes for left and right segment sides. |
| `ONEWAY` | Character | 10 | Directionality indicator: `FT` (From-To), `TF` (To-From), `B` (Both directions). |
| `LAR` | Character | 1 | Limited Access Roadway flag: `Y` = Interstate or highway accessible only by ramps; `N` = Surface street. |
| `LARDIR` | Character | 4 | Direction of travel on Limited Access Roadway. |
| `FCC` | Character | 20 | Census Feature Class Code (e.g. `A10` Interstate, `A20` Primary highway, `A30` Secondary road, `A40` Local street). |
| `SPEED` | Numeric | 5 | Posted speed. *Note: Data Model Page 7 states this field is unmaintained and derived from legacy sources.* |
| `F_NODE` | Character | 1 | "From" topological junction node identifier. |
| `T_NODE` | Character | 1 | "To" topological junction node identifier. |
| `Shape_Leng` | Float | 19 | Length of centerline geometry in Pennsylvania State Plane South Feet (EPSG:2272). |

---

## 5. Coordinate Selection & Discrepancy Policy for Phase 3 Module B

1. **State Route Crashes:**
   - Where `ROUTE`, `SEGMENT`, and `OFFSET` are valid, `DEC_LAT` and `DEC_LONG` provide the primary ground truth because they are deterministically linked to PennDOT's state route network.
2. **Police GPS Coordinates:**
   - Converted using the verified `DD MM:SS.ddd` transformation.
   - For records lacking state route decimal coordinates (e.g., local municipal roads), converted police coordinates provide candidate crash locations.
3. **Discrepancy Gating:**
   - In 2,146 cases where police and state decimal coordinates disagree by $>500$ meters, the crash must be flagged with `COORDINATE_CONFLICT = True` and reviewed rather than arbitrarily assigned.
