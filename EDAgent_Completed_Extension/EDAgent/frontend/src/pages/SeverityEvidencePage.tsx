import { useState } from 'react';
import { ReleaseStatus, useReleaseRequest } from '../components/layout/ReleaseStatus';
import { count, DataTable, evidenceCard, EvidenceHeader, EvidenceIdentity, EvidenceSource, percent } from '../components/road-safety/EvidenceFigure';
import {
  confirmRelease, loadProvenance, releaseTables, type CountyPeriod, type FieldCoverage, type Severity,
} from '../services/roadSafetyService';

type Missingness = { source_field: string; missing_crashes: number; reported_crashes: number; missing_percent_of_reported: number | null };
type Association = {
  feature: string; period_start: number; period_end: number; tested_crashes: number;
  known_severity_crashes_in_period: number; reported_crashes_in_period: number;
  tested_levels: number; pooled_source_levels: string | null; min_expected_cell: number;
  cramers_v: number | null; fdr_bh_q: number | null; fdr_bh_q_underflow: boolean;
};

const eras = [[2004, 2015], [2016, 2024]];
const features: Record<string, string> = {
  COLLISION_LABEL: 'Collision type', ILLUMINATION_LABEL: 'Illumination',
  TIME_PERIOD: 'Time period', INTERSECTION_LABEL: 'Intersection type',
};
const fields = { valid_hour: 'Valid hour', nonmissing_illumination: 'Populated illumination' };

async function loadEvidence(signal: AbortSignal) {
  const provenance = await loadProvenance(signal);
  const { table, caveats } = releaseTables(provenance, signal);
  const [county, severity, coverage, missingness, associations] = await Promise.all([
    table<CountyPeriod>('county_periods'), table<Severity>('severity_composition'),
    table<FieldCoverage>('field_coverage_by_year'), table<Missingness>('source_missingness'),
    table<Association>('severity_associations'),
  ]);
  const composition = eras.map(([start, end]) => {
    const totals = county.find(row => row.period_grain === 'era' && row.period_start === start && row.period_end === end);
    const groups = severity.filter(row => row.period_grain === 'era' && row.period_start === start && row.period_end === end);
    // Known codes use the measured severity population. Excluded codes use all reports.
    const known = groups.filter(row => row.denominator_population === 'known severity');
    const excluded = groups.filter(row => row.denominator_population === 'all reports');
    if (totals && groups.length && (
      known.reduce((sum, row) => sum + row.crashes, 0) !== totals.known_severity_crashes
      || excluded.reduce((sum, row) => sum + row.crashes, 0) !== totals.unknown_severity_crashes
      || known.length + excluded.length !== groups.length
      || totals.known_severity_crashes + totals.unknown_severity_crashes !== totals.reported_crashes
      || known.some(row => row.denominator_crashes !== totals.known_severity_crashes)
      || excluded.some(row => row.denominator_crashes !== totals.reported_crashes)
    )) throw new Error('The severity denominators do not reconcile.');
    return { start, end, totals, known, excluded };
  });
  await confirmRelease(provenance, signal);
  return { provenance, composition, coverage, missingness, associations, caveats };
}

const confirmEvidence = ({ provenance }: Awaited<ReturnType<typeof loadEvidence>>, signal: AbortSignal) =>
  confirmRelease(provenance, signal);

function Bars({ rows }: { rows: { key: string; label: string; width: number | null; value: string }[] }) {
  return <ul className="max-w-2xl space-y-2 text-sm" aria-hidden="true">
    {rows.map(({ key, label, width, value }) => <li key={key}>
      <div className="flex flex-wrap justify-between gap-x-2"><span>{label}</span><span className="tabular-nums">{value}</span></div>
      {width !== null && <div className="h-2 bg-stone-200"><div className="h-full bg-[#0e6059]" style={{ width: `${width}%` }} /></div>}
    </li>)}
  </ul>;
}

export function SeverityEvidencePage() {
  const { state, retry } = useReleaseRequest(loadEvidence, confirmEvidence);
  return <article className="public-document">
    <EvidenceHeader title="Severity and measurement">
      Explore how crash severity was recorded, where field coverage limits comparisons, and how strongly recorded features were associated with serious or fatal outcomes.
    </EvidenceHeader>
    {state.kind === 'ready' ? <SeverityFigures data={state.data} /> : <div className="public-measure"><ReleaseStatus kind={state.kind} retry={retry} /></div>}
  </article>;
}

function SeverityFigures({ data }: { data: Awaited<ReturnType<typeof loadEvidence>> }) {
  const { provenance, composition, coverage, missingness, caveats, associations } = data;
  const recording = Object.entries(fields).map(([metric, label]) => ({
    label, row: coverage.find(row => row.period_start === 2024 && row.metric_id === metric),
  }));
  const ordered = [...associations].sort((a, b) => (b.cramers_v ?? -1) - (a.cramers_v ?? -1));
  return <div className="space-y-5">
    <figure className={evidenceCard}>
      <h2>How was severity recorded in each era?</h2>
      <p>PennDOT changed its injury-severity standard in 2016. {caveats.SEVERITY_CODING_BREAK_2016} A combined serious/fatal measure across both eras is unavailable.</p>
      <div className="grid gap-5 xl:grid-cols-2">
        {composition.map(({ start, end, totals, known, excluded }) => {
          const period = `${start}–${end}`;
          return <section key={period} aria-label={period} className="min-w-0 space-y-2">
            <h3 className="font-semibold">{period}</h3>
            {totals && known.length ? <>
              <p>{count(totals.known_severity_crashes)} of {count(totals.reported_crashes)} reports have known severity.
                {' '}{count(totals.unknown_severity_crashes)} reports are excluded from that population.</p>
              <Bars rows={known.map(row => ({ key: row._stableKey, label: row.severity_group, width: row.percent_of_denominator,
                value: percent(row.percent_of_denominator) }))} />
              <p className="text-sm">{totals.serious_fatal_crashes === null
                ? 'Combined serious or fatal counts are unavailable for this era.'
                : `${count(totals.serious_fatal_crashes)} of ${count(totals.known_severity_crashes)} known-severity reports (${percent(totals.serious_fatal_percent_of_known)}) were serious or fatal.`}</p>
              <DataTable label={`Recorded severity ${period}`} columns={['Recorded group', 'Reports', 'Denominator', 'Share']}
                rows={[...known, ...excluded].map(row => [row.severity_group, count(row.crashes),
                  `${count(row.denominator_crashes)} ${row.denominator_population}`, percent(row.percent_of_denominator)])} />
            </> : <p role="status">Severity composition unavailable for {period}.</p>}
          </section>;
        })}
      </div>
      <EvidenceSource provenance={provenance} tables={[[ 'severity_composition', 'Severity composition' ], [ 'county_periods', 'County totals by period' ]]} />
    </figure>

    <figure className={evidenceCard}>
      <h2>What was recorded about time and lighting in 2024?</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {recording.map(({ label, row }) => <section key={label} className="border border-stone-300 p-3">
          <h3 className="font-semibold">{label}</h3>
          <p>{row ? <><strong>{count(row.covered_crashes)} of {count(row.reported_crashes)}</strong> reports ({percent(row.covered_percent_of_reported)}).</>
            : '2024 coverage unavailable.'}</p>
          {row?._annotation.caveat_codes?.map(code => <p className="text-sm" key={code}>{caveats[code]}</p>)}
        </section>)}
      </div>
      <p>Populated illumination includes recorded unknown codes. A measured zero describes field coverage. The lighting conditions of those crashes remain unknown.</p>
      <DataTable label="2024 measurement coverage" columns={['Field', 'Covered reports', 'Excluded reports', 'All 2024 reports', 'Coverage']}
        rows={recording.map(({ label, row }) => [label, count(row?.covered_crashes), count(row?.excluded_crashes), count(row?.reported_crashes), percent(row?.covered_percent_of_reported)])} />
      <EvidenceSource provenance={provenance} tables={[[ 'field_coverage_by_year', 'Annual field coverage' ]]} />
    </figure>

    <MissingnessFigure data={data} />

    <figure className={evidenceCard}>
      <h2>How strongly were recorded features associated with serious or fatal severity?</h2>
      <p>These tests compare feature levels with the recorded serious/fatal outcome among police-reported crashes with known severity in 2016–2023.
        Cramér’s V ranges from 0 to 1 and measures association strength. Crash risk and causal effects are outside the scope of these tests.</p>
      {ordered.length ? <>
        <Bars rows={ordered.map(row => ({ key: row._stableKey, label: features[row.feature] ?? row.feature,
          width: row.cramers_v == null ? null : row.cramers_v * 100, value: row.cramers_v?.toFixed(4) ?? 'Unavailable' }))} />
        <p className="text-sm">The expected-cell check uses the smallest expected count under independence. BH q-values adjust for multiple tests.</p>
        <p className="text-sm xl:hidden">Scroll the table horizontally to see pooling, expected counts and q-values.</p>
        <DataTable label="Severity associations" columns={['Feature', 'Period', 'Tested reports', 'Known severity', 'All reports in period',
          'Cramér’s V', 'Tested levels', 'Pooled levels', 'Minimum expected count', 'BH q-value']}
          rows={ordered.map(row => [
            features[row.feature] ?? row.feature, `${row.period_start}–${row.period_end}`, count(row.tested_crashes),
            count(row.known_severity_crashes_in_period), count(row.reported_crashes_in_period), row.cramers_v?.toFixed(4) ?? 'Unavailable',
            count(row.tested_levels), row.pooled_source_levels ??
              (row._annotation.nulls?.pooled_source_levels?.reason_code === 'NO_POOLING' ? 'None' : 'Unavailable'),
            row.min_expected_cell?.toFixed(2) ?? 'Unavailable',
            // Underflow is a flagged null in D7. It remains unavailable at display precision.
            row.fdr_bh_q_underflow || row._annotation.nulls?.fdr_bh_q?.reason_code === 'FLOATING_POINT_UNDERFLOW'
              ? 'Unavailable (numerical underflow)' : row.fdr_bh_q?.toExponential(3) ?? 'Unavailable',
          ])} />
      </> : <p role="status">Severity associations unavailable.</p>}
      <EvidenceSource provenance={provenance} tables={[[ 'severity_associations', 'Severity association tests' ]]} />
    </figure>
    <EvidenceIdentity provenance={provenance} />
  </div>;
}

function MissingnessFigure({ data }: { data: Awaited<ReturnType<typeof loadEvidence>> }) {
  const { provenance, missingness, caveats } = data;
  const [field, setField] = useState(missingness.find(row => row.source_field === 'HOUR_OF_DAY')?._stableKey ?? missingness[0]?._stableKey);
  const selected = missingness.find(row => row._stableKey === field);
  return <figure className={evidenceCard}>
    <h2>How often was a source field blank?</h2>
    <p>Each share uses all reports in the 2004–2024 extract. A populated code can still be unknown or invalid for a particular measure.</p>
    {selected ? <>
      <label className="block w-fit max-w-full text-sm">Source field
        <select className="block max-w-full rounded border border-stone-500 bg-white px-2 py-1" value={field}
          onChange={event => setField(event.target.value)}>
          {missingness.map(row => <option key={row._stableKey} value={row._stableKey}>{row.source_field}</option>)}
        </select>
      </label>
      <Bars rows={[{ key: selected._stableKey, label: 'Blank reports', width: selected.missing_percent_of_reported,
        value: percent(selected.missing_percent_of_reported) }]} />
      <DataTable label="Selected source field missingness" columns={['Source field', 'Blank reports', 'All reports', 'Blank share']}
        rows={[[selected.source_field, count(selected.missing_crashes), count(selected.reported_crashes), percent(selected.missing_percent_of_reported)]]} />
      {selected._annotation.caveat_codes?.map(code => <p className="text-sm" key={code}>{caveats[code]}</p>)}
    </> : <p role="status">Source missingness unavailable.</p>}
    <EvidenceSource provenance={provenance} tables={[[ 'source_missingness', 'Missingness for all source fields' ]]} />
  </figure>;
}
