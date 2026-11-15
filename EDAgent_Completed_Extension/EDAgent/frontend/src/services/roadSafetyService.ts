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
  missing_decimal_pair_crashes: number;
  invalid_decimal_pair_crashes: number;
  placeholder_decimal_pair_crashes: number;
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

export type RowAnnotation = {
  nulls?: Record<string, { value_state?: string; reason_code?: string }>;
  caveat_codes?: string[];
};

export type RowWithAnnotation<T> = T & {
  _stableKey: string;
  _annotation: RowAnnotation;
};

export type Bundle = { kind: string; version: string; manifest_sha256: string; approval_state: string; output_sha256?: string };

export type Provenance = {
  scope: { county: string; period_start: number; period_end: number; geoid?: string };
  run_id: string;
  bundle: Bundle;
  grid: {
    crs: string; side_degrees: number; occupied_cells: number; mapped_crashes: number; reported_crashes: number;
    county_bbox_wsen: [number, number, number, number];
  };
  sources: Record<string, string>;
  outputs: Record<string, string>;
  tables?: Record<string, { rows: number }>;
};

export type OverviewData = {
  provenance: Provenance;
  county: RowWithAnnotation<CountyPeriod>[];
  severity: RowWithAnnotation<Severity>[];
  coordinates: RowWithAnnotation<Coordinates>[];
  fields: RowWithAnnotation<FieldCoverage>[];
  totals: RowWithAnnotation<CountyPeriod>;
  mapped: RowWithAnnotation<Coordinates>;
  caveatCaptions: Record<string, string>;
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

export function makeStableRowKey<T extends object>(row: T, keyFields: string[]): string {
  return keyFields.map(k => String(row[k as keyof T] ?? '')).join(':');
}

function sameRelease(current: { bundle: Bundle; run_id: string }, expected: Provenance) {
  const a = current.bundle;
  const b = expected.bundle;
  return a && a.kind === b.kind && a.version === b.version && a.manifest_sha256 === b.manifest_sha256
    && a.approval_state === b.approval_state && current.run_id === expected.run_id;
}

export async function confirmRelease(provenance: Provenance, signal: AbortSignal) {
  if (!sameRelease(await loadProvenance(signal), provenance)) {
    throw Object.assign(new Error('The release has changed.'), { status: 503, code: 'OVERVIEW_UNAVAILABLE' });
  }
}

export function releaseTables(provenance: Provenance, signal: AbortSignal) {
  const caveats: Record<string, string> = {};
  const table = async <T extends object>(id: string) => {
    const result = await getData<{
      rows: T[];
      row_key: string[];
      annotations?: Record<string, RowAnnotation>;
      caveats?: Record<string, string>;
      table_id: string;
      run_id: string;
      bundle: Bundle;
    }>(`${overviewPath}/tables/${id}`, signal, overviewTimeout);
    const expected = provenance.outputs[`${id}.json`];
    // A release can change between reads. Only show rows from the verified manifest.
    if (!expected || !result || !sameRelease(result, provenance) || result.bundle.output_sha256 !== expected
      || !Array.isArray(result.rows) || !result.row_key?.length || result.table_id !== id) {
      throw new Error('Could not verify a consistent release.');
    }
    // Associate annotations with stable row keys before sorting or filtering.
    Object.assign(caveats, result.caveats);
    return result.rows.map((row, index): RowWithAnnotation<T> => ({
      ...row,
      _stableKey: makeStableRowKey(row, result.row_key),
      _annotation: result.annotations?.[index] ?? {},
    }));
  };
  return { table, caveats };
}

export async function loadOverview(signal: AbortSignal): Promise<OverviewData> {
  const provenance = await loadProvenance(signal);
  const { table, caveats } = releaseTables(provenance, signal);
  const [county, severity, coordinates, fields] = await Promise.all([
    table<CountyPeriod>('county_periods'),
    table<Severity>('severity_composition'),
    table<Coordinates>('coordinate_coverage'),
    table<FieldCoverage>('field_coverage_by_year'),
  ]);
  const totals = county.find(row => row.period_grain === 'county');
  const mapped = coordinates.find(row => row.period_grain === 'county');
  if (!totals || !mapped || !provenance.grid) throw new Error('The record is incomplete.');
  await confirmRelease(provenance, signal);
  return { provenance, county, severity, coordinates, fields, totals, mapped, caveatCaptions: caveats };
}

export const confirmOverview = ({ provenance }: OverviewData, signal: AbortSignal) => confirmRelease(provenance, signal);

export const overviewUrl = (path: string) => apiClient.getUri({ url: `${overviewPath}${path}` });

export const pinnedArtifactPath = (path: string, provenance: Provenance) =>
  `${path}?manifest_sha256=${provenance.bundle.manifest_sha256}`;

export const pinnedArtifactUrl = (path: string, provenance: Provenance) => overviewUrl(pinnedArtifactPath(path, provenance));
