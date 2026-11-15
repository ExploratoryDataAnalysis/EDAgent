import React, { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { PlotlyChart } from '../charts/PlotlyChart';
import {
  type OverviewData,
  pinnedArtifactUrl,
  type Period,
  type CountyPeriod,
  type Coordinates,
  type FieldCoverage,
  type RowWithAnnotation,
} from '../../services/roadSafetyService';

const formatCount = new Intl.NumberFormat('en-US');
const count = (n: number | null | undefined) => (n === null || n === undefined ? 'Unavailable' : formatCount.format(n));
const percent = (n: number | null | undefined) => (n === null || n === undefined ? 'Unavailable' : `${n.toFixed(2)}%`);
const period = (row: Pick<Period, 'period_start' | 'period_end'>) =>
  row.period_start === row.period_end ? String(row.period_start) : `${row.period_start}–${row.period_end}`;

const card = 'min-w-0 border border-stone-300 bg-[#fffcf4] p-4 sm:p-6';

export interface AnnualCrashFigureProps {
  data: OverviewData;
  showFullRecordLink?: boolean;
}

export const AnnualCrashFigure: React.FC<AnnualCrashFigureProps> = ({ data, showFullRecordLink = false }) => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Extract annual county period rows sorted chronologically
  const annualCounty = useMemo(() => {
    return data.county
      .filter(row => row.period_grain === 'year')
      .sort((a, b) => a.period_start - b.period_start);
  }, [data.county]);

  const availableYears = useMemo(() => annualCounty.map(r => r.period_start), [annualCounty]);
  const defaultYear = availableYears.length > 0 ? availableYears[availableYears.length - 1] : 2024;

  // Single source of truth: synchronize selected year with URL search param '?year='
  const selectedYear = useMemo(() => {
    const raw = searchParams.get('year');
    if (!raw) return defaultYear;
    const parsed = parseInt(raw, 10);
    return !isNaN(parsed) && availableYears.includes(parsed) ? parsed : defaultYear;
  }, [searchParams, availableYears, defaultYear]);

  const handleSelectYear = (year: number) => {
    if (availableYears.includes(year)) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set('year', String(year));
      setSearchParams(nextParams);
    }
  };

  // Associate selected year with verified rows across tables
  const selectedCounty = useMemo(
    () => annualCounty.find(r => r.period_start === selectedYear) || annualCounty[annualCounty.length - 1],
    [annualCounty, selectedYear]
  );

  const selectedCoord = useMemo(
    () => data.coordinates.find(r => r.period_grain === 'year' && r.period_start === selectedYear),
    [data.coordinates, selectedYear]
  );

  const selectedHour = useMemo(
    () => data.fields.find(r => r.period_start === selectedYear && r.metric_id === 'valid_hour'),
    [data.fields, selectedYear]
  );

  const selectedLight = useMemo(
    () => data.fields.find(r => r.period_start === selectedYear && r.metric_id === 'nonmissing_illumination'),
    [data.fields, selectedYear]
  );

  const { scope, bundle, run_id } = data.provenance;
  const synthetic = bundle.version.startsWith('fixture-');
  const sourceName = synthetic ? 'Synthetic test fixture' : 'WPRDC frozen v6 extract';
  const context = `${scope.county} · ${period(scope)} · ${sourceName}`;

  return (
    <div className="space-y-6" data-testid="annual-crash-figure">
      {/* Editorial Header / Bounded Finding */}
      <section className={`${card} space-y-3`} aria-labelledby="annual-crash-heading">
        <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-2 border-b border-stone-200 pb-3">
          <div>
            <h2 id="annual-crash-heading" className="text-xl font-bold text-[#182021]">
              Annual crash reports in Allegheny County
            </h2>
            <p className="text-sm text-stone-600">
              {context} · County extract grain (GEOID {scope.geoid || '42003'})
            </p>
          </div>
          {/* Year selector control usable via keyboard and touch */}
          <div className="flex items-center gap-2 pt-1 sm:pt-0">
            <label htmlFor="annual-year-select" className="font-semibold text-sm text-[#182021] whitespace-nowrap">
              Select observation year:
            </label>
            <select
              id="annual-year-select"
              aria-label="Select observation year"
              value={selectedYear}
              onChange={e => handleSelectYear(Number(e.target.value))}
              className="border border-stone-400 bg-white px-2.5 py-1 text-sm rounded font-medium focus:outline-none focus:ring-2 focus:ring-[#0E6059]"
            >
              {availableYears.map(y => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
        </div>

        <p className="text-sm text-slate-700">
          The plot shows all unique police-reported crashes recorded in the extract per calendar year. Selecting a year
          highlights the series marker and displays the coordinate and field recording coverage for that year.
        </p>

        {/* Plotly Chart with Selected-Year Highlight */}
        <div aria-hidden="true" className="min-w-0">
          <PlotlyChart
            className="h-72 w-full"
            config={{ staticPlot: true, displayModeBar: false }}
            data={[
              {
                name: 'Reported crashes',
                x: availableYears,
                y: annualCounty.map(r => r.reported_crashes),
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#0E6059', width: 2.5 },
                marker: { size: 6, color: '#0E6059' },
                connectgaps: false,
              },
              {
                name: `Selected: ${selectedYear} (${count(selectedCounty?.reported_crashes)} crashes)`,
                x: [selectedYear],
                y: [selectedCounty ? selectedCounty.reported_crashes : null],
                type: 'scatter',
                mode: 'markers',
                marker: {
                  size: 14,
                  color: '#8D3821', // warning rust token
                  symbol: 'circle',
                  line: { width: 2, color: '#182021' },
                },
                hoverinfo: 'x+y+name',
              },
            ]}
            layout={{
              margin: { l: 65, r: 15, t: 15, b: 50 },
              legend: { orientation: 'h', y: -0.22 },
              xaxis: {
                title: 'Observation year',
                tickmode: 'linear',
                tickformat: 'd',
                dtick: availableYears.length > 10 ? 2 : 1,
              },
              yaxis: {
                title: 'Police-reported crashes',
                rangemode: 'tozero',
              },
            }}
          />
        </div>

        <p className="text-xs text-stone-500">
          Marker highlight indicates the active selected observation year: <strong>{selectedYear}</strong> ({count(selectedCounty?.reported_crashes)} crashes).
        </p>
      </section>

      {/* Meaningful Selected-Year Coverage Panel */}
      <section
        className={`${card} space-y-4`}
        aria-labelledby="selected-coverage-title"
        data-testid="selected-year-coverage"
      >
        <div className="border-b border-stone-200 pb-2">
          <h3 id="selected-coverage-title" className="text-lg font-bold text-[#182021]">
            Selected Year: {selectedYear} · Coverage and Measurement Details
          </h3>
          <p className="text-sm text-stone-600">
            Examining {count(selectedCounty?.reported_crashes)} police-reported crashes in Allegheny County ({selectedYear}).
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Geographic Coordinate Coverage */}
          <div className="border border-stone-200 bg-white p-3 rounded space-y-1 text-sm">
            <h4 className="font-semibold text-[#0E6059]">Coordinate Mapping Coverage</h4>
            <p>
              <strong>{count(selectedCoord?.mapped_crashes)}</strong> of{' '}
              <strong>{count(selectedCoord?.reported_crashes)}</strong> reports mapped (
              <span className="font-semibold">{percent(selectedCoord?.mapped_percent_of_reported)}</span>).
            </p>
            <p className="text-xs text-stone-600">
              Numerator: reports covered by Census county polygon (GEOID 42003). Denominator: all extract reports in {selectedYear}.
            </p>
            <p className="text-xs text-stone-600">
              Unusable coordinates: {count(selectedCoord?.unusable_decimal_crashes)} crashes. Usable coordinates outside county: {count(selectedCoord?.outside_county_crashes)} ({percent(selectedCoord?.outside_percent_of_usable)} of usable pairs).
            </p>
            <p className="text-xs text-stone-500 italic">
              Interpretation: Only polygon-screened reports appear on the county map. Reports without usable coordinates remain in county totals but cannot be placed in geographic grids.
            </p>
          </div>

          {/* Time & Lighting Field Coverage */}
          <div className="border border-stone-200 bg-white p-3 rounded space-y-1 text-sm">
            <h4 className="font-semibold text-[#0E6059]">Field Recording Coverage</h4>
            <p>
              Valid hour of day: <strong>{count(selectedHour?.covered_crashes)}</strong> / {count(selectedHour?.reported_crashes)} ({percent(selectedHour?.covered_percent_of_reported)}).
            </p>
            <p className="text-xs text-stone-600">
              {selectedYear === 2024 ? (
                <span className="text-[#8D3821] font-medium">
                  Caveat (LOW_2024_HOUR_COVERAGE): Sparse 2024 recording (3.78% valid hours in extract). Withhold 2024 hourly distributions.
                </span>
              ) : (
                <span className="text-stone-600">
                  Caveat (HOUR_HEAPING): Recorded hours exhibit a 02:00 spike and whole/half-hour heaping.
                </span>
              )}
            </p>
            <p className="pt-1">
              Populated illumination: <strong>{count(selectedLight?.covered_crashes)}</strong> / {count(selectedLight?.reported_crashes)} ({percent(selectedLight?.covered_percent_of_reported)}).
            </p>
            <p className="text-xs text-stone-600">
              {selectedYear === 2024 ? (
                <span className="text-[#8D3821] font-medium">
                  Observed zero (NO_2024_ILLUMINATION_COVERAGE): Exactly 0 reports in 2024 have populated illumination. This is a measured zero count of recorded values, not missing data. Withhold 2024 lighting distributions.
                </span>
              ) : (
                <span className="text-stone-600">
                  Illumination field populated as recorded in source data.
                </span>
              )}
            </p>
          </div>

          {/* Severity Breakdown & 2016 Seam */}
          <div className="border border-stone-200 bg-white p-3 rounded space-y-1 text-sm">
            <h4 className="font-semibold text-[#0E6059]">Severity Recording & 2016 Coding Boundary</h4>
            <p>
              Known severity (codes 0–4): <strong>{count(selectedCounty?.known_severity_crashes)}</strong> ({percent(selectedCounty?.known_severity_percent_of_reported)} of reports).
            </p>
            <p className="text-xs text-stone-600">
              Unknown severity: {count(selectedCounty?.unknown_severity_crashes)} reports. Fatal crashes (code 1): {count(selectedCounty?.fatal_crashes)} ({percent(selectedCounty?.fatal_percent_of_known)} of known severity).
            </p>
            <div className="pt-1">
              {selectedYear >= 2016 ? (
                <p>
                  Serious or fatal crashes (codes 1 & 2): <strong>{count(selectedCounty?.serious_fatal_crashes)}</strong> ({percent(selectedCounty?.serious_fatal_percent_of_known)} of known severity).
                </p>
              ) : (
                <p className="text-[#8D3821] text-xs font-medium">
                  Serious or fatal crashes: <em>Unavailable</em>. Caveat (SEVERITY_CODING_BREAK_2016): PennDOT revised the injury-severity standard in 2016. Combined serious/fatal metrics are withheld prior to 2016 because definitions differ across eras.
                </p>
              )}
            </div>
          </div>

          {/* Scope and Non-Inference Disclaimer */}
          <div className="border border-stone-200 bg-white p-3 rounded space-y-1 text-sm">
            <h4 className="font-semibold text-[#8D3821]">Scope & Scientific Boundaries</h4>
            <p className="text-xs text-slate-700">
              This annual series counts police-reported crashes in the fixed extract.
            </p>
            <ul className="text-xs text-stone-600 list-disc list-inside space-y-0.5">
              <li>Zero accepted road-site assignments in extract.</li>
              <li>Travel exposure and traffic volumes are unmeasured here.</li>
              <li>Supports no inference regarding per-trip risk, site ranking, or treatment effects.</li>
              <li>Distinguishes observed zero (measured zero count), missing, and unavailable metrics.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Accessible Data Table with Selection State */}
      <section className={`${card} space-y-3`} aria-labelledby="annual-table-heading">
        <details>
          <summary id="annual-table-heading" className="cursor-pointer font-semibold text-[#182021]">
            Annual trends data table
          </summary>
          <p className="text-xs text-stone-600 pt-1 pb-2">
            Select any year row to view its coverage summary and highlight the point on the chart.
          </p>
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Annual reported crashes and severity">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Annual reported crashes and severity</caption>
              <thead>
                <tr className="border-b border-stone-300">
                  <th scope="col" className="p-2 font-semibold">Year</th>
                  <th scope="col" className="p-2 font-semibold">Reported</th>
                  <th scope="col" className="p-2 font-semibold">Known severity</th>
                  <th scope="col" className="p-2 font-semibold">Unknown severity</th>
                  <th scope="col" className="p-2 font-semibold">Fatal</th>
                  <th scope="col" className="p-2 font-semibold">Fatal share</th>
                  <th scope="col" className="p-2 font-semibold">Serious or fatal</th>
                  <th scope="col" className="p-2 font-semibold">Serious or fatal share</th>
                  <th scope="col" className="p-2 font-semibold">Mapped</th>
                  <th scope="col" className="p-2 font-semibold">Mapped %</th>
                  <th scope="col" className="p-2 font-semibold">Valid hour %</th>
                  <th scope="col" className="p-2 font-semibold">Illumination %</th>
                </tr>
              </thead>
              <tbody>
                {annualCounty.map(row => {
                  const isSelected = row.period_start === selectedYear;
                  const cRow = data.coordinates.find(r => r.period_grain === 'year' && r.period_start === row.period_start);
                  const hRow = data.fields.find(r => r.period_start === row.period_start && r.metric_id === 'valid_hour');
                  const lRow = data.fields.find(r => r.period_start === row.period_start && r.metric_id === 'nonmissing_illumination');

                  return (
                    <tr
                      key={period(row)}
                      aria-selected={isSelected}
                      onClick={() => handleSelectYear(row.period_start)}
                      className={`border-b border-stone-200 cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-[#eef5f4] font-semibold border-l-4 border-l-[#0E6059]'
                          : 'hover:bg-stone-50'
                      }`}
                    >
                      <th scope="row" className="p-2 font-medium">
                        {period(row)}
                      </th>
                      <td className="p-2 tabular-nums">{count(row.reported_crashes)}</td>
                      <td className="p-2 tabular-nums">{count(row.known_severity_crashes)}</td>
                      <td className="p-2 tabular-nums">{count(row.unknown_severity_crashes)}</td>
                      <td className="p-2 tabular-nums">{count(row.fatal_crashes)}</td>
                      <td className="p-2 tabular-nums">{percent(row.fatal_percent_of_known)}</td>
                      <td className="p-2 tabular-nums">{count(row.serious_fatal_crashes)}</td>
                      <td className="p-2 tabular-nums">{percent(row.serious_fatal_percent_of_known)}</td>
                      <td className="p-2 tabular-nums">{count(cRow?.mapped_crashes)}</td>
                      <td className="p-2 tabular-nums">{percent(cRow?.mapped_percent_of_reported)}</td>
                      <td className="p-2 tabular-nums">{percent(hRow?.covered_percent_of_reported)}</td>
                      <td className="p-2 tabular-nums">{percent(lRow?.covered_percent_of_reported)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      {/* Scope, Sources, and Verified CSV Export */}
      <section className={`${card} space-y-2`} aria-labelledby="export-heading">
        <h4 id="export-heading" className="font-semibold text-sm text-[#182021]">
          Source Verification & Downloadable Series
        </h4>
        <p className="text-xs text-stone-600">
          Allegheny County, Pennsylvania (GEOID {scope.geoid || '42003'}) · 2004–2024 · Source: {sourceName} · Bundle: {bundle.version} · Run: {run_id}
        </p>
        <p className="text-xs text-stone-600">
          The CSV download covers the <strong>complete 2004–2024 annual series</strong> of verified aggregate crash reports.
        </p>
        <div className="flex flex-wrap items-center gap-4 pt-1 text-sm">
          <a
            href={pinnedArtifactUrl('/downloads/county_periods', data.provenance)}
            download="county_periods.csv"
            className="text-[#0E6059] font-medium underline hover:text-[#0b4d47]"
          >
            Download complete annual series (county_periods.csv)
          </a>
          <a
            href={pinnedArtifactUrl('/downloads/coordinate_coverage', data.provenance)}
            download="coordinate_coverage.csv"
            className="text-[#0E6059] font-medium underline hover:text-[#0b4d47]"
          >
            Download coordinate coverage (coordinate_coverage.csv)
          </a>
          <a
            href="https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/2c13021f-74a9-4289-a1e5-fe0472c89881"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#0E6059] font-medium underline hover:text-[#0b4d47]"
          >
            WPRDC primary source dataset
          </a>
        </div>
        <p className="text-xs text-stone-500 break-all pt-1">
          Manifest SHA-256: <code className="bg-stone-100 px-1 py-0.5 rounded">{bundle.manifest_sha256}</code>
        </p>
      </section>

      {showFullRecordLink && (
        <div className="public-actions">
          <Link to={`/road-safety?year=${selectedYear}`}>
            Open the complete road-safety crash record
          </Link>
          <Link to="/methods">Read the Methods</Link>
        </div>
      )}
    </div>
  );
};
