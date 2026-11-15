/**
 * EDAgent API contract types. Field names are snake_case exactly as the backend returns them,
 * so responses can be used without a mapping layer.
 */

export type UUID = string;

// API Response Envelopes
export interface APIResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  errors?: string[];
}

// User & Auth
export interface User {
  id: UUID;
  email: string;
  full_name?: string | null;
  is_active?: boolean;
  guest?: {
    expires_at: number;
    max_upload_bytes: number;
    max_datasets: number;
    max_actions: number;
  } | null;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: User;
}

// Dataset
export type FileFormat = 'csv' | 'tsv' | 'xlsx';

export interface Dataset {
  id: UUID;
  name: string;
  original_filename: string;
  file_format: FileFormat;
  file_size_bytes: number;
  row_count?: number | null;
  column_count?: number | null;
  checksum_sha256?: string;
  created_at?: string;
  updated_at?: string;
  metadata_summary?: {
    selected_sheet?: string | null;
    requires_sheet_selection?: boolean;
    parsed_sheets?: string[] | null;
    parse_options?: Record<string, unknown> | null;
  } | null;
}

export type DatasetResponse = Dataset;

export interface DatasetUploadResult {
  dataset_id: UUID;
  name: string;
  original_filename: string;
  file_format: FileFormat;
  file_size_bytes: number;
  multiple_sheets_found: boolean;
  detected_sheets?: string[] | null;
  selected_sheet?: string | null;
  requires_sheet_selection: boolean;
  parsing_decision: string;
  storage_uri: string;
  created_at: string;
}

export interface SampleDataset {
  id: string;
  name: string;
  size_bytes: number;
  description: string;
}

export interface SheetInfo {
  name: string;
  row_count_estimate?: number | null;
  column_count_estimate?: number | null;
}

export interface SheetInspectionResponse {
  dataset_id: UUID;
  sheets: SheetInfo[];
  default_sheet?: string | null;
}

export interface DatasetPreview {
  dataset_id: UUID;
  selected_sheet?: string | null;
  total_rows: number;
  total_columns: number;
  column_names: string[];
  inferred_types: Record<string, string>;
  head_records: Record<string, unknown>[];
  tail_records: Record<string, unknown>[];
  sample_records: Record<string, unknown>[];
  parsing_warnings: string[];
}

export type DatasetListItem = Pick<Dataset, 'id' | 'name' | 'original_filename' | 'file_format' | 'file_size_bytes' | 'row_count' | 'column_count' | 'created_at'>;

export interface DatasetListResponse {
  items: DatasetListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DatasetRecoveryCandidate {
  dataset_id: UUID;
  name: string;
  file_format: FileFormat;
  file_size_bytes: number;
  modified_at: string;
}

// ==========================================
// Profiler Types (Phase 2 Full Specifications)
// ==========================================

export type SemanticRole =
  | 'identifier'
  | 'measure'
  | 'category'
  | 'datetime'
  | 'boolean'
  | 'text'
  | 'unknown';

export type Severity = 'low' | 'medium' | 'high';

export interface NumericSummary {
  count: number;
  mean?: number;
  std?: number;
  min?: number;
  q25?: number;
  median?: number;
  q75?: number;
  max?: number;
  iqr?: number;
  skewness?: number;
  kurtosis?: number;
  zeros_count?: number;
  zeros_percentage?: number;
  infinite_count?: number;
  nan_count?: number;
  // camelCase compatibility
  zerosCount?: number;
  zerosPercentage?: number;
  infiniteCount?: number;
  nanCount?: number;
}

export interface CategoricalTopValue {
  value: string;
  count: number;
  percentage: number;
}

export interface CategoricalSummary {
  unique_count: number;
  most_frequent_value?: string;
  most_frequent_count?: number;
  most_frequent_percentage?: number;
  top_values: CategoricalTopValue[];
  is_high_cardinality: boolean;
  // camelCase compatibility
  uniqueCount?: number;
  topValues?: CategoricalTopValue[];
  isHighCardinality?: boolean;
}

export interface DateSummary {
  parse_success_rate: number;
  min_date?: string;
  max_date?: string;
  invalid_date_count: number;
  date_range_days?: number;
  timezone_warnings: string[];
}

export interface ColumnProfile {
  name: string;
  storage_dtype: string;
  inferred_type: string;
  semantic_role: SemanticRole;
  role_confidence: number;
  role_uncertainty_reason?: string;
  non_null_count: number;
  missing_count: number;
  missing_percentage: number;
  distinct_count: number;
  is_unique: boolean;
  numeric_summary?: NumericSummary;
  categorical_summary?: CategoricalSummary;
  date_summary?: DateSummary;
  sample_values: unknown[];
  // camelCase compatibility
  storageDtype?: string;
  inferredType?: string;
  semanticRole?: SemanticRole;
  roleConfidence?: number;
  nonNullCount?: number;
  missingCount?: number;
  missingPercentage?: number;
  distinctCount?: number;
  isUnique?: boolean;
  numericSummary?: NumericSummary;
  categoricalSummary?: CategoricalSummary;
  dateSummary?: DateSummary;
  sampleValues?: unknown[];
}

export interface QualityWarning {
  column?: string;
  check_type: string;
  severity: Severity;
  message: string;
  affected_count?: number;
  title?: string;
  // camelCase compatibility
  checkType?: string;
  affectedCount?: number;
}

export interface MissingnessChartItem {
  column: string;
  missing_count: number;
  missing_percentage: number;
  present_count: number;
}

export interface MissingnessPatternItem {
  missing_columns: string[];
  row_count: number;
  percentage: number;
}

export interface MissingnessReport {
  total_cells: number;
  missing_cells: number;
  total_missing_cells?: number;
  overall_missing_percentage: number;
  per_column: Record<string, number>;
  columns_with_missing: string[];
  missingness_chart_data?: MissingnessChartItem[];
  missingness_patterns?: MissingnessPatternItem[];
  // camelCase compatibility
  totalCells?: number;
  missingCells?: number;
  overallMissingPercentage?: number;
  perColumn?: Record<string, number>;
  columnsWithMissing?: string[];
}

export interface DuplicatesReport {
  exact_duplicate_rows_count: number;
  duplicate_row_count?: number;
  exact_duplicate_percentage: number;
  candidate_duplicate_keys: string[];
  duplicate_rows_sample?: { row: Record<string, unknown>; occurrences: number }[];
  // camelCase compatibility
  exactDuplicateRowsCount?: number;
  exactDuplicatePercentage?: number;
  candidateDuplicateKeys?: string[];
}

export interface DatasetOverview {
  dataset_name: string;
  total_rows: number;
  total_columns: number;
  file_size_bytes: number;
  memory_estimate_bytes: number;
  selected_sheet?: string;
  load_time_seconds: number;
  profiling_duration_seconds?: number;
  parsing_warnings: string[];
  // camelCase compatibility
  datasetName?: string;
  totalRows?: number;
  totalColumns?: number;
  fileSizeBytes?: number;
  memoryEstimateBytes?: number;
  loadTimeSeconds?: number;
  parsingWarnings?: string[];
}

// Distribution Analysis Schemas
export interface HistogramBin {
  bin_start: number;
  bin_end: number;
  count: number;
  percentage: number;
}

export interface NumericHistogram {
  column: string;
  bins: HistogramBin[];
}

export interface NumericBoxplot {
  column: string;
  min: number;
  q25: number;
  median: number;
  q75: number;
  max: number;
  iqr: number;
  lower_fence: number;
  upper_fence: number;
  outlier_count: number;
  outliers_sample: number[];
}

export interface CategoricalFrequencyItem {
  value: string;
  count: number;
  percentage: number;
}

export interface CategoricalFrequencyChart {
  column: string;
  categories: CategoricalFrequencyItem[];
  other_count: number;
  other_percentage: number;
}

export interface DateDistributionItem {
  period: string;
  count: number;
}

export interface DateDistributionChart {
  column: string;
  unit: string;
  buckets: DateDistributionItem[];
}

export interface TimeDistributionChart {
  column: string;
  day_of_week: Record<string, number>;
  hour_of_day: Record<string, number>;
}

export interface DistributionAnalysis {
  histograms: NumericHistogram[];
  boxplots: NumericBoxplot[];
  categorical_frequencies: any;
  date_distributions: DateDistributionChart[];
  time_distributions: TimeDistributionChart[];
  numeric_histograms?: Record<string, any>;
}

// Relationships Schemas
export interface CorrelationMatrix {
  columns: string[];
  matrix: Record<string, Record<string, number | null>>;
}

export interface CategoricalAssociation {
  column_x: string;
  column_y: string;
  cramers_v: number;
  chi2: number;
  p_value: number;
}

export interface RelationshipAnalysis {
  pearson?: CorrelationMatrix;
  spearman?: CorrelationMatrix;
  categorical_associations: CategoricalAssociation[];
  warnings: string[];
  excluded_columns: string[];
}

export interface SuggestedAnalysis {
  title: string;
  description: string;
  operation: string;
  columns: string[];
  rationale: string;
}

export interface ProfilerResult {
  dataset_id?: UUID;
  datasetId?: UUID;
  overview: DatasetOverview;
  columns: ColumnProfile[];
  missingness: MissingnessReport;
  duplicates: DuplicatesReport;
  distributions?: DistributionAnalysis;
  quality_warnings: QualityWarning[];
  qualityWarnings?: QualityWarning[];
  relationships?: RelationshipAnalysis;
  suggested_analyses?: SuggestedAnalysis[];
  suggested_questions?: string[];
  suggestedQuestions?: string[];
  correlation_matrix?: Record<string, Record<string, number | null>>;
  correlationMatrix?: Record<string, Record<string, number | null>>;
  computed_at: string;
  computedAt?: string;
}

// ==========================================
// Analysis, Chat, Sessions, Reports, Jobs
// ==========================================

export type AnalysisOperation = string;

export interface FilterCondition {
  column: string;
  operator: string;
  value?: unknown;
}

export interface FilterGroup {
  logic: 'and' | 'or';
  conditions: (FilterCondition | FilterGroup)[];
}

export interface StructuredAnalysisPlan {
  operation: AnalysisOperation;
  column?: string | null;
  target_columns?: string[];
  group_by?: string[];
  date_column?: string | null;
  aggregation?: string;
  filters?: FilterGroup | null;
  sort_by?: string | null;
  sort_order?: 'asc' | 'desc';
  top_n?: number | null;
  bins?: number | null;
  interval?: 'day' | 'week' | 'month' | 'quarter' | 'year';
  method?: string | null;
  missing_policy?: 'exclude_and_report' | 'fail_on_missing';
  scope?: 'full_dataset' | 'sample';
  sample_size?: number | null;
  seed?: number;
  chart_type?: string | null;
  parameters?: Record<string, unknown>;
}

export interface ResultTable {
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
  truncated: boolean;
}

export interface ResultChart {
  id: string;
  title: string;
  kind: string;
  spec: { data: any[]; layout?: any };
}

export interface ExclusionNote {
  reason: string;
  count: number;
  column?: string | null;
}

export interface AnalysisResult {
  id: UUID;
  request_id?: UUID | null;
  dataset_id: UUID;
  dataset_fingerprint: string;
  operation: string;
  columns_used: string[];
  plan: StructuredAnalysisPlan;
  filters_applied?: FilterGroup | null;
  records_examined: number;
  records_used: number;
  records_excluded: number;
  exclusions: ExclusionNote[];
  missing_value_handling: string;
  is_sampled: boolean;
  sample_size?: number | null;
  sampling_method?: string | null;
  is_approximate: boolean;
  metrics: Record<string, any>;
  tables: ResultTable[];
  charts: ResultChart[];
  warnings: string[];
  methodology: string;
  summary_text: string;
  interpretation?: string | null;
  execution: {
    time_ms: number;
    engine: string;
    seed: number;
    cache_hit: boolean;
    code: string;
    library_versions: Record<string, string>;
    executed_at: string;
  };
  created_at?: string;
}

export interface ToolParam {
  name: string;
  type: string;
  description: string;
  choices?: string[] | null;
  min?: number | null;
  max?: number | null;
}

export interface ToolSpec {
  operation: string;
  family: string;
  description: string;
  column?: { kind: string; required: boolean; label: string } | null;
  target_columns?: { min: number; max: number; kind: string } | null;
  group_by?: { min: number; max: number; kind: string } | null;
  date_column: boolean;
  needs_filters: boolean;
  uses_aggregation: boolean;
  uses_interval: boolean;
  uses_bins: boolean;
  uses_top_n: boolean;
  methods?: string[] | null;
  cost: string;
  parameters: ToolParam[];
}

export interface SuggestedAnalysisPlan {
  title: string;
  description: string;
  family: string;
  plan: StructuredAnalysisPlan;
}

// Chat
export type ChatKind = 'analysis' | 'clarification' | 'cannot_answer' | 'ai_unavailable' | 'error';

export interface ChatResponse {
  session_id: UUID;
  request_id?: UUID | null;
  kind: ChatKind;
  reply_text: string;
  is_clarification_needed: boolean;
  clarifying_question?: string | null;
  cannot_answer_reason?: string | null;
  analysis_plan?: StructuredAnalysisPlan | null;
  analysis_result?: AnalysisResult | null;
  suggested_questions: string[];
  explanation_source?: 'llm' | 'template' | null;
  ai_configured: boolean;
  created_at?: string | null;
}

export interface ChatTurn {
  request_id: UUID;
  user_query: string;
  kind: ChatKind;
  assistant_message?: string | null;
  explanation_source?: 'llm' | 'template' | null;
  plan?: StructuredAnalysisPlan | null;
  result?: AnalysisResult | null;
  status: string;
  created_at: string;
}

export interface AIStatus {
  configured: boolean;
  provider?: string | null;
  message?: string | null;
}

// Sessions
export interface SessionSummary {
  id: UUID;
  dataset_id: UUID;
  dataset_name?: string | null;
  title: string;
  turn_count: number;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends SessionSummary {
  turns: ChatTurn[];
}

// Reports
export type ReportSection =
  | 'cover' | 'executive_summary' | 'dimensions_inventory' | 'types_roles' | 'descriptive_stats' | 'missing_values'
  | 'duplicates' | 'quality_findings' | 'univariate' | 'bivariate_multivariate' | 'correlations' | 'time_analysis'
  | 'user_analyses' | 'charts_tables' | 'interpretation_limitations' | 'reproducibility';

export interface ReportConfig {
  session_id: UUID;
  title: string;
  format: 'pdf' | 'html';
  concise_mode: boolean;
  included_sections: ReportSection[];
  included_result_ids?: UUID[] | null;
}

export interface ReportResponse {
  report_id: UUID;
  session_id: UUID;
  title: string;
  format: 'pdf' | 'html';
  status: 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILURE';
  download_url?: string | null;
  dataset_fingerprint: string;
  created_at: string;
  job_id?: string | null;
  error_message?: string | null;
  config?: ReportConfig | null;
}

// Background Jobs
export type JobStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILURE' | 'REVOKED';

export interface JobStatusResponse {
  job_id: string;
  dataset_id?: UUID | null;
  session_id?: UUID | null;
  job_type: 'profiling' | 'analysis' | 'report_generation' | 'conversion';
  status: JobStatus;
  progress_percentage: number;
  status_message: string;
  error_details?: string | null;
  result_ref?: Record<string, string> | null;
  created_at: string;
  completed_at?: string | null;
}
