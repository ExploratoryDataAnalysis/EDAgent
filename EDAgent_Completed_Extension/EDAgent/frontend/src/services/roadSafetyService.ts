import { apiClient } from './apiClient';

export const overviewPath = '/road-safety/overview';

export async function getData<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await apiClient.get<{ data: T }>(path, { signal });
  return response.data.data;
}

export type RoadSafetyError = Error & { status?: number; code?: string; problems?: string[] };

export type Period = { period_start: number; period_end: number; period_grain: string };

export type CountyPeriod = Period & {
  reported_crashes: number;
  known_severity_crashes: number;
  unknown_severity_crashes: number;
  fatal_crashes: number;
  serious_fatal_crashes: number | null;
  fatal_percent_of_known: number | null;
  serious_fatal_percent_of_known: number | null;
  known_severity_percent_of_reported?: number | null;
};

export type Severity = Period & {
  severity_group: string;
  severity_code: number | null;
  crashes: number;
  denominator_crashes: number | null;
  denominator_population: string | null;
  percent_of_denominator: number | null;
};

export type Coordinates = Period & {
  reported_crashes: number;
  usable_decimal_crashes: number;
  unusable_decimal_crashes: number;
  outside_county_crashes: number;
  mapped_crashes: number;
  mapped_percent_of_reported: number | null;
  outside_percent_of_usable?: number | null;
};

export type FieldCoverage = Period & {
  metric_id: string;
  covered_crashes: number;
  excluded_crashes: number;
  reported_crashes: number;
  covered_percent_of_reported: number | null;
};

export type Finding = Period & {
  finding_id: number;
  finding: string;
  population: string;
  review_state: string;
  narrative: string;
};

export type SeverityAssociation = {
  feature: string;
  analysis_years: string;
  known_severity_population_n: number;
  tested_known_severity_n: number;
  within_population_coverage_percent: number;
  cramers_v: number;
  chi2_stat: number;
  degrees_freedom: number;
  raw_p: number;
  fdr_bh_q: number;
};

export type Provenance = {
  scope: { county: string; period_start: number; period_end: number; claim_class?: string };
  run_id: string;
  bundle: { version: string; manifest_sha256: string; approval_state?: string };
  grid: { side_degrees: number; occupied_cells: number; mapped_crashes: number; reported_crashes: number; mapped_percent_of_reported?: number };
  sources: Record<string, string>;
  tables: Record<string, unknown>;
};

export interface HotspotFeature {
  type: string;
  geometry: {
    type: string;
    coordinates: [number, number]; // [lon, lat]
  };
  properties: {
    rank: number;
    site_id: string;
    road_class: string;
    site_type: string;
    total_crashes: number;
    fatal_crashes: number;
    major_injury_crashes: number;
    ksi_crashes: number;
    vru_crashes: number;
    crash_density_per_km: number;
    persistence_category: string;
    road_class_percentile?: number;
  };
}

export interface HotspotCollection {
  type: string;
  metadata?: Record<string, any>;
  features: HotspotFeature[];
}

export interface ModelComparisonMetric {
  model: string;
  test_records: number;
  test_prevalence_percent: number;
  average_precision: number;
  roc_auc: number;
  "balanced_accuracy_at_0.50": number;
  brier_score_uncalibrated: number;
}

export interface RoadClassConcentration {
  road_class: string;
  total_crashes: string | number;
  matched_crashes: string | number;
  ambiguous_crashes: string | number;
  unmatched_crashes: string | number;
  unique_matched_sites: string | number;
  match_coverage_percent: string;
  missing_coord_percent: string;
}

export async function loadOverview(signal?: AbortSignal) {
  const table = async <T>(id: string) => (await getData<{ rows: T[] }>(`${overviewPath}/tables/${id}`, signal)).rows;
  const [provenance, county, severity, coordinates, fields, findings, associations] = await Promise.all([
    getData<Provenance>(`${overviewPath}/provenance`, signal),
    table<CountyPeriod>('county_periods'),
    table<Severity>('severity_composition'),
    table<Coordinates>('coordinate_coverage'),
    table<FieldCoverage>('field_coverage_by_year'),
    table<Finding>('findings'),
    table<SeverityAssociation>('severity_associations').catch(() => []),
  ]);
  return { provenance, county, severity, coordinates, fields, findings, associations };
}

export async function loadHotspots(signal?: AbortSignal): Promise<HotspotCollection> {
  const resp = await apiClient.get<HotspotCollection>(`${overviewPath}/spatial/hotspots`, { signal });
  return resp.data;
}

export async function loadModelComparison(signal?: AbortSignal): Promise<ModelComparisonMetric[]> {
  const resp = await apiClient.get<{ data: ModelComparisonMetric[] }>(`${overviewPath}/models/comparison`, { signal });
  return resp.data.data;
}

export async function loadRoadClasses(signal?: AbortSignal): Promise<RoadClassConcentration[]> {
  const resp = await apiClient.get<{ data: RoadClassConcentration[] }>(`${overviewPath}/concentration/road-classes`, { signal });
  return resp.data.data;
}

export const overviewUrl = (path: string) => apiClient.getUri({ url: `${overviewPath}${path}` });
