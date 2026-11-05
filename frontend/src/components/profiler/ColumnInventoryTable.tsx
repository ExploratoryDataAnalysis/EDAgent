import React, { useState, useMemo } from 'react';
import { Search, Filter, Eye, ChevronRight } from 'lucide-react';
import { ColumnProfile, SemanticRole } from '../../types';
import { Badge } from '../ui/Badge';
import { ColumnDetailModal } from './ColumnDetailModal';

interface ColumnInventoryTableProps {
  columns: ColumnProfile[];
}

export const ColumnInventoryTable: React.FC<ColumnInventoryTableProps> = ({ columns }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('all');
  const [selectedCol, setSelectedCol] = useState<ColumnProfile | null>(null);

  const roleFilterOptions = [
    { id: 'all', label: 'All Columns', count: columns.length },
    { id: 'measure', label: 'Measures', count: columns.filter((c) => (c.semantic_role || c.semanticRole) === 'measure').length },
    { id: 'category', label: 'Categories', count: columns.filter((c) => (c.semantic_role || c.semanticRole) === 'category').length },
    { id: 'identifier', label: 'Identifiers', count: columns.filter((c) => (c.semantic_role || c.semanticRole) === 'identifier').length },
    { id: 'datetime', label: 'Datetime', count: columns.filter((c) => (c.semantic_role || c.semanticRole) === 'datetime').length },
    { id: 'boolean', label: 'Booleans', count: columns.filter((c) => (c.semantic_role || c.semanticRole) === 'boolean').length },
    { id: 'text', label: 'Text', count: columns.filter((c) => (c.semantic_role || c.semanticRole) === 'text').length },
  ];

  const filteredColumns = useMemo(() => {
    return columns.filter((col) => {
      const role = col.semantic_role || col.semanticRole || 'unknown';
      const matchesSearch = col.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesRole = selectedRole === 'all' || role === selectedRole;
      return matchesSearch && matchesRole;
    });
  }, [columns, searchTerm, selectedRole]);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      {/* Controls Bar: Search & Role Filters */}
      <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search column inventory..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-slate-100"
          />
        </div>

        {/* Role Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 md:pb-0">
          <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0 mr-1" />
          {roleFilterOptions.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setSelectedRole(opt.id)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-colors flex items-center space-x-1 ${
                selectedRole === opt.id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              <span>{opt.label}</span>
              <span className={`text-[10px] px-1 rounded-full ${selectedRole === opt.id ? 'bg-indigo-700 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-500'}`}>
                {opt.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800 text-xs">
          <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 font-semibold tracking-wider uppercase text-[11px]">
            <tr>
              <th className="px-5 py-3 text-left">Column</th>
              <th className="px-4 py-3 text-left">Semantic Role</th>
              <th className="px-4 py-3 text-left">Data Types</th>
              <th className="px-4 py-3 text-left">Missingness</th>
              <th className="px-4 py-3 text-left">Distinct Values</th>
              <th className="px-4 py-3 text-left">Sample Values</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {filteredColumns.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-slate-400">
                  No columns match your search or filter.
                </td>
              </tr>
            ) : (
              filteredColumns.map((col) => {
                const role = col.semantic_role || col.semanticRole || 'unknown';
                const missingPct = col.missing_percentage ?? col.missingPercentage ?? 0;
                const samples = col.sample_values || col.sampleValues || [];

                return (
                  <tr
                    key={col.name}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors cursor-pointer group"
                    onClick={() => setSelectedCol(col)}
                  >
                    {/* Column Name */}
                    <td className="px-5 py-3.5 font-mono font-bold text-slate-900 dark:text-slate-100 whitespace-nowrap">
                      {col.name}
                    </td>

                    {/* Semantic Role with Confidence */}
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <div className="flex items-center space-x-1.5">
                        <Badge role={role}>{role.toUpperCase()}</Badge>
                        <span className="text-[11px] text-slate-400 font-mono" title="Role Confidence">
                          {Math.round((col.role_confidence || col.roleConfidence || 1) * 100)}%
                        </span>
                      </div>
                    </td>

                    {/* Storage & Inferred Type */}
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="font-mono text-slate-700 dark:text-slate-300">
                          {col.inferred_type || col.inferredType}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          storage: {col.storage_dtype || col.storageDtype}
                        </span>
                      </div>
                    </td>

                    {/* Missingness with mini progress bar */}
                    <td className="px-4 py-3.5 whitespace-nowrap min-w-[120px]">
                      <div className="flex flex-col space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className={missingPct > 0 ? 'text-amber-600 dark:text-amber-400 font-bold' : 'text-slate-500'}>
                            {missingPct}%
                          </span>
                          <span className="text-slate-400 font-mono">
                            {col.missing_count ?? col.missingCount} missing
                          </span>
                        </div>
                        <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              missingPct > 40 ? 'bg-rose-500' : missingPct > 10 ? 'bg-amber-500' : 'bg-indigo-500'
                            }`}
                            style={{ width: `${Math.min(missingPct, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Distinct Count */}
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-medium text-slate-700 dark:text-slate-300">
                          {col.distinct_count ?? col.distinctCount}
                        </span>
                        {(col.is_unique || col.isUnique) && (
                          <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                            Unique Key
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Sample Values */}
                    <td className="px-4 py-3.5">
                      <div className="flex items-center space-x-1 max-w-xs overflow-hidden">
                        {samples.slice(0, 3).map((s, i) => (
                          <span
                            key={i}
                            className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[11px] font-mono text-slate-600 dark:text-slate-300 truncate max-w-[90px]"
                            title={String(s)}
                          >
                            {String(s)}
                          </span>
                        ))}
                        {samples.length > 3 && (
                          <span className="text-[10px] text-slate-400 font-mono shrink-0">
                            +{samples.length - 3}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Action */}
                    <td className="px-4 py-3.5 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedCol(col);
                        }}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Column Detail Modal */}
      <ColumnDetailModal
        column={selectedCol}
        onClose={() => setSelectedCol(null)}
      />
    </div>
  );
};
