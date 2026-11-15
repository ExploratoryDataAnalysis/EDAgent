"""Verify a named approval against a specific road-safety artifact bundle."""

import hashlib
import json
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path


class ReleaseUnavailable(ValueError):
    pass


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _checksums(values):
    return (
        isinstance(values, dict) and bool(values)
        and all(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
                for value in values.values())
    )


def verify_release(directory, approval_file, kind, *, expected_manifest_sha256=None):
    manifest, _ = verify_release_decision(directory, approval_file, kind, expected_manifest_sha256=expected_manifest_sha256)
    return manifest


def verify_release_decision(directory, approval_file, kind, *, expected_manifest_sha256=None):
    """The approval ledger lives in deployment configuration, outside the bundle."""
    directory = Path(directory).resolve()
    try:
        ledger_path = Path(approval_file).resolve()
        if ledger_path.is_relative_to(directory):
            raise ValueError("The approval ledger must be outside the bundle")
        decisions = json.loads(ledger_path.read_bytes())
        manifest_bytes = (directory / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        fingerprint = hashlib.sha256(manifest_bytes).hexdigest()
        if expected_manifest_sha256 is not None and fingerprint != expected_manifest_sha256:
            raise ValueError("Unsupported manifest fingerprint")
        decision = decisions[kind]
        if (
            manifest["kind"] != kind or manifest["status"] != "REVIEW_CANDIDATE"
            or decision["decision"] != "APPROVED" or decision["manifest_sha256"] != fingerprint
            or not decision["reviewer"].strip()
            or date.fromisoformat(decision["date"]).isoformat() != decision["date"]
            or not manifest["version"].strip()
            or not isinstance(manifest["scope"], dict) or not manifest["scope"]
            or not _checksums(manifest["inputs"]) or not _checksums(manifest["outputs"])
        ):
            raise ValueError("Approval, version or scope is invalid")
        for name, checksum in manifest["outputs"].items():
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or name == "manifest.json":
                raise ValueError("Invalid artifact name")
            path = directory / name
            if path.is_symlink() or digest(path) != checksum:
                raise ValueError(f"Artifact checksum mismatch: {name}")
        return manifest, decision
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ReleaseUnavailable(f"{kind} release blocked: {exc}") from exc


def approved_bytes(directory, manifest, name):
    """Serve the verified bytes even if a deployment file changes during a request."""
    try:
        expected = manifest["outputs"][name]
        payload = (Path(directory) / name).read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError("Artifact checksum mismatch")
        return payload
    except (KeyError, OSError, ValueError) as exc:
        raise ReleaseUnavailable(f"Unavailable artifact: {name}") from exc


def publish_release(stage, destination, approval_file, kind):
    manifest = verify_release(stage, approval_file, kind)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ReleaseUnavailable(f"Publication blocked: {destination} already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        copy = Path(temp) / "bundle"
        copy.mkdir()
        for name in ("manifest.json", *manifest["outputs"]):
            shutil.copyfile(Path(stage) / name, copy / name)
        verify_release(copy, approval_file, kind)
        copy.rename(destination)
