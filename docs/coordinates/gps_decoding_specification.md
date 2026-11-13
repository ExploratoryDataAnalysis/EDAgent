# Phase 3 — Module B: GPS Decoding Specification

> **Superseded scope:** This report records earlier work and decisions. [Project Plan v3](../EDAgent_Project_Plan_v3.pdf) and the [v3 roadmap](../implementation_plan.md#v3-transition-and-roadmap) govern release scope: site-level historical screening, frequency/EB modelling and real-site treatment estimates are out of scope; geographic matches are diagnostic, with zero accepted primary assignments. Earlier claims of approval, mandatory pathways or pending release describe historical proposals, not current authorization.

**Project:** EDAgent Road-Safety Analytics  
**Phase:** Phase 3 — Roadway Crosswalk and Geographic Integration  
**Module:** Module B — GPS Decoding and Coordinate Validation  
**Document:** Technical Specification for GPS Decoding & Transformation  
**Authority:** PennDOT Crash Data Dictionary (2026 Edition, Page 4), Project Plan v2 (§12–14)  
**Package:** `src/edagent/coordinates/`  

---

## 1. Official Encoding Authority & Specification

### 1.1 The Encoding Finding
Prior research iterations noted that field-level GPS coordinate encodings remained unverified. Investigation of authoritative state documentation—specifically the **PennDOT Crash Data Dictionary (2026 Edition, Page 4)**—formally establishes the exact format:

| Field Name | Official Short Title | Data Type | Length | Documented Constraints |
|---|---|---|---|---|
| `LATITUDE` | GPS Latitude determined by PennDOT | `TEXT` | 12 | `DD MM:SS.ddd` |
| `LONGITUDE` | GPS Longitude determined by PennDOT (in negative degrees) | `TEXT` | 12 | `DD MM:SS.ddd` |
| `DEC_LATITUDE` (`DEC_LAT`) | Decimal format of the Latitude | `NUMBER` | 2.4 | Latitude expressed in decimal degrees `99.9999` |
| `DEC_LONGITUDE` (`DEC_LONG`) | Decimal format of the Longitude | `NUMBER` | 2.4 | Longitude expressed in decimal degrees `99.9999` |

> [!IMPORTANT]
> **No Guesswork / No Synthetic Approximations:** The fields labeled `LATITUDE` and `LONGITUDE` do **not** contain decimal degrees. They contain Degrees, Minutes, and Seconds formatted with a space and a colon: `DD MM:SS.ddd`. Assuming standard decimal floats without this parsing causes total coordinate failure.

---

## 2. Mathematical Coordinate Conversion

### 2.1 Formula Definition
For any valid Degrees-Minutes-Seconds text string conforming to `DD MM:SS.ddd`:

$$\text{Degrees} \in [0, 90] \quad (\text{Latitude}), \quad \text{Degrees} \in [0, 180] \quad (\text{Longitude})$$
$$\text{Minutes} \in [0, 60)$$
$$\text{Seconds} \in [0, 60)$$

The normalized decimal degree coordinate is:
$$\text{Decimal Degrees} = \text{Degrees} + \frac{\text{Minutes}}{60.0} + \frac{\text{Seconds}}{3600.0}$$

### 2.2 Hemisphere Rules
- **Latitude:** In Pennsylvania (Northern Hemisphere), degrees are positive ($+N$).
- **Longitude:** In Pennsylvania (Western Hemisphere), longitude is negative ($-W$). The raw police text strings store positive degree values (e.g., `'79 54:27.197'`). The decoder negates the resulting decimal degrees:
  $$\text{Decimal Longitude} = -\left(\text{Degrees} + \frac{\text{Minutes}}{60.0} + \frac{\text{Seconds}}{3600.0}\right)$$

### 2.3 Verification Examples from Frozen Baseline
Verified against `analysis/outputs/spatial/police_coordinate_encoding_audit.csv`:

| Raw Field Value | Component Breakdown | Normalized Decimal Degrees | Regional Validity |
|---|---|---|---|
| `'40 19:05.530'` (Lat) | Deg: 40, Min: 19, Sec: 05.530 | $+40.31820278^\circ\text{N}$ | Allegheny County South |
| `'79 54:27.197'` (Lon) | Deg: 79, Min: 54, Sec: 27.197 | $-79.90755472^\circ\text{W}$ | Allegheny County East |
| `'40 29:18.923'` (Lat) | Deg: 40, Min: 29, Sec: 18.923 | $+40.48858972^\circ\text{N}$ | Allegheny County North |
| `'80 20:13.631'` (Lon) | Deg: 80, Min: 20, Sec: 13.631 | $-80.33711972^\circ\text{W}$ | Allegheny County West |

---

## 3. Parsing Grammar, Regular Expressions & Validation

### 3.1 Regular Expression
The decoder applies a strict anchored regular expression to ensure malformed inputs are not silently accepted:

```regex
^(\d{1,3})\s+(\d{1,2}):(\d{1,2}(?:\.\d+)?)$
```

- Group 1: 1 to 3 integer digits (Degrees).
- Separator: 1 or more whitespace characters.
- Group 2: 1 to 2 integer digits (Minutes).
- Separator: Exactly one colon (`:`).
- Group 3: 1 to 2 integer digits with optional decimal point and fractional digits (Seconds).

### 3.2 Error Categories & Validation Flags
When parsing fails or values violate mathematical bounds, explicit flags are assigned:

| Error Category | Condition | Resulting Flag |
|---|---|---|
| **Syntax Malformation** | String does not match `^(\d{1,3})\s+(\d{1,2}):(\d{1,2}(?:\.\d+)?)$` | `MALFORMED_LATITUDE_FORMAT`<br>`MALFORMED_LONGITUDE_FORMAT` |
| **Numeric Conversion** | Substring cannot be converted to IEEE 754 float | `NON_NUMERIC_COORDINATE_VALUE` |
| **Minute Domain Error** | $\text{Minutes} < 0.0$ or $\text{Minutes} \ge 60.0$ | `MINUTES_OUT_OF_RANGE` |
| **Second Domain Error** | $\text{Seconds} < 0.0$ or $\text{Seconds} \ge 60.0$ | `SECONDS_OUT_OF_RANGE` |
| **Global Degree Error** | $\text{Lat Deg} > 90$ or $\text{Lon Deg} > 180$ | `LATITUDE_OUT_OF_GLOBAL_RANGE`<br>`LONGITUDE_OUT_OF_GLOBAL_RANGE` |
| **Missing / Placeholder** | String in `{None, "", "0", "0.0", "nan", "null", "99.9999", ...}` | `MISSING_POLICE_LATITUDE`<br>`MISSING_POLICE_LONGITUDE` |

---

## 4. Precision, Resolution & Geodesic Calculation

### 4.1 Resolution Analysis
- **Police DMS Text:** Seconds are recorded to three decimal places ($0.001''$).
  - One degree of latitude $\approx 111,000 \text{ m}$.
  - One arcsecond of latitude $\approx 30.8 \text{ m}$.
  - $0.001''$ arcsecond $\approx 0.0308 \text{ m} = 3.08 \text{ cm}$.
  - Theoretical sensor/entry precision is centimeter-scale.
- **State Route Decimal Coordinates:** Stored as `NUMBER 2.4` (4 decimal places in state database, 6–8 in CSV extract).
  - 4 decimal places ($0.0001^\circ$) $\approx 11.1 \text{ m}$ latitude resolution; $\approx 8.5 \text{ m}$ longitude resolution at $40.4^\circ\text{N}$.

### 4.2 Haversine Spherical Distance
Pairwise discrepancies between police GPS and State Route decimal coordinates are computed using the spherical Haversine formula ($R = 6,371,000\text{ m}$):

$$\Delta\phi = \phi_2 - \phi_1, \quad \Delta\lambda = \lambda_2 - \lambda_1$$
$$a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos\phi_1\cos\phi_2\sin^2\left(\frac{\Delta\lambda}{2}\right)$$
$$d = 2 R \arcsin\left(\min(1.0, \sqrt{a})\right)$$

This formula is benchmarked against the frozen v6 research outputs (`candidate_coordinate_disagreements_review.csv`) and reproduces the frozen distance metrics within $10^{-9}$ meters.

---

## 5. Software Architecture: `src/edagent/coordinates/`

```
src/edagent/coordinates/
├── __init__.py         # Package entry point and public symbol exports
├── models.py           # Dataclasses: CoordinateRecord, DecodedCoordinate, ValidationStatus
├── decoder.py          # GPSDecoder: DMS text and decimal degrees parsing
├── validator.py        # CoordinateValidator: Spatial screening, boundaries, conflicts
└── pipeline.py         # CoordinatePipeline: Batch processing and quality metric aggregation
```

### 5.1 Public API Example
```python
from edagent.coordinates import GPSDecoder, CoordinateValidator

validator = CoordinateValidator()

record = validator.process_crash_record(
    crash_crn=2015001234,
    crash_year=2015,
    raw_latitude="40 26:07.800",
    raw_longitude="79 45:10.800",
    raw_dec_lat="40.435501",
    raw_dec_long="-79.753000",
    is_state_route=True,
)

print(record.validation_status)   # ValidationStatus.VALID
print(record.decoded_latitude)    # 40.435501
print(record.pair_distance_meters) # 17.43 (meters)
```
