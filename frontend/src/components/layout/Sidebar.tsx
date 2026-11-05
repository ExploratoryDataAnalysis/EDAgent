import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Home,
  UploadCloud,
  LayoutDashboard,
  Table2,
  Cpu,
  MessageSquare,
  BarChart2,
  History,
  FileSpreadsheet,
  Download,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  Database,
  Sparkles,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useDataset } from '../../context/DatasetContext';

export const Sidebar: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const { activeDataset, isDemoMode } = useDataset();

  const navigationItems = [
    { to: '/', label: 'Home', icon: Home },
    { to: '/upload', label: 'Upload Dataset', icon: UploadCloud },
    { to: '/overview', label: 'Dataset Overview', icon: LayoutDashboard },
    { to: '/inventory', label: 'Column Inventory', icon: Table2 },
    { to: '/workspace', label: 'Analysis Workspace', icon: Cpu },
    { to: '/chat', label: 'AI Dataset Chat', icon: MessageSquare },
    { to: '/visualize', label: 'Visualizations', icon: BarChart2 },
    { to: '/history', label: 'Analysis History', icon: History },
    { to: '/reports', label: 'Report Builder', icon: FileSpreadsheet },
    { to: '/exports', label: 'Export Centre', icon: Download },
  ];

  return (
    <aside
      className={`relative flex flex-col bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transition-all duration-300 z-30 select-none ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-slate-100 dark:border-slate-800">
        <NavLink to="/" className="flex items-center space-x-3 overflow-hidden">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 text-white shadow-md shadow-indigo-500/20 shrink-0">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-lg font-black tracking-tight text-slate-900 dark:text-white">
                EDA<span className="text-indigo-600 dark:text-indigo-400">gent</span>
              </span>
              <span className="text-[10px] font-medium text-slate-400 dark:text-slate-500 tracking-wider uppercase">
                v0.2.0 • Phase 2 Profiler
              </span>
            </div>
          )}
        </NavLink>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Active Dataset Pill */}
      {!collapsed && (
        <div className="p-3 mx-3 my-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/70 dark:border-slate-700/50">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                {activeDataset ? activeDataset.name : 'No dataset loaded'}
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                {activeDataset
                  ? `${activeDataset.rowCount || 0} rows • ${activeDataset.columnCount || 0} cols`
                  : 'Select or upload data'}
              </p>
            </div>
          </div>
          {isDemoMode && (
            <div className="mt-1.5 flex items-center justify-between">
              <span className="inline-block px-1.5 py-0.2 rounded text-[10px] font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300">
                Demo Preview Mode
              </span>
            </div>
          )}
        </div>
      )}

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center px-3 py-2.5 rounded-xl text-xs font-medium transition-all group ${
                  isActive
                    ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 shadow-sm border border-indigo-100 dark:border-indigo-900/50 font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/80 hover:text-slate-900 dark:hover:text-slate-200'
                }`
              }
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-110" />
              {!collapsed && <span className="ml-3 truncate">{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom Controls: Theme & Profile */}
      <div className="p-3 border-t border-slate-100 dark:border-slate-800 space-y-2">
        <button
          onClick={toggleTheme}
          className="flex items-center w-full px-3 py-2 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          {theme === 'dark' ? (
            <>
              <Sun className="w-4 h-4 text-amber-400 shrink-0" />
              {!collapsed && <span className="ml-3">Light Mode</span>}
            </>
          ) : (
            <>
              <Moon className="w-4 h-4 text-indigo-500 shrink-0" />
              {!collapsed && <span className="ml-3">Dark Mode</span>}
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
