"""
Pytest Fixtures for EDAgent Testing
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    """Provides a synchronous FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_csv_path() -> str:
    """Returns absolute path to benchmark sample dataset."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(project_root, "data", "samples", "baseline_benchmark.csv")
    assert os.path.exists(path), f"Benchmark file missing at: {path}"
    return path


@pytest.fixture
def temp_dir():
    """Provides a temporary directory cleaned up after test."""
    with tempfile.TemporaryDirectory() as td:
        yield td
