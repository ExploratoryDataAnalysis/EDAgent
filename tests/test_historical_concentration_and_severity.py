"""Comprehensive test suite for Phase 4 Module C: Historical Concentration & Retrospective Severity.

Verifies:
- Multidimensional historical concentration calculations (by year, road class, site type).
- Visibility of unmatched, ambiguous, and missing-coordinate records.
- Geographic coordinate assignment and GeoJSON visualization contracts.
- Retrospective severity audit (outcome definition, 2016 code break, class imbalance).
- Distinction between retrospective associations and predictive forecasting.
- API response metadata contracts (analysis_type, analysis_period, is_predictive=False).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

# Ensure src and backend are in sys.path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("EDAgent_Completed_Extension/EDAgent/backend").resolve()))

from edagent.severity.retrospective import RetrospectiveSeverityAnalyzer
from edagent.severity.schemas import (
    RetrospectiveAssociationMetric,
    RetrospectiveSeverityAudit,
    SeverityModelPerformance,
)


class TestHistoricalConcentrationStratifications:
    @pytest.mark.skip(reason="Legacy v1.0.0 release artifact is unapproved; provisional contract tested separately")
    def test_annual_concentration_summary(self):
        csv_path = Path("data/exports/frequency/historical_concentration_by_year.csv")
        assert csv_path.exists()

        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)

        assert len(rows) == 21  # 2004 to 2024
        assert int(rows[0]["crash_year"]) == 2004
        assert int(rows[-1]["crash_year"]) == 2024

        total_crashes = sum(int(r["total_crashes"]) for r in rows)
        matched_crashes = sum(int(r["matched_crashes"]) for r in rows)
        ambiguous_crashes = sum(int(r["ambiguous_crashes"]) for r in rows)
        unmatched_crashes = sum(int(r["unmatched_crashes"]) for r in rows)

        assert total_crashes == 248810
        assert matched_crashes == 187068
        assert ambiguous_crashes == 5856
        assert unmatched_crashes == 55886

        # Invariant checks
        for r in rows:
            assert r["is_predictive"] == "False"
            assert r["analysis_period"] == "2004-2024"
            assert float(r["missing_coord_percent"].replace("%", "")) >= 0.0

    @pytest.mark.skip(reason="Legacy v1.0.0 release artifact is unapproved; provisional contract tested separately")
    def test_road_class_concentration_summary(self):
        csv_path = Path("data/exports/frequency/historical_concentration_by_road_class.csv")
        assert csv_path.exists()

        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)

        assert len(rows) == 5
        classes = {r["road_class"] for r in rows}
        assert classes == {"STATE_ROUTE", "INTERSTATE", "LOCAL_STREET", "COUNTY_ROAD", "RAMP"}

        total_crashes = sum(int(r["total_crashes"]) for r in rows)
        matched_crashes = sum(int(r["matched_crashes"]) for r in rows)
        assert total_crashes == 248810
        assert matched_crashes == 187068

        for r in rows:
            assert r["is_predictive"] == "False"
            assert int(r["unique_matched_sites"]) > 0

    @pytest.mark.skip(reason="Legacy v1.0.0 release artifact is unapproved; provisional contract tested separately")
    def test_site_type_concentration_summary(self):
        csv_path = Path("data/exports/frequency/historical_concentration_by_site_type.csv")
        assert csv_path.exists()

        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)

        assert len(rows) == 2
        types = {r["site_type"] for r in rows}
        assert types == {"INTERSECTION", "ROAD_SEGMENT"}

        total_crashes = sum(int(r["total_crashes"]) for r in rows)
        matched_crashes = sum(int(r["matched_crashes"]) for r in rows)
        assert total_crashes == 248810
        assert matched_crashes == 187068


class TestGeographicVisualizations:
    @pytest.mark.skip(reason="Legacy v1.0.0 release artifact is unapproved; provisional contract tested separately")
    def test_top_sites_geographic_csv(self):
        csv_path = Path("data/exports/frequency/top_concentration_sites_geographic.csv")
        assert csv_path.exists()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 100
        for r in rows:
            assert r["is_predictive"] == "False"
            assert r["analysis_period"] == "2004-2024"
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            # Bounding box for Allegheny County region
            assert 40.1 <= lat <= 40.8
            assert -80.4 <= lon <= -79.6
            assert float(r["crash_density_per_km"]) > 0.0

    @pytest.mark.skip(reason="Legacy v1.0.0 release artifact is unapproved; provisional contract tested separately")
    def test_top_sites_geojson(self):
        json_path = Path("data/exports/frequency/top_concentration_sites_geographic.geojson")
        assert json_path.exists()

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["type"] == "FeatureCollection"
        assert data["metadata"]["is_predictive"] is False
        assert data["metadata"]["analysis_period"] == "2004-2024"
        assert len(data["features"]) == 100

        f0 = data["features"][0]
        assert f0["type"] == "Feature"
        assert f0["geometry"]["type"] == "Point"
        coords = f0["geometry"]["coordinates"]
        assert len(coords) == 2
        assert -80.4 <= coords[0] <= -79.6  # longitude
        assert 40.1 <= coords[1] <= 40.8   # latitude
        assert f0["properties"]["is_predictive"] is False


class TestRetrospectiveSeverityAnalysis:
    def test_severity_audit_contract(self):
        analyzer = RetrospectiveSeverityAnalyzer()
        audit = analyzer.build_audit()

        assert audit.is_predictive is False
        assert audit.is_causal is False
        assert audit.analysis_type == "RETROSPECTIVE_SEVERITY_ASSOCIATION"
        assert audit.temporal_code_break_year == 2016
        assert audit.severe_outcome_prevalence_percent == 4.44
        assert audit.known_severity_percent == 82.61
        assert len(audit.limitations) >= 7

        # Models check
        assert len(audit.models) == 4
        hgb = next(m for m in audit.models if "HistGradientBoosting" in m.model_name)
        assert hgb.average_precision == 0.1548
        assert hgb.roc_auc == 0.6921
        assert hgb.ap_interval_95[0] < 0.1548 < hgb.ap_interval_95[1]

        rf_no_coll = next(m for m in audit.models if "without collision" in m.model_name)
        assert rf_no_coll.average_precision == 0.0517
        assert rf_no_coll.includes_collision_type is False

        # Associations check
        assert len(audit.associations) >= 4
        coll_assoc = next(a for a in audit.associations if a.feature_name == "COLLISION_LABEL")
        assert coll_assoc.cramers_v == 0.202
        assert coll_assoc.post_crash_observed is True

    @pytest.mark.skip(reason="Legacy v1.0.0 release artifact is unapproved; provisional contract tested separately")
    def test_severity_csv_export(self):
        csv_path = Path("data/exports/frequency/severity_retrospective_associations.csv")
        assert csv_path.exists()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 8
        categories = {r["category"] for r in rows}
        assert "ASSOCIATION" in categories
        assert "MODEL" in categories


class TestAPIModuleCEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.endpoints.frequency import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/frequency")
        return TestClient(app)

    @pytest.mark.parametrize("path", ["concentration/annual", "concentration/breakdown", "concentration/geojson", "severity/retrospective"])
    def test_unreviewed_outputs_blocked(self, client, path):
        assert client.get("/api/v1/frequency/" + path).status_code == 503
