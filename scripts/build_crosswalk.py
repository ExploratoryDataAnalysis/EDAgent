"""CLI script to build the Phase 3 crash-to-site crosswalk and stratified reports."""

import sys
import time
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edagent.crosswalk.reconciler import CrosswalkReconciler


def main():
    raise RuntimeError(
        "Crosswalk release blocked: the matcher uses crash-derived LRS keys and "
        "centerline bounding-box midpoints and lacks an intersection inventory. "
        "Independent versioned LRS references and reviewed geometry matching are required."
    )
    print("=" * 70)
    print("EDAgent Road-Safety Crosswalk Reconciliation (Phase 3 Module D)")
    print("=" * 70)

    crash_csv = "data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv"
    centerline_zip = "data/reference/street_centerlines/alleghenycounty_streetcenterlines202610.zip"
    disagreements_csv = "analysis/outputs/spatial/candidate_coordinate_disagreements_review.csv"
    out_dir = "data/exports/crosswalk"

    reconciler = CrosswalkReconciler(
        crash_csv_path=crash_csv,
        centerline_zip_path=centerline_zip,
        disagreements_csv_path=disagreements_csv,
        output_dir=out_dir,
        crosswalk_version="1.0.0",
    )

    print("\n[1/2] Initializing reference registry & loading spatial features...")
    t0 = time.time()
    reconciler.setup()
    t_setup = time.time() - t0
    print(f"Registry initialized with {reconciler.registry.size()} reference sites in {t_setup:.2f}s.")

    print("\n[2/2] Executing batch reconciliation across full crash dataset...")
    manifest = reconciler.run()

    print("\nReconciliation completed successfully!")
    print(f"Total crashes processed: {manifest['summary_metrics']['total_crashes']:,}")
    print(f"Status counts: {manifest['summary_metrics']['status_counts']}")
    print(f"Status percentages: {manifest['summary_metrics']['status_percents_cohort_denominator']}")
    print(f"Processing time: {manifest['summary_metrics']['processing_time_seconds']}s "
          f"({manifest['summary_metrics']['processing_rate_rec_per_sec']} rec/s)")
    print(f"Output files stored in: {out_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
