import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { PlotlyChart } from '../components/charts/PlotlyChart';
import { ReleaseStatus, useReleaseRequest } from '../components/layout/ReleaseStatus';
import { confirmOverview, loadOverview, pinnedArtifactUrl, type Period, type OverviewData } from '../services/roadSafetyService';
import { AnnualCrashFigure } from '../components/road-safety/AnnualCrashFigure';
import { DataTable } from '../components/road-safety/EvidenceFigure';

const formatCount = new Intl.NumberFormat('en-US');
const count = (n: number | null) => n === null ? 'Unavailable' : formatCount.format(n);
const percent = (n: number | null) => n === null ? 'Unavailable' : `${n.toFixed(2)}%`;
const period = (row: Pick<Period, 'period_start' | 'period_end'>) => row.period_start === row.period_end
  ? String(row.period_start) : `${row.period_start}–${row.period_end}`;
const fieldLabels: Record<string, string> = { valid_hour: 'Valid hour', nonmissing_illumination: 'Populated illumination' };

const card = 'min-w-0 border border-stone-300 bg-[#fffcf4] p-4 sm:p-6';

function Chart({ years, series, yLabel }: { years: number[]; series: { name: string; values: (number | null)[] }[]; yLabel: string }) {
  return <div aria-hidden="true" className="min-w-0">
    <PlotlyChart className="h-64 w-full" config={{ staticPlot: true, displayModeBar: false }}
      data={series.map(({ name, values }) => ({ name, x: years, y: values, type: 'scatter', mode: 'lines+markers', connectgaps: false }))}
      layout={{ margin: { l: 62, r: 12, t: 12, b: 50 }, legend: { orientation: 'h' }, xaxis: { tickformat: 'd', nticks: 5 },
        yaxis: { title: yLabel, rangemode: 'tozero' } }} />
  </div>;
}

function Caption({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-600">{children}</p>;
}

export function RoadSafetyPage() {
  const { state, retry } = useReleaseRequest(loadOverview, confirmOverview);
  return <article className="public-document">
    <header className="public-hero public-measure">
      <p className="public-kicker">Allegheny County, Pennsylvania · 2004–2024</p>
      <h1>Road Safety Overview</h1>
      <p className="public-lede">The historical record of police-reported crashes by year, with coverage for recorded severity, time and location.</p>
      <div className="public-actions">
        <Link to="/road-safety/map">County crash grid</Link>
        <Link to="/road-safety/evidence">Severity and measurement</Link>
      </div>
    </header>
    {state.kind === 'ready' ? <VerifiedRecord data={state.data} /> : <div className="public-measure">
      <ReleaseStatus kind={state.kind} retry={retry} />
    </div>}
  </article>;
}

function VerifiedRecord({ data }: { data: OverviewData }) {
  const [mapError, setMapError] = useState(false);
  const { scope, bundle, grid } = data.provenance;
  const artifactUrl = (path: string) => pinnedArtifactUrl(path, data.provenance);
  const synthetic = bundle.version.startsWith('fixture-');
  const source = synthetic ? 'Synthetic fixture' : 'WPRDC frozen v6 extract';
  const context = `${scope.county} · ${period(scope)} · ${source}`;
  const { totals, mapped } = data;
  const annual = data.county.filter(row => row.period_grain === 'year');
  const years = annual.map(row => row.period_start);

  return <div className="space-y-6">
    <div className="public-actions"><Link to="/methods">Read the Methods</Link></div>
    {synthetic && <p role="status">Synthetic test fixture. Counts are invented for verification.</p>}
    <section className="grid gap-3 sm:grid-cols-2" aria-label="Crash totals">
      <div className={card}><h2 className="font-semibold">Reported crashes</h2><p className="text-3xl font-bold">{count(totals.reported_crashes)}</p>
        <Caption>{context} All unique reports, including reports without mapped coordinates.</Caption></div>
      <div className={card}><h2 className="font-semibold">Mapped crashes</h2><p className="text-3xl font-bold">{count(mapped.mapped_crashes)}</p>
        <Caption>{context} Reports inside or on the county boundary. {percent(mapped.mapped_percent_of_reported)} of all {count(mapped.reported_crashes)} reports.</Caption></div>
    </section>

    {/* Reference Implementation for Phase 7B: Annual Crash Reports & Selected-Year Coverage */}
    <AnnualCrashFigure data={data} />

    <section className={`${card} space-y-3`} aria-labelledby="severity-composition">
      <h2 id="severity-composition" className="text-lg font-bold">Severity composition and trends</h2>
      <Caption>{scope.county} · Source: {source}. The 2016 coding change defines the two reporting eras. Known groups use known-severity reports. Unknown, missing and unrecognised groups use all reports.</Caption>
      <Chart years={years} yLabel="% of known severity" series={[
        { name: 'Fatal crashes', values: annual.map(row => row.fatal_percent_of_known) },
        { name: 'Serious or fatal crashes', values: annual.map(row => row.serious_fatal_percent_of_known) },
      ]} />
      <Caption>The 2016 severity coding change limits the combined serious/fatal series to 2016 onward. Fatal shares use the known-severity counts shown below.</Caption>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {data.county.filter(row => row.period_grain === 'era').map(era => <div key={period(era)} className="min-w-0">
          <h3 className="font-semibold">{period(era)}</h3>
          <DataTable label={`Recorded severity ${period(era)}`} columns={['Recorded group', 'Crashes', 'Denominator', 'Share']}
            rows={data.severity.filter(row => row.period_grain === 'era' && row.period_start === era.period_start).map(row => [row.severity_group, count(row.crashes),
              row.denominator_crashes === null ? 'Unavailable' : `${count(row.denominator_crashes)} ${row.denominator_population}`, percent(row.percent_of_denominator)])} />
        </div>)}
      </div>
    </section>
    <section className={`${card} space-y-3`} aria-labelledby="coverage">
      <h2 id="coverage" className="text-lg font-bold">Coordinate and field coverage</h2>
      <Caption>{context} Coordinate counts use county reports. Mapping coverage uses all reports per year. Outside-county counts are among usable decimal pairs.</Caption>
      <p>{count(mapped.unusable_decimal_crashes)} reports have unusable pairs. {count(mapped.outside_county_crashes)} of {count(mapped.usable_decimal_crashes)} usable pairs lie outside the county.</p>
      <details><summary className="cursor-pointer font-semibold">Annual coordinate coverage table</summary>
        <DataTable label="Annual coordinate coverage" columns={['Year', 'All reports', 'Usable pairs', 'Unusable pairs', 'Outside county', 'Mapped', 'Mapped share']}
          rows={data.coordinates.filter(row => row.period_grain === 'year').map(row => [period(row), count(row.reported_crashes), count(row.usable_decimal_crashes), count(row.unusable_decimal_crashes), count(row.outside_county_crashes), count(row.mapped_crashes), percent(row.mapped_percent_of_reported)])} />
      </details>
      <h3 className="font-semibold">Hour and illumination recording</h3>
      <Caption>Coverage measures the share of all reports per year with a valid hour or populated illumination field. The illumination coverage includes recorded unknown codes.</Caption>
      <Chart years={years} yLabel="% of all reports" series={Object.entries(fieldLabels).map(([metric, name]) => ({
        name, values: years.map(year => data.fields.find(row => row.period_start === year && row.metric_id === metric)?.covered_percent_of_reported ?? null),
      }))} />
      <p>Coverage varies by year. Compare the number of usable records before interpreting time or lighting patterns.</p>
      <details open><summary className="cursor-pointer font-semibold">2024 recording coverage table</summary>
        <DataTable label="2024 hour and illumination coverage" columns={['Field', 'Covered crashes', 'Excluded crashes', 'All reports', 'Coverage']}
          rows={data.fields.filter(row => row.period_start === 2024).map(row => [fieldLabels[row.metric_id], count(row.covered_crashes), count(row.excluded_crashes), count(row.reported_crashes), percent(row.covered_percent_of_reported)])} />
      </details>
      <details><summary className="cursor-pointer font-semibold">Annual recording coverage table</summary>
        <DataTable label="Annual hour and illumination coverage" columns={['Year and field', 'Covered crashes', 'Excluded crashes', 'All reports', 'Coverage']}
          rows={data.fields.map(row => [`${period(row)} · ${fieldLabels[row.metric_id]}`, count(row.covered_crashes), count(row.excluded_crashes), count(row.reported_crashes), percent(row.covered_percent_of_reported)])} />
      </details>
    </section>
    <section className={`${card} space-y-3`} aria-labelledby="grid">
      <h2 id="grid" className="text-lg font-bold">Historical concentration of reported crashes</h2>
      <figure className="space-y-2">
        {mapError ? <p role="status">County grid image unavailable.</p> : <img className="h-auto w-full bg-white" src={artifactUrl('/assets/county_grid.svg')}
          alt="County boundary and occupied grid cells shaded by counts of mapped reported crashes. Map coverage and a CSV data alternative follow." onError={() => setMapError(true)} />}
        <figcaption className="text-sm">{context} {grid.side_degrees}° × {grid.side_degrees}° cells clipped to the 2024 Census county boundary, approximately 111 m × 85 m before clipping.
          {' '}{count(grid.mapped_crashes)} of {count(grid.reported_crashes)} reported crashes map to {count(grid.occupied_cells)} occupied cells. Cell units are crashes. Travel exposure is unmeasured. Empty cells carry no inferred count.</figcaption>
      </figure>
      <a href={artifactUrl('/downloads/historical_grid')}>Download grid cell counts (CSV)</a>
    </section>
    <section className={`${card} space-y-3`} aria-labelledby="provenance">
      <h2 id="provenance" className="text-lg font-bold">Methodology and downloads</h2>
      <p><a href={artifactUrl('/assets/descriptive_release_data_dictionary.md')} download>Data dictionary (Markdown)</a></p>
      <p className="break-all text-sm">Bundle {data.provenance.bundle.version} · Run {data.provenance.run_id} · Manifest SHA-256 {data.provenance.bundle.manifest_sha256}</p>
      <details><summary className="cursor-pointer font-semibold">Source checksums and aggregate CSVs</summary>
        <ul className="break-all text-sm">{Object.entries(data.provenance.sources).map(([name, hash]) => <li key={name}>{name} · {hash}</li>)}</ul>
        <ul className="mt-3 space-y-1">{['county_periods', 'severity_composition', 'coordinate_coverage', 'field_coverage_by_year'].map(id => <li key={id}><a href={artifactUrl(`/downloads/${id}`)}>{id.replace(/_/g, ' ')} (CSV)</a></li>)}</ul>
      </details>
    </section>
    <Link to="/illustrative-scenario">Open the illustrative scenario workspace</Link>
  </div>;
}
