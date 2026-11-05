import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  Dataset,
  DatasetListItem,
  DatasetPreview,
  ProfilerResult,
  UUID,
} from '../types';
import { datasetService } from '../services/datasetService';
import { profilingService } from '../services/profilingService';
import {
  DEMO_DATASET,
  DEMO_PREVIEW,
  DEMO_PROFILER_RESULT,
  DEMO_SAMPLE_DATASETS,
} from '../services/demoData';

const SESSION_STORAGE_KEY = 'edagent_active_dataset_id';

interface DatasetContextType {
  activeDataset: Dataset | null;
  profile: ProfilerResult | null;
  profilerResult: ProfilerResult | null;
  preview: DatasetPreview | null;
  previewData: DatasetPreview | null;
  datasets: DatasetListItem[];
  isDemoMode: boolean;
  isLoading: boolean;
  error: string | null;
  refreshDatasets: () => Promise<void>;
  selectDataset: (id: UUID) => Promise<void>;
  loadDemoBenchmark: (sampleId?: string) => void;
  setUploadedDataset: (dataset: Dataset, prof?: ProfilerResult, prev?: DatasetPreview) => void;
  triggerProfiling: (datasetId?: UUID) => Promise<void>;
  clearError: () => void;
}

const DatasetContext = createContext<DatasetContextType | undefined>(undefined);

export const DatasetProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeDataset, setActiveDataset] = useState<Dataset | null>(DEMO_DATASET);
  const [profile, setProfile] = useState<ProfilerResult | null>(DEMO_PROFILER_RESULT);
  const [preview, setPreview] = useState<DatasetPreview | null>(DEMO_PREVIEW);
  const [datasets, setDatasets] = useState<DatasetListItem[]>([]);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = () => setError(null);

  // Fetch available datasets from backend API
  const refreshDatasets = useCallback(async () => {
    try {
      const res = await datasetService.listDatasets();
      setDatasets(res.items || []);
    } catch {
      // Backend may be offline or unreachable; fall back gracefully
    }
  }, []);

  // Hydrate session from localStorage on initial mount
  useEffect(() => {
    const hydrateSession = async () => {
      refreshDatasets();
      const savedId = localStorage.getItem(SESSION_STORAGE_KEY);
      if (!savedId) return;

      // Check if savedId is a demo benchmark
      const isBenchmark = DEMO_SAMPLE_DATASETS.some((s) => s.id === savedId) || savedId === DEMO_DATASET.id;
      if (isBenchmark) {
        loadDemoBenchmark(savedId);
        return;
      }

      // Saved ID is a real dataset from backend
      try {
        setIsLoading(true);
        const datasetObj = await datasetService.getDataset(savedId);
        let [profData, prevData] = await Promise.all([
          profilingService.getProfile(savedId).catch(() => null),
          datasetService.getPreview(savedId).catch(() => null),
        ]);

        // If profile was not yet computed, trigger it deterministically
        if (!profData) {
          profData = await profilingService.triggerProfile(savedId).catch(() => null);
        }

        if (datasetObj) {
          setActiveDataset(datasetObj);
          if (profData) setProfile(profData);
          if (prevData) setPreview(prevData);
          setIsDemoMode(false);
        }
      } catch {
        // Saved dataset not found on backend (e.g. database reset); revert to benchmark
        localStorage.removeItem(SESSION_STORAGE_KEY);
        loadDemoBenchmark();
      } finally {
        setIsLoading(false);
      }
    };

    hydrateSession();
  }, [refreshDatasets]);

  // Select dataset handler
  const selectDataset = async (id: UUID) => {
    // Check if selecting a demo sample
    const sample = DEMO_SAMPLE_DATASETS.find((s) => s.id === id);
    if (sample || id === DEMO_DATASET.id) {
      loadDemoBenchmark(id);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const datasetObj = await datasetService.getDataset(id);
      let [profData, prevData] = await Promise.all([
        profilingService.getProfile(id).catch(() => null),
        datasetService.getPreview(id).catch(() => null),
      ]);

      // If profiling was not pre-calculated, compute it now
      if (!profData) {
        profData = await profilingService.triggerProfile(id).catch(() => null);
      }

      setActiveDataset(datasetObj);
      if (profData) setProfile(profData);
      if (prevData) setPreview(prevData);
      setIsDemoMode(false);
      localStorage.setItem(SESSION_STORAGE_KEY, id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load dataset';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Switch to demo mode benchmark
  const loadDemoBenchmark = (sampleId?: string) => {
    setIsDemoMode(true);
    setError(null);
    const targetSample = DEMO_SAMPLE_DATASETS.find((s) => s.id === sampleId) || DEMO_SAMPLE_DATASETS[0];

    setActiveDataset({
      ...DEMO_DATASET,
      id: targetSample.id,
      name: targetSample.name,
      rowCount: targetSample.rows,
      columnCount: targetSample.columns,
    });
    setProfile(DEMO_PROFILER_RESULT);
    setPreview(DEMO_PREVIEW);
    localStorage.setItem(SESSION_STORAGE_KEY, targetSample.id);
  };

  // Update context after new file upload
  const setUploadedDataset = (
    dataset: Dataset,
    prof?: ProfilerResult,
    prev?: DatasetPreview
  ) => {
    setActiveDataset(dataset);
    if (prof) setProfile(prof);
    if (prev) setPreview(prev);
    setIsDemoMode(false);
    localStorage.setItem(SESSION_STORAGE_KEY, dataset.id);
    refreshDatasets();
  };

  // On-demand profiler re-run
  const triggerProfiling = async (datasetId?: UUID) => {
    const targetId = datasetId || activeDataset?.id;
    if (!targetId || isDemoMode) return;

    setIsLoading(true);
    setError(null);
    try {
      const prof = await profilingService.triggerProfile(targetId);
      setProfile(prof);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Profiling computation failed';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <DatasetContext.Provider
      value={{
        activeDataset,
        profile,
        profilerResult: profile,
        preview,
        previewData: preview,
        datasets,
        isDemoMode,
        isLoading,
        error,
        refreshDatasets,
        selectDataset,
        loadDemoBenchmark,
        setUploadedDataset,
        triggerProfiling,
        clearError,
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
};

export const useDataset = (): DatasetContextType => {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return context;
};

export default DatasetContext;
