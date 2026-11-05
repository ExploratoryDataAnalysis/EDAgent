import React from 'react';

export const HomePage: React.FC = () => {
  return (
    <div className="max-w-5xl mx-auto px-4 py-12">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-extrabold tracking-tight text-gray-900 sm:text-5xl">
          EDAgent
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          Upload your data. Discover insights. Ask anything. Verify every result.
        </p>
      </div>
      <div className="mt-12 bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900">Supported Formats</h2>
        <p className="mt-1 text-sm text-gray-500">
          CSV, TSV, and Excel (XLSX/XLS). Parquet and JSON coming in future releases.
        </p>
      </div>
    </div>
  );
};
