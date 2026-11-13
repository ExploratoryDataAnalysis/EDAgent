import { apiClient } from './apiClient';

export const overviewPath = '/road-safety/overview';

export async function getData<T>(path: string, signal: AbortSignal): Promise<T> {
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
export type Provenance = {
  scope: { county: string; period_start: number; period_end: number };
  run_id: string;
  bundle: { version: string; manifest_sha256: string };
  grid: { side_degrees: number; occupied_cells: number; mapped_crashes: number; reported_crashes: number };
  sources: Record<string, string>;
  tables: Record<string, unknown>;
};

export async function loadOverview(signal: AbortSignal) {
  const table = async <T>(id: string) => (await getData<{ rows: T[] }>(`${overviewPath}/tables/${id}`, signal)).rows;
  const [provenance, county, severity, coordinates, fields, findings] = await Promise.all([
    getData<Provenance>(`${overviewPath}/provenance`, signal),
    table<CountyPeriod>('county_periods'), table<Severity>('severity_composition'),
    table<Coordinates>('coordinate_coverage'), table<FieldCoverage>('field_coverage_by_year'), table<Finding>('findings'),
  ]);
  return { provenance, county, severity, coordinates, fields, findings };
}

// Assets are public and can use the same configured base URL without an Authorization header.
export const overviewUrl = (path: string) => apiClient.getUri({ url: `${overviewPath}${path}` });
