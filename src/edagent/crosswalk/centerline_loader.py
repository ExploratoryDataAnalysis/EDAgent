"""Allegheny County Centerline loader and PennDOT State Route registry builder.

Parses official DBF and SHP geometry from alleghenycounty_streetcenterlines202610.zip,
converts State Plane South feet (EPSG:2272) to WGS84 (EPSG:4326), and populates
the SiteRegistry with validated road segments and intersection sites.
"""

from __future__ import annotations

import math
import struct
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from edagent.roadway.intersections import IntersectionSite
from edagent.roadway.normalization import map_road_class, normalize_route_number, normalize_street_name
from edagent.roadway.registry import SiteRegistry
from edagent.roadway.schema import RoadClass, SiteRecord, SiteType
from edagent.roadway.segments import RoadSegmentSite, SegmentIdentifier

# Constants for EPSG:2272 (NAD83 / Pennsylvania South ftUS) to WGS84 conversion
_A = 6378137.0  # GRS80 semi-major axis (meters)
_F = 1.0 / 298.257222101
_E2 = 2 * _F - _F * _F
_E = math.sqrt(_E2)
_PHI1 = math.radians(39.0 + 56.0 / 60.0)
_PHI2 = math.radians(40.0 + 58.0 / 60.0)
_PHI0 = math.radians(39.0 + 20.0 / 60.0)
_LAM0 = math.radians(-77.75)
_X0 = 1968500.0 * (1200.0 / 3937.0)  # False easting in meters
_M1 = math.cos(_PHI1) / math.sqrt(1.0 - _E2 * math.sin(_PHI1)**2)
_M2 = math.cos(_PHI2) / math.sqrt(1.0 - _E2 * math.sin(_PHI2)**2)
_T0 = math.tan(math.pi / 4.0 - _PHI0 / 2.0) / ((1.0 - _E * math.sin(_PHI0)) / (1.0 + _E * math.sin(_PHI0)))**(_E / 2.0)
_T1 = math.tan(math.pi / 4.0 - _PHI1 / 2.0) / ((1.0 - _E * math.sin(_PHI1)) / (1.0 + _E * math.sin(_PHI1)))**(_E / 2.0)
_T2 = math.tan(math.pi / 4.0 - _PHI2 / 2.0) / ((1.0 - _E * math.sin(_PHI2)) / (1.0 + _E * math.sin(_PHI2)))**(_E / 2.0)
_N = (math.log(_M1) - math.log(_M2)) / (math.log(_T1) - math.log(_T2))
_F_COEFF = _M1 / (_N * _T1**_N)
_RHO0 = _A * _F_COEFF * _T0**_N


def epsg2272_to_wgs84(x_ft: float, y_ft: float) -> Tuple[float, float]:
    """Convert Pennsylvania State Plane South (survey feet) to WGS84 (Lat, Lon)."""
    x_m = x_ft * (1200.0 / 3937.0)
    y_m = y_ft * (1200.0 / 3937.0)
    x_rel = x_m - _X0
    y_rel = _RHO0 - y_m
    rho = math.hypot(x_rel, y_rel)
    theta = math.atan2(x_rel, y_rel)
    t = (rho / (_A * _F_COEFF))**(1.0 / _N)
    lam = _LAM0 + theta / _N
    phi = math.pi / 2.0 - 2.0 * math.atan(t)
    for _ in range(5):
        phi = math.pi / 2.0 - 2.0 * math.atan(
            t * ((1.0 - _E * math.sin(phi)) / (1.0 + _E * math.sin(phi)))**(_E / 2.0)
        )
    return math.degrees(phi), math.degrees(lam)


class CenterlineLoader:
    """Loads and registers official County Centerline and PennDOT State Route reference features."""

    @staticmethod
    def load_centerlines_from_zip(
        zip_path: str,
        registry: SiteRegistry,
        max_features: Optional[int] = None,
    ) -> int:
        """Extract and register street centerline features from the official zip archive."""
        path = Path(zip_path)
        if not path.exists():
            raise FileNotFoundError(f"Centerline zip file not found: {zip_path}")

        count = 0
        with zipfile.ZipFile(path, "r") as z:
            # 1. Read shapefile bounding boxes and midpoints
            midpoints: Dict[int, Tuple[float, float]] = {}
            with z.open("AlleghenyCounty_StreetCenterlines202610.shp") as shp_f:
                hdr = shp_f.read(100)
                file_len = struct.unpack(">I", hdr[24:28])[0] * 2
                rec_idx = 0
                while shp_f.tell() < file_len:
                    rec_hdr = shp_f.read(8)
                    if not rec_hdr or len(rec_hdr) < 8:
                        break
                    _, content_len = struct.unpack(">II", rec_hdr)
                    rec_bytes = shp_f.read(content_len * 2)
                    if len(rec_bytes) < 36:
                        rec_idx += 1
                        continue
                    # Polyline bounding box: xmin, ymin, xmax, ymax
                    xmin, ymin, xmax, ymax = struct.unpack("<4d", rec_bytes[4:36])
                    mid_x = (xmin + xmax) / 2.0
                    mid_y = (ymin + ymax) / 2.0
                    lat, lon = epsg2272_to_wgs84(mid_x, mid_y)
                    midpoints[rec_idx] = (lat, lon)
                    rec_idx += 1
                    if max_features and rec_idx >= max_features:
                        break

            # 2. Read DBF attributes
            with z.open("AlleghenyCounty_StreetCenterlines202610.dbf") as dbf_f:
                dbf_hdr = dbf_f.read(32)
                num_records, header_len, record_len = struct.unpack("<IHH", dbf_hdr[4:12])
                fields = []
                for _ in range((header_len - 33) // 32):
                    fld = dbf_f.read(32)
                    name = fld[:11].replace(b"\x00", b"").decode("ascii").strip()
                    typ = chr(fld[11])
                    length = fld[16]
                    fields.append((name, typ, length))
                dbf_f.read(1)  # header record terminator

                limit = min(num_records, max_features) if max_features else num_records
                for rec_i in range(limit):
                    rec = dbf_f.read(record_len)
                    if not rec or len(rec) < record_len:
                        break
                    if rec[0:1] == b"*":  # deleted record
                        continue

                    pos = 1
                    vals: Dict[str, str] = {}
                    for name, typ, length in fields:
                        vals[name] = rec[pos : pos + length].strip().decode("ascii", errors="ignore")
                        pos += length

                    feat_key = vals.get("FEATURE_KE") or f"RCL_{rec_i}"
                    full_name = vals.get("FULL_NAME") or vals.get("ST_NAME") or "UNNAMED"
                    fcc = vals.get("FCC") or ""
                    lar = vals.get("LAR") or ""
                    road_cls = map_road_class(fcc=fcc, lar=lar)

                    mid_coord = midpoints.get(rec_i)
                    lat = mid_coord[0] if mid_coord else None
                    lon = mid_coord[1] if mid_coord else None

                    site_id = SegmentIdentifier.generate_centerline_segment_id(feat_key)
                    canonical_name = f"{normalize_street_name(full_name)} [{feat_key}]"

                    site_rec = SiteRecord(
                        site_id=site_id,
                        site_type=SiteType.SEGMENT,
                        canonical_name=canonical_name,
                        municipality_name=vals.get("LMUNI") or vals.get("RMUNI"),
                        road_class=road_cls,
                        street_names=[normalize_street_name(full_name)],
                        centroid_lat=lat,
                        centroid_lon=lon,
                        source_reference_ids=[f"AC_CENTERLINE_{feat_key}"],
                        version="2026.10",
                    )
                    registry.register(site_rec)
                    count += 1

        return count

    @staticmethod
    def populate_state_route_segments_from_crashes(
        crash_csv_path: str,
        registry: SiteRegistry,
    ) -> int:
        """Scan crash dataset and register official PennDOT State Route Segments (LRS)."""
        path = Path(crash_csv_path)
        if not path.exists():
            raise FileNotFoundError(f"Crash dataset not found: {crash_csv_path}")

        import csv

        registered_lrs: Dict[Tuple[str, str], Dict[str, Any]] = {}

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r_raw = row.get("ROUTE")
                s_raw = row.get("SEGMENT")
                if not r_raw or not s_raw:
                    continue

                norm_r = normalize_route_number(str(r_raw))
                if not norm_r:
                    continue

                seg_digits = "".join(filter(str.isdigit, str(s_raw)))
                if not seg_digits:
                    continue
                norm_s = f"{int(seg_digits):04d}"

                key = (norm_r, norm_s)
                if key not in registered_lrs:
                    # Capture representative attributes
                    lat_val = None
                    lon_val = None
                    dec_lat = row.get("DEC_LAT")
                    dec_lon = row.get("DEC_LONG")
                    if dec_lat and dec_lon:
                        try:
                            lat_val = float(dec_lat)
                            lon_val = float(dec_lon)
                        except (ValueError, TypeError):
                            pass

                    registered_lrs[key] = {
                        "route": norm_r,
                        "segment": norm_s,
                        "street_name": row.get("STREET_NAME") or "",
                        "municipality": str(row.get("MUNICIPALITY") or "").strip(),
                        "road_owner": row.get("ROAD_OWNER"),
                        "lat": lat_val,
                        "lon": lon_val,
                    }

        count = 0
        for (r, s), info in registered_lrs.items():
            site_id = SegmentIdentifier.generate_state_segment_id("02", r, s)
            st_name = normalize_street_name(info["street_name"])
            canon_name = f"SR {r} SEG {s}"
            if st_name:
                canon_name = f"{canon_name} ({st_name})"

            road_cls = map_road_class(
                road_owner=info["road_owner"],
                route=r,
            )

            site_rec = SiteRecord(
                site_id=site_id,
                site_type=SiteType.SEGMENT,
                canonical_name=canon_name,
                municipality_code=info["municipality"],
                road_class=road_cls,
                street_names=[st_name] if st_name else [],
                centroid_lat=info["lat"],
                centroid_lon=info["lon"],
                source_reference_ids=[f"PENNDOT_RMS_02_{r}_{s}"],
                version="1.0.0",
            )
            registry.register(site_rec)
            count += 1

        return count
