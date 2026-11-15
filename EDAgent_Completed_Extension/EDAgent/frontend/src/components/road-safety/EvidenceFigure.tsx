import { isValidElement, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { pinnedArtifactUrl, type Provenance } from '../../services/roadSafetyService';

export const evidenceCard = 'min-w-0 space-y-3 border border-stone-300 bg-[#fffcf4] p-4 sm:p-6';
const number = new Intl.NumberFormat('en-US');
export const count = (value: number | null | undefined) => value == null ? 'Unavailable' : number.format(value);
export const percent = (value: number | null | undefined) => value == null ? 'Unavailable' : `${value.toFixed(2)}%`;

export function EvidenceHeader({ title, children }: { title: string; children: ReactNode }) {
  return <header className="public-hero public-measure">
    <p className="public-kicker">Allegheny County, Pennsylvania · 2004–2024</p>
    <h1>{title}</h1>
    <p className="public-lede">{children}</p>
    <div className="public-actions"><Link to="/road-safety">Road Safety Overview</Link></div>
  </header>;
}

export function EvidenceSource({ provenance, tables }: { provenance: Provenance; tables: [string, string][] }) {
  const fixture = provenance.bundle.version.startsWith('fixture-');
  return <figcaption className="space-y-1 border-t border-stone-300 pt-3 text-sm text-stone-700">
    <p>{fixture ? 'Synthetic verification data. Counts are invented.' : 'Frozen WPRDC Allegheny County crash extract.'}</p>
    <div className="public-actions">
      {tables.map(([table, label]) => <a key={table} href={pinnedArtifactUrl(`/downloads/${table}`, provenance)}>{label} (CSV)</a>)}
      <a href={pinnedArtifactUrl('/assets/descriptive_release_data_dictionary.md', provenance)}>Release data dictionary</a>
      <Link to="/methods">Methods</Link>
    </div>
  </figcaption>;
}

export function EvidenceIdentity({ provenance }: { provenance: Provenance }) {
  return <p className="break-words text-sm text-stone-600">
    Bundle {provenance.bundle.version} · Run {provenance.run_id} · Manifest SHA-256 {provenance.bundle.manifest_sha256}
  </p>;
}

export function DataTable({ label, columns, rows }: { label: string; columns: string[]; rows: ReactNode[][] }) {
  return <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={label}>
    <table className="w-full text-left text-sm">
      <caption className="sr-only">{label}</caption>
      <thead><tr>{columns.map(column => <th key={column} scope="col" className="border-b p-2">{column}</th>)}</tr></thead>
      <tbody>{rows.map(([heading, ...values]) => <tr key={isValidElement(heading) ? heading.key : String(heading)} className="border-b border-slate-200">
        <th scope="row" className="p-2 font-medium">{heading}</th>
        {values.map((value, index) => <td key={columns[index + 1]} className="p-2 tabular-nums">{value}</td>)}
      </tr>)}</tbody>
    </table>
  </div>;
}
