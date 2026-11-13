"""Contract vectors for Phase 5 and the real-site refusal boundary."""

import json
import pickle
from decimal import Decimal, localcontext

import joblib
import pytest

from app import road_safety_release
from app.api.v1.endpoints import frequency, interventions
from app.schemas.intervention import InterventionScenario
from app.services.intervention_service import calculate_scenario

SCENARIOS = "/api/v1/interventions/scenarios"
EVIDENCE = "/api/v1/interventions/evidence"
VECTORS = [
    # Baseline, CMF, exact after and delta, display after and delta.
    ("10", "0.8", "8", "2", "8.00", "2.00"),
    ("10", "1", "10", "0", "10.00", "0.00"),
    ("10", "1.25", "12.5", "-2.5", "12.50", "-2.50"),
    ("0", "1.25", "0", "0", "0.00", "0.00"),
    ("12.345", "0.8765", "10.8203925", "1.5246075", "10.82", "1.52"),
    ("1", "0.994999", "0.994999", "0.005001", "0.99", "0.01"),
    ("1", "0.995", "0.995", "0.005", "1.00", "0.01"),
    ("1", "1.004999", "1.004999", "-0.004999", "1.00", "0.00"),
    ("1", "1.005", "1.005", "-0.005", "1.01", "-0.01"),
    ("999999999999", "999999999999", "999999999998000000000001",
     "-999999999997000000000002", "999999999998000000000001.00", "-999999999997000000000002.00"),
]


def payload(baseline="10", factor="0.8"):
    return {
        "schema_version": "1",
        "scenario_kind": "HYPOTHETICAL",
        "hypothetical_baseline_n": baseline,
        "crash_type": "PEDESTRIAN",
        "analysis_period": {"length": 1, "unit": "YEARS"},
        "units": "CRASHES_PER_ANALYSIS_PERIOD",
        "cmf": {"origin": "USER_ENTERED_HYPOTHETICAL", "crash_type": "PEDESTRIAN", "value": factor},
    }


def assert_counts(result, after, delta, display_after, display_delta):
    assert Decimal(result["exact"]["after_n"]) == Decimal(after)
    assert Decimal(result["exact"]["delta_n"]) == Decimal(delta)
    assert result["display"]["after_n"] == display_after
    assert result["display"]["delta_n"] == display_delta


@pytest.mark.parametrize("baseline, factor, after, delta, display_after, display_delta", VECTORS)
def test_calculator_vectors(baseline, factor, after, delta, display_after, display_delta):
    scenario = InterventionScenario.model_validate(payload(baseline, factor))
    # The caller's decimal settings do not change scenario results.
    with localcontext() as context:
        context.prec = 2
        result = calculate_scenario(scenario).model_dump(mode="json")
    assert_counts(result, after, delta, display_after, display_delta)


@pytest.mark.parametrize("baseline, factor, after, delta, display_after, display_delta", VECTORS)
def test_api_vectors(anon_client, baseline, factor, after, delta, display_after, display_delta):
    body = payload(baseline, factor)
    response = anon_client.post(SCENARIOS, json=body)
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["status"] == "ILLUSTRATIVE_ONLY"
    assert result["label"] == "Illustrative scenario"
    assert result["scenario"] == {**body, "cmf": {**body["cmf"], "bounds": None}}
    assert_counts(result, after, delta, display_after, display_delta)


@pytest.mark.parametrize("baseline, expected", [
    ("10", (("6.00", "13.00"), ("-3.00", "4.00"))),
    ("0", (("0.00", "0.00"), ("0.00", "0.00"))),
    ("0.025", (("0.02", "0.03"), ("-0.01", "0.01"))),
])
def test_factor_bounds(anon_client, baseline, expected):
    body = payload(baseline)
    body["analysis_period"]["length"] = 2
    body["cmf"]["bounds"] = {"lower": "0.6", "upper": "1.3"}
    response = anon_client.post(SCENARIOS, json=body)
    assert response.status_code == 200, response.text
    exact = response.json()["data"]["exact"]["sensitivity"]
    assert Decimal(exact["after_n"]["lower"]) == Decimal(baseline) * Decimal("0.6")
    assert Decimal(exact["after_n"]["upper"]) == Decimal(baseline) * Decimal("1.3")
    assert Decimal(exact["delta_n"]["lower"]) == Decimal(baseline) * Decimal("-0.3")
    assert Decimal(exact["delta_n"]["upper"]) == Decimal(baseline) * Decimal("0.4")
    shown = response.json()["data"]["display"]["sensitivity"]
    assert shown["label"] == "Hypothetical factor sensitivity range"
    assert shown["after_n"] == dict(zip(("lower", "upper"), expected[0]))
    assert shown["delta_n"] == dict(zip(("lower", "upper"), expected[1]))


@pytest.mark.parametrize("field, value, error_type", [
    ("hypothetical_baseline_n", "-1", "greater_than_equal"),
    ("hypothetical_baseline_n", "NaN", "decimal_text"),
    ("hypothetical_baseline_n", "0.0000001", "decimal_text"),
    ("hypothetical_baseline_n", "1234567890123.012345", "decimal_text"),
    ("hypothetical_baseline_n", True, "decimal_text"),
    ("hypothetical_baseline_n", 10.1, "decimal_text"),
    ("cmf.value", "-0.8", "greater_than"),
    ("cmf.value", "0", "greater_than"),
    ("cmf.value", "Infinity", "decimal_text"),
    ("cmf.value", "-Infinity", "decimal_text"),
    ("cmf.bounds", {"lower": "NaN", "upper": "1.2"}, "decimal_text"),
    ("cmf.bounds", {"lower": "0.6"}, "missing"),
    ("cmf.bounds", {"lower": "1.2", "upper": "0.6"}, "invalid_factor_bounds"),
    ("cmf.bounds", {"lower": "0.9", "upper": "1.2"}, "invalid_factor_bounds"),
    ("analysis_period.length", 0, "greater_than"),
    ("analysis_period.length", -1, "greater_than"),
    ("analysis_period.length", 1.5, "int_type"),
    ("analysis_period.length", True, "int_type"),
    ("analysis_period.unit", "DAYS", "literal_error"),
    ("units", "CRASHES_PER_VEHICLE", "literal_error"),
    ("cmf.crash_type", "ALL", "crash_type_mismatch"),
    ("crash_type", "OTHER", "literal_error"),
    ("schema_version", "2", "literal_error"),
    ("cmf.origin", "VERIFIED_STUDY", "union_tag_invalid"),
    ("description", "Free text", "extra_forbidden"),
])
def test_invalid_scenarios(anon_client, field, value, error_type):
    body = payload()
    parent, separator, child = field.partition(".")
    if separator:
        body[parent][child] = value
    else:
        body[parent] = value
    response = anon_client.post(SCENARIOS, json=body)
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == error_type


def test_unquoted_nonfinite_input(anon_client):
    body = json.dumps(payload()).replace('"0.8"', "NaN")
    response = anon_client.post(SCENARIOS, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == "decimal_text"


@pytest.mark.parametrize("case, fields, query", [
    ("valid", {"site_id": "Station 375"}, ""),
    ("valid", {"site_id": "Station 375"}, "?unused=1"),
    ("valid", {"stationNumber": 375}, ""),
    ("valid", {"reAl_SiTe": False}, ""),
    ("valid", {"coordinates": [40.4, -80.0]}, ""),
    ("valid", {"mapSelection": None}, ""),
    ("valid", {"inputs": {"road_segment_id": "0080"}}, ""),
    ("valid", {"location_name": "Allegheny County"}, ""),
    ("valid", {}, "?route_id=US22"),
    ("valid", {}, "?mode=real_location"),
    ("valid", {}, "?siteId=375&siteId="),
    ("invalid", {"site_id": 375}, ""),
    ("invalid", {"scenario_kind": "REAL_SITE"}, ""),
    ("invalid", {"request_type": "REAL_SITE_BENEFIT"}, ""),
    ("invalid", {"cmf": {"origin": "EVIDENCE_REGISTER", "location": {"station": 375}}}, ""),
    ("missing", {"mode": "real-site"}, ""),
])
def test_real_site_refusal(anon_client, monkeypatch, case, fields, query):
    def blocked(*args, **kwargs):
        pytest.fail("The real-site boundary must run before lookup or calculation")

    monkeypatch.setattr(interventions, "_read_register", blocked)
    monkeypatch.setattr(interventions, "calculate_scenario", blocked)
    body = {} if case == "missing" else payload("-1" if case == "invalid" else "10")
    response = anon_client.post(SCENARIOS + query, json={**body, **fields})
    assert response.status_code == 503, response.text
    envelope = response.json()
    assert set(envelope) == {"success", "message", "errors", "detail"}
    assert envelope["success"] is False
    assert set(envelope["detail"]) == {"code", "message"}
    assert envelope["detail"]["code"] == "REAL_SITE_BENEFIT_UNAVAILABLE"


def test_reference_entries_and_missing_factor(anon_client):
    response = anon_client.get(EVIDENCE)
    assert response.status_code == 200, response.text
    register = response.json()["data"]
    assert register["register_version"] == "v3-d8-1"
    assert register["status"] == "NO_APPROVED_NUMERIC_CMF"
    assert len({entry["EVIDENCE_ID"] for entry in register["records"]}) == 6
    for entry in register["records"]:
        assert set(entry["source_ids"]) <= register["sources"].keys()
        assert entry["EVIDENCE_STATUS"] == "REFERENCE_ONLY"
        assert entry["study_factor"] is None
        assert entry["study_confidence_interval"] is None
        body = payload()
        body["cmf"] = {"origin": "EVIDENCE_REGISTER", "evidence_id": entry["EVIDENCE_ID"]}
        response = anon_client.post(SCENARIOS, json=body)
        assert response.status_code == 422, response.text
        data = response.json()
        assert "data" not in data
        assert data["detail"]["code"] == "NO_APPROVED_NUMERIC_CMF"
        assert data["detail"]["evidence_id"] == entry["EVIDENCE_ID"]
        assert data["detail"]["evidence_status"] == "REFERENCE_ONLY"
    body["cmf"]["evidence_id"] = "unknown"
    response = anon_client.post(SCENARIOS, json=body)
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "EVIDENCE_NOT_FOUND"


def test_evidence_query_with_site_is_unavailable(anon_client):
    response = anon_client.get(EVIDENCE + "?station=375")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "REAL_SITE_BENEFIT_UNAVAILABLE"


def test_phase5_routes_do_not_use_release_or_model_loaders(anon_client, monkeypatch, tmp_path):
    def blocked(*args, **kwargs):
        pytest.fail("Phase 5 endpoints must be independent of release artifacts and models")

    monkeypatch.setenv("ROAD_SAFETY_RELEASE_ROOT", str(tmp_path))
    monkeypatch.setenv("ROAD_SAFETY_APPROVALS", str(tmp_path / "approvals.json"))
    monkeypatch.setattr(frequency, "verify_release", blocked)
    monkeypatch.setattr(frequency, "approved_bytes", blocked)
    monkeypatch.setattr(road_safety_release, "verify_release", blocked)
    monkeypatch.setattr(road_safety_release, "approved_bytes", blocked)
    monkeypatch.setattr(joblib, "load", blocked)
    monkeypatch.setattr(pickle, "load", blocked)
    assert anon_client.get(EVIDENCE).status_code == 200
    assert anon_client.post(SCENARIOS, json=payload()).status_code == 200


def test_openapi_describes_versioned_request(anon_client):
    spec = anon_client.get("/api/v1/openapi.json").json()
    request_schema = spec["paths"][SCENARIOS]["post"]["requestBody"]["content"]["application/json"]
    input_name = request_schema["schema"]["$ref"].split("/")[-1]
    scenario = spec["components"]["schemas"][input_name]["properties"]
    assert scenario["schema_version"]["const"] == "1"
    assert scenario["cmf"]["discriminator"]["propertyName"] == "origin"
    assert scenario["hypothetical_baseline_n"]["type"] == "string"
