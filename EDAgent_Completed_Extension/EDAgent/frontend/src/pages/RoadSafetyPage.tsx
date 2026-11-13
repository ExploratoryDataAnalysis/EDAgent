import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { PlotlyChart } from '../components/charts/PlotlyChart';
import { loadOverview, overviewUrl, type Period, type RoadSafetyError } from '../services/roadSafetyService';

const formatCount = new Intl.NumberFormat('en-US');
const count = (n: number | null) => n === null ? 'Unavailable' : formatCount.format(n);
const percent = (n: number | null) => n === null ? 'Unavailable' : `${n.toFixed(2)}%`;
const period = (row: Pick<Period, 'period_start' | 'period_end'>) => row.period_start === row.period_end
  ? String(row.period_start) : `${row.period_start}–${row.period_end}`;
const fieldLabels: Record<string, string> = { valid_hour: 'Valid hour', nonmissing_illumination: 'Populated illumination' };

const card = 'min-w-0 rounded-xl border border-slate-200 bg-white p-4 sm:p-6 dark:border-slate-800 dark:bg-slate-900';
const link = 'text-indigo-700 underline underline-offset-4 dark:text-indigo-300';

function DataTable({ label, columns, rows }: { label: string; columns: string[]; rows: ReactNode[][] }) {
  return <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={label}>
    <table className="w-full text-left text-sm">
      <caption className="sr-only">{label}</caption>
      <thead><tr>{columns.map(column => <th key={column} scope="col" className="border-b p-2">{column}</th>)}</tr></thead>
      <tbody>{rows.map(([heading, ...values]) => <tr key={String(heading)} className="border-b border-slate-200 dark:border-slate-700">
        <th scope="row" className="p-2 font-medium">{heading}</th>
        {values.map((value, index) => <td key={columns[index + 1]} className="p-2 tabular-nums">{value}</td>)}
      </tr>)}</tbody>
    </table>
  </div>;
}

function Chart({ years, series, yLabel }: { years: number[]; series: { name: string; values: (number | null)[] }[]; yLabel: string }) {
  return <div aria-hidden="true" className="min-w-0">
    <PlotlyChart className="h-64 w-full" config={{ staticPlot: true, displayModeBar: false }}
      data={series.map(({ name, values }) => ({ name, x: years, y: values, type: 'scatter', mode: 'lines+markers', connectgaps: false }))}
      layout={{ margin: { l: 62, r: 12, t: 12, b: 50 }, legend: { orientation: 'h' }, xaxis: { tickformat: 'd', nticks: 5 },
        yaxis: { title: yLabel, rangemode: 'tozero' } }} />
  </div>;
}

function Caption({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-600 dark:text-slate-300">{children}</p>;
}

export function RoadSafetyPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof loadOverview>> | null>(null);
  const [error, setError] = useState<RoadSafetyError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [mapError, setMapError] = useState(false);
  useEffect(() => {
    const request = new AbortController();
    loadOverview(request.signal).then(setData).catch((error: RoadSafetyError) => {
      if (!request.signal.aborted) setError(error);
    });
    return () => request.abort();
  }, [attempt]);

  const scope = data?.provenance.scope;
  const source = data?.provenance.bundle.version.startsWith('fixture-') ? 'Synthetic fixture' : 'WPRDC frozen v6 extract';
  const context = scope ? `${scope.county} · ${period(scope)} · Source: ${source}.` : '';
  const totals = data?.county.find(row => row.period_grain === 'county');
  const mapped = data?.coordinates.find(row => row.period_grain === 'county');
  const annual = data?.county.filter(row => row.period_grain === 'year') ?? [];
  const years = annual.map(row => row.period_start);
  const grid = data?.provenance.grid;
  const pending = error?.code === 'OVERVIEW_UNAVAILABLE';

  return <article className="mx-auto max-w-6xl space-y-6 p-3 text-slate-900 sm:p-6 dark:text-slate-100">
    <header className="space-y-2">
      <h1 className="text-2xl font-bold sm:text-3xl">Road Safety Overview</h1>
      <Caption>{scope ? context : 'Historical crash reports and coverage for Allegheny County, Pennsylvania.'}</Caption>
      {data?.provenance.bundle.version.startsWith('fixture-') && <p role="status">Synthetic test fixture. Counts are invented for verification.</p>}
    </header>
    {error ? <section className={card}>
      <div role="alert">
        <h2 className="font-bold">{pending ? 'Reviewed data unavailable' : 'Could not load the Overview'}</h2>
        <p>{pending ? 'The Overview requires approval and verification of the reviewed release. Data stays unavailable while approval is pending or verification fails.' : error.message}</p>
      </div>
      <button className={`${link} mt-3`} onClick={() => { setError(null); setAttempt(attempt + 1); }}>Retry Overview</button>
    </section> : !data ? <p role="status">Loading Road Safety Overview…</p> : !totals || !mapped || !grid ? <p role="status">The reviewed release contains no Overview totals.</p> : <>
      <section className="grid gap-3 sm:grid-cols-2" aria-label="Crash totals">
        <div className={card}><h2 className="font-semibold">Reported crashes</h2><p className="text-3xl font-bold">{count(totals.reported_crashes)}</p>
          <Caption>{context} All unique reports, including reports without mapped coordinates.</Caption></div>
        <div className={card}><h2 className="font-semibold">Mapped crashes</h2><p className="text-3xl font-bold">{count(mapped.mapped_crashes)}</p>
          <Caption>{context} Reports inside or on the county boundary. {percent(mapped.mapped_percent_of_reported)} of all {count(mapped.reported_crashes)} reports.</Caption></div>
      </section>
      <section className={`${card} space-y-3`} aria-labelledby="annual-crashes">
        <h2 id="annual-crashes" className="text-lg font-bold">Annual crash trends</h2>
        <Caption>{context} Counts use all reports per year. Severity shares use reports with known severity (codes 0–4) per year.</Caption>
        <Chart years={years} yLabel="Crashes" series={[{ name: 'Reported crashes', values: annual.map(row => row.reported_crashes) }]} />
        <Chart years={years} yLabel="% of known severity" series={[
          { name: 'Fatal crashes', values: annual.map(row => row.fatal_percent_of_known) },
          { name: 'Serious or fatal crashes', values: annual.map(row => row.serious_fatal_percent_of_known) },
        ]} />
        <Caption>The 2016 severity coding change limits the combined serious/fatal series to 2016 onward. Fatal shares use the known-severity counts shown below.</Caption>
        <details><summary className="cursor-pointer font-semibold">Annual trends data table</summary>
          <DataTable label="Annual reported crashes and severity" columns={['Year', 'Reported', 'Known severity', 'Unknown severity', 'Fatal', 'Fatal share', 'Serious or fatal', 'Serious or fatal share']}
            rows={annual.map(row => [period(row), count(row.reported_crashes), count(row.known_severity_crashes), count(row.unknown_severity_crashes), count(row.fatal_crashes), percent(row.fatal_percent_of_known), count(row.serious_fatal_crashes), percent(row.serious_fatal_percent_of_known)])} />
        </details>
      </section>
      <section className={`${card} space-y-3`} aria-labelledby="severity-composition">
        <h2 id="severity-composition" className="text-lg font-bold">Severity composition</h2>
        <Caption>{scope?.county} · Source: {source}. The 2016 coding change defines the two reporting eras. Known groups use known-severity reports. Unknown, missing and unrecognised groups use all reports.</Caption>
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
        <p>2024 hour-of-day and lighting comparisons are unavailable due to sparse recording. Earlier hour records show a 02:00 spike and whole- and half-hour heaping.</p>
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
          {mapError ? <p role="status">County grid image unavailable.</p> : <img className="h-auto w-full bg-white" src={overviewUrl('/assets/county_grid.svg')}
            alt="County boundary and occupied grid cells shaded by counts of mapped reported crashes. Map coverage and a CSV data alternative follow." onError={() => setMapError(true)} />}
          <figcaption className="text-sm">{context} {grid.side_degrees}° × {grid.side_degrees}° cells clipped to the 2024 Census county boundary, approximately 111 m × 85 m before clipping.
            {' '}{count(grid.mapped_crashes)} of {count(grid.reported_crashes)} reported crashes map to {count(grid.occupied_cells)} occupied cells. Cell units are crashes. Travel exposure is unmeasured. Empty cells carry no inferred count.</figcaption>
        </figure>
        <a className={link} href={overviewUrl('/downloads/historical_grid')}>Download grid cell counts (CSV)</a>
      </section>
      <section className={`${card} space-y-3`} aria-labelledby="findings">
        <h2 id="findings" className="text-lg font-bold">Findings and scope</h2>
        {data.findings.map(row => <details key={row.finding_id}>
          <summary className="cursor-pointer font-semibold">{row.finding}</summary>
          <Caption>{period(row)} · {row.population} · {row.review_state}</Caption>
          <p>{row.narrative}</p>
          {row.review_state === 'REVIEW_ONLY' && <p>Public severity inference is unavailable.</p>}
        </details>)}
      </section>
      <section className={`${card} space-y-3`} aria-labelledby="provenance">
        <h2 id="provenance" className="text-lg font-bold">Methodology and downloads</h2>
        <p><a className={link} href={overviewUrl('/assets/descriptive_release_data_dictionary.md')} download>Data dictionary (Markdown)</a></p>
        <p className="break-all text-sm">Bundle {data.provenance.bundle.version} · Run {data.provenance.run_id} · Manifest SHA-256 {data.provenance.bundle.manifest_sha256}</p>
        <details><summary className="cursor-pointer font-semibold">Source checksums and aggregate CSVs</summary>
          <ul className="break-all text-sm">{Object.entries(data.provenance.sources).map(([name, hash]) => <li key={name}>{name} · {hash}</li>)}</ul>
          <ul className="mt-3 space-y-1">{Object.keys(data.provenance.tables).map(id => <li key={id}><a className={link} href={overviewUrl(`/downloads/${id}`)}>{id.replace(/_/g, ' ')} (CSV)</a></li>)}</ul>
        </details>
      </section>
    </>}
    <Link className={link} to="/illustrative-scenario">Open the illustrative scenario workspace</Link>
  </article>;
}
