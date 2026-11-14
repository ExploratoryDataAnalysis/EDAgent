/**
 * Holds the active dataset, its profile/preview, and the active analysis session.
 * All data comes from the backend; the active dataset and session ids are remembered in
 * localStorage and re-validated against the server on load (so a deleted dataset never lingers).
 */
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Dataset, DatasetListItem, DatasetPreview, ProfilerResult, SampleDataset, SessionSummary, UUID } from '../types';
import { datasetService, profilingService, sampleApi, sessionService } from '../services/api';
import { useAuth } from './AuthContext';

const DATASET_KEY = 'edagent_active_dataset_id';
const SESSION_KEY = 'edagent_active_session_id';

interface DatasetContextType {
  activeDataset: Dataset | null;
  profile: ProfilerResult | null;
  profilerResult: ProfilerResult | null;
  preview: DatasetPreview | null;
  previewData: DatasetPreview | null;
  datasets: DatasetListItem[];
  samples: SampleDataset[];
  session: SessionSummary | null;
  isLoading: boolean;
  error: string | null;
  refreshDatasets: () => Promise<DatasetListItem[]>;
  selectDataset: (id: UUID) => Promise<void>;
  /** Loads an uploaded dataset (already stored on the server) as the active one. */
  setUploadedDataset: (datasetId: UUID) => Promise<void>;
  loadSample: (sampleId: string) => Promise<UUID | null>;
  deleteDataset: (id: UUID) => Promise<void>;
  triggerProfiling: () => Promise<void>;
  /** Returns the active session id, creating a session if none exists yet. */
  ensureSession: () => Promise<UUID>;
  newSession: (title?: string) => Promise<SessionSummary>;
  openSession: (id: UUID) => Promise<void>;
  clearError: () => void;
}

const DatasetContext = createContext<DatasetContextType | undefined>(undefined);

export const DatasetProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [activeDataset, setActiveDataset] = useState<Dataset | null>(null);
  const [profile, setProfile] = useState<ProfilerResult | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [datasets, setDatasets] = useState<DatasetListItem[]>([]);
  const [samples, setSamples] = useState<SampleDataset[]>([]);
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionRef = useRef<SessionSummary | null>(null);
  sessionRef.current = session;

  const message = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback);

  const refreshDatasets = useCallback(async (): Promise<DatasetListItem[]> => {
    try {
      const res = await datasetService.listDatasets();
      const items = res.items || [];
      setDatasets(items);
      return items;
    } catch (e) {
      setError(message(e, 'Could not load your datasets'));
      return [];
    }
  }, []);

  const reset = () => {
    setActiveDataset(null);
    setProfile(null);
    setPreview(null);
    setSession(null);
  };

  const selectDataset = useCallback(async (id: UUID) => {
    setIsLoading(true);
    setError(null);
    try {
      const ds = await datasetService.getDataset(id);
      const [prof, prev] = await Promise.all([
        profilingService.getProfile(id).catch(() => null),
        datasetService.getPreview(id).catch(() => null),
      ]);
      setActiveDataset(ds);
      setProfile(prof);
      setPreview(prev);
      localStorage.setItem(DATASET_KEY, id);

      // Resume the most recent session for this dataset (restored via /history or the chat page).
      const saved = localStorage.getItem(SESSION_KEY);
      const sessions = await sessionService.list(id).catch(() => [] as SessionSummary[]);
      const resume = sessions.find((s) => s.id === saved) || sessions[0] || null;
      setSession(resume);
      if (resume) localStorage.setItem(SESSION_KEY, resume.id);
      else localStorage.removeItem(SESSION_KEY);
    } catch (e) {
      setError(message(e, 'Failed to load dataset'));
      localStorage.removeItem(DATASET_KEY);
      reset();
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load everything for the user; auto-select active dataset; clear on sign-out.
  useEffect(() => {
    if (!user) {
      reset();
      setDatasets([]);
      return;
    }
    sampleApi().then(setSamples).catch(() => setSamples([]));
    refreshDatasets().then((items) => {
      const saved = localStorage.getItem(DATASET_KEY);
      if (saved && items.some((d) => d.id === saved)) {
        selectDataset(saved);
      } else if (items.length > 0) {
        selectDataset(items[0].id);
      }
    });
  }, [user, refreshDatasets, selectDataset]);

  const setUploadedDataset = useCallback(async (datasetId: UUID) => {
    await selectDataset(datasetId);
    await refreshDatasets();
  }, [selectDataset, refreshDatasets]);

  const loadSample = useCallback(async (sampleId: string): Promise<UUID | null> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await datasetService.loadSample(sampleId);
      await selectDataset(res.dataset_id);
      await refreshDatasets();
      return res.dataset_id;
    } catch (e) {
      setError(message(e, 'Could not load the sample dataset'));
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [selectDataset, refreshDatasets]);

  const deleteDataset = useCallback(async (id: UUID) => {
    await datasetService.deleteDataset(id);
    if (activeDataset?.id === id) {
      localStorage.removeItem(DATASET_KEY);
      localStorage.removeItem(SESSION_KEY);
      reset();
    }
    await refreshDatasets();
  }, [activeDataset, refreshDatasets]);

  const triggerProfiling = useCallback(async () => {
    if (!activeDataset) return;
    setIsLoading(true);
    setError(null);
    try {
      setProfile(await profilingService.rerun(activeDataset.id));
    } catch (e) {
      setError(message(e, 'Profiling failed'));
    } finally {
      setIsLoading(false);
    }
  }, [activeDataset]);

  const newSession = useCallback(async (title?: string) => {
    if (!activeDataset) throw new Error('Select a dataset first.');
    const s = await sessionService.create(activeDataset.id, title);
    setSession(s);
    localStorage.setItem(SESSION_KEY, s.id);
    return s;
  }, [activeDataset]);

  const ensureSession = useCallback(async (): Promise<UUID> => {
    if (sessionRef.current) return sessionRef.current.id;
    return (await newSession()).id;
  }, [newSession]);

  const openSession = useCallback(async (id: UUID) => {
    const detail = await sessionService.get(id);
    if (!activeDataset || activeDataset.id !== detail.dataset_id) await selectDataset(detail.dataset_id);
    setSession(detail);
    localStorage.setItem(SESSION_KEY, id);
  }, [activeDataset, selectDataset]);

  return (
    <DatasetContext.Provider
      value={{
        activeDataset, profile, profilerResult: profile, preview, previewData: preview, datasets, samples, session,
        isLoading, error, refreshDatasets, selectDataset, setUploadedDataset, loadSample, deleteDataset,
        triggerProfiling, ensureSession, newSession, openSession, clearError: () => setError(null),
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
};

export const useDataset = (): DatasetContextType => {
  const context = useContext(DatasetContext);
  if (!context) throw new Error('useDataset must be used within a DatasetProvider');
  return context;
};

export default DatasetContext;
