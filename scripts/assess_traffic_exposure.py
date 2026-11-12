"""CLI script to execute the Phase 4 Module A traffic exposure assessment and feasibility audit."""

import json
import sys
import time
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edagent.exposure.coverage import TrafficCoverageAssessment
from edagent.exposure.feasibility import TrafficFeasibilityEvaluator
from edagent.exposure.panel import SiteYearPanelBuilder
from edagent.exposure.sources import get_official_traffic_sources


def main():
    print("=" * 75)
    print("EDAgent Phase 4 Module A: Traffic Exposure & Feasibility Assessment")
    print("=" * 75)

    crosswalk_path = "data/exports/crosswalk/crosswalk_v1.0.0.csv.gz"
    out_dir = "data/exports/traffic_exposure"

    # 1. Source Inventory
    print("\n[1/4] Inventorying official candidate traffic exposure sources...")
    sources = get_official_traffic_sources()
    print(f"Loaded {len(sources)} candidate traffic exposure sources.")
    for s in sources:
        print(f" - {s.source_id}: {s.source_name} ({s.coverage_level.value}, {s.temporal_type.value})")

    # 2. Coverage Assessment
    print("\n[2/4] Computing empirical coverage across 2004–2024 crosswalk universe...")
    t0 = time.time()
    assessor = TrafficCoverageAssessment(crosswalk_path)
    cov_files = assessor.export_reports(out_dir)
    metrics = assessor.compute_coverage_metrics()
    t_cov = time.time() - t0

    cohort = metrics["cohort_summary"]
    evals = metrics["coverage_evaluations"]

    print(f"Coverage assessment completed in {t_cov:.2f}s:")
    print(f" - Total Crashes: {cohort['total_crashes']:,}")
    print(f" - Matched Crashes: {cohort['matched_crashes']:,} ({cohort['matched_crashes']/cohort['total_crashes']*100:.2f}%)")
    print(f" - Total Unique Matched Sites: {cohort['total_unique_sites']:,}")
    print(f" - Potential Site-Years (2004–2024): {cohort['potential_site_years_universe']:,}")
    print(f" - Verified Annual Historical Exposure Coverage: {evals['verified_annual_historical_panel']['sites_covered_pct']:.2f}%")
    print(f" - Modern Cross-Sectional State Route Proxy Coverage: {evals['modern_cross_sectional_proxy_scenario']['sites_covered_pct']:.2f}% of matched sites ({evals['modern_cross_sectional_proxy_scenario']['countywide_centerlines_covered_pct']:.2f}% of county network)")
    print(f" - Local Road Exposure Coverage: {evals['modern_cross_sectional_proxy_scenario']['local_road_sites_covered_pct']:.2f}% (100% missing)")

    # 3. Site-Year Panel Prototype
    print("\n[3/4] Constructing site-year panel prototype (2016–2024 evaluation window)...")
    panel_builder = SiteYearPanelBuilder(crosswalk_path, start_year=2016, end_year=2024)
    # Build for verified state route corridors to establish legitimate zero-crash site-years
    panel_rows = panel_builder.build_panel(focus_state_routes_only=True)
    panel_out_path = Path(out_dir) / "site_year_panel_prototype.csv"
    panel_builder.export_csv(panel_rows, str(panel_out_path))

    zero_count = sum(1 for r in panel_rows if r["is_zero_crash_observation"])
    print(f"Panel prototype generated: {len(panel_rows):,} site-years ({len(panel_rows)//9:,} unique state route sites)")
    print(f" - Legitimate zero-crash site-years: {zero_count:,} ({zero_count/len(panel_rows)*100:.2f}%)")
    print(f" - Unverified missing exposure site-years: {len(panel_rows):,} (100.00% missing exposure)")
    print(f" - Panel saved to: {panel_out_path}")

    # 4. Feasibility Decision
    print("\n[4/4] Evaluating feasibility criteria for frequency modelling...")
    decision_matrix_path = Path(out_dir) / "feasibility_decision_matrix.csv"
    TrafficFeasibilityEvaluator.export_decision_matrix(str(decision_matrix_path))
    eval_result = TrafficFeasibilityEvaluator.evaluate()

    print(f"Criteria Evaluated: {eval_result['criteria_evaluated_n']}, Failed: {eval_result['criteria_failed_n']}")
    print(f"BINDING DECISION: {eval_result['overall_decision']}")
    print(f"Action: {eval_result['mandated_alternative']}")
    print("=" * 75)


if __name__ == "__main__":
    main()
