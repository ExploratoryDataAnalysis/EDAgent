import React from 'react';

export const WorkspacePage: React.FC = () => {
  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left Sidebar: Schema and History */}
      <aside className="w-72 bg-gray-50 border-r border-gray-200 flex flex-col p-4 overflow-y-auto">
        <h3 className="font-semibold text-gray-700 text-sm mb-3 uppercase tracking-wider">Columns</h3>
        <div className="space-y-1 text-sm text-gray-600">
          <p className="italic text-xs text-gray-400">Select dataset to inspect columns</p>
        </div>
      </aside>

      {/* Center Canvas: Charts, Tables & Results */}
      <main className="flex-1 bg-white p-6 overflow-y-auto">
        <div className="border border-gray-200 rounded-lg p-6 bg-gray-50 text-center">
          <p className="text-gray-500">Analysis results and interactive charts will render here.</p>
        </div>
      </main>

      {/* Right Sidebar: AI Conversational Chat */}
      <aside className="w-96 bg-white border-l border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-800">AI Analysis Chat</h3>
        </div>
        <div className="flex-1 p-4 overflow-y-auto space-y-4">
          <div className="bg-blue-50 text-blue-900 p-3 rounded-lg text-sm">
            Ask any question about your data. EDAgent plans the calculation and computes exact results.
          </div>
        </div>
        <div className="p-4 border-t border-gray-200">
          <input
            type="text"
            placeholder="e.g. Show distribution of revenue..."
            className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </aside>
    </div>
  );
};
