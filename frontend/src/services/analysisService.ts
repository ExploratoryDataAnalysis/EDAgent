import { apiClient } from './apiClient';
import {
  APIResponse,
  AnalysisResult,
  StructuredAnalysisPlan,
  UUID,
} from '../types';

export const analysisService = {
  async executePlan(
    sessionId: UUID,
    query: string,
    plan?: StructuredAnalysisPlan
  ): Promise<AnalysisResult> {
    const res = await apiClient.post<APIResponse<AnalysisResult>>('/analysis/execute', {
      session_id: sessionId,
      user_query: query,
      override_plan: plan,
    });
    return res.data.data!;
  },

  async getResult(resultId: UUID): Promise<AnalysisResult> {
    const res = await apiClient.get<APIResponse<AnalysisResult>>(`/analysis/results/${resultId}`);
    return res.data.data!;
  },
};
