import React from 'react';

export const ReportBuilderPage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">One-Click EDA Report Builder</h2>
      <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
        <h3 className="font-semibold text-gray-800 mb-4">Select Report Sections</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-700">
          <label className="flex items-center space-x-2">
            <input type="checkbox" defaultChecked className="rounded text-blue-600" />
            <span>Executive Summary & Overview</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" defaultChecked className="rounded text-blue-600" />
            <span>Data Structure & Quality</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" defaultChecked className="rounded text-blue-600" />
            <span>Univariate & Bivariate Distributions</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" defaultChecked className="rounded text-blue-600" />
            <span>User-Requested Analyses</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" defaultChecked className="rounded text-blue-600" />
            <span>Methodology, Limitations & Appendix</span>
          </label>
        </div>
        <div className="mt-6 flex space-x-4">
          <button className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700">
            Generate PDF Report
          </button>
          <button className="border border-gray-300 text-gray-700 px-4 py-2 rounded text-sm font-medium hover:bg-gray-50">
            Export HTML
          </button>
        </div>
      </div>
    </div>
  );
};
