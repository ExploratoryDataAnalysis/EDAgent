import React from 'react';

export const OverviewPage: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Automatic Dataset Profile</h2>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-4 rounded-lg shadow border border-gray-100">
          <span className="text-sm text-gray-500">Total Rows</span>
          <p className="text-2xl font-semibold text-gray-900 mt-1">-</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-100">
          <span className="text-sm text-gray-500">Columns</span>
          <p className="text-2xl font-semibold text-gray-900 mt-1">-</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-100">
          <span className="text-sm text-gray-500">Missing Values</span>
          <p className="text-2xl font-semibold text-gray-900 mt-1">-</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-100">
          <span className="text-sm text-gray-500">Exact Duplicates</span>
          <p className="text-2xl font-semibold text-gray-900 mt-1">-</p>
        </div>
      </div>
    </div>
  );
};
