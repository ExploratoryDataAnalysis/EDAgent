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
  LogOut,
  Map,
  Calculator,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useDataset } from '../../context/DatasetContext';
import { useAuth } from '../../context/AuthContext';

export const Sidebar: React.FC = () => {
  // Start collapsed on narrow screens so the content area keeps usable width.
  const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' && window.innerWidth < 900);
  const { theme, toggleTheme } = useTheme();
  const { activeDataset } = useDataset();
  const { user, logout } = useAuth();

  const navigationItems = [
    { to: '/analyser', label: 'Home Workspace', icon: Home },
    { to: '/', label: 'Investigation', icon: Map },
    { to: '/upload', label: 'Upload Dataset', icon: UploadCloud },
    { to: '/overview', label: 'Dataset Overview', icon: LayoutDashboard },
    { to: '/inventory', label: 'Column Inventory', icon: Table2 },
    { to: '/workspace', label: 'Analysis Workspace', icon: Cpu },
    { to: '/visualize', label: 'Visualizations', icon: BarChart2 },
    { to: '/chat', label: 'AI Dataset Chat', icon: MessageSquare },
    { to: '/illustrative-scenario', label: 'Scenario Calculator', icon: Calculator },
    { to: '/history', label: 'Analysis History', icon: History },
    { to: '/reports', label: 'Report Builder', icon: FileSpreadsheet },
    { to: '/exports', label: 'Export Centre', icon: Download },
  ];
  const visibleItems = user?.guest ? navigationItems.filter((item) => item.to !== '/chat') : navigationItems;

  return (
    <aside
      className={`relative flex flex-col bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transition-all duration-300 z-30 select-none ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-slate-100 dark:border-slate-800">
        <NavLink to="/analyser" className="flex items-center space-x-3 overflow-hidden">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 text-white shadow-md shadow-indigo-500/20 shrink-0">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-lg font-black tracking-tight text-slate-900 dark:text-white">
                EDA<span className="text-indigo-600 dark:text-indigo-400">gent</span>
              </span>
              <span className="text-[10px] font-medium text-slate-400 dark:text-slate-500 tracking-wider uppercase">
                v1.0.0
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
      {!collapsed && user && (
        <div className="p-3 mx-3 my-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/70 dark:border-slate-700/50">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                {activeDataset ? activeDataset.name : 'No dataset loaded'}
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                {activeDataset
                  ? `${(activeDataset.row_count ?? 0).toLocaleString()} rows • ${activeDataset.column_count ?? 0} cols`
                  : 'Select or upload data'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {visibleItems.map((item) => {
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
              aria-label={item.label}
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
          aria-label={theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
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
        {user && !user.guest && (
          <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800/60">
            {!collapsed && (
              <span className="text-[11px] text-slate-600 dark:text-slate-300 truncate mr-2" title={user.email}>
                {user.email}
              </span>
            )}
            <button
              onClick={logout}
              title="Sign out"
              className="p-1 text-slate-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};
