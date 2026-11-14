import { apiClient } from './apiClient';

export const overviewPath = '/road-safety/overview';

export async function getData<T>(path: string, signal?: AbortSignal, timeout?: number): Promise<T> {
  const response = await apiClient.get<{ data: T }>(path, { signal, timeout });
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

type Bundle = { kind: string; version: string; manifest_sha256: string; approval_state: string; output_sha256?: string };

type Provenance = {
  scope: { county: string; period_start: number; period_end: number };
  run_id: string;
  bundle: Bundle;
  grid: { side_degrees: number; occupied_cells: number; mapped_crashes: number; reported_crashes: number };
  sources: Record<string, string>;
  outputs: Record<string, string>;
};

const overviewTimeout = 12000;

export async function loadProvenance(signal: AbortSignal) {
  const provenance = await getData<Provenance>(`${overviewPath}/provenance`, signal, overviewTimeout);
  if (provenance?.bundle?.kind !== 'descriptive_release'
    || provenance.bundle.approval_state !== 'APPROVED_AGGREGATE_RELEASE'
    || !/^[a-f0-9]{64}$/.test(provenance.bundle.manifest_sha256)) {
    throw new Error('Could not establish release identity.');
  }
  return provenance;
}

export async function loadOverview(signal: AbortSignal) {
  const provenance = await loadProvenance(signal);
  const table = async <T>(id: string) => {
    const result = await getData<{ rows: T[]; run_id: string; bundle: Bundle }>(`${overviewPath}/tables/${id}`, signal, overviewTimeout);
    const expected = provenance.outputs[`${id}.json`];
    const bundle = result?.bundle;
    // A release can change between reads. Only show rows from the verified manifest.
    if (!expected || !bundle || bundle.kind !== provenance.bundle.kind
      || bundle.version !== provenance.bundle.version || bundle.manifest_sha256 !== provenance.bundle.manifest_sha256
      || bundle.approval_state !== provenance.bundle.approval_state || bundle.output_sha256 !== expected
      || result.run_id !== provenance.run_id || !Array.isArray(result.rows)) {
      throw new Error('Could not verify a consistent release.');
    }
    return result.rows;
  };
  const [county, severity, coordinates, fields] = await Promise.all([
    table<CountyPeriod>('county_periods'),
    table<Severity>('severity_composition'),
    table<Coordinates>('coordinate_coverage'),
    table<FieldCoverage>('field_coverage_by_year'),
  ]);
  const totals = county.find(row => row.period_grain === 'county');
  const mapped = coordinates.find(row => row.period_grain === 'county');
  if (!totals || !mapped || !provenance.grid) throw new Error('The record is incomplete.');
  return { provenance, county, severity, coordinates, fields, totals, mapped };
}

export const overviewUrl = (path: string) => apiClient.getUri({ url: `${overviewPath}${path}` });
