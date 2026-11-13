"""Traffic exposure feasibility assessment and decision engine.

Developed under historical Project Plan v2 (§8, §14, §18); v3 governs release scope.
Evaluates historical statistical and operational feasibility criteria.
Site-level screening and frequency modelling are outside v3 release scope.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List


class FeasibilityStatus(str, Enum):
    """Evaluation outcome for an individual feasibility criterion."""
    PASS = "PASS"
    FAIL = "FAIL"
    CONDITIONAL = "CONDITIONAL"


class OverallDecision(str, Enum):
    """Authoritative decision regarding predictive site-year frequency modelling."""
    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"
    NO_GO = "NO_GO"


@dataclass
class FeasibilityCriterion:
    """Evaluation record for a specific scientific or data prerequisite."""
    criterion_id: str
    name: str
    required_threshold: str
    empirical_value: str
    status: FeasibilityStatus
    critical_implication: str
    violates_guidelines_if_proceeded: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "name": self.name,
            "required_threshold": self.required_threshold,
            "empirical_value": self.empirical_value,
            "status": self.status.value,
            "critical_implication": self.critical_implication,
            "violates_guidelines_if_proceeded": self.violates_guidelines_if_proceeded,
        }


class TrafficFeasibilityEvaluator:
    """Evaluates prerequisites for site-year frequency modelling."""

    @staticmethod
    def get_standard_criteria() -> List[FeasibilityCriterion]:
        """Return the explicit, pre-defined feasibility criteria."""
        return [
            FeasibilityCriterion(
                criterion_id="CRIT-01",
                name="Network-Wide Exposure Availability",
                required_threshold=">= 80.0% of physical roadway sites have verified exposure measurements",
                empirical_value="0.00% annual panel coverage (at best 4.96% modern state-route snapshot)",
                status=FeasibilityStatus.FAIL,
                critical_implication=(
                    "Over 95% of the physical roadway network lacks traffic exposure. "
                    "Models would lack the necessary exposure offset (AADT * length)."
                ),
                violates_guidelines_if_proceeded=True,
            ),
            FeasibilityCriterion(
                criterion_id="CRIT-02",
                name="Temporal Exposure Continuity",
                required_threshold=">= 80.0% of historical study years (2004–2024) have verified annual counts",
                empirical_value="0.00% annual panel available (single cross-sectional snapshot only)",
                status=FeasibilityStatus.FAIL,
                critical_implication=(
                    "A single modern AADT snapshot cannot be backward-projected across 21 years "
                    "of economic fluctuations and pandemic travel shifts without fabricating unsupported numbers."
                ),
                violates_guidelines_if_proceeded=True,
            ),
            FeasibilityCriterion(
                criterion_id="CRIT-03",
                name="Road-Class Representation & Selection Bias",
                required_threshold="Representative coverage across all functional classes including local roads",
                empirical_value="100.0% missing on local municipal streets (which comprise 73.4% of unique crash sites)",
                status=FeasibilityStatus.FAIL,
                critical_implication=(
                    "Fitting a model exclusively on State Routes introduces severe selection bias, "
                    "erasing municipal residential streets, pedestrian corridors, and local intersections."
                ),
                violates_guidelines_if_proceeded=True,
            ),
            FeasibilityCriterion(
                criterion_id="CRIT-04",
                name="Legitimate Zero-Crash Observation Frame",
                required_threshold="Authoritative historical existence ledger for unmonitored road segments",
                empirical_value="Single modern 2026 centerline snapshot; zero annual historical existence records",
                status=FeasibilityStatus.FAIL,
                critical_implication=(
                    "Assuming unmonitored roads existed continuously from 2004–2024 would manufacture "
                    "synthetic zero-crash site-years in direct violation of project guidelines."
                ),
                violates_guidelines_if_proceeded=True,
            ),
            FeasibilityCriterion(
                criterion_id="CRIT-05",
                name="Intersection Exposure Compatibility",
                required_threshold="Entering vehicle volumes for all intersection approaches",
                empirical_value="0.00% entering volume available on municipal and state intersections",
                status=FeasibilityStatus.FAIL,
                critical_implication=(
                    "Intersection exposure cannot be approximated by segment length * AADT. "
                    "Intersection frequency modelling is mathematically blocked."
                ),
                violates_guidelines_if_proceeded=True,
            ),
        ]

    @classmethod
    def evaluate(cls) -> Dict[str, Any]:
        """Perform authoritative feasibility evaluation and render binding decision."""
        criteria = cls.get_standard_criteria()
        fail_count = sum(1 for c in criteria if c.status == FeasibilityStatus.FAIL)

        decision = OverallDecision.NO_GO
        recommended_action = (
            "Project Plan v3 excludes site-level historical screening, frequency and Empirical Bayes modelling, "
            "and real-site treatment estimates from release. Use reviewed v6 aggregates and diagnostic geography; "
            "retain severity results for review and use hypothetical inputs for intervention arithmetic."
        )

        return {
            "overall_decision": decision.value,
            "evaluation_status": "DECISIVE_NO_GO",
            "criteria_evaluated_n": len(criteria),
            "criteria_failed_n": fail_count,
            "binding_decision_summary": (
                "Site-year crash frequency modelling is STATISTICALLY AND OPERATIONALLY UNFEASIBLE. "
                "All 5 scientific feasibility criteria failed."
            ),
            "mandated_alternative": recommended_action,
            "prohibited_actions": [
                "Do NOT fit Poisson or Negative Binomial regression models using invented exposure offsets.",
                "Do NOT backward-project a single modern AADT snapshot to represent 2004–2024 history.",
                "Do NOT manufacture synthetic zero-crash site-years for unmonitored local streets.",
                "Do NOT multiply generic CMFs without verified local exposure and calibrated SPFs.",
            ],
            "criteria": [c.to_dict() for c in criteria],
        }

    @classmethod
    def export_decision_matrix(cls, output_filepath: str) -> None:
        """Export the decision criteria matrix to CSV."""
        path = Path(output_filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        eval_result = cls.evaluate()

        fieldnames = [
            "criterion_id",
            "name",
            "required_threshold",
            "empirical_value",
            "status",
            "critical_implication",
            "violates_guidelines_if_proceeded",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for c in eval_result["criteria"]:
                writer.writerow(c)
