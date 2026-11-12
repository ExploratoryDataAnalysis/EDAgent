"""Schemas and contracts for retrospective crash severity association analysis.

Governed by Project Plan v2 (§8, §14, §18) and Phase 4 Module C requirements.
Enforces that severity results are strictly retrospective associations, never to be
represented as pre-crash predictive risk or causal probabilities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SeverityOutcomeDefinition(str, Enum):
    """Standardized injury severity outcome definitions under KABCO scale."""

    FATAL_OR_MAJ_INJ = "FATAL_OR_MAJ_INJ"  # Levels K (Fatal) or A (Suspected Serious Injury)
    FATAL_ONLY = "FATAL_ONLY"              # Level K only
    ANY_INJURY = "ANY_INJURY"              # Levels K, A, B, or C


@dataclass(frozen=True)
class RetrospectiveAssociationMetric:
    """Categorical association metric with Benjamini-Hochberg multiplicity correction."""

    feature_name: str
    cramers_v: float
    degrees_of_freedom: int
    p_value: float
    benjamini_hochberg_q: float
    association_strength: str
    post_crash_observed: bool
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SeverityModelPerformance:
    """Retrospective classification model performance metrics."""

    model_name: str
    feature_set: str
    includes_collision_type: bool
    test_records: int
    test_prevalence_percent: float
    average_precision: float
    ap_interval_95: Tuple[float, float]
    roc_auc: float
    balanced_accuracy: float
    brier_score_uncalibrated: float

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["ap_interval_lower"] = self.ap_interval_95[0]
        res["ap_interval_upper"] = self.ap_interval_95[1]
        del res["ap_interval_95"]
        return res


@dataclass
class RetrospectiveSeverityAudit:
    """Canonical audit ledger of retrospective severity modeling and limitations."""

    analysis_type: str = "RETROSPECTIVE_SEVERITY_ASSOCIATION"
    analysis_period: str = "2016-2023"
    is_predictive: bool = False
    is_causal: bool = False
    total_dataset_records: int = 248810
    known_severity_records: int = 205544
    known_severity_percent: float = 82.61
    severe_outcome_prevalence_percent: float = 4.44
    temporal_code_break_year: int = 2016
    models: List[SeverityModelPerformance] = field(default_factory=list)
    associations: List[RetrospectiveAssociationMetric] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_type": self.analysis_type,
            "analysis_period": self.analysis_period,
            "is_predictive": self.is_predictive,
            "is_causal": self.is_causal,
            "total_dataset_records": self.total_dataset_records,
            "known_severity_records": self.known_severity_records,
            "known_severity_percent": self.known_severity_percent,
            "severe_outcome_prevalence_percent": self.severe_outcome_prevalence_percent,
            "temporal_code_break_year": self.temporal_code_break_year,
            "models": [m.to_dict() for m in self.models],
            "associations": [a.to_dict() for a in self.associations],
            "limitations": self.limitations,
        }
