"""Unavailable releases must not leak stale concentration artifacts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path("EDAgent_Completed_Extension/EDAgent/backend").resolve()))
from app.api.v1.endpoints.frequency import _standard_metadata, require_reviewed_concentration, router


def test_api_withholds_unreviewed_artifacts():
    assert _standard_metadata()["coverage_status"] == "UNVERIFIED"
    protected = [r for r in router.routes if '/concentration/' in r.path or '/severity/' in r.path]
    assert len(protected) == 6
    assert all(any(d.call is require_reviewed_concentration for d in r.dependant.dependencies) for r in protected)
