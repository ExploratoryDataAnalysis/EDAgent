"""Retrospective crash severity association and limitations module.

Governed by Project Plan v2 (§8, §14, §18) and Phase 4 Module C requirements.
"""

from edagent.severity.retrospective import RetrospectiveSeverityAnalyzer
from edagent.severity.schemas import (
    RetrospectiveAssociationMetric,
    RetrospectiveSeverityAudit,
    SeverityModelPerformance,
    SeverityOutcomeDefinition,
)

__all__ = [
    "RetrospectiveAssociationMetric",
    "RetrospectiveSeverityAnalyzer",
    "RetrospectiveSeverityAudit",
    "SeverityModelPerformance",
    "SeverityOutcomeDefinition",
]
