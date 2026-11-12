"""Traffic exposure research, coverage assessment, panel prototyping, and feasibility module.

Governed by Phase 4 Module A requirements and Project Plan v2 (§8, §14, §18).
"""

from edagent.exposure.coverage import TrafficCoverageAssessment
from edagent.exposure.feasibility import (
    FeasibilityCriterion,
    FeasibilityStatus,
    OverallDecision,
    TrafficFeasibilityEvaluator,
)
from edagent.exposure.panel import SiteYearPanelBuilder
from edagent.exposure.sources import (
    ExposureCoverageLevel,
    ExposureTemporalType,
    TrafficExposureSource,
    get_official_traffic_sources,
)

__all__ = [
    "ExposureCoverageLevel",
    "ExposureTemporalType",
    "TrafficExposureSource",
    "get_official_traffic_sources",
    "TrafficCoverageAssessment",
    "SiteYearPanelBuilder",
    "FeasibilityStatus",
    "OverallDecision",
    "FeasibilityCriterion",
    "TrafficFeasibilityEvaluator",
]
