import React, { useState, useRef } from 'react';
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
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { profilingService } from '../services/profilingService';
import { DatasetUploadResult, DatasetPreview, SheetInfo } from '../types';
import { useDataset } from '../context/DatasetContext';
import { Modal } from '../components/ui/Modal';
import { Tabs } from '../components/ui/Tabs';

export const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const { setUploadedDataset, loadDemoBenchmark } = useDataset();

  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

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

  const processFileUpload = async (file: File) => {
    setError(null);
    setPreview(null);
    setUploadResult(null);
    setIsUploading(true);
    setUploadProgress(0);

    try {
      const res = await datasetService.uploadFile(file, undefined, undefined, (percent) => {
        setUploadProgress(percent);
      });
      setUploadResult(res);

      if (res.requires_sheet_selection) {
        const sheetRes = await datasetService.inspectSheets(res.dataset_id);
        setAvailableSheets(sheetRes.sheets || []);
        setIsSheetModalOpen(true);
      } else {
        // Ingestion completed; fetch preview and trigger profiler
        const [prev, prof] = await Promise.all([
          datasetService.getPreview(res.dataset_id),
          profilingService.getProfile(res.dataset_id).catch(() => null),
        ]);
        setPreview(prev);

        setUploadedDataset(
          {
            id: res.dataset_id,
            name: res.name,
            originalFilename: res.original_filename,
            fileFormat: res.file_format,
            fileSizeBytes: res.file_size_bytes,
            rowCount: prev.total_rows,
            columnCount: prev.total_columns,
          },
          prof || undefined,
          prev
        );
      }
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
      const prof = await profilingService.getProfile(uploadResult.dataset_id).catch(() => null);

      setUploadedDataset(
        {
          id: uploadResult.dataset_id,
          name: `${uploadResult.name} (${sheetName})`,
          originalFilename: uploadResult.original_filename,
          fileFormat: uploadResult.file_format,
          fileSizeBytes: uploadResult.file_size_bytes,
          rowCount: prev.total_rows,
          columnCount: prev.total_columns,
        },
        prof || undefined,
        prev
      );
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
    <div className="max-w-6xl mx-auto px-6 py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
            Ingest Dataset
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Accepts CSV, TSV, or multi-sheet Excel (.xlsx). Enforces isolated storage and SHA-256 fingerprinting.
          </p>
        </div>

        {/* Load Sample Benchmark Button */}
        <button
          onClick={() => {
            loadDemoBenchmark();
            navigate('/overview');
          }}
          className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors shrink-0"
        >
          <Database className="w-3.5 h-3.5" />
          <span>Load Phase 0 Benchmark (Instant)</span>
        </button>
      </div>

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
          accept=".csv,.tsv,.xlsx,.xls,.parquet"
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
              Supports CSV, TSV, XLSX, XLS up to 100MB
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
              <span>Streaming & computing SHA-256...</span>
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
