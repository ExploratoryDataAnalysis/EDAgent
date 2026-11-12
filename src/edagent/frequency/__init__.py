"""Frequency modelling, statistical baseline, and historical concentration package.

Governed by Project Plan v2 (§8, §18) and Phase 4 Module B requirements.
"""

from edagent.frequency.concentration import (
    HistoricalConcentrationAnalyzer,
    PersistenceCategory,
    SiteConcentrationRecord,
)
from edagent.frequency.data_preparation import (
    InsufficientExposureError,
    ModellingDataset,
    SiteYearDataPreparer,
    SiteYearRecord,
    TemporalLeakageError,
)
from edagent.frequency.negative_binomial import (
    ModelComparisonReport,
    NegativeBinomialFit,
    NegativeBinomialModel,
)
from edagent.frequency.output_contract import PredictionStatus, SiteYearPrediction
from edagent.frequency.persistence import ModelManifest, ModelPersistenceManager
from edagent.frequency.poisson import (
    OutOfSampleMetrics,
    PoissonModelFit,
    PoissonRegressionModel,
)
from edagent.frequency.validation import (
    ChronologicalValidator,
    ExpandingWindowFold,
    ResidualDiagnostics,
    StratifiedCalibration,
)

__all__ = [
    "ChronologicalValidator",
    "ExpandingWindowFold",
    "HistoricalConcentrationAnalyzer",
    "InsufficientExposureError",
    "ModelComparisonReport",
    "ModelManifest",
    "ModelPersistenceManager",
    "ModellingDataset",
    "NegativeBinomialFit",
    "NegativeBinomialModel",
    "OutOfSampleMetrics",
    "PersistenceCategory",
    "PoissonModelFit",
    "PoissonRegressionModel",
    "PredictionStatus",
    "ResidualDiagnostics",
    "SiteConcentrationRecord",
    "SiteYearDataPreparer",
    "SiteYearPrediction",
    "SiteYearRecord",
    "StratifiedCalibration",
    "TemporalLeakageError",
]
