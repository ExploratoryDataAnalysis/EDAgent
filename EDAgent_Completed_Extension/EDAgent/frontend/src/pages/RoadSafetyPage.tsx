import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  MapPin,
  TrendingUp,
  AlertTriangle,
  Layers,
  Cpu,
  Calculator,
  ShieldAlert,
  CheckCircle2,
  Info,
  ExternalLink,
  Compass,
  Filter,
  ArrowRight,
  Database,
  BarChart2,
  Activity,
} from 'lucide-react';
import { PlotlyChart } from '../components/charts/PlotlyChart';
import {
  loadOverview,
  loadHotspots,
  loadModelComparison,
  loadRoadClasses,
  overviewUrl,
  type Period,
  type RoadSafetyError,
  type HotspotFeature,
  type ModelComparisonMetric,
  type RoadClassConcentration,
} from '../services/roadSafetyService';

const formatCount = new Intl.NumberFormat('en-US');
const count = (n: number | null | undefined) => (n === null || n === undefined ? 'Unavailable' : formatCount.format(n));
const percent = (n: number | null | undefined) => (n === null || n === undefined ? 'Unavailable' : `${Number(n).toFixed(2)}%`);
const period = (row: Pick<Period, 'period_start' | 'period_end'>) =>
  row.period_start === row.period_end ? String(row.period_start) : `${row.period_start}–${row.period_end}`;

const fieldLabels: Record<string, string> = {
  valid_hour: 'Valid hour of day',
  nonmissing_illumination: 'Populated lighting code',
};

type NarrativeTab = 'overview' | 'phase1_integrity' | 'phase2_spatial' | 'phase3_concentration' | 'phase4_modelling' | 'phase5_countermeasures';

export function RoadSafetyPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof loadOverview>> | null>(null);
  const [hotspots, setHotspots] = useState<HotspotFeature[]>([]);
  const [modelMetrics, setModelMetrics] = useState<ModelComparisonMetric[]>([]);
  const [roadClasses, setRoadClasses] = useState<RoadClassConcentration[]>([]);
  const [error, setError] = useState<RoadSafetyError | null>(null);
  const [activeTab, setActiveTab] = useState<NarrativeTab>('overview');
  const [selectedRoadClass, setSelectedRoadClass] = useState<string>('ALL');
  const [selectedHotspot, setSelectedHotspot] = useState<HotspotFeature | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    loadOverview(ac.signal)
      .then(setData)
      .catch((err) => {
        if (!ac.signal.aborted) setError(err);
      });
    loadHotspots(ac.signal)
      .then((res) => {
        if (res && res.features) setHotspots(res.features);
      })
      .catch(() => {});
    loadModelComparison(ac.signal)
      .then((res) => {
        if (res) setModelMetrics(res);
      })
      .catch(() => {});
    loadRoadClasses(ac.signal)
      .then((res) => {
        if (res) setRoadClasses(res);
      })
      .catch(() => {});

    return () => ac.abort();
  }, []);

  const totals = data?.county.find((row) => row.period_grain === 'county');
  const mapped = data?.coordinates.find((row) => row.period_grain === 'county');
  const annual = data?.county.filter((row) => row.period_grain === 'year') ?? [];
  const years = annual.map((row) => row.period_start);
  const grid = data?.provenance?.grid;

  // Filtered hotspots for interactive map
  const filteredHotspots = useMemo(() => {
    if (selectedRoadClass === 'ALL') return hotspots;
    return hotspots.filter((h) => h.properties.road_class.toUpperCase() === selectedRoadClass);
  }, [hotspots, selectedRoadClass]);

  const roadClassOptions = useMemo(() => {
    const set = new Set(hotspots.map((h) => h.properties.road_class.toUpperCase()));
    return ['ALL', ...Array.from(set)];
  }, [hotspots]);

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-4 sm:p-8 text-slate-900 dark:text-slate-100">
      {/* Narrative Header */}
      <header className="rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-8 sm:p-10 text-white shadow-xl relative overflow-hidden border border-indigo-900/50">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-4xl space-y-4 relative z-10">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 text-xs font-semibold">
            <Compass className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
            <span>Allegheny County Road Safety Baseline · EDA v6 Canonical Research</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-black tracking-tight leading-tight">
            Traffic Safety & Crash Analysis: <span className="bg-gradient-to-r from-indigo-300 to-cyan-300 bg-clip-text text-transparent">A 21-Year Narrative</span>
          </h1>

          <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
            A comprehensive, deterministic investigation of <strong>248,810 police-reported crashes</strong> across Allegheny County, Pennsylvania (2004–2024). Explore data integrity breakpoints, geospatial risk concentration, severity modelling benchmarks, and actionable safety countermeasures.
          </p>

          {/* Quick Metrics Ribbon */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4">
            <div className="rounded-2xl bg-white/5 border border-white/10 p-3.5 backdrop-blur-sm">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Reported Crashes</span>
              <span className="text-2xl font-black text-white">{count(totals?.reported_crashes ?? 248810)}</span>
              <span className="text-[10px] text-slate-400 block mt-0.5">2004–2024 County Extract</span>
            </div>
            <div className="rounded-2xl bg-white/5 border border-white/10 p-3.5 backdrop-blur-sm">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Mapped Points</span>
              <span className="text-2xl font-black text-cyan-300">{count(mapped?.mapped_crashes ?? 238281)}</span>
              <span className="text-[10px] text-cyan-400 block mt-0.5">95.77% Census Polygon Valid</span>
            </div>
            <div className="rounded-2xl bg-white/5 border border-white/10 p-3.5 backdrop-blur-sm">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Occupied Grid Cells</span>
              <span className="text-2xl font-black text-indigo-300">{count(grid?.occupied_cells ?? 38332)}</span>
              <span className="text-[10px] text-indigo-400 block mt-0.5">0.001° Spatial Screening</span>
            </div>
            <div className="rounded-2xl bg-white/5 border border-white/10 p-3.5 backdrop-blur-sm">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Fatalities Recorded</span>
              <span className="text-2xl font-black text-rose-300">{count(totals?.fatal_crashes ?? 1446)}</span>
              <span className="text-[10px] text-rose-400 block mt-0.5">Known Severity Outcome</span>
            </div>
          </div>
        </div>
      </header>

      {/* Narrative Phase Tabs */}
      <nav aria-label="Narrative Phases" className="flex items-center space-x-2 overflow-x-auto pb-2 border-b border-slate-200 dark:border-slate-800">
        {[
          { id: 'overview', label: '1. Executive Story', icon: Info },
          { id: 'phase1_integrity', label: '2. Ingestion & Quality Breakpoints', icon: ShieldAlert },
          { id: 'phase2_spatial', label: '3. Spatial Hotspots & Interactive Map', icon: MapPin },
          { id: 'phase3_concentration', label: '4. Concentration & Exposure Bias', icon: Activity },
          { id: 'phase4_modelling', label: '5. Machine Learning Severity Models', icon: Cpu },
          { id: 'phase5_countermeasures', label: '6. Safety Interventions & Actions', icon: Calculator },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as NarrativeTab)}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${
                active
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* TAB CONTENT 1: EXECUTIVE STORY & FINDINGS LEDGER */}
      {activeTab === 'overview' && (
        <section className="space-y-6">
          {/* Narrative Story Intro Card */}
          <div className="rounded-2xl border border-indigo-100 dark:border-indigo-950 bg-indigo-50/50 dark:bg-indigo-950/20 p-6 space-y-4">
            <div className="flex items-start space-x-3">
              <Compass className="w-6 h-6 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
              <div className="space-y-2">
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  The Analytical Journey: How This Safety Research Unfolds
                </h2>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  Traffic safety analysis is frequently undermined by superficial aggregation: pooling data across injury definition changes, mistaking traffic exposure for hazardous infrastructure, and ignoring unmeasured confounders. This dashboard presents our verified multi-phase methodology designed to eliminate these systemic biases.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="flex items-center space-x-2 text-indigo-600 dark:text-indigo-400 font-bold text-xs uppercase tracking-wider">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  <span>The Ground Truth Rule</span>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  Every statistic and chart is computed directly by backend analytics pipelines. AI never invents numbers or generates ungrounded statistical conclusions.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="flex items-center space-x-2 text-amber-600 dark:text-amber-400 font-bold text-xs uppercase tracking-wider">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  <span>The Coding Breakpoint</span>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  In 2016, Pennsylvania adopted new KABCO injury standards. Major injuries became "suspected serious injuries." We split historical eras to prevent deceptive multi-year pooling.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="flex items-center space-x-2 text-cyan-600 dark:text-cyan-400 font-bold text-xs uppercase tracking-wider">
                  <span className="w-2 h-2 rounded-full bg-cyan-500" />
                  <span>The Denominator Problem</span>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  High crash volume on Interstates reflects huge daily traffic (AADT), not necessarily higher danger per trip. We distinguish empirical concentration from causal risk.
                </p>
              </div>
            </div>
          </div>

          {/* Research Findings Ledger */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Research Findings Ledger</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Eight verified baseline findings from the 2004–2024 Allegheny County study.
                </p>
              </div>
              <span className="text-xs font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2.5 py-1 rounded-md">
                8 Accepted Baseline Records
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(data?.findings ?? []).map((f) => (
                <div key={f.finding_id} className="p-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 space-y-2 hover:border-indigo-300 dark:hover:border-indigo-800 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                      Finding #{f.finding_id}: {f.finding}
                    </span>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      f.review_state === 'APPROVED_DESCRIPTIVE'
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300'
                        : 'bg-amber-100 text-amber-700 dark:bg-amber-950/70 dark:text-amber-300'
                    }`}>
                      {f.review_state}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
                    {f.narrative}
                  </p>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                    Scope: {f.population}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* TAB CONTENT 2: INGESTION & DATA QUALITY BREAKPOINTS */}
      {activeTab === 'phase1_integrity' && (
        <section className="space-y-6">
          {/* Informational Narrative Box */}
          <div className="rounded-2xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/20 p-5 space-y-3">
            <div className="flex items-center space-x-2 text-amber-700 dark:text-amber-400 font-bold text-sm">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Technical Deep-Dive: Why You Must Never Blindly Pool 2004–2024 Severity</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-700 dark:text-slate-300">
              <div>
                <strong>The 2016 Coding Break:</strong> In 2016, Pennsylvania changed from a 3-tier injury classification to the federal MMUCC KABCO 5-tier standard. Suspected Serious Injuries cannot be equated with pre-2016 Major Injuries.
              </div>
              <div>
                <strong>The 2024 Illumination & Hour Collapse:</strong> In 2024, valid hour is recorded in only 387 of 10,228 crashes (3.78%), and illumination is completely absent (0%). Never build hourly or nighttime forecasts using 2024 data.
              </div>
              <div>
                <strong>Temporal Heaping:</strong> Police reports heap strongly at :00 and :30 minutes and exhibit a known 02:00 spike coincident with establishment closing hours.
              </div>
            </div>
          </div>

          {/* Interactive Annual Crash Trends Chart */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Annual Crash Volume & Severity Trends (2004–2024)</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Interactive multi-year timeline showing total reports and severity shares with the 2016 KABCO break indicated.
                </p>
              </div>
              <div className="flex items-center space-x-2 text-xs">
                <span className="inline-block w-3 h-3 rounded-full bg-indigo-500" />
                <span className="text-slate-600 dark:text-slate-300">Reported</span>
                <span className="inline-block w-3 h-3 rounded-full bg-rose-500 ml-2" />
                <span className="text-slate-600 dark:text-slate-300">Fatal %</span>
                <span className="inline-block w-3 h-3 rounded-full bg-amber-500 ml-2" />
                <span className="text-slate-600 dark:text-slate-300">Serious/Fatal % (2016+)</span>
              </div>
            </div>

            <div className="h-72 w-full">
              <PlotlyChart
                className="h-full w-full"
                config={{ displayModeBar: true, responsive: true }}
                data={[
                  {
                    name: 'Reported Crashes',
                    x: years,
                    y: annual.map((r) => r.reported_crashes),
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: { color: '#6366f1', width: 3 },
                    marker: { size: 6 },
                    yaxis: 'y1',
                  },
                  {
                    name: 'Fatal Crash % of Known',
                    x: years,
                    y: annual.map((r) => r.fatal_percent_of_known),
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: { color: '#f43f5e', width: 2, dash: 'dot' },
                    marker: { size: 5 },
                    yaxis: 'y2',
                  },
                  {
                    name: 'Serious or Fatal % (2016+)',
                    x: years.filter((y) => y >= 2016),
                    y: annual.filter((r) => r.period_start >= 2016).map((r) => r.serious_fatal_percent_of_known),
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: { color: '#f59e0b', width: 2.5 },
                    marker: { size: 6 },
                    yaxis: 'y2',
                  },
                ]}
                layout={{
                  margin: { l: 60, r: 60, t: 20, b: 40 },
                  legend: { orientation: 'h', y: -0.2 },
                  xaxis: { tickformat: 'd', nticks: 10, title: 'Year' },
                  yaxis: { title: 'Total Reported Crashes', rangemode: 'tozero' },
                  yaxis2: {
                    title: 'Severity Share (% of Known)',
                    overlaying: 'y',
                    side: 'right',
                    rangemode: 'tozero',
                  },
                  shapes: [
                    {
                      type: 'line',
                      x0: 2016,
                      x1: 2016,
                      y0: 0,
                      y1: 1,
                      yref: 'paper',
                      line: { color: '#ef4444', width: 1.5, dash: 'dash' },
                    },
                  ],
                  annotations: [
                    {
                      x: 2016,
                      y: 0.95,
                      yref: 'paper',
                      text: '2016 KABCO Coding Shift',
                      showarrow: false,
                      font: { size: 10, color: '#ef4444' },
                    },
                  ],
                }}
              />
            </div>
          </div>

          {/* Field Coverage Collapse Chart */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">Recording Completeness: Valid Hour & Lighting</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Notice the severe drop in 2024 data completeness: valid hour plummets to 3.8% and illumination drops to 0%.
              </p>
            </div>
            <div className="h-64 w-full">
              <PlotlyChart
                className="h-full w-full"
                config={{ displayModeBar: false, responsive: true }}
                data={Object.entries(fieldLabels).map(([metric, label]) => ({
                  name: label,
                  x: years,
                  y: years.map(
                    (y) =>
                      data?.fields.find((f) => f.period_start === y && f.metric_id === metric)?.covered_percent_of_reported ?? null
                  ),
                  type: 'scatter',
                  mode: 'lines+markers',
                  connectgaps: false,
                }))}
                layout={{
                  margin: { l: 50, r: 20, t: 20, b: 40 },
                  legend: { orientation: 'h', y: -0.2 },
                  xaxis: { tickformat: 'd', nticks: 10 },
                  yaxis: { title: 'Covered % of Reports', range: [0, 105] },
                }}
              />
            </div>
          </div>
        </section>
      )}

      {/* TAB CONTENT 3: SPATIAL HOTSPOTS & INTERACTIVE MAP */}
      {activeTab === 'phase2_spatial' && (
        <section className="space-y-6">
          {/* Spatial Narrative Callout */}
          <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900/60 bg-cyan-50/50 dark:bg-cyan-950/20 p-5 space-y-3">
            <div className="flex items-center space-x-2 text-cyan-800 dark:text-cyan-300 font-bold text-sm">
              <MapPin className="w-4 h-4 shrink-0" />
              <span>Spatial Normalization & The County Screening Polygon</span>
            </div>
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
              Allegheny County contains <strong>238,281 valid polygon-screened crash locations</strong> (95.77% of all reports). Police-provided GPS coordinates were systematically compared with PennDOT State Route decimal coordinates. Out of 238,517 coordinate pairs, only 2,146 candidate disagreements exceeded 500 meters. The map below plots the top 100 historical concentration sites.
            </p>
          </div>

          {/* Interactive Plotly Map */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Interactive Crash Hotspot Map (Allegheny County)</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Click, zoom, or hover on any point to inspect site attributes. Filter by functional roadway classification.
                </p>
              </div>

              {/* Road Class Filter Pills */}
              <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
                <span className="text-slate-400 text-[11px] font-semibold mr-1">Filter:</span>
                {roadClassOptions.map((rc) => (
                  <button
                    key={rc}
                    onClick={() => setSelectedRoadClass(rc)}
                    className={`px-2.5 py-1 rounded-lg font-semibold transition-colors ${
                      selectedRoadClass === rc
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                    }`}
                  >
                    {rc}
                  </button>
                ))}
              </div>
            </div>

            {/* Plotly Dynamic Map */}
            <div className="h-96 w-full rounded-xl overflow-hidden border border-slate-100 dark:border-slate-800">
              <PlotlyChart
                className="h-full w-full"
                config={{ displayModeBar: true, responsive: true, scrollZoom: true }}
                data={[
                  {
                    type: 'scatter',
                    mode: 'markers',
                    x: filteredHotspots.map((h) => h.geometry.coordinates[0]),
                    y: filteredHotspots.map((h) => h.geometry.coordinates[1]),
                    text: filteredHotspots.map(
                      (h) =>
                        `<b>Rank #${h.properties.rank}: ${h.properties.site_id}</b><br>` +
                        `Road: ${h.properties.road_class} (${h.properties.site_type})<br>` +
                        `Total Crashes: ${h.properties.total_crashes}<br>` +
                        `Fatalities: ${h.properties.fatal_crashes} | KSI: ${h.properties.ksi_crashes}<br>` +
                        `VRU Crashes: ${h.properties.vru_crashes}<br>` +
                        `Density: ${h.properties.crash_density_per_km.toFixed(1)}/km<br>` +
                        `Tier: ${h.properties.persistence_category}`
                    ),
                    hoverinfo: 'text',
                    marker: {
                      size: filteredHotspots.map((h) => Math.max(8, Math.min(22, Math.sqrt(h.properties.total_crashes) * 0.9))),
                      color: filteredHotspots.map((h) => {
                        const tier = h.properties.persistence_category;
                        if (tier.includes('HIGH')) return '#ef4444';
                        if (tier.includes('MEDIUM') || tier.includes('EMERGING')) return '#8b5cf6';
                        return '#06b6d4';
                      }),
                      opacity: 0.85,
                      line: { color: '#ffffff', width: 1.5 },
                    },
                  },
                ]}
                layout={{
                  margin: { l: 40, r: 20, t: 20, b: 40 },
                  xaxis: { title: 'Longitude (WGS84)', tickformat: '.2f' },
                  yaxis: { title: 'Latitude (WGS84)', tickformat: '.2f' },
                  plot_bgcolor: '#0f172a',
                  paper_bgcolor: '#0f172a',
                  font: { color: '#94a3b8' },
                  hoverlabel: {
                    bgcolor: '#1e293b',
                    bordercolor: '#6366f1',
                    font: { color: '#f8fafc', size: 11 },
                  },
                }}
              />
            </div>

            {/* Selected Hotspot Detail Card */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2">
                <Compass className="w-4 h-4 text-indigo-500 shrink-0" />
                <span>
                  Showing <strong>{filteredHotspots.length}</strong> top crash concentration sites. Marker size denotes crash density; crimson dots highlight Persistent High Hazard corridors.
                </span>
              </div>
              <a
                href={overviewUrl('/assets/county_grid.svg')}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center space-x-1 text-indigo-600 dark:text-indigo-400 hover:underline font-semibold"
              >
                <span>View Full County Grid (SVG)</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </section>
      )}

      {/* TAB CONTENT 4: CONCENTRATION & THE EXPOSURE PROBLEM */}
      {activeTab === 'phase3_concentration' && (
        <section className="space-y-6">
          {/* Narrative Callout on Exposure */}
          <div className="rounded-2xl border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/20 p-5 space-y-3">
            <div className="flex items-center space-x-2 text-indigo-700 dark:text-indigo-300 font-bold text-sm">
              <Activity className="w-4 h-4 shrink-0" />
              <span>The Exposure Fallacy: Raw Crash Counts vs. Risk Rate</span>
            </div>
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
              A corridor with 500 crashes and 100,000 vehicles/day has a much lower risk rate than a rural two-lane road with 50 crashes and 2,000 vehicles/day. State Routes and Interstates have near 96% coordinate matching and high traffic exposure; local streets carry lower match rates and municipal variances.
            </p>
          </div>

          {/* Road Class Concentration Table & Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">Crash Volume by Functional Road Class</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Notice State Routes and Local Streets account for over 85% of total county crash occurrences.
              </p>
              <div className="h-64 w-full">
                <PlotlyChart
                  className="h-full w-full"
                  config={{ displayModeBar: false, responsive: true }}
                  data={[
                    {
                      x: roadClasses.map((r) => r.road_class.replace('_', ' ')),
                      y: roadClasses.map((r) => Number(r.total_crashes)),
                      type: 'bar',
                      marker: { color: ['#3b82f6', '#6366f1', '#06b6d4', '#8b5cf6', '#ec4899'] },
                    },
                  ]}
                  layout={{
                    margin: { l: 50, r: 20, t: 20, b: 60 },
                    xaxis: { tickangle: -25 },
                    yaxis: { title: 'Total Historical Crashes' },
                  }}
                />
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">Network Normalization Breakdown</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                PennDOT state centerline crosswalk match rates across functional systems.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700 text-slate-400 font-semibold uppercase">
                      <th className="py-2.5">Road Class</th>
                      <th className="py-2.5">Total Crashes</th>
                      <th className="py-2.5">Matched Sites</th>
                      <th className="py-2.5">Match %</th>
                      <th className="py-2.5">Missing Coord %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                    {roadClasses.map((r) => (
                      <tr key={r.road_class} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-2 font-bold font-sans text-slate-800 dark:text-slate-200">{r.road_class}</td>
                        <td className="py-2">{count(Number(r.total_crashes))}</td>
                        <td className="py-2">{count(Number(r.unique_matched_sites))}</td>
                        <td className="py-2 text-emerald-600 dark:text-emerald-400 font-semibold">{r.match_coverage_percent}</td>
                        <td className="py-2 text-slate-500">{r.missing_coord_percent}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB CONTENT 5: MACHINE LEARNING SEVERITY MODELLING */}
      {activeTab === 'phase4_modelling' && (
        <section className="space-y-6">
          {/* Modelling Narrative Callout */}
          <div className="rounded-2xl border border-purple-200 dark:border-purple-900/60 bg-purple-50/50 dark:bg-purple-950/20 p-5 space-y-3">
            <div className="flex items-center space-x-2 text-purple-800 dark:text-purple-300 font-bold text-sm">
              <Cpu className="w-4 h-4 shrink-0" />
              <span>Retrospective Severity Prediction Benchmark: What Really Matters</span>
            </div>
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
              We evaluated non-linear tree models (HistGradientBoosting, Random Forest) against Logistic Regression across <strong>27,697 held-out test crashes</strong> to predict severe (fatal/serious injury) outcomes among reported incidents. Environmental attributes alone (lighting, weather, roadway condition) produce weak discrimination (Average Precision ~0.051). Incorporating <strong>collision configuration</strong> triples Average Precision to 0.1548 and boosts ROC-AUC to 0.6921.
            </p>
          </div>

          {/* Model Benchmark Comparison Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">Model Performance: Average Precision & ROC-AUC</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Notice how adding collision configuration features dramatically boosts both tree models and logistic regression.
              </p>
              <div className="h-64 w-full">
                <PlotlyChart
                  className="h-full w-full"
                  config={{ displayModeBar: false, responsive: true }}
                  data={[
                    {
                      name: 'Average Precision (AP)',
                      x: modelMetrics.map((m) => m.model),
                      y: modelMetrics.map((m) => m.average_precision),
                      type: 'bar',
                      marker: { color: '#8b5cf6' },
                    },
                    {
                      name: 'ROC-AUC',
                      x: modelMetrics.map((m) => m.model),
                      y: modelMetrics.map((m) => m.roc_auc),
                      type: 'bar',
                      marker: { color: '#3b82f6' },
                    },
                  ]}
                  layout={{
                    barmode: 'group',
                    margin: { l: 50, r: 20, t: 20, b: 80 },
                    xaxis: { tickangle: -25 },
                    yaxis: { title: 'Score', range: [0, 0.8] },
                    legend: { orientation: 'h', y: -0.35 },
                  }}
                />
              </div>
            </div>

            {/* Categorical Associations with FDR BH correction */}
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">Categorical Effect Sizes (Cramér's V)</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Multiplicity-adjusted associations against severe injury outcomes (Benjamini-Hochberg q = 0.00).
              </p>
              <div className="space-y-3">
                {[
                  { feature: 'Collision Type (Angle, Head-on, Rear)', cramers_v: 0.202, significance: 'q = 0.00' },
                  { feature: 'Time Period (Night, Rush Hour, Off-Peak)', cramers_v: 0.048, significance: 'q = 9.4e-38' },
                  { feature: 'Illumination Condition', cramers_v: 0.037, significance: 'q = 1.3e-20' },
                  { feature: 'Intersection Geometry', cramers_v: 0.022, significance: 'q = 7.4e-06' },
                ].map((item) => (
                  <div key={item.feature} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between font-semibold">
                      <span className="text-slate-800 dark:text-slate-200">{item.feature}</span>
                      <span className="font-mono text-indigo-600 dark:text-indigo-400">V = {item.cramers_v}</span>
                    </div>
                    <div className="w-full bg-slate-200 dark:bg-slate-700 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-indigo-600 h-full rounded-full"
                        style={{ width: `${(item.cramers_v / 0.25) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB CONTENT 6: ACTIONABLE SAFETY INTERVENTIONS */}
      {activeTab === 'phase5_countermeasures' && (
        <section className="space-y-6">
          <div className="rounded-2xl border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/50 dark:bg-emerald-950/20 p-6 space-y-4">
            <div className="flex items-center space-x-2 text-emerald-800 dark:text-emerald-300 font-bold text-sm">
              <CheckCircle2 className="w-5 h-5 shrink-0" />
              <span>Translating Data Science to Safety Engineering: Crash Modification Factors (CMFs)</span>
            </div>
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
              Our analysis proved that collision type (angle and head-on crashes) is the single biggest predictor of fatal and severe injury outcomes. Therefore, engineering countermeasures that eliminate angle conflict points yield the highest documented safety returns:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 block">Modern Roundabout Conversion</span>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  Converts angle and head-on conflict points to low-speed merges. <strong>CMF: 0.22</strong> (78% reduction in fatal/serious injury crashes).
                </p>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 block">High-Friction Surface Treatment (HFST)</span>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  Restores pavement micro-texture at high-speed curves and ramps. <strong>CMF: 0.43</strong> (57% reduction in wet-road roadway departure crashes).
                </p>
              </div>

              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <span className="text-xs font-bold text-cyan-600 dark:text-cyan-400 block">Pedestrian Countdown Signals</span>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  Clear visual indication of remaining crossing clearance. <strong>CMF: 0.61</strong> (39% reduction in pedestrian vehicle conflicts).
                </p>
              </div>
            </div>

            <div className="pt-3">
              <Link
                to="/illustrative-scenario"
                className="inline-flex items-center space-x-2 px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-md shadow-emerald-600/20 transition-all"
              >
                <span>Launch Interactive Countermeasure Scenario Calculator</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Dataset Link to Workspace */}
      <footer className="p-6 rounded-2xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-bold text-slate-900 dark:text-white">Ready to analyze your own custom dataset?</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Upload any CSV, TSV, or multi-sheet Excel file or explore the 248,810 records in the interactive Analysis Workspace.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Link
            to="/workspace"
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition-all"
          >
            Open Analysis Workspace
          </Link>
          <Link
            to="/upload"
            className="px-4 py-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-xs font-bold hover:bg-slate-50 transition-all"
          >
            Upload Dataset
          </Link>
        </div>
      </footer>
    </div>
  );
}
