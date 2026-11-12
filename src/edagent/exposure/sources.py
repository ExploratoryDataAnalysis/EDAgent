"""Traffic exposure data source inventory and metadata registry.

Governed by Phase 4 Module A requirements.
Catalogs official traffic exposure and volume sources, documenting geographic coverage,
temporal resolution, measurement methodology, segment compatibility, and missingness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExposureCoverageLevel(str, Enum):
    """Categorization of traffic exposure geographic and network coverage."""
    STATE_ROUTES_ONLY = "STATE_ROUTES_ONLY"
    LOCAL_POINT_COUNTS_ONLY = "LOCAL_POINT_COUNTS_ONLY"
    REGIONAL_MACRO_MODEL = "REGIONAL_MACRO_MODEL"
    NONE = "NONE"


class ExposureTemporalType(str, Enum):
    """Temporal characteristics of the exposure source."""
    CROSS_SECTIONAL_SNAPSHOT = "CROSS_SECTIONAL_SNAPSHOT"
    PERIODIC_COUNT_CYCLE = "PERIODIC_COUNT_CYCLE"
    MODEL_HORIZON_FORECAST = "MODEL_HORIZON_FORECAST"
    ANNUAL_PANEL = "ANNUAL_PANEL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class TrafficExposureSource:
    """Metadata record for an official traffic exposure data source."""
    source_id: str
    source_name: str
    official_publisher: str
    source_url: str
    publication_vintage: str
    geographic_coverage: str
    temporal_coverage: str
    temporal_type: ExposureTemporalType
    coverage_level: ExposureCoverageLevel
    measurement_methodology: str
    segment_id_compatibility: str
    network_coverage_percent: float  # Estimated % of Allegheny County centerline network
    local_road_coverage: bool
    annual_panel_available: bool
    data_format: str
    licensing: str
    known_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "official_publisher": self.official_publisher,
            "source_url": self.source_url,
            "publication_vintage": self.publication_vintage,
            "geographic_coverage": self.geographic_coverage,
            "temporal_coverage": self.temporal_coverage,
            "temporal_type": self.temporal_type.value,
            "coverage_level": self.coverage_level.value,
            "measurement_methodology": self.measurement_methodology,
            "segment_id_compatibility": self.segment_id_compatibility,
            "network_coverage_percent": self.network_coverage_percent,
            "local_road_coverage": self.local_road_coverage,
            "annual_panel_available": self.annual_panel_available,
            "data_format": self.data_format,
            "licensing": self.licensing,
            "known_limitations": self.known_limitations,
        }


def get_official_traffic_sources() -> List[TrafficExposureSource]:
    """Return the authoritative registry of candidate traffic exposure sources."""
    return [
        TrafficExposureSource(
            source_id="EXP-SRC-001",
            source_name="PennDOT RMSSEG State Roads (AADT Attribute Layer)",
            official_publisher="Pennsylvania Department of Transportation (PennDOT), Bureau of Planning and Research",
            source_url="https://data-pennshare.opendata.arcgis.com/datasets/pennshare::pennsylvania-state-roads",
            publication_vintage="2024 Edition",
            geographic_coverage="State-maintained highway segments in Pennsylvania (Allegheny County ~4,303 segments)",
            temporal_coverage="Single modern cross-sectional estimate (CUR_AADT)",
            temporal_type=ExposureTemporalType.CROSS_SECTIONAL_SNAPSHOT,
            coverage_level=ExposureCoverageLevel.STATE_ROUTES_ONLY,
            measurement_methodology=(
                "Annualized daily volume derived from permanent ATRs and rotating 24- to 48-hour "
                "pneumatic tube sample counts factored by seasonal, axle, and day-of-week adjustment factors."
            ),
            segment_id_compatibility=(
                "High for State Routes (matches PennDOT LRS County 02, Route, and Segment). "
                "Completely incompatible with local municipal street centerlines."
            ),
            network_coverage_percent=4.96,  # 4,303 state segments / 86,676 total reference features
            local_road_coverage=False,
            annual_panel_available=False,
            data_format="Esri Feature Service / Shapefile / GeoJSON",
            licensing="PA Commonwealth Open Data License",
            known_limitations=[
                "Zero coverage for local municipal streets and county-maintained roads.",
                "Provides only a single cross-sectional snapshot; lacks 2004–2024 historical annual time-series.",
                "Subject to 3- to 5-year counting latency; inter-count years are linearly factored estimates.",
                "Intersection entering volumes are not provided.",
            ],
        ),
        TrafficExposureSource(
            source_id="EXP-SRC-002",
            source_name="PennDOT Traffic Monitoring System (TMS / TIRe)",
            official_publisher="PennDOT Bureau of Planning and Research, Traffic Monitoring Division",
            source_url="https://www.penndot.pa.gov/ProjectAndPrograms/Planning/Pages/Traffic-Information.aspx",
            publication_vintage="Continuous / Periodic Releases",
            geographic_coverage="Point sensor stations on state highways (~10-15 permanent ATRs in Allegheny County)",
            temporal_coverage="Continuous annual for ATRs; rotating 3- to 5-year cycle for coverage stations",
            temporal_type=ExposureTemporalType.PERIODIC_COUNT_CYCLE,
            coverage_level=ExposureCoverageLevel.STATE_ROUTES_ONLY,
            measurement_methodology=(
                "Continuous automated inductive loop and piezoelectric axle sensors at permanent stations; "
                "portable pneumatic hoses for short-term 48-hour samples."
            ),
            segment_id_compatibility=(
                "Point sensor locations (latitude/longitude and count station ID). Requires manual spatial "
                "attribution and corridor expansion to map to roadway segments."
            ),
            network_coverage_percent=0.02,  # Isolated sensor stations
            local_road_coverage=False,
            annual_panel_available=False,
            data_format="Tabular CSV / Database export",
            licensing="PA Commonwealth Public Records",
            known_limitations=[
                "Station counts represent discrete points, not contiguous network segments.",
                "Zero stations located on local municipal residential streets.",
                "Historical raw continuous count files are not linked to GIS segment centerlines.",
            ],
        ),
        TrafficExposureSource(
            source_id="EXP-SRC-003",
            source_name="Southwestern Pennsylvania Commission (SPC) Regional Travel Demand Model",
            official_publisher="Southwestern Pennsylvania Commission (SPC MPO)",
            source_url="https://www.spcregion.org/programs-services/transportation/planning-tools/travel-demand-modeling/",
            publication_vintage="2020 / 2025 Horizon Models",
            geographic_coverage="10-County Southwestern Pennsylvania Region (Regional transportation network)",
            temporal_coverage="Horizon forecast years (e.g. 2015, 2020, 2025, 2030, 2045)",
            temporal_type=ExposureTemporalType.MODEL_HORIZON_FORECAST,
            coverage_level=ExposureCoverageLevel.REGIONAL_MACRO_MODEL,
            measurement_methodology=(
                "Four-step macroscopic travel demand modeling (trip generation, distribution, mode choice, assignment) "
                "calibrated to regional survey data and select highway counts."
            ),
            segment_id_compatibility=(
                "Incompatible with physical street centerlines. Uses aggregated network links and "
                "Traffic Analysis Zone (TAZ) centroid connectors."
            ),
            network_coverage_percent=12.5,
            local_road_coverage=False,
            annual_panel_available=False,
            data_format="TransCAD / Shapefile network",
            licensing="MPO Internal / Available upon agency data request",
            known_limitations=[
                "Model-simulated traffic volumes, not empirical empirical traffic measurements.",
                "Local neighborhood and residential streets are represented as centroid abstractions.",
                "Outputs reflect 5-year model scenario horizons, not historical annual empirical reality.",
            ],
        ),
        TrafficExposureSource(
            source_id="EXP-SRC-004",
            source_name="Allegheny County Street Centerlines Database",
            official_publisher="Allegheny County Division of Computer Services (GIS)",
            source_url="https://open-data-alleghenycountygis.hub.arcgis.com/",
            publication_vintage="October 2026 Snapshot",
            geographic_coverage="Allegheny County (82,365 polyline segments)",
            temporal_coverage="Single modern baseline (2026)",
            temporal_type=ExposureTemporalType.UNAVAILABLE,
            coverage_level=ExposureCoverageLevel.NONE,
            measurement_methodology="No traffic volume measurement program maintained.",
            segment_id_compatibility="100% compatible with county centerline segment IDs (SEG:AC:...)",
            network_coverage_percent=0.0,
            local_road_coverage=True,  # Road geometry exists, but 0% exposure data
            annual_panel_available=False,
            data_format="Shapefile archive (ZIP)",
            licensing="Creative Commons / Allegheny County Open Data",
            known_limitations=[
                "Contains zero traffic volume, count, or AADT fields.",
                "Speed limits and traffic attributes are officially unmaintained per County Addressing Data Model.",
            ],
        ),
        TrafficExposureSource(
            source_id="EXP-SRC-005",
            source_name="City of Pittsburgh DOMI Traffic Counts (WPRDC)",
            official_publisher="City of Pittsburgh Department of Mobility and Infrastructure / WPRDC",
            source_url="https://data.wprdc.org/dataset/city-traffic-counts",
            publication_vintage="2017–2020 Study Data",
            geographic_coverage="Selected municipal streets within City of Pittsburgh only (~400 count points)",
            temporal_coverage="Intermittent 7-day snapshots between 2017 and 2020",
            temporal_type=ExposureTemporalType.PERIODIC_COUNT_CYCLE,
            coverage_level=ExposureCoverageLevel.LOCAL_POINT_COUNTS_ONLY,
            measurement_methodology="Short-term portable pneumatic tube counts for local traffic calming and speed hump evaluations.",
            segment_id_compatibility="Low. Recorded as discrete coordinate points and text street names without segment LRS.",
            network_coverage_percent=0.48,  # ~400 points / 82,365 segments
            local_road_coverage=True,
            annual_panel_available=False,
            data_format="Tabular CSV",
            licensing="Creative Commons Attribution",
            known_limitations=[
                "Extremely sparse spatial coverage (covers <0.5% of Allegheny County centerlines).",
                "Restricted to City of Pittsburgh; 0% coverage across the other 129 municipalities in the county.",
                "Zero historical coverage prior to 2017.",
                "Conducted in response to neighborhood complaints, introducing severe traffic calming selection bias.",
            ],
        ),
    ]
