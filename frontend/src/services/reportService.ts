import { apiClient } from './apiClient';
import { APIResponse, ReportConfig, ReportResponse } from '../types';

export const reportService = {
  async generateReport(config: ReportConfig): Promise<ReportResponse> {
    const res = await apiClient.post<APIResponse<ReportResponse>>('/reports/generate', {
      session_id: config.sessionId,
      title: config.title,
      format: config.format,
      concise_mode: config.conciseMode,
      included_sections: config.includedSections,
    });
    return res.data.data!;
  },
};
