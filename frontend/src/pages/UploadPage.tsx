import React, { useState, useRef } from 'react';
import { datasetService } from '../services/datasetService';
import { DatasetUploadResult, DatasetPreview, SheetInfo } from '../types';

export const UploadPage: React.FC = () => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Staged Multi-Sheet Excel State
  const [uploadResult, setUploadResult] = useState<DatasetUploadResult | null>(null);
  const [availableSheets, setAvailableSheets] = useState<SheetInfo[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>('');

  // Final Ingestion Preview State
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [activeTab, setActiveTab] = useState<'head' | 'tail' | 'sample'>('head');

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
    setAvailableSheets([]);
    setIsUploading(true);
    setUploadProgress(0);

    try {
      const res = await datasetService.uploadFile(file, undefined, undefined, (percent) => {
        setUploadProgress(percent);
      });
      setUploadResult(res);

      if (res.requires_sheet_selection) {
        // Fetch sheet details for user to pick
        const sheetsRes = await datasetService.inspectSheets(res.dataset_id);
        setAvailableSheets(sheetsRes.sheets);
        if (sheetsRes.sheets.length > 0) {
          setSelectedSheet(sheetsRes.sheets[0].name);
        }
      } else {
        // Direct preview available
        const previewRes = await datasetService.getPreview(res.dataset_id, 10);
        setPreview(previewRes);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed. Please check your file.';
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSelectSheetConfirm = async () => {
    if (!uploadResult || !selectedSheet) return;
    setError(null);
    setIsUploading(true);
    try {
      const previewRes = await datasetService.selectSheet(uploadResult.dataset_id, selectedSheet);
      setPreview(previewRes);
      setAvailableSheets([]); // Close sheet selection modal
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to parse selected sheet.';
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const currentRecords = () => {
    if (!preview) return [];
    if (activeTab === 'head') return preview.head_records;
    if (activeTab === 'tail') return preview.tail_records;
    return preview.sample_records;
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div className="flex justify-between items-center border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Upload & Ingest Dataset</h1>
          <p className="text-sm text-gray-500 mt-1">
            Supported formats: CSV, TSV, and Excel (.xlsx). Maximum file size: 100 MB.
          </p>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-md">
          <div className="flex">
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Ingestion Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Dropzone & File Picker */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer ${
          isDragging
            ? 'border-blue-500 bg-blue-50/50'
            : 'border-gray-300 hover:border-gray-400 bg-white'
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".csv,.tsv,.xlsx"
          className="hidden"
        />

        <div className="space-y-3">
          <div className="mx-auto w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <div>
            <p className="text-base font-medium text-gray-700">
              Drag and drop your file here, or <span className="text-blue-600 hover:underline">browse</span>
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Deterministic parsing with delimiter sniffing, encoding recovery, and column role validation.
            </p>
          </div>
        </div>

        {/* Progress Bar */}
        {isUploading && (
          <div className="mt-6 max-w-xs mx-auto">
            <div className="flex justify-between text-xs text-gray-600 mb-1">
              <span>Uploading & Validating...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Multi-Sheet Selection Modal / Section */}
      {availableSheets.length > 1 && (
        <div className="bg-white rounded-lg border border-amber-200 p-6 shadow-sm">
          <div className="flex items-start space-x-3">
            <div className="p-2 bg-amber-100 text-amber-800 rounded-md">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-gray-900">Multiple Sheets Detected</h2>
              <p className="text-sm text-gray-600 mt-1">
                This workbook contains {availableSheets.length} worksheets. Please select which sheet to analyze:
              </p>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                {availableSheets.map((s) => (
                  <button
                    key={s.name}
                    type="button"
                    onClick={() => setSelectedSheet(s.name)}
                    className={`p-3 text-left border rounded-lg transition-all ${
                      selectedSheet === s.name
                        ? 'border-blue-600 bg-blue-50 ring-2 ring-blue-500'
                        : 'border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-medium text-gray-900">{s.name}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      {s.row_count_estimate ? `~${s.row_count_estimate} rows` : 'Table data'}
                    </div>
                  </button>
                ))}
              </div>
              <div className="mt-5 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={handleSelectSheetConfirm}
                  disabled={isUploading || !selectedSheet}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  Confirm & Ingest Worksheet
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Dataset Preview Screen */}
      {preview && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-gray-100 flex flex-wrap justify-between items-center gap-4 bg-gray-50/50">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-green-700 bg-green-100 px-2 py-1 rounded">
                Ingested Successfully
              </span>
              <h2 className="text-xl font-bold text-gray-900 mt-2">
                {uploadResult?.name || 'Dataset Preview'}
              </h2>
              <p className="text-xs text-gray-500 mt-1">
                {preview.total_rows} rows &times; {preview.total_columns} columns
                {preview.selected_sheet && ` (Sheet: ${preview.selected_sheet})`}
              </p>
            </div>
            <div className="flex space-x-2">
              <button
                type="button"
                onClick={() => setActiveTab('head')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md ${
                  activeTab === 'head' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                First 10 Rows
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('tail')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md ${
                  activeTab === 'tail' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Last 10 Rows
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('sample')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md ${
                  activeTab === 'sample' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Random Sample
              </button>
            </div>
          </div>

          {/* Parsing Warnings Alert */}
          {preview.parsing_warnings && preview.parsing_warnings.length > 0 && (
            <div className="px-6 py-3 bg-amber-50 border-b border-amber-100 text-xs text-amber-800">
              <span className="font-semibold">Parsing Warnings:</span>
              <ul className="list-disc list-inside mt-1 space-y-0.5">
                {preview.parsing_warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Column Inferred Types Badges */}
          <div className="p-4 border-b border-gray-100 flex flex-wrap gap-2 bg-white">
            <span className="text-xs font-semibold text-gray-500 self-center mr-2">Inferred Types:</span>
            {preview.column_names.map((col) => (
              <span
                key={col}
                className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800"
              >
                <span className="font-semibold mr-1">{col}:</span>
                <span className="text-blue-600">{preview.inferred_types[col] || 'string'}</span>
              </span>
            ))}
          </div>

          {/* Table Canvas with Horizontal & Vertical Scrolling */}
          <div className="overflow-x-auto max-h-96">
            <table className="min-w-full divide-y divide-gray-200 text-xs">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-2.5 text-left font-semibold text-gray-500">#</th>
                  {preview.column_names.map((col) => (
                    <th key={col} className="px-4 py-2.5 text-left font-semibold text-gray-700 whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200 font-mono">
                {currentRecords().map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-gray-50/80">
                    <td className="px-4 py-2 text-gray-400 whitespace-nowrap">{rIdx + 1}</td>
                    {preview.column_names.map((col) => (
                      <td key={col} className="px-4 py-2 text-gray-800 whitespace-nowrap max-w-xs truncate">
                        {String(row[col] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
