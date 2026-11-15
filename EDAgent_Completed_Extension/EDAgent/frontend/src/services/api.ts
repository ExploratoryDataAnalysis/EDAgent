/** Typed wrappers for every backend endpoint the UI uses. */

import { apiClient, downloadFile } from './apiClient';
import {
  AIStatus, AnalysisResult, APIResponse, AuthToken, ChatResponse, DatasetListResponse, DatasetPreview, DatasetResponse,
  DatasetRecoveryCandidate, DatasetUploadResult, JobStatusResponse, ProfilerResult, ReportConfig, ReportResponse, SampleDataset, SessionDetail, SessionSummary,
  SheetInspectionResponse, StructuredAnalysisPlan, SuggestedAnalysisPlan, ToolSpec, User, UUID,
} from '../types';

const unwrap = <T>(r: { data: APIResponse<T> }): T => r.data.data as T;

export const authService = {
  register: async (email: string, password: string, full_name?: string) =>
    unwrap<AuthToken>(await apiClient.post('/auth/register', { email, password, full_name })),
  login: async (email: string, password: string) => unwrap<AuthToken>(await apiClient.post('/auth/login', { email, password })),
  me: async () => unwrap<User>(await apiClient.get('/auth/me')),
  guestAvailability: async () => unwrap<{ available: boolean }>(await apiClient.get('/auth/guest-session')),
  startGuest: async () => unwrap<AuthToken>(await apiClient.post('/auth/guest-session')),
  clearGuest: async () => { await apiClient.delete('/auth/guest-session'); },
};

export const datasetService = {
  async uploadFile(file: File, sheetName?: string, onProgress?: (pct: number) => void): Promise<DatasetUploadResult> {
    const form = new FormData();
    form.append('file', file);
    if (sheetName) form.append('sheet_name', sheetName);
    const res = await apiClient.post<APIResponse<DatasetUploadResult>>('/datasets/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded * 100) / e.total)),
    });
    return unwrap(res);
  },
  importUrl: async (url: string, dataset_name?: string) => unwrap<DatasetUploadResult>(await apiClient.post('/datasets/import-url', { url, dataset_name })),
  listSamples: async () => unwrap<SampleDataset[]>(await apiClient.get('/datasets/samples')),
  listRecoverable: async () => unwrap<DatasetRecoveryCandidate[]>(await apiClient.get('/datasets/recoverable')),
  recover: async (id: UUID) => unwrap<DatasetUploadResult>(await apiClient.post(`/datasets/${id}/recover`)),
  loadSample: async (id: string) => unwrap<DatasetUploadResult>(await apiClient.post(`/datasets/samples/${encodeURIComponent(id)}`)),
  inspectSheets: async (id: UUID) => unwrap<SheetInspectionResponse>(await apiClient.get(`/datasets/${id}/sheets`)),
  selectSheet: async (id: UUID, sheet_name: string) => unwrap<DatasetPreview>(await apiClient.post(`/datasets/${id}/select-sheet`, { sheet_name })),
  confirmIngestion: async (id: UUID, o: { sheetName?: string; delimiter?: string; encoding?: string }) =>
    unwrap<DatasetPreview>(await apiClient.post(`/datasets/${id}/confirm`, { sheet_name: o.sheetName, delimiter: o.delimiter, encoding: o.encoding })),
  getPreview: async (id: UUID, limit = 10) => unwrap<DatasetPreview>(await apiClient.get(`/datasets/${id}/preview`, { params: { limit } })),
  getDataset: async (id: UUID) => unwrap<DatasetResponse>(await apiClient.get(`/datasets/${id}`)),
  listDatasets: async (skip = 0, limit = 100) => unwrap<DatasetListResponse>(await apiClient.get('/datasets', { params: { skip, limit } })),
  deleteDataset: async (id: UUID) => unwrap<boolean>(await apiClient.delete(`/datasets/${id}`)),
};

export const profilingService = {
  getProfile: async (id: UUID) => unwrap<ProfilerResult>(await apiClient.get(`/profiling/${id}`)),
  rerun: async (id: UUID) => unwrap<ProfilerResult>(await apiClient.post(`/profiling/${id}`)),
};

export const analysisService = {
  catalogue: async () => unwrap<ToolSpec[]>(await apiClient.get('/analysis/catalogue')),
  suggestions: async (datasetId: UUID) => unwrap<SuggestedAnalysisPlan[]>(await apiClient.get(`/analysis/suggestions/${datasetId}`)),
  execute: async (session_id: UUID, plan: StructuredAnalysisPlan, label?: string) =>
    unwrap<AnalysisResult>(await apiClient.post('/analysis/execute', { session_id, plan, label })),
  executeAsync: async (session_id: UUID, plan: StructuredAnalysisPlan, label?: string) =>
    unwrap<{ job_id: string }>(await apiClient.post('/analysis/execute-async', { session_id, plan, label })),
  getResult: async (id: UUID) => unwrap<AnalysisResult>(await apiClient.get(`/analysis/results/${id}`)),
};

export const chatService = {
  status: async () => unwrap<AIStatus>(await apiClient.get('/chat/status')),
  send: async (session_id: UUID, message: string, signal: AbortSignal) =>
    unwrap<ChatResponse>(await apiClient.post('/chat/message', { session_id, message }, { signal, timeout: 55000 })),
};

export const sessionService = {
  create: async (dataset_id: UUID, title?: string) => unwrap<SessionSummary>(await apiClient.post('/sessions', { dataset_id, title })),
  list: async (dataset_id?: UUID) => unwrap<SessionSummary[]>(await apiClient.get('/sessions', { params: dataset_id ? { dataset_id } : {} })),
  get: async (id: UUID) => unwrap<SessionDetail>(await apiClient.get(`/sessions/${id}`)),
  rename: async (id: UUID, title: string) => unwrap<SessionSummary>(await apiClient.patch(`/sessions/${id}`, { title })),
  remove: async (id: UUID) => unwrap<boolean>(await apiClient.delete(`/sessions/${id}`)),
};

export const jobService = {
  get: async (id: string) => unwrap<JobStatusResponse>(await apiClient.get(`/jobs/${id}`)),
  /** Polls until the job reaches a final state. */
  async waitFor(id: string, onUpdate?: (j: JobStatusResponse) => void, timeoutMs = 10 * 60 * 1000): Promise<JobStatusResponse> {
    const end = Date.now() + timeoutMs;
    for (;;) {
      const job = await jobService.get(id);
      onUpdate?.(job);
      if (['SUCCESS', 'FAILURE', 'REVOKED'].includes(job.status)) return job;
      if (Date.now() > end) throw new Error('Timed out waiting for the job.');
      await new Promise((r) => setTimeout(r, 1000));
    }
  },
};

export const reportService = {
  generate: async (cfg: ReportConfig) => unwrap<ReportResponse>(await apiClient.post('/reports/generate', cfg)),
  list: async (session_id?: UUID) => unwrap<ReportResponse[]>(await apiClient.get('/reports', { params: session_id ? { session_id } : {} })),
  get: async (id: UUID) => unwrap<ReportResponse>(await apiClient.get(`/reports/${id}`)),
  remove: async (id: UUID) => unwrap<boolean>(await apiClient.delete(`/reports/${id}`)),
  download: (id: UUID, name: string) => downloadFile(`/reports/${id}/download`, name),
};

export const exportService = {
  chart: (resultId: UUID, chartId: string, format: 'png' | 'svg' | 'html' | 'json') =>
    downloadFile(`/exports/results/${resultId}/charts/${encodeURIComponent(chartId)}`, `${chartId}.${format}`, { format }),
  table: (resultId: UUID, index: number, format: 'csv' | 'xlsx') => downloadFile(`/exports/results/${resultId}/tables/${index}`, `table.${format}`, { format }),
  metadata: (resultId: UUID) => downloadFile(`/exports/results/${resultId}/metadata`, 'metadata.json'),
  code: (resultId: UUID, format: 'py' | 'ipynb') => downloadFile(`/exports/results/${resultId}/code`, `analysis.${format}`, { format }),
  resultBundle: (resultId: UUID) => downloadFile(`/exports/results/${resultId}/bundle`, 'analysis_bundle.zip'),
  sessionBundle: (sessionId: UUID) => downloadFile(`/exports/sessions/${sessionId}/bundle`, 'session_results.zip'),
  profile: (datasetId: UUID, format: 'xlsx' | 'json') => downloadFile(`/exports/datasets/${datasetId}/profile`, `profile.${format}`, { format }),
};

/** Convenience for the dataset context. */
export const sampleApi = () => datasetService.listSamples();
