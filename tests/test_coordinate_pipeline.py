"""Unit tests for CoordinatePipeline end-to-end processing and quality metrics."""

import json
import pytest
from edagent.coordinates.models import CoordinateRecord, ValidationStatus
from edagent.coordinates.pipeline import CoordinatePipeline


@pytest.fixture
def pipeline() -> CoordinatePipeline:
    return CoordinatePipeline()


class TestCoordinatePipeline:
    """Tests for batch processing and quality reporting."""

    def test_pipeline_batch_processing(self, pipeline: CoordinatePipeline):
        rows = [
            # 1. Valid concordant State Route record
            {
                "CRASH_CRN": "2015000001",
                "CRASH_YEAR": "2015",
                "LATITUDE": "40 26:07.800",
                "LONGITUDE": "79 45:10.800",
                "DEC_LAT": "40.435501",
                "DEC_LONG": "-79.753000",
                "ROUTE": "0022",
            },
            # 2. Local road with only police GPS
            {
                "CRASH_CRN": "2019000002",
                "CRASH_YEAR": "2019",
                "LATITUDE": "40 28:15.500",
                "LONGITUDE": "79 59:30.200",
                "DEC_LAT": "",
                "DEC_LONG": "",
                "ROUTE": "",
            },
            # 3. Conflicting pair (>500m)
            {
                "CRASH_CRN": "2007000003",
                "CRASH_YEAR": "2007",
                "LATITUDE": "40 23:29.000",
                "LONGITUDE": "79 10:45.370",
                "DEC_LAT": "40.435501",
                "DEC_LONG": "-79.748802",
                "ROUTE": "0022",
            },
            # 4. Completely missing coordinates
            {
                "CRASH_CRN": "2004000004",
                "CRASH_YEAR": "2004",
                "LATITUDE": "",
                "LONGITUDE": "",
                "DEC_LAT": "",
                "DEC_LONG": "",
                "ROUTE": "",
            },
            # 5. Out of bounds (Miami, FL)
            {
                "CRASH_CRN": "2018000005",
                "CRASH_YEAR": "2018",
                "LATITUDE": "25 45:36.000",
                "LONGITUDE": "80 11:24.000",
                "DEC_LAT": "",
                "DEC_LONG": "",
                "ROUTE": "",
            },
        ]

        records = pipeline.process_records(rows)
        assert len(records) == 5

        # Check statuses
        assert records[0].validation_status == ValidationStatus.VALID
        assert records[1].validation_status == ValidationStatus.VALID
        assert records[2].validation_status == ValidationStatus.CONFLICT
        assert records[3].validation_status == ValidationStatus.MISSING
        assert records[4].validation_status == ValidationStatus.INVALID

        # Generate summary
        summary = pipeline.generate_quality_summary(records)
        assert summary["total_records"] == 5
        assert summary["status_counts"]["VALID"] == 2
        assert summary["status_counts"]["CONFLICT"] == 1
        assert summary["status_counts"]["MISSING"] == 1
        assert summary["status_counts"]["INVALID"] == 1

        # Percentages must sum to 100%
        pct_sum = sum(summary["status_percentages"].values())
        assert pytest.approx(pct_sum, rel=1e-3) == 100.0

        # Check distance statistics
        assert summary["pairwise_comparisons"] == 2
        assert summary["distance_stats"]["median_m"] is not None

    def test_record_serialization(self, pipeline: CoordinatePipeline):
        row = {
            "CRASH_CRN": "2020123456",
            "CRASH_YEAR": "2020",
            "LATITUDE": "40 26:07.800",
            "LONGITUDE": "79 45:10.800",
            "DEC_LAT": "40.435501",
            "DEC_LONG": "-79.753000",
            "ROUTE": "0022",
        }
        records = pipeline.process_records([row])
        rec = records[0]

        d = rec.to_dict()
        assert d["crash_crn"] == 2020123456
        assert d["crs"] == "EPSG:4326"
        assert d["decoder_version"] == "1.0.0"

        # Verify JSON serializability
        json_str = json.dumps(d)
        assert "2020123456" in json_str
        parsed = json.loads(json_str)
        assert parsed["validation_status"] == "VALID"
