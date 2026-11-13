"""Model artifact persistence, manifest generation, and integrity verification.

Developed under historical Project Plan v2 (§8, §18) and Phase 4 Module B requirements; v3 governs release scope.
Stores model parameters, feature metadata, dataset checksums, and validation metrics
in versioned JSON manifests for full reproducibility.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from edagent.frequency.negative_binomial import ModelComparisonReport, NegativeBinomialFit
from edagent.frequency.poisson import PoissonModelFit


@dataclass
class ModelManifest:
    """Canonical model manifest documenting provenance, hyperparameters, and metrics."""

    model_name: str
    model_version: str
    software_version: str
    crosswalk_version: str
    training_dataset_checksum: str
    exposure_dataset_checksum: str
    training_period: str
    validation_period: str
    feature_definitions: List[str]
    parameters: Dict[str, float]
    standard_errors: Dict[str, float]
    dispersion_parameter_alpha: Optional[float]
    metrics: Dict[str, Any]
    approval_status: str
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelPersistenceManager:
    """Handles serialization and persistence of frequency model artifacts and manifests."""

    @staticmethod
    def compute_file_sha256(filepath: str | Path) -> str:
        """Compute SHA-256 checksum of a file on disk."""
        p = Path(filepath)
        if not p.exists():
            return "FILE_NOT_FOUND"
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def save_manifest(
        cls,
        output_path: str | Path,
        manifest: ModelManifest,
    ) -> Path:
        """Save ModelManifest to a formatted JSON file."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)
        return out

    @classmethod
    def load_manifest(
        cls,
        manifest_path: str | Path,
    ) -> Dict[str, Any]:
        """Load and parse ModelManifest from JSON file."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
