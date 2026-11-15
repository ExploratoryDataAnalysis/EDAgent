import { apiClient } from './apiClient';
import type { Bundle, Provenance } from './roadSafetyService';

export const modelsBasePath = '/road-safety/models';

export type ModelComparison = {
  model_id: string;
  model_name: string;
  model_family: string;
  feature_set: string;
  feature_timing: string;
  includes_collision_type: boolean;
  training_cohort: string;
  training_records: number;
  training_positives: number;
  test_cohort: string;
  test_records: number;
  test_positives: number;
  test_prevalence_percent: number;
  average_precision: number;
  ap_chance_baseline: number;
  ap_interval_lower_95: number;
  ap_interval_upper_95: number;
  roc_auc: number;
  roc_chance_baseline: number;
  balanced_accuracy_0_50: number;
  brier_score: number;
  brier_constant_baseline: number;
  calibration_state: string;
  calibration_method: string;
};

export type FeatureAblation = {
  feature_id: string;
  feature_name: string;
  timing_category: string;
  observation_timing: string;
  analysis_population: string;
  cramers_v: number;
  chi2_statistic: number;
  degrees_of_freedom: number;
  raw_p_value: number;
  fdr_bh_q_value: number;
  is_post_crash: boolean;
};

export type ThresholdPerformance = {
  model_id: string;
  model_name: string;
  threshold: number;
  evaluation_records: number;
  actual_positives: number;
  actual_negatives: number;
  true_negatives: number;
  false_positives: number;
  false_negatives: number;
  true_positives: number;
  sensitivity_recall: number;
  specificity: number;
  balanced_accuracy: number;
};

export type CalibrationDiagnostics = {
  model_id: string;
  model_name: string;
  fitting_interval: string;
  evaluation_interval: string;
  brier_score: number;
  brier_constant_baseline: number;
  beats_constant_baseline: boolean;
  calibration_state: string;
  calibration_method: string;
  notes?: string;
};

export type ModelsProvenance = Provenance & {
  schema_version: number | string;
  scope: {
    geoid: string;
    county_name: string;
    claim_class: string;
    training_period: [number, number];
    test_period: [number, number];
    PRIMARY_SITE_ASSIGNMENTS_ACCEPTED: number;
    SITE_PREDICTIONS_PERMITTED: boolean;
    LIVE_INFERENCE_PERMITTED: boolean;
    CASES_SCORED_PERMITTED: boolean;
  };
  manifest_status: string;
};

export type ModelsData = {
  provenance: ModelsProvenance;
  comparisons: ModelComparison[];
  ablation: FeatureAblation[];
  thresholds: ThresholdPerformance[];
  calibration: CalibrationDiagnostics[];
};

export async function loadModelsProvenance(signal?: AbortSignal): Promise<ModelsProvenance> {
  const response = await apiClient.get<{ data: ModelsProvenance }>(`${modelsBasePath}/provenance`, { signal });
  return response.data.data;
}

export async function loadModelsTable<T>(tableId: string, signal?: AbortSignal): Promise<T[]> {
  const response = await apiClient.get<{ data: { table_id: string; rows: T[] } }>(
    `${modelsBasePath}/tables/${tableId}`,
    { signal }
  );
  return response.data.data.rows;
}

export async function loadModelsData(signal: AbortSignal): Promise<ModelsData> {
  const provenance = await loadModelsProvenance(signal);
  const [comparisons, ablation, thresholds, calibration] = await Promise.all([
    loadModelsTable<ModelComparison>('model_comparisons', signal),
    loadModelsTable<FeatureAblation>('feature_ablation', signal),
    loadModelsTable<ThresholdPerformance>('threshold_performance', signal),
    loadModelsTable<CalibrationDiagnostics>('calibration_diagnostics', signal),
  ]);

  return { provenance, comparisons, ablation, thresholds, calibration };
}

export async function confirmModelsRelease(data: ModelsData, signal: AbortSignal): Promise<void> {
  const current = await loadModelsProvenance(signal);
  if (current.bundle.manifest_sha256 !== data.provenance.bundle.manifest_sha256) {
    throw new Error('Models derivative manifest changed.');
  }
}

export function modelsDownloadUrl(tableId: string, manifestSha256?: string): string {
  const query = manifestSha256 ? `?manifest_sha256=${manifestSha256}` : '';
  return apiClient.getUri({ url: `${modelsBasePath}/downloads/${tableId}${query}` });
}

export function modelsAssetUrl(assetName: string, manifestSha256?: string): string {
  const query = manifestSha256 ? `?manifest_sha256=${manifestSha256}` : '';
  return apiClient.getUri({ url: `${modelsBasePath}/assets/${assetName}${query}` });
}
