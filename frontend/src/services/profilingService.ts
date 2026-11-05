import { apiClient } from './apiClient';
import { APIResponse, ProfilerResult, UUID } from '../types';

export const profilingService = {
  /**
   * Retrieves cached baseline profiling results for the specified dataset.
   */
  async getProfile(datasetId: UUID, userId?: string): Promise<ProfilerResult> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const res = await apiClient.get<APIResponse<ProfilerResult>>(`/profiling/${datasetId}`, {
      headers,
    });
    return res.data.data!;
  },

  /**
   * Triggers deterministic profiling computation for a dataset.
   */
  async triggerProfile(
    datasetId: UUID,
    sheetName?: string,
    userId?: string
  ): Promise<ProfilerResult> {
    const headers: Record<string, string> = {};
    if (userId) headers['X-User-ID'] = userId;

    const params: Record<string, string> = {};
    if (sheetName) params['sheet_name'] = sheetName;

    const res = await apiClient.post<APIResponse<ProfilerResult>>(
      `/profiling/${datasetId}`,
      null,
      { headers, params }
    );
    return res.data.data!;
  },
};

export default profilingService;
