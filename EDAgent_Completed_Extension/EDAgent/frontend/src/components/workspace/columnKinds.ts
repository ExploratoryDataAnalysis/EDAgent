import { ColumnProfile, ProfilerResult } from '../../types';

export type ColumnKind = 'numeric' | 'categorical' | 'datetime' | 'any';

/** Classifies a profiled column using what the backend profiler computed for it. */
export function kindOf(c: ColumnProfile): Exclude<ColumnKind, 'any'> {
  if (c.numeric_summary || c.semantic_role === 'measure') return 'numeric';
  if (c.date_summary || c.semantic_role === 'datetime') return 'datetime';
  return 'categorical';
}

/** Columns that satisfy a catalogue "kind" requirement. */
export function columnsFor(profile: ProfilerResult | null, kind: string | undefined): ColumnProfile[] {
  const cols = profile?.columns ?? [];
  if (!kind || kind === 'any') return cols;
  if (kind === 'categorical') return cols.filter((c) => kindOf(c) === 'categorical');
  return cols.filter((c) => kindOf(c) === kind);
}
