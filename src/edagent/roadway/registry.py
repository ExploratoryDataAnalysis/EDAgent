"""Stable identifier registry module.

Maintains the authoritative catalog of physical intersections and road segments,
providing deterministic key lookups, spatial proximity indexing, and serialization.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from edagent.coordinates.decoder import haversine_distance_meters
from edagent.roadway.intersections import IntersectionIdentifier
from edagent.roadway.normalization import normalize_route_number, normalize_street_name
from edagent.roadway.schema import RoadClass, SiteRecord, SiteType


class SiteRegistry:
    """Authoritative registry of validated roadway sites (intersections and segments)."""

    def __init__(self) -> None:
        self._sites: Dict[str, SiteRecord] = {}
        # Inverted index: (muni_code, tuple of sorted streets) -> site_id
        self._intersection_index: Dict[Tuple[str, Tuple[str, ...]], str] = {}
        # Inverted index: (county_code, route_4, segment_4) -> site_id
        self._lrs_index: Dict[Tuple[str, str, str], str] = {}
        # Spatial list of sites with coordinates: (site_id, lat, lon)
        self._spatial_index: List[Tuple[str, float, float]] = []
        # Spatial grid buckets: (grid_lat, grid_lon) -> List[(site_id, lat, lon)]
        self._spatial_grid: Dict[Tuple[int, int], List[Tuple[str, float, float]]] = {}

    def _get_grid_cell(self, lat: float, lon: float) -> Tuple[int, int]:
        """Convert coordinates to ~1km grid bucket indices."""
        if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
            return (0, 0)
        return (int(math.floor(lat * 100)), int(math.floor(lon * 100)))

    def register(self, site: SiteRecord) -> SiteRecord:
        """Register a SiteRecord in the registry, updating indexes.

        If a site with the same site_id already exists, its source reference IDs
        and street names are merged.
        """
        existing = self._sites.get(site.site_id)
        if existing:
            # Merge references
            for ref in site.source_reference_ids:
                if ref not in existing.source_reference_ids:
                    existing.source_reference_ids.append(ref)
            for st in site.street_names:
                if st not in existing.street_names:
                    existing.street_names.append(st)
            if existing.centroid_lat is None and site.centroid_lat is not None:
                existing.centroid_lat = site.centroid_lat
                existing.centroid_lon = site.centroid_lon
                self._spatial_index.append((site.site_id, site.centroid_lat, site.centroid_lon))
                cell = self._get_grid_cell(site.centroid_lat, site.centroid_lon)
                self._spatial_grid.setdefault(cell, []).append(
                    (site.site_id, site.centroid_lat, site.centroid_lon)
                )
            return existing

        self._sites[site.site_id] = site

        # Index intersections
        if site.site_type == SiteType.INTERSECTION and site.municipality_code:
            streets_key = tuple(IntersectionIdentifier.canonical_streets(site.street_names))
            if len(streets_key) >= 2:
                self._intersection_index[(site.municipality_code, streets_key)] = site.site_id

        # Index PennDOT LRS segments
        if site.site_type == SiteType.SEGMENT and site.site_id.startswith("SEG:"):
            parts = site.site_id.split(":")
            # Format: SEG:county:SRroute:seg
            if len(parts) >= 4 and parts[2].startswith("SR"):
                county = parts[1]
                route = parts[2][2:]  # Strip 'SR'
                seg = parts[3]
                self._lrs_index[(county, route, seg)] = site.site_id

        # Index coordinates
        if site.centroid_lat is not None and site.centroid_lon is not None:
            self._spatial_index.append((site.site_id, site.centroid_lat, site.centroid_lon))
            cell = self._get_grid_cell(site.centroid_lat, site.centroid_lon)
            self._spatial_grid.setdefault(cell, []).append(
                (site.site_id, site.centroid_lat, site.centroid_lon)
            )

        return site

    def get(self, site_id: str) -> Optional[SiteRecord]:
        """Retrieve a site by its stable project identifier."""
        return self._sites.get(site_id)

    def contains(self, site_id: str) -> bool:
        """Check if a site ID is present in the registry."""
        return site_id in self._sites

    def find_intersection(
        self, muni_code: str, street_names: List[str]
    ) -> Optional[SiteRecord]:
        """Find an intersection site by municipality and intersecting streets."""
        clean_muni = str(muni_code).strip()
        canonical_streets = tuple(IntersectionIdentifier.canonical_streets(street_names))
        if len(canonical_streets) < 2:
            return None

        # Direct tuple lookup
        site_id = self._intersection_index.get((clean_muni, canonical_streets))
        if site_id:
            return self._sites.get(site_id)

        # Fallback: check subset matching if intersection has >2 legs
        for (muni, streets), s_id in self._intersection_index.items():
            if muni == clean_muni:
                if set(canonical_streets).issubset(set(streets)):
                    return self._sites.get(s_id)

        return None

    def find_segment_by_lrs(
        self, county_code: str, route: str, segment: str
    ) -> Optional[SiteRecord]:
        """Find a PennDOT state segment site by county, route, and segment numbers."""
        clean_county = str(county_code).strip().zfill(2)
        norm_route = normalize_route_number(route)
        if not norm_route:
            return None

        clean_seg = str(segment).strip().zfill(4)
        site_id = self._lrs_index.get((clean_county, norm_route, clean_seg))
        if site_id:
            return self._sites.get(site_id)

        # Construct deterministic ID directly
        candidate_id = f"SEG:{clean_county}:SR{norm_route}:{clean_seg}"
        return self._sites.get(candidate_id)

    def find_nearby_sites(
        self,
        lat: float,
        lon: float,
        max_distance_meters: float = 50.0,
        site_type: Optional[SiteType] = None,
    ) -> List[Tuple[SiteRecord, float]]:
        """Find registered sites within a distance threshold of given coordinates.

        Uses spatial grid bucketing for high-throughput proximity queries.
        Returns:
            List of (SiteRecord, distance_meters) tuples sorted by distance ascending.
        """
        candidates: List[Tuple[SiteRecord, float]] = []
        center_cell = self._get_grid_cell(lat, lon)

        # Check center cell and 8 adjacent neighbor cells
        candidate_items: List[Tuple[str, float, float]] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                cell = (center_cell[0] + dy, center_cell[1] + dx)
                items = self._spatial_grid.get(cell)
                if items:
                    candidate_items.extend(items)

        # Fallback to linear scan if spatial grid is empty
        items_to_check = candidate_items if candidate_items else self._spatial_index

        for site_id, s_lat, s_lon in items_to_check:
            site = self._sites.get(site_id)
            if not site:
                continue
            if site_type is not None and site.site_type != site_type:
                continue

            dist = haversine_distance_meters(lat, lon, s_lat, s_lon)
            if dist <= max_distance_meters:
                candidates.append((site, dist))

        # Sort by distance ascending
        candidates.sort(key=lambda x: x[1])
        return candidates

    def size(self) -> int:
        """Return the total number of registered sites."""
        return len(self._sites)

    def all_sites(self) -> List[SiteRecord]:
        """Return a list of all registered sites."""
        return list(self._sites.values())

    def summary(self) -> Dict[str, Any]:
        """Produce an audit summary of the registry contents."""
        counts_by_type: Dict[str, int] = {}
        counts_by_class: Dict[str, int] = {}

        for site in self._sites.values():
            counts_by_type[site.site_type.value] = (
                counts_by_type.get(site.site_type.value, 0) + 1
            )
            counts_by_class[site.road_class.value] = (
                counts_by_class.get(site.road_class.value, 0) + 1
            )

        return {
            "total_sites": len(self._sites),
            "by_type": counts_by_type,
            "by_class": counts_by_class,
            "spatial_count": len(self._spatial_index),
        }

    def export_csv(self, filepath: str) -> None:
        """Export registry to a standardized CSV file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "site_id",
            "site_type",
            "canonical_name",
            "municipality_code",
            "municipality_name",
            "road_class",
            "street_names",
            "centroid_lat",
            "centroid_lon",
            "source_reference_ids",
            "version",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for site in sorted(self._sites.values(), key=lambda s: s.site_id):
                d = site.to_dict()
                d["street_names"] = ";".join(d["street_names"])
                d["source_reference_ids"] = ";".join(d["source_reference_ids"])
                writer.writerow(d)

    def export_json(self, filepath: str) -> None:
        """Export registry to a JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = [site.to_dict() for site in sorted(self._sites.values(), key=lambda s: s.site_id)]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_from_json(self, filepath: str) -> int:
        """Load sites from a JSON file into the registry."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for item in data:
            site = SiteRecord(
                site_id=item["site_id"],
                site_type=SiteType(item["site_type"]),
                canonical_name=item["canonical_name"],
                municipality_code=item.get("municipality_code"),
                municipality_name=item.get("municipality_name"),
                road_class=RoadClass(item.get("road_class", RoadClass.UNKNOWN.value)),
                street_names=item.get("street_names", []),
                centroid_lat=item.get("centroid_lat"),
                centroid_lon=item.get("centroid_lon"),
                source_reference_ids=item.get("source_reference_ids", []),
                version=item.get("version", "1.0.0"),
            )
            self.register(site)
            count += 1

        return count
