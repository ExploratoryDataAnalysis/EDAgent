/**
 * EDAgent API Contract & Domain Type Definitions
 * Strictly aligns with Phase 0, 1, and 2 backend Pydantic specifications.
 */

export type UUID = string;

// API Response Envelopes
export interface APIResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  errors?: string[];
}

export interface ErrorResponse {
  success: false;
  message: string;
  errors: string[];
  errorCode?: string;
}

// User & Auth
export interface User {
  id: UUID;
  email: string;
  fullName?: string;
  isActive: boolean;
  isSuperuser: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AuthTokens {
  accessToken: string;
  tokenType: string;
  expiresInSeconds: number;
}

// Dataset Formats & Entity
export type FileFormat = 'csv' | 'tsv' | 'xlsx' | 'xls' | 'parquet';

export interface Dataset {
  id: UUID;
  userId?: UUID;
  name: string;
  originalFilename?: string;
  fileFormat: FileFormat;
  fileSizeBytes: number;
  rowCount?: number;
  columnCount?: number;
  checksumSha256?: string;
  isDeleted?: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export type DatasetResponse = Dataset;

export interface DatasetUploadResult {
  dataset_id: UUID;
  name: string;
  original_filename: string;
  file_format: FileFormat;
  file_size_bytes: number;
  multiple_sheets_found: boolean;
  detected_sheets?: string[];
  selected_sheet?: string;
  requires_sheet_selection: boolean;
  parsing_decision: string;
  storage_uri: string;
  created_at: string;
}

export interface SheetInfo {
  name: string;
  row_count_estimate?: number;
  column_count_estimate?: number;
}

export interface SheetInspectionResponse {
  dataset_id: UUID;
  sheets: SheetInfo[];
  default_sheet?: string;
}

export interface DatasetPreview {
  dataset_id: UUID;
  selected_sheet?: string;
  total_rows: number;
  total_columns: number;
  column_names: string[];
  inferred_types: Record<string, string>;
  head_records: Record<string, unknown>[];
  tail_records: Record<string, unknown>[];
  sample_records: Record<string, unknown>[];
  parsing_warnings: string[];
}

export interface DatasetListItem {
  id: UUID;
  name: string;
  original_filename: string;
  file_format: FileFormat;
  file_size_bytes: number;
  row_count?: number;
  column_count?: number;
  created_at: string;
}

export interface DatasetListResponse {
  items: DatasetListItem[];
  total: number;
  page: number;
  page_size: number;
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
// Analysis, Chat & Execution Schemas
// ==========================================

export type AnalysisOperation =
  | 'descriptive_stats'
  | 'histogram'
  | 'boxplot'
  | 'violin_plot'
  | 'correlation'
  | 'group_by'
  | 'outlier_iqr'
  | 'outlier_zscore'
  | 'crosstab'
  | 'time_trend'
  | 'scatter_plot'
  | 'custom_chart'
  | 'outlier_scan'
  | 'summary_query'
  | string;

export interface StructuredAnalysisPlan {
  operation: AnalysisOperation;
  column?: string;
  targetColumns?: string[];
  filterExpression?: string;
  groupByColumn?: string;
  aggregation?: string;
  bins?: string;
  missingPolicy?: 'exclude_and_report' | 'exclude_silent' | 'fail_on_missing' | string;
  scope?: 'full_dataset' | 'sample';
  chartType?: string;
  parameters?: Record<string, unknown>;
}

export interface AnalysisResult {
  id: UUID;
  requestId?: UUID;
  operationType: string;
  summaryText: string;
  executionCode: string;
  recordsExamined: number;
  recordsUsed: number;
  isSampled: boolean;
  sampleSize?: number;
  plotSpec?: Record<string, unknown>;
  dataTable?: Record<string, unknown>[];
  warnings: string[];
  executionTimeMs: number;
}

// Chat
export type MessageRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id?: string;
  role: MessageRole;
  content: string;
  analysisPlan?: StructuredAnalysisPlan;
  analysisResult?: AnalysisResult;
  suggestedQuestions?: string[];
  createdAt?: string;
}

export interface ChatResponse {
  sessionId: UUID;
  replyText: string;
  isClarificationNeeded: boolean;
  clarifyingQuestion?: string;
  cannotAnswerReason?: string;
  analysisPlan?: StructuredAnalysisPlan;
  analysisResult?: AnalysisResult;
}

// Reports
export type ReportSection =
  | 'executive_summary'
  | 'dataset_overview'
  | 'data_quality'
  | 'univariate_distributions'
  | 'bivariate_relationships'
  | 'user_analyses'
  | 'limitations_appendix';

export interface ReportConfig {
  sessionId?: UUID;
  datasetId?: UUID;
  title: string;
  format: 'pdf' | 'html' | 'markdown';
  conciseMode: boolean;
  includedSections: ReportSection[];
  anonymizeRecords?: boolean;
}

export interface ReportResponse {
  reportId: UUID;
  sessionId?: UUID;
  title: string;
  format: 'pdf' | 'html' | 'markdown';
  downloadUrl: string;
  datasetFingerprint: string;
  createdAt: string;
}

// Background Jobs
export type JobStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILURE' | 'REVOKED';

export interface JobStatusResponse {
  jobId: string;
  datasetId?: UUID;
  sessionId?: UUID;
  jobType: 'profiling' | 'analysis' | 'report_generation' | 'conversion';
  status: JobStatus;
  progressPercentage: number;
  statusMessage: string;
  errorDetails?: string;
  createdAt: string;
  completedAt?: string;
}
