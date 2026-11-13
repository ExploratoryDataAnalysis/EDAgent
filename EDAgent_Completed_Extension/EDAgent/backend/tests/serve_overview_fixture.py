"""Run the synthetic Overview against the real API for local browser checks."""

import os
import tempfile
from pathlib import Path

import uvicorn

from app.api.v1.endpoints import overview
from app.road_safety_release import digest
from tests.overview_fixture import FIXTURE_VERSION, write_decision, write_fixture


def main():
    with tempfile.TemporaryDirectory(prefix="edagent-overview-browser-") as directory:
        local = Path(directory).resolve()
        release = write_fixture(local / "release")
        ledger = local / "test-approvals.json"
        fingerprint = digest(release / "manifest.json")
        write_decision(ledger, fingerprint)
        # Only this test process can recognize the fixture fingerprint.
        overview.MANIFEST_SHA256 = fingerprint
        overview.VERSION = FIXTURE_VERSION
        os.environ.update(
            ENVIRONMENT="test",
            DATABASE_URL=f"sqlite+aiosqlite:///{(local / 'fixture.db').as_posix()}",
            LOCAL_STORAGE_PATH=str(local / "uploads"),
            EXPORTS_STORAGE_PATH=str(local / "exports"),
            ROAD_SAFETY_RELEASE_ROOT=str(release.parent),
            ROAD_SAFETY_APPROVALS=str(ledger),
            SECRET_KEY="synthetic-fixture-key-for-local-tests-only",
            LLM_PROVIDER="mock",
            LLM_API_KEY="",
        )
        uvicorn.run("app.main:app", host="127.0.0.1", port=8016)


if __name__ == "__main__":
    main()
