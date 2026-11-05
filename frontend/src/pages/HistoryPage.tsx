import React from 'react';

export const HistoryPage: React.FC = () => {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Session & Dataset History</h2>
      <div className="bg-white rounded-lg shadow overflow-hidden border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Dataset</th>
              <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Format</th>
              <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Rows</th>
              <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Created</th>
              <th className="px-6 py-3 text-right font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            <tr>
              <td colSpan={5} className="px-6 py-4 text-center text-gray-400">
                No analysis sessions found. Upload a dataset to begin.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};
