/**
 * EDAgent API Contract & Domain Type Definitions
 * Strictly mirrors backend Pydantic schemas.
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

// Dataset
export type FileFormat = 'csv' | 'tsv' | 'xlsx' | 'xls' | 'parquet';

export interface Dataset {
  id: UUID;
  userId?: UUID;
  name: string;
  originalFilename: string;
  fileFormat: FileFormat;
  fileSizeBytes: number;
  rowCount?: number;
  columnCount?: number;
  checksumSha256: string;
  isDeleted: boolean;
  createdAt: string;
  updatedAt: string;
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

// Profiler
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
  skewness?: number;
  kurtosis?: number;
  zerosCount?: number;
  infiniteCount?: number;
}

export interface CategoricalTopValue {
  value: string;
  count: number;
  percentage: number;
}

export interface CategoricalSummary {
  uniqueCount: number;
  topValues: CategoricalTopValue[];
  isHighCardinality: boolean;
}

export interface ColumnProfile {
  name: string;
  storageDtype: string;
  inferredType: string;
  semanticRole: SemanticRole;
  roleConfidence: number;
  nonNullCount: number;
  missingCount: number;
  missingPercentage: number;
  distinctCount: number;
  isUnique: boolean;
  numericSummary?: NumericSummary;
  categoricalSummary?: CategoricalSummary;
  sampleValues: unknown[];
}

export interface QualityWarning {
  column?: string;
  checkType: string;
  severity: Severity;
  message: string;
  affectedCount?: number;
}

export interface MissingnessReport {
  totalCells: number;
  missingCells: number;
  overallMissingPercentage: number;
  perColumn: Record<string, number>;
  columnsWithMissing: string[];
}

export interface DuplicatesReport {
  exactDuplicateRowsCount: number;
  exactDuplicatePercentage: number;
  candidateDuplicateKeys: string[];
}

export interface DatasetOverview {
  datasetName: string;
  totalRows: number;
  totalColumns: number;
  fileSizeBytes: number;
  memoryEstimateBytes: number;
  selectedSheet?: string;
  loadTimeSeconds: number;
  parsingWarnings: string[];
}

export interface ProfilerResult {
  datasetId: UUID;
  overview: DatasetOverview;
  columns: ColumnProfile[];
  missingness: MissingnessReport;
  duplicates: DuplicatesReport;
  qualityWarnings: QualityWarning[];
  suggestedQuestions: string[];
  correlationMatrix?: Record<string, Record<string, number>>;
  computedAt: string;
}

// Analysis & Tools
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
  | 'custom_chart';

export interface StructuredAnalysisPlan {
  operation: AnalysisOperation;
  column?: string;
  targetColumns?: string[];
  filterExpression?: string;
  groupByColumn?: string;
  aggregation?: string;
  bins?: string;
  missingPolicy?: 'exclude_and_report' | 'exclude_silent' | 'fail_on_missing';
  scope?: 'full_dataset' | 'sample';
  chartType?: string;
  parameters?: Record<string, unknown>;
}

export interface AnalysisResult {
  id: UUID;
  requestId: UUID;
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
  role: MessageRole;
  content: string;
  resultId?: UUID;
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
  | 'cover'
  | 'executive_summary'
  | 'dataset_structure'
  | 'data_quality'
  | 'univariate_analysis'
  | 'bivariate_multivariate'
  | 'time_geography'
  | 'user_requested_analyses'
  | 'limitations'
  | 'appendix';

export interface ReportConfig {
  sessionId: UUID;
  title: string;
  format: 'pdf' | 'html';
  conciseMode: boolean;
  includedSections: ReportSection[];
}

export interface ReportResponse {
  reportId: UUID;
  sessionId: UUID;
  title: string;
  format: 'pdf' | 'html';
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
