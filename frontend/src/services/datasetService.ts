import { apiClient } from './apiClient';
import {
  APIResponse,
  DatasetResponse,
  DatasetUploadResult,
  DatasetPreview,
  SheetInspectionResponse,
  DatasetListResponse,
  UUID,
} from '../types';

export const datasetService = {
  /**
   * Uploads a CSV, TSV, or XLSX file with upload progress callback.
   */
  async uploadFile(
    file: File,
    sheetName?: string,
    userId?: string,
    onProgress?: (percentage: number) => void
  ): Promise<DatasetUploadResult> {
    const formData = new FormData();
    formData.append('file', file);
    if (sheetName) {
      formData.append('sheet_name', sheetName);
    }

    const headers: Record<string, string> = {
      'Content-Type': 'multipart/form-data',
    };
    if (userId) {
      headers['X-User-ID'] = userId;
    }

    const res = await apiClient.post<APIResponse<DatasetUploadResult>>('/datasets/upload', formData, {
      headers,
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
    return res.data.data!;
  },

  /**
   * Inspects all sheets of an uploaded Excel workbook.
   */
  async inspectSheets(datasetId: UUID, userId?: string): Promise<SheetInspectionResponse> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.get<APIResponse<SheetInspectionResponse>>(
      `/datasets/${datasetId}/sheets`,
      { headers }
    );
    return res.data.data!;
  },

  /**
   * Selects a worksheet for an Excel dataset.
   */
  async selectSheet(datasetId: UUID, sheetName: string, userId?: string): Promise<DatasetPreview> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.post<APIResponse<DatasetPreview>>(
      `/datasets/${datasetId}/select-sheet`,
      { sheet_name: sheetName },
      { headers }
    );
    return res.data.data!;
  },

  /**
   * Confirms parsing options (e.g. custom delimiter or encoding).
   */
  async confirmIngestion(
    datasetId: UUID,
    options: { sheetName?: string; delimiter?: string; encoding?: string },
    userId?: string
  ): Promise<DatasetPreview> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.post<APIResponse<DatasetPreview>>(
      `/datasets/${datasetId}/confirm`,
      {
        sheet_name: options.sheetName,
        delimiter: options.delimiter,
        encoding: options.encoding,
      },
      { headers }
    );
    return res.data.data!;
  },

  /**
   * Retrieves dataset preview (head 10, tail 10, sample 10, inferred types).
   */
  async getPreview(datasetId: UUID, limit = 10, userId?: string): Promise<DatasetPreview> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.get<APIResponse<DatasetPreview>>(
      `/datasets/${datasetId}/preview`,
      {
        params: { limit },
        headers,
      }
    );
    return res.data.data!;
  },

  /**
   * Retrieves dataset metadata and storage details.
   */
  async getDataset(datasetId: UUID, userId?: string): Promise<DatasetResponse> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.get<APIResponse<DatasetResponse>>(
      `/datasets/${datasetId}`,
      { headers }
    );
    return res.data.data!;
  },

  /**
   * Lists datasets with pagination.
   */
  async listDatasets(skip = 0, limit = 20, userId?: string): Promise<DatasetListResponse> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.get<APIResponse<DatasetListResponse>>('/datasets', {
      params: { skip, limit },
      headers,
    });
    return res.data.data!;
  },

  /**
   * Deletes a dataset and frees its isolated storage.
   */
  async deleteDataset(datasetId: UUID, userId?: string): Promise<boolean> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.delete<APIResponse<boolean>>(`/datasets/${datasetId}`, {
      headers,
    });
    return res.data.data!;
  },
};
