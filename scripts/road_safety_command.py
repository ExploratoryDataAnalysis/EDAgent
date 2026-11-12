"""Shared staging and publication arguments for the four road-safety commands."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "EDAgent_Completed_Extension/EDAgent/backend"))
sys.path.insert(0, str(ROOT / "src"))

from app.road_safety_release import ReleaseUnavailable, digest, publish_release


def write_manifest(output, kind, version, scope, inputs, status="REVIEW_CANDIDATE"):
    manifest = {
        "kind": kind,
        "version": version,
        "status": status,
        "scope": scope,
        "inputs": inputs,
        "outputs": {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def run(kind, stage_builder, argv=None):
    parser = argparse.ArgumentParser(description=f"Stage or publish {kind} artifacts")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stage", type=Path, metavar="OUTPUT")
    mode.add_argument("--publish", type=Path, metavar="STAGED_BUNDLE")
    parser.add_argument("--input", type=Path, help="Input directory for staging")
    parser.add_argument("--approvals", type=Path, default=os.environ.get("ROAD_SAFETY_APPROVALS"))
    parser.add_argument("--release-root", type=Path, default=ROOT / "data/exports/road_safety")
    args = parser.parse_args(argv)
    if args.stage:
        root = (ROOT / ".repro").resolve()
        output = args.stage.resolve()
        if not output.is_relative_to(root) or output == root or output.exists():
            raise ValueError("Staging requires a new output directory below .repro")
        stage_builder(output, args.input, args.approvals)
        return
    if args.publish and args.approvals:
        publish_release(args.publish, args.release_root / kind, args.approvals, kind)
        return
    raise ReleaseUnavailable(f"{kind} release blocked: a staged bundle and approval ledger are required")
