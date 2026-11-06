import React from 'react';
import { SemanticRole, Severity } from '../../types';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'primary' | 'role' | 'severity' | 'outline' | 'success' | 'warning' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  role?: SemanticRole;
  severity?: Severity;
  className?: string;
  title?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  role,
  severity,
  className = '',
  title,
}) => {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  if (variant === 'role' || role) {
    const roleStyles: Record<SemanticRole, string> = {
      measure: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800',
      category: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800',
      identifier: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
      datetime: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
      boolean: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800',
      text: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800',
      unknown: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
    };
    const activeStyle = role ? roleStyles[role] : roleStyles.unknown;

    return (
      <span
        title={title}
        className={`inline-flex items-center rounded-full font-semibold border ${sizeClasses} ${activeStyle} ${className}`}
      >
        {children}
      </span>
    );
  }

  if (variant === 'severity' || severity) {
    const sevStyles: Record<Severity, string> = {
      high: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/50 dark:text-red-300 dark:border-red-800',
      medium: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800',
      low: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800',
    };
    const activeStyle = severity ? sevStyles[severity] : sevStyles.low;

    return (
      <span
        title={title}
        className={`inline-flex items-center rounded-full font-semibold border ${sizeClasses} ${activeStyle} ${className}`}
      >
        {children}
      </span>
    );
  }

  if (variant === 'primary') {
    return (
      <span
        title={title}
        className={`inline-flex items-center rounded-full font-semibold border bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/50 dark:text-indigo-300 dark:border-indigo-800 ${sizeClasses} ${className}`}
      >
        {children}
      </span>
    );
  }

  if (variant === 'success') {
    return (
      <span
        title={title}
        className={`inline-flex items-center rounded-full font-semibold border bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800 ${sizeClasses} ${className}`}
      >
        {children}
      </span>
    );
  }

  if (variant === 'warning') {
    return (
      <span
        title={title}
        className={`inline-flex items-center rounded-full font-semibold border bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800 ${sizeClasses} ${className}`}
      >
        {children}
      </span>
    );
  }

  if (variant === 'danger') {
    return (
      <span
        title={title}
        className={`inline-flex items-center rounded-full font-semibold border bg-red-50 text-red-700 border-red-200 dark:bg-red-950/50 dark:text-red-300 dark:border-red-800 ${sizeClasses} ${className}`}
      >
        {children}
      </span>
    );
  }

  if (variant === 'outline') {
    return (
      <span
        title={title}
        className={`inline-flex items-center rounded-full font-semibold border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 bg-transparent ${sizeClasses} ${className}`}
      >
        {children}
      </span>
    );
  }

  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-full font-medium bg-slate-100 text-slate-800 border border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700 ${sizeClasses} ${className}`}
    >
      {children}
    </span>
  );
};

export default Badge;
