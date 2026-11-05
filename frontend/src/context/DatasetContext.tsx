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

  const refreshDatasets = useCallback(async () => {
    try {
      const res = await datasetService.listDatasets();
      setDatasets(res.items || []);
    } catch {
      // Backend may be offline or in demo mode; fall back gracefully
    }
  }, []);

  useEffect(() => {
    refreshDatasets();
  }, [refreshDatasets]);

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
      const [profData, prevData] = await Promise.all([
        profilingService.getProfile(id).catch(() => null),
        datasetService.getPreview(id).catch(() => null),
      ]);

      setActiveDataset(datasetObj);
      setProfile(profData || DEMO_PROFILER_RESULT);
      setPreview(prevData || DEMO_PREVIEW);
      setIsDemoMode(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load dataset';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

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
  };

  const setUploadedDataset = (
    dataset: Dataset,
    prof?: ProfilerResult,
    prev?: DatasetPreview
  ) => {
    setActiveDataset(dataset);
    if (prof) setProfile(prof);
    if (prev) setPreview(prev);
    setIsDemoMode(false);
    refreshDatasets();
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
