"""Output contract and schema specifications for site-year frequency modelling.

Governed by Project Plan v2 (§8, §18) and Phase 4 Module B requirements.
Enforces the core invariant that expected crash frequency is a model prediction,
never to be confused with observed historical crash counts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PredictionStatus(str, Enum):
    """Execution and validity status for site-year crash frequency predictions."""

    VALID_PREDICTION = "VALID_PREDICTION"
    BLOCKED_INSUFFICIENT_EXPOSURE = "BLOCKED_INSUFFICIENT_EXPOSURE"
    UNSUPPORTED_PREDICTION = "UNSUPPORTED_PREDICTION"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"


@dataclass(frozen=True)
class SiteYearPrediction:
    """Stable, documented output contract for site-year frequency predictions.

    Attributes:
        site_id: Canonical physical site identifier (e.g., SEG:02:SR0022:0040).
        prediction_year: Evaluation or forecast calendar year.
        expected_crash_frequency: Model-predicted mean annual crash frequency (E[Y]).
            Strictly None when prediction_status != VALID_PREDICTION.
        model_name: Identifier of the fitted model family (e.g., Poisson_GLM, Negative_Binomial_NB2).
        model_version: Semantic version of the model artifact.
        exposure_basis: Documentation of the exposure offset used (e.g., "AADT * Length_km * 365"
            or "UNAVAILABLE").
        training_period: Calendar year range of the training split (e.g., "2016-2020").
        validation_period: Calendar year range of the out-of-sample validation split (e.g., "2021-2024").
        prediction_status: Formal validity status flag.
        limitations: Explicit list of analytical and domain caveats.
        confidence_interval_95: Statistically justified 95% Wald or profile confidence interval,
            if available.
    """

    site_id: str
    prediction_year: int
    expected_crash_frequency: Optional[float]
    model_name: str
    model_version: str
    exposure_basis: str
    training_period: str
    validation_period: str
    prediction_status: PredictionStatus
    limitations: List[str] = field(default_factory=list)
    confidence_interval_95: Optional[Tuple[float, float]] = None

    def __post_init__(self) -> None:
        """Validate output contract invariants."""
        # Invariant 1: Expected frequency must be None if status is blocked or unsupported
        if self.prediction_status != PredictionStatus.VALID_PREDICTION:
            if self.expected_crash_frequency is not None:
                raise ValueError(
                    f"expected_crash_frequency must be None when prediction_status is "
                    f"'{self.prediction_status.value}', got {self.expected_crash_frequency}."
                )

        # Invariant 2: Expected frequency must be non-negative if present
        if self.expected_crash_frequency is not None and self.expected_crash_frequency < 0.0:
            raise ValueError(
                f"expected_crash_frequency cannot be negative, got {self.expected_crash_frequency}."
            )

        # Invariant 3: Prediction intervals must be ordered
        if self.confidence_interval_95 is not None:
            lower, upper = self.confidence_interval_95
            if lower < 0.0 or upper < lower:
                raise ValueError(
                    f"Invalid confidence interval: lower={lower}, upper={upper}."
                )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize contract to standard dictionary representation."""
        res = asdict(self)
        res["prediction_status"] = self.prediction_status.value
        if self.confidence_interval_95 is not None:
            res["ci_95_lower"] = self.confidence_interval_95[0]
            res["ci_95_upper"] = self.confidence_interval_95[1]
        else:
            res["ci_95_lower"] = None
            res["ci_95_upper"] = None
        del res["confidence_interval_95"]
        return res
