import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { ColumnProfile, FilterCondition, FilterGroup } from '../../types';
import { kindOf } from './columnKinds';

const OPERATORS: { value: string; label: string; arity: 0 | 1 | 2 | 'list' }[] = [
  { value: 'eq', label: '=', arity: 1 },
  { value: 'ne', label: '≠', arity: 1 },
  { value: 'gt', label: '>', arity: 1 },
  { value: 'gte', label: '≥', arity: 1 },
  { value: 'lt', label: '<', arity: 1 },
  { value: 'lte', label: '≤', arity: 1 },
  { value: 'between', label: 'between', arity: 2 },
  { value: 'in', label: 'is one of', arity: 'list' },
  { value: 'not_in', label: 'is not one of', arity: 'list' },
  { value: 'contains', label: 'contains', arity: 1 },
  { value: 'not_contains', label: 'does not contain', arity: 1 },
  { value: 'starts_with', label: 'starts with', arity: 1 },
  { value: 'is_null', label: 'is missing', arity: 0 },
  { value: 'not_null', label: 'is present', arity: 0 },
];

const field =
  'px-2 py-1.5 rounded-lg text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500';

/** Converts raw text into the type the backend expects for that column. */
function coerce(raw: string, numeric: boolean): string | number {
  const t = raw.trim();
  if (numeric && t !== '' && !Number.isNaN(Number(t))) return Number(t);
  return t;
}

interface Props {
  columns: ColumnProfile[];
  value: FilterGroup | null;
  onChange: (g: FilterGroup | null) => void;
}

/** Flat AND/OR filter builder. Values are typed by the selected column. */
export const FilterEditor: React.FC<Props> = ({ columns, value, onChange }) => {
  const conditions = (value?.conditions ?? []) as FilterCondition[];
  const logic = value?.logic ?? 'and';

  const emit = (conds: FilterCondition[], lg = logic) => onChange(conds.length ? { logic: lg, conditions: conds } : null);
  const update = (i: number, patch: Partial<FilterCondition>) => emit(conditions.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  const add = () => emit([...conditions, { column: columns[0]?.name ?? '', operator: 'eq', value: '' }]);

  const isNumeric = (name: string) => {
    const col = columns.find((c) => c.name === name);
    return col ? kindOf(col) === 'numeric' : false;
  };

  const renderValue = (c: FilterCondition, i: number) => {
    const op = OPERATORS.find((o) => o.value === c.operator);
    const numeric = isNumeric(c.column);
    if (!op || op.arity === 0) return null;
    if (op.arity === 2) {
      const [lo, hi] = Array.isArray(c.value) ? (c.value as unknown[]) : ['', ''];
      return (
        <>
          <input className={`${field} w-24`} placeholder="from" value={String(lo ?? '')} onChange={(e) => update(i, { value: [coerce(e.target.value, numeric), hi ?? ''] })} />
          <input className={`${field} w-24`} placeholder="to" value={String(hi ?? '')} onChange={(e) => update(i, { value: [lo ?? '', coerce(e.target.value, numeric)] })} />
        </>
      );
    }
    if (op.arity === 'list') {
      return (
        <input
          className={`${field} w-48`}
          placeholder="a, b, c"
          value={Array.isArray(c.value) ? (c.value as unknown[]).join(', ') : ''}
          onChange={(e) => update(i, { value: e.target.value.split(',').map((v) => coerce(v, numeric)).filter((v) => v !== '') })}
        />
      );
    }
    return (
      <input
        className={`${field} w-40`}
        placeholder="value"
        value={c.value === undefined || c.value === null ? '' : String(c.value)}
        onChange={(e) => update(i, { value: ['contains', 'not_contains', 'starts_with'].includes(c.operator) ? e.target.value : coerce(e.target.value, numeric) })}
      />
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">Filters</span>
        <div className="flex items-center gap-2">
          {conditions.length > 1 && (
            <select aria-label="Combine filters with" className={field} value={logic} onChange={(e) => emit(conditions, e.target.value as 'and' | 'or')}>
              <option value="and">match ALL</option>
              <option value="or">match ANY</option>
            </select>
          )}
          <button type="button" onClick={add} disabled={!columns.length} className="inline-flex items-center space-x-1 text-xs text-indigo-600 dark:text-indigo-400 font-semibold disabled:opacity-40">
            <Plus className="w-3.5 h-3.5" /><span>Add filter</span>
          </button>
        </div>
      </div>
      {conditions.length === 0 && <p className="text-[11px] text-slate-400">No filters — the whole dataset is used.</p>}
      {conditions.map((c, i) => (
        <div key={i} className="flex flex-wrap items-center gap-1.5">
          <select aria-label="Filter column" className={field} value={c.column} onChange={(e) => update(i, { column: e.target.value, value: '' })}>
            {columns.map((col) => <option key={col.name} value={col.name}>{col.name}</option>)}
          </select>
          <select aria-label="Filter operator" className={field} value={c.operator} onChange={(e) => update(i, { operator: e.target.value, value: '' })}>
            {OPERATORS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {renderValue(c, i)}
          <button type="button" aria-label="Remove filter" onClick={() => emit(conditions.filter((_, idx) => idx !== i))} className="p-1 text-slate-400 hover:text-red-500">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
};

export default FilterEditor;
