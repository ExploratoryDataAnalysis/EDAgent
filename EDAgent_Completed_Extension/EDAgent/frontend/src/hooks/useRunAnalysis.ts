import { useCallback, useState } from 'react';
import { AnalysisResult, StructuredAnalysisPlan } from '../types';
import { analysisService, jobService } from '../services/api';
import { useDataset } from '../context/DatasetContext';

/** Operations that fit models: run as background jobs so the page never blocks. */
const BACKGROUND_OPS = new Set(['kmeans', 'pca', 'linear_regression', 'classification']);

/**
 * Runs a validated analysis plan against the active dataset (creating a session on first use)
 * and exposes loading, progress and error state for the UI.
 */
export function useRunAnalysis(onDone?: (r: AnalysisResult) => void) {
  const { ensureSession } = useDataset();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const run = useCallback(async (plan: StructuredAnalysisPlan, label?: string) => {
    setRunning(true);
    setError(null);
    setProgress(null);
    try {
      const sessionId = await ensureSession();
      let res: AnalysisResult;
      if (BACKGROUND_OPS.has(plan.operation)) {
        const { job_id } = await analysisService.executeAsync(sessionId, plan, label);
        const job = await jobService.waitFor(job_id, (j) => setProgress(`${j.status_message} (${Math.round(j.progress_percentage)}%)`));
        if (job.status !== 'SUCCESS' || !job.result_ref?.result_id) throw new Error(job.error_details || job.status_message || 'The analysis did not finish.');
        res = await analysisService.getResult(job.result_ref.result_id);
      } else {
        res = await analysisService.execute(sessionId, plan, label);
      }
      setResult(res);
      onDone?.(res);
      return res;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
      return null;
    } finally {
      setRunning(false);
      setProgress(null);
    }
  }, [ensureSession, onDone]);

  return { run, running, progress, error, result, setResult, clearError: () => setError(null) };
}
