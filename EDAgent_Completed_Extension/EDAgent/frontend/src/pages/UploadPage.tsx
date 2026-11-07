import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Database,
  Layers,
  Settings2,
  RefreshCw,
  FileText,
  Link2,
} from 'lucide-react';
import { datasetService } from '../services/api';
import { DatasetRecoveryCandidate, DatasetUploadResult, DatasetPreview, SheetInfo } from '../types';
import { useDataset } from '../context/DatasetContext';
import { Modal } from '../components/ui/Modal';
import { Tabs } from '../components/ui/Tabs';

export const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const { setUploadedDataset, loadSample, samples } = useDataset();
  const [importUrl, setImportUrl] = useState('');

  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [recoverableFiles, setRecoverableFiles] = useState<DatasetRecoveryCandidate[]>([]);
  const [recoveringDatasetId, setRecoveringDatasetId] = useState<string | null>(null);

  // Staged multi-sheet and preview states
  const [uploadResult, setUploadResult] = useState<DatasetUploadResult | null>(null);
  const [availableSheets, setAvailableSheets] = useState<SheetInfo[]>([]);
  const [isSheetModalOpen, setIsSheetModalOpen] = useState(false);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [activePreviewTab, setActivePreviewTab] = useState<'head' | 'tail' | 'sample'>('head');

  // Advanced parsing overrides
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customDelimiter, setCustomDelimiter] = useState<string>(',');
  const [customEncoding, setCustomEncoding] = useState<string>('utf-8');

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    datasetService.listRecoverable()
      .then((files) => { if (active) setRecoverableFiles(files); })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not check for stored uploads.');
      });
    return () => { active = false; };
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFileUpload(e.target.files[0]);
    }
  };

  /** Shared tail of upload / URL import: ask for a sheet if needed, otherwise open the dataset. */
  const afterIngest = async (res: DatasetUploadResult) => {
    setUploadResult(res);
    if (res.requires_sheet_selection) {
      const sheetRes = await datasetService.inspectSheets(res.dataset_id);
      setAvailableSheets(sheetRes.sheets || []);
      setIsSheetModalOpen(true);
      return;
    }
    setPreview(await datasetService.getPreview(res.dataset_id));
    await setUploadedDataset(res.dataset_id);
  };

  const handleImportUrl = async () => {
    if (!importUrl.trim()) return;
    setError(null);
    setPreview(null);
    setUploadResult(null);
    setIsUploading(true);
    setUploadProgress(0);
    try {
      await afterIngest(await datasetService.importUrl(importUrl.trim()));
      setImportUrl('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Import failed.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadSample = async (id: string) => {
    setError(null);
    const dsId = await loadSample(id);
    if (dsId) navigate('/overview');
  };

  const handleRecover = async (candidate: DatasetRecoveryCandidate) => {
    setError(null);
    setIsUploading(true);
    setRecoveringDatasetId(candidate.dataset_id);
    try {
      const result = await datasetService.recover(candidate.dataset_id);
      setRecoverableFiles((files) => files.filter((file) => file.dataset_id !== candidate.dataset_id));
      await afterIngest(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not restore the stored upload.');
    } finally {
      setIsUploading(false);
      setRecoveringDatasetId(null);
    }
  };

  const processFileUpload = async (file: File) => {
    setError(null);
    setPreview(null);
    setUploadResult(null);
    setIsUploading(true);
    setUploadProgress(0);

    try {
      const res = await datasetService.uploadFile(file, undefined, (percent) => {
        setUploadProgress(percent);
      });
      await afterIngest(res);

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed.';
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSelectWorksheet = async (sheetName: string) => {
    if (!uploadResult) return;
    setIsSheetModalOpen(false);
    setIsUploading(true);

    try {
      const prev = await datasetService.selectSheet(uploadResult.dataset_id, sheetName);
      setPreview(prev);
      await setUploadedDataset(uploadResult.dataset_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Sheet selection failed.';
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleApplyOverrides = async () => {
    if (!uploadResult) return;
    setIsUploading(true);
    setError(null);

    try {
      const prev = await datasetService.confirmIngestion(uploadResult.dataset_id, {
        delimiter: customDelimiter,
        encoding: customEncoding,
      });
      setPreview(prev);
      await setUploadedDataset(uploadResult.dataset_id); // profile and caches changed with the parse
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Re-parsing failed.';
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const activeRecords =
    activePreviewTab === 'head'
      ? preview?.head_records || []
      : activePreviewTab === 'tail'
      ? preview?.tail_records || []
      : preview?.sample_records || [];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
            Ingest Dataset
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Accepts CSV, TSV, or multi-sheet Excel (.xlsx). Your files are private to your account and fingerprinted with SHA-256.
          </p>
        </div>

      </div>

      {/* Sample datasets (served by the backend, copied into your account) and URL import */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center space-x-1.5"><Database className="w-3.5 h-3.5 text-indigo-500" /><span>Try a sample dataset</span></h3>
          {samples.length === 0 && <p className="text-xs text-slate-400">No samples available on this server.</p>}
          <ul className="space-y-1.5">
            {samples.map((sm) => (
              <li key={sm.id}>
                <button onClick={() => handleLoadSample(sm.id)} className="w-full text-left px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-indigo-400 text-xs flex items-center justify-between">
                  <span><b className="text-slate-800 dark:text-slate-200">{sm.name}</b><span className="block text-[11px] text-slate-500">{sm.description}</span></span>
                  <span className="ml-2 px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 text-[10px] font-semibold shrink-0">Sample</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center space-x-1.5"><Link2 className="w-3.5 h-3.5 text-indigo-500" /><span>Import from a URL</span></h3>
          <p className="text-[11px] text-slate-500 mb-2">Public http(s) links to a CSV, TSV or XLSX file. Private and internal addresses are blocked.</p>
          <div className="flex gap-2">
            <input value={importUrl} onChange={(e) => setImportUrl(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleImportUrl()} placeholder="https://example.com/data.csv" className="flex-1 min-w-0 px-3 py-2 rounded-xl text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100" />
            <button onClick={handleImportUrl} disabled={isUploading || !importUrl.trim()} className="px-3 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50">Import</button>
          </div>
        </div>
      </div>

      {recoverableFiles.length > 0 && (
        <section className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-indigo-200 dark:border-indigo-900/60">
          <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 mb-1 flex items-center space-x-1.5">
            <RefreshCw className="w-3.5 h-3.5 text-indigo-500" />
            <span>Restore saved uploads</span>
          </h3>
          <p className="text-[11px] text-slate-500 mb-3">
            These files are already stored for your account but are not registered on the dashboard.
          </p>
          <ul className="space-y-2">
            {recoverableFiles.map((file) => (
              <li key={file.dataset_id} className="flex items-center justify-between gap-3 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800">
                <span className="min-w-0 flex items-center gap-2 text-xs">
                  <FileText className="w-4 h-4 shrink-0 text-indigo-500" />
                  <span className="truncate font-semibold text-slate-800 dark:text-slate-200">{file.name}</span>
                  <span className="shrink-0 text-[11px] text-slate-500">{(file.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                </span>
                <button
                  type="button"
                  onClick={() => handleRecover(file)}
                  disabled={isUploading}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                >
                  {recoveringDatasetId === file.dataset_id ? 'Restoring…' : 'Restore'}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 flex items-start space-x-3 text-rose-700 dark:text-rose-300 text-xs">
          <AlertTriangle className="w-5 h-5 shrink-0 text-rose-500 mt-0.5" />
          <div>
            <strong className="font-bold">Ingestion Warning / Error:</strong>
            <p className="mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Drag & Drop Upload Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative rounded-3xl border-2 border-dashed p-10 text-center transition-all cursor-pointer ${
          isDragging
            ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30 scale-[1.01]'
            : 'border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-400 dark:hover:border-slate-700 shadow-sm'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.tsv,.xlsx"
          onChange={handleFileChange}
          className="hidden"
        />

        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center shadow-inner">
            <UploadCloud className="w-8 h-8" />
          </div>

          <div>
            <p className="text-base font-bold text-slate-800 dark:text-slate-100">
              Drag & drop your dataset file here, or <span className="text-indigo-600 dark:text-indigo-400 underline">browse</span>
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Supports CSV, TSV and XLSX
            </p>
          </div>

          <div className="flex items-center space-x-2 pt-2">
            <span className="px-2.5 py-1 rounded-md text-[10px] font-mono font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              CSV (Comma / Tab)
            </span>
            <span className="px-2.5 py-1 rounded-md text-[10px] font-mono font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              Excel (.XLSX)
            </span>
            <span className="px-2.5 py-1 rounded-md text-[10px] font-mono font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              TSV
            </span>
          </div>
        </div>

        {/* Upload Progress Bar */}
        {isUploading && (
          <div className="mt-6 max-w-sm mx-auto space-y-2">
            <div className="flex justify-between text-xs font-semibold text-slate-600 dark:text-slate-300">
              <span>Uploading and validating…</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Parsing Decision Banner if uploaded */}
      {uploadResult && (
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
            <div>
              <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                {uploadResult.name} Ingested Successfully
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {uploadResult.parsing_decision}
              </p>
            </div>
          </div>

          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-colors"
          >
            <Settings2 className="w-3.5 h-3.5" />
            <span>Parsing Settings</span>
          </button>
        </div>
      )}

      {/* Advanced Overrides Drawer */}
      {showAdvanced && uploadResult && (
        <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4">
          <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
            Override Ingestion Parameters
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-slate-600 dark:text-slate-400 mb-1">Delimiter</label>
              <select
                value={customDelimiter}
                onChange={(e) => setCustomDelimiter(e.target.value)}
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-slate-100"
              >
                <option value=",">Comma (,)</option>
                <option value="&#9;">Tab (\t)</option>
                <option value=";">Semicolon (;)</option>
                <option value="|">Pipe (|)</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-600 dark:text-slate-400 mb-1">Encoding</label>
              <select
                value={customEncoding}
                onChange={(e) => setCustomEncoding(e.target.value)}
                className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-slate-100"
              >
                <option value="utf-8">UTF-8</option>
                <option value="latin-1">Latin-1 (ISO-8859-1)</option>
                <option value="cp1252">Windows-1252</option>
              </select>
            </div>
          </div>
          <button
            onClick={handleApplyOverrides}
            className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Re-Parse Dataset</span>
          </button>
        </div>
      )}

      {/* Live Ingestion Preview Tabs & Table */}
      {preview && (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Ingestion Preview ({preview.total_rows} Rows × {preview.total_columns} Columns)
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                First 10 rows, last 10 rows, and random reservoir sample.
              </p>
            </div>

            <div className="flex items-center space-x-2">
              <Tabs
                variant="pills"
                activeTab={activePreviewTab}
                onChange={(id) => setActivePreviewTab(id as any)}
                tabs={[
                  { id: 'head', label: 'Head (First 10)', badge: preview.head_records.length },
                  { id: 'tail', label: 'Tail (Last 10)', badge: preview.tail_records.length },
                  { id: 'sample', label: 'Reservoir Sample', badge: preview.sample_records.length },
                ]}
              />
            </div>
          </div>

          {/* Inferred Column Types Badges Bar */}
          <div className="flex flex-wrap gap-1.5 py-1">
            {preview.column_names.map((col) => (
              <span
                key={col}
                className="px-2 py-1 rounded-md text-[11px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
              >
                {col}: <strong className="text-indigo-600 dark:text-indigo-400">{preview.inferred_types[col]}</strong>
              </span>
            ))}
          </div>

          {/* Records Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800 max-h-96">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800 text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800 font-semibold text-slate-500 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-mono">#</th>
                  {preview.column_names.map((col) => (
                    <th key={col} className="px-3 py-2 text-left font-mono whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {activeRecords.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="px-3 py-2 font-mono text-slate-400">{rIdx + 1}</td>
                    {preview.column_names.map((col) => (
                      <td key={col} className="px-3 py-2 font-mono text-slate-800 dark:text-slate-200 whitespace-nowrap">
                        {String(row[col] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Action CTAs to Profiler & Workspace */}
          <div className="pt-4 flex flex-wrap gap-3 justify-end border-t border-slate-100 dark:border-slate-800">
            <button
              onClick={() => navigate('/overview')}
              className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition-all"
            >
              <span>Explore Profiler Dashboard</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => navigate('/workspace')}
              className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
            >
              <span>Launch Analysis Workspace</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Excel Sheet Selector Modal */}
      <Modal
        isOpen={isSheetModalOpen}
        onClose={() => setIsSheetModalOpen(false)}
        title="Select Excel Worksheet"
        subtitle="This workbook contains multiple sheets. Choose which sheet to analyze."
        maxWidth="md"
      >
        <div className="space-y-3">
          {availableSheets.map((s) => (
            <button
              key={s.name}
              onClick={() => handleSelectWorksheet(s.name)}
              className="w-full p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-indigo-500 dark:hover:border-indigo-500 bg-white dark:bg-slate-800 text-left flex items-center justify-between group transition-all"
            >
              <div className="flex items-center space-x-3">
                <FileSpreadsheet className="w-5 h-5 text-indigo-500" />
                <div>
                  <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 group-hover:text-indigo-600">
                    {s.name}
                  </h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {s.row_count_estimate ? `~${s.row_count_estimate} rows` : 'Dimension scan ready'}
                  </p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-1 transition-all" />
            </button>
          ))}
        </div>
      </Modal>
    </div>
  );
};
