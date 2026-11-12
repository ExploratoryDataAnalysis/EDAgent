"""Build the Phase 3 review package or publish a separately approved bundle."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from road_safety_command import run, write_manifest


def stage(output, source_directory, approvals):
    from build_provisional_crosswalk import CONFLICTS, NETWORK, RAW, ROOT, VERSION, build, digest
    from review_roadway_sources import (
        COUNTY_BOUNDARY, review_junction_candidates, review_lineage, review_locations,
        review_official_archive, review_penndot,
    )

    build(output)
    checkpoint = (output / "manifest.json").rename(output / "checkpoint_manifest.json")
    source_directory = source_directory or ROOT / ".repro/source_review"
    report = {
        "network": review_lineage(output, source_directory),
        "locations": review_locations(output),
        "penndot": review_penndot(),
        "penndot_202411_rms": review_official_archive(
            source_directory, output, "PaStateRoads2024_11.zip", "PaStateRoads"),
        "penndot_202411_at_grade": review_official_archive(
            source_directory, output, "PA_AtGradeIntersections2024_11.zip", "PA_AtGrade_Intersections"),
    }
    report["junction_crash_diagnostic"] = review_junction_candidates(output)
    (output / "evidence_review.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    inputs = {"v6_crashes": digest(RAW), "frozen_conflicts": digest(CONFLICTS),
              "pasda_202412": digest(NETWORK), "county_boundary_2024": digest(COUNTY_BOUNDARY),
              "provisional_checkpoint": digest(checkpoint)}
    inputs.update({f"pasda_{version}": row["sha256"] for version, row
                   in report["network"]["archives"].items() if "sha256" in row})
    if "sha256" in report["penndot"]:
        inputs["penndot_roadway"] = report["penndot"]["sha256"]
    for key in ("penndot_202411_rms", "penndot_202411_at_grade"):
        if "sha256" in report[key]:
            inputs[key] = report[key]["sha256"]
    write_manifest(output, "crosswalk", VERSION + "-review", {
        "county": "Allegheny", "crash_years": [2004, 2024], "candidate_snapshot": "2024-12",
        "supported_assignment_scope": [], "crosswalk_version": VERSION,
    }, inputs, "PROVISIONAL")


def main(argv=None):
    run("crosswalk", stage, argv)


if __name__ == "__main__":
    main()
