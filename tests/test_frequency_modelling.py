"""Comprehensive test suite for Phase 4 Module B: Frequency Modelling & Historical Concentration.

Verifies:
- Poisson baseline fitting, exposure offset, and deviance diagnostics.
- Negative Binomial overdispersion evaluation (alpha, Cameron-Trivedi test, LR test).
- Chronological validation and zero-leakage enforcement.
- Output contract invariants (expected frequency None when blocked).
- Missing and invalid exposure handling.
- Historical crash concentration reporting pathway.
- Model persistence and checksum verification.
- Backend API route integration and graceful prediction blocking.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List

import numpy as np
import pytest

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
from edagent.roadway.schema import RoadClass


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def synthetic_records() -> List[SiteYearRecord]:
    """Generate controlled site-year records across 2016-2024 for testing."""
    records = []
    rng = np.random.default_rng(42)

    # 20 sites across 9 years (2016-2024)
    for site_idx in range(1, 21):
        site_id = f"SEG:02:SR00{site_idx:02d}:0010"
        road_class = RoadClass.INTERSTATE if site_idx <= 5 else RoadClass.STATE_ROUTE
        length_km = 0.8
        base_rate = 3.5 if road_class == RoadClass.INTERSTATE else 1.2

        for year in range(2016, 2025):
            # Exposure in Million VMT
            exp = 0.5 + 0.05 * (site_idx % 3)
            # True mean with overdispersion
            mu = exp * base_rate
            # Draw from negative binomial: n = 1/alpha = 5, p = n / (n + mu)
            n_param = 5.0
            p_param = n_param / (n_param + mu)
            count = int(rng.negative_binomial(n_param, p_param))

            records.append(
                SiteYearRecord(
                    site_id=site_id,
                    year=year,
                    crash_count=count,
                    is_zero_crash=(count == 0),
                    road_class=road_class,
                    length_km=length_km,
                    traffic_exposure=exp,
                )
            )
    return records


# -----------------------------------------------------------------------------
# 1. Output Contract & Invariants Tests
# -----------------------------------------------------------------------------

class TestOutputContract:
    def test_valid_prediction_contract(self):
        pred = SiteYearPrediction(
            site_id="SEG:02:SR0022:0040",
            prediction_year=2024,
            expected_crash_frequency=2.45,
            model_name="Poisson_GLM",
            model_version="1.0.0",
            exposure_basis="Annual Daily VMT",
            training_period="2016-2020",
            validation_period="2021-2024",
            prediction_status=PredictionStatus.VALID_PREDICTION,
            confidence_interval_95=(1.8, 3.2),
        )
        assert pred.expected_crash_frequency == 2.45
        d = pred.to_dict()
        assert d["prediction_status"] == "VALID_PREDICTION"
        assert d["ci_95_lower"] == 1.8
        assert d["ci_95_upper"] == 3.2

    def test_blocked_prediction_must_have_none_expected_frequency(self):
        # Invariant: expected_frequency must be None when status != VALID_PREDICTION
        with pytest.raises(ValueError, match="expected_crash_frequency must be None"):
            SiteYearPrediction(
                site_id="SEG:02:SR0022:0040",
                prediction_year=2024,
                expected_crash_frequency=2.45,  # Invalid: not None!
                model_name="Poisson_GLM",
                model_version="1.0.0",
                exposure_basis="UNAVAILABLE",
                training_period="2016-2020",
                validation_period="2021-2024",
                prediction_status=PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE,
            )

    def test_valid_blocked_prediction(self):
        pred = SiteYearPrediction(
            site_id="SEG:02:SR0022:0040",
            prediction_year=2024,
            expected_crash_frequency=None,
            model_name="Poisson_GLM",
            model_version="1.0.0",
            exposure_basis="UNAVAILABLE",
            training_period="2016-2020",
            validation_period="2021-2024",
            prediction_status=PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE,
            limitations=["Predictive modeling blocked under Module A NO-GO decision."],
        )
        assert pred.expected_crash_frequency is None
        assert pred.prediction_status == PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE


# -----------------------------------------------------------------------------
# 2. Data Preparation & Leakage Prevention Tests
# -----------------------------------------------------------------------------

class TestDataPreparation:
    def test_validate_site_identity(self):
        preparer = SiteYearDataPreparer()
        assert preparer.validate_site_identity("SEG:02:SR0022:0040") is True
        assert preparer.validate_site_identity("SEG:AC:12345") is True
        assert preparer.validate_site_identity("INT:123456789abc") is True
        assert preparer.validate_site_identity("UNKNOWN_ID") is False
        assert preparer.validate_site_identity("") is False

    def test_chronological_separation_and_leakage_detection(self):
        preparer = SiteYearDataPreparer()
        # Train years overlapping test years must raise TemporalLeakageError
        with pytest.raises(TemporalLeakageError, match="Chronological separation violated"):
            ModellingDataset(
                train_records=[],
                test_records=[],
                train_years=(2016, 2017, 2018, 2021),
                test_years=(2020, 2021, 2022),
                feature_names=[],
                has_valid_exposure=False,
                exposure_basis="UNAVAILABLE",
            )

    def test_require_exposure_raises_when_missing(self):
        preparer = SiteYearDataPreparer(
            default_train_years=(2016, 2017),
            default_test_years=(2018, 2019),
        )
        sample_rows = [
            {"site_id": "SEG:02:SR0001:0010", "year": "2016", "crash_count": "1", "traffic_exposure": ""},
            {"site_id": "SEG:02:SR0001:0010", "year": "2018", "crash_count": "0", "traffic_exposure": ""},
        ]
        with pytest.raises(InsufficientExposureError, match="requires verified traffic exposure"):
            preparer.prepare_dataset(sample_rows, require_exposure=True)


# -----------------------------------------------------------------------------
# 3. Poisson GLM Baseline Tests
# -----------------------------------------------------------------------------

class TestPoissonBaseline:
    def test_poisson_fit_and_diagnostics(self, synthetic_records):
        train = [r for r in synthetic_records if r.year <= 2020]
        test = [r for r in synthetic_records if r.year > 2020]

        model = PoissonRegressionModel(reference_road_class=RoadClass.STATE_ROUTE)
        fit = model.fit(train, require_exposure=True)

        assert fit.converged is True
        assert "Intercept" in fit.coefficients
        assert fit.degrees_of_freedom > 0
        assert fit.log_likelihood < 0.0
        assert fit.aic > 0.0
        assert fit.dispersion_ratio > 0.0

        # Out-of-sample evaluation
        metrics = model.evaluate_out_of_sample(test)
        assert metrics.rmse > 0.0
        assert metrics.mae > 0.0
        assert metrics.calibration_ratio > 0.0

    def test_poisson_predict_without_exposure_returns_blocked(self, synthetic_records):
        train = [r for r in synthetic_records if r.year <= 2020]
        test_missing_exp = [
            SiteYearRecord(
                site_id=r.site_id,
                year=r.year,
                crash_count=r.crash_count,
                is_zero_crash=r.is_zero_crash,
                road_class=r.road_class,
                length_km=r.length_km,
                traffic_exposure=None,  # Missing exposure
            )
            for r in synthetic_records if r.year > 2020
        ]

        model = PoissonRegressionModel()
        model.fit(train, require_exposure=True)
        preds = model.predict(test_missing_exp)

        assert len(preds) == len(test_missing_exp)
        for p in preds:
            assert p.prediction_status == PredictionStatus.BLOCKED_INSUFFICIENT_EXPOSURE
            assert p.expected_crash_frequency is None


# -----------------------------------------------------------------------------
# 4. Negative Binomial (NB2) & Overdispersion Tests
# -----------------------------------------------------------------------------

class TestNegativeBinomial:
    def test_nb2_fit_and_overdispersion_detection(self, synthetic_records):
        train = [r for r in synthetic_records if r.year <= 2020]
        test = [r for r in synthetic_records if r.year > 2020]

        poisson_model = PoissonRegressionModel()
        poisson_model.fit(train, require_exposure=True)

        nb_model = NegativeBinomialModel()
        nb_fit = nb_model.fit(train, require_exposure=True, poisson_baseline=poisson_model)

        assert nb_fit.converged is True
        assert nb_fit.alpha > 0.0
        assert nb_fit.cameron_trivedi_t_stat != 0.0
        assert nb_fit.lr_test_vs_poisson >= 0.0

        comp = nb_model.compare_with_poisson(poisson_model, test)
        assert comp.recommended_model in ("Negative_Binomial_NB2", "Poisson_GLM")
        assert len(comp.selection_justification) > 10


# -----------------------------------------------------------------------------
# 5. Chronological Validation & Expanding Window Tests
# -----------------------------------------------------------------------------

class TestChronologicalValidation:
    def test_expanding_window_evaluation(self, synthetic_records):
        folds = ChronologicalValidator.evaluate_expanding_windows(
            records=synthetic_records,
            start_train_years=(2016, 2017, 2018),
            eval_years=(2019, 2020, 2021),
        )
        assert len(folds) == 3
        for f in folds:
            assert f.rmse > 0.0
            assert f.calibration_ratio > 0.0
            assert f.num_train_records > 0
            assert f.num_val_records > 0

    def test_leakage_audit_catches_leakage(self, synthetic_records):
        tr = [r for r in synthetic_records if r.year <= 2021]  # Contains 2021
        te = [r for r in synthetic_records if r.year >= 2020]  # Min is 2020 <= 2021

        with pytest.raises(TemporalLeakageError, match="Data leakage detected"):
            ChronologicalValidator.audit_leakage(tr, te)


# -----------------------------------------------------------------------------
# 6. Model Persistence Tests
# -----------------------------------------------------------------------------

class TestModelPersistence:
    def test_manifest_roundtrip(self, tmp_path):
        manifest_path = tmp_path / "model_manifest.json"
        m = ModelManifest(
            model_name="Negative_Binomial_NB2",
            model_version="1.0.0",
            software_version="1.0.0",
            crosswalk_version="1.0.0",
            training_dataset_checksum="abc123hash",
            exposure_dataset_checksum="UNAVAILABLE",
            training_period="2016-2020",
            validation_period="2021-2024",
            feature_definitions=["Intercept", "length_km"],
            parameters={"Intercept": 0.5, "length_km": 0.2},
            standard_errors={"Intercept": 0.05, "length_km": 0.02},
            dispersion_parameter_alpha=0.18,
            metrics={"aic": 1250.4, "bic": 1265.1},
            approval_status="NOT_APPROVED_FOR_PRODUCTION",
            limitations=["Controlled benchmark only"],
        )
        saved = ModelPersistenceManager.save_manifest(manifest_path, m)
        assert saved.exists()

        loaded = ModelPersistenceManager.load_manifest(manifest_path)
        assert loaded["model_name"] == "Negative_Binomial_NB2"
        assert loaded["dispersion_parameter_alpha"] == 0.18


# -----------------------------------------------------------------------------
# 7. Historical Crash Concentration Tests
# -----------------------------------------------------------------------------

class TestHistoricalCrashConcentration:
    @pytest.mark.skip(reason="Legacy v1.0.0 release artifact is unapproved; provisional contract tested separately")
    def test_concentration_csv_exists_and_valid(self):
        csv_path = Path("data/exports/frequency/historical_crash_concentration.csv")
        assert csv_path.exists()
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [next(reader) for _ in range(20)]
            assert len(rows) == 20
            first = rows[0]
            assert "site_id" in first
            assert "crash_density_per_km" in first
            assert "persistence_category" in first
            assert "road_class_percentile" in first
            assert float(first["road_class_percentile"]) > 0.0

    def test_persistence_category_enum(self):
        assert PersistenceCategory.PERSISTENT_HIGH_HAZARD.value == "PERSISTENT_HIGH_HAZARD"
        assert PersistenceCategory.EMERGING_HIGH_HAZARD.value == "EMERGING_HIGH_HAZARD"
        assert PersistenceCategory.HISTORIC_RESOLVED.value == "HISTORIC_RESOLVED"
        assert PersistenceCategory.TRANSIENT_STOCHASTIC.value == "TRANSIENT_STOCHASTIC"


# -----------------------------------------------------------------------------
# 8. API Integration Tests
# -----------------------------------------------------------------------------

class TestFrequencyAPIIntegration:
    @pytest.fixture
    def client(self):
        import sys
        sys.path.insert(0, str(Path("EDAgent_Completed_Extension/EDAgent/backend").resolve()))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.endpoints.frequency import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/frequency")
        return TestClient(app)

    def test_status_endpoint(self, client):
        data = client.get("/api/v1/frequency/status").json()["data"]
        assert data["predictive_frequency_modeling"]["status"] == "BLOCKED"
        assert data["mandated_active_pathway"]["status"] == "BLOCKED_PENDING_REVIEW"
        assert data["metadata"]["coverage_status"] == "UNVERIFIED"

    def test_prediction_gracefully_blocked(self, client):
        data = client.get("/api/v1/frequency/predictions/SEG:02:SR0376:0744?year=2024").json()["data"]
        assert data["expected_crash_frequency"] is None
        assert data["historical_concentration_alternative"] is None

    def test_stale_artifact_is_not_served(self, client, tmp_path, monkeypatch):
        from app.api.v1.endpoints import frequency
        stale = tmp_path / 'stale.csv'
        stale.write_text('site_id,total_crashes_2004_2024\nexample,999\n', encoding='utf8')
        monkeypatch.setattr(frequency, 'CONCENTRATION_CSV_PATH', stale)
        assert client.get('/api/v1/frequency/concentration/example').status_code == 503
        data = client.get('/api/v1/frequency/predictions/example').json()['data']
        assert data['historical_concentration_alternative'] is None

    @pytest.mark.parametrize("path", ["concentration/SEG:02:SR0376:0744", "concentration/top", "concentration/annual", "concentration/breakdown", "concentration/geojson", "severity/retrospective"])
    def test_unreviewed_outputs_blocked(self, client, path):
        assert client.get("/api/v1/frequency/" + path).status_code == 503
