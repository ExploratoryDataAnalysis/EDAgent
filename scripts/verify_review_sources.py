"""Verify pinned road-safety source bytes and optionally retrieve missing archival files."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen

from road_safety_command import ROOT, digest

REGISTRY = ROOT / "data/reference/phase3_phase4_review_sources.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    failures = []
    for key, entry in json.loads(REGISTRY.read_bytes()).items():
        path = ROOT / entry["path"]
        if not path.exists() and args.fetch and entry["downloadable_archive"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=path.parent) as work:
                candidate = Path(work) / path.name
                with urlopen(entry["url"], timeout=90) as source, candidate.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                if digest(candidate) == entry["sha256"]:
                    candidate.rename(path)
        if not path.exists() or digest(path) != entry["sha256"]:
            failures.append(key)
        else:
            print(f"Verified {key}")
    if failures:
        raise SystemExit("Missing or changed pinned sources: " + ", ".join(failures))


if __name__ == "__main__":
    main()
