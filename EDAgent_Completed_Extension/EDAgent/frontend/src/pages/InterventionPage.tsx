import { useEffect, useRef, useState, type FormEvent } from 'react';
import { apiClient } from '../services/apiClient';
import { getData, type RoadSafetyError } from '../services/roadSafetyService';

const crashTypes = {
  ALL: 'All crashes', PEDESTRIAN: 'Pedestrian crashes', BICYCLIST: 'Bicyclist crashes',
  REAR_END: 'Rear-end crashes', ANGLE: 'Angle crashes', NIGHTTIME: 'Nighttime crashes',
};
type CrashType = keyof typeof crashTypes;
type Reference = {
  EVIDENCE_ID: string; TREATMENT: string; EVIDENCE_STATUS: string; description: string;
  source_ids: string[]; facility_type: string | null; target_crash_type: string | null;
  context: string; limitations: string;
};
type Evidence = {
  records: Reference[]; applicability_notice: string;
  sources: Record<string, { citation: string; urls?: string[]; path?: string }>;
};
type Interval = { lower: string; upper: string };
type Result = {
  notice: string;
  scenario: { crash_type: CrashType; analysis_period: { length: number }; cmf: { value: string } };
  exact: { delta_n: string };
  display: { hypothetical_baseline_n: string; after_n: string; delta_n: string;
    sensitivity: { label: string; after_n: Interval; delta_n: Interval } | null };
};
const panel = 'min-w-0 space-y-4 border border-stone-300 bg-[#fffcf4] p-4 sm:p-6';
const input = 'block w-full rounded-lg border border-slate-400 bg-transparent px-3 py-2 font-normal';
const decimalPattern = '[0-9]{1,12}(\\.[0-9]{1,6})?';

export function InterventionPage() {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceError, setEvidenceError] = useState<RoadSafetyError | null>(null);
  const [reference, setReference] = useState('');
  const [factor, setFactor] = useState('');
  const [bounds, setBounds] = useState({ lower: '', upper: '' });
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<RoadSafetyError | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => {
    const request = new AbortController();
    getData<Evidence>('/interventions/evidence', request.signal).then(setEvidence).catch(error => {
      if (!request.signal.aborted) setEvidenceError(error);
    });
    return () => { request.abort(); pending.current?.abort(); };
  }, []);

  function clearResult() {
    // An edit invalidates both the displayed result and any calculation still in flight.
    pending.current?.abort();
    setBusy(false);
    setResult(null);
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearResult();
    const form = new FormData(event.currentTarget);
    const text = (field: string) => String(form.get(field) ?? '');
    const length = Number(text('years'));
    if (!Number.isSafeInteger(length) || length < 1) {
      setError(new Error('Enter a positive whole number of years.'));
      return;
    }
    const lower = text('lower');
    const upper = text('upper');
    if (Boolean(lower) !== Boolean(upper)) {
      setError(new Error('Enter both sensitivity bounds or leave both empty.'));
      return;
    }
    const request = new AbortController();
    pending.current = request;
    setBusy(true);
    try {
      const crashType = text('crashType');
      const response = await apiClient.post<{ data: Result }>('/interventions/scenarios', {
        schema_version: '1', scenario_kind: 'HYPOTHETICAL', hypothetical_baseline_n: text('baseline'),
        crash_type: crashType, analysis_period: { length, unit: 'YEARS' }, units: 'CRASHES_PER_ANALYSIS_PERIOD',
        cmf: { origin: 'USER_ENTERED_HYPOTHETICAL', crash_type: crashType, value: text('factor'),
          ...(lower && upper ? { bounds: { lower, upper } } : {}) },
      }, { signal: request.signal });
      if (!request.signal.aborted) setResult(response.data.data);
    } catch (error) {
      if (!request.signal.aborted) setError(error as RoadSafetyError);
    } finally {
      if (!request.signal.aborted) setBusy(false);
    }
  }

  const evidenceUnavailable = evidenceError?.code === 'REAL_SITE_BENEFIT_UNAVAILABLE';
  const referenceEntry = evidence?.records.find(record => record.EVIDENCE_ID === reference);
  const delta = result?.exact.delta_n;
  const change = delta === undefined ? '' : Number(delta) === 0 ? 'no change' : delta.startsWith('-') ? 'more hypothetical crashes' : 'fewer hypothetical crashes';

  return <article className="space-y-5">
    <header className="space-y-2">
      <h1 className="text-2xl font-bold sm:text-3xl">What-if calculator</h1>
      <p>Explore hypothetical crash-count changes using a crash modification factor (CMF) you supply.</p>
    </header>
    <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
      <section className={panel} aria-labelledby="references">
        <h2 id="references" className="text-lg font-bold">Treatment references</h2>
        {evidenceError ? <div role="alert">{evidenceUnavailable && <p>REAL_SITE_BENEFIT_UNAVAILABLE</p>}<p>{evidenceError.message}</p></div>
          : !evidence ? <p role="status">Loading treatment references…</p> : !evidence.records.length ? <p>No treatment references are available.</p> : <>
          <p>{evidence.applicability_notice}</p>
          <label className="block font-medium">Select a treatment reference
            <select className={input} value={reference} onChange={event => {
              setReference(event.target.value);
              setFactor('');
              setBounds({ lower: '', upper: '' });
              clearResult();
            }}>
              <option value="">Choose a reference</option>
              {evidence.records.map(record => <option key={record.EVIDENCE_ID} value={record.EVIDENCE_ID}>{record.TREATMENT}</option>)}
            </select>
          </label>
          {referenceEntry && <div className="space-y-2" aria-live="polite">
            <p className="font-semibold">{referenceEntry.EVIDENCE_STATUS}</p>
            <p>{referenceEntry.description}</p>
            <p>{referenceEntry.context}</p>
            {referenceEntry.facility_type && <p>Candidate facilities · {referenceEntry.facility_type}</p>}
            {referenceEntry.target_crash_type && <p>Candidate crash type · {referenceEntry.target_crash_type}</p>}
            <p>{referenceEntry.limitations}</p>
            <h3 className="font-semibold">Sources</h3>
            <ul className="list-disc space-y-1 pl-5">{referenceEntry.source_ids.map(id => {
              const source = evidence.sources[id];
              return <li key={id}>
                {source.urls?.[0] ? <a className="underline" href={source.urls[0]}>{source.citation}</a> : source.citation}
              </li>;
            })}</ul>
            <p>This treatment reference has no approved numeric factor. You can enter a hypothetical factor in illustrative mode.</p>
          </div>}
        </>}
      </section>
      <section className={panel} aria-labelledby="calculator">
        <h2 id="calculator" className="text-lg font-bold">Hypothetical calculator</h2>
        <form className="space-y-4" onSubmit={submit} onChange={clearResult}>
          <label className="block font-medium">Shared crash type
            <select className={input} name="crashType">
              {Object.entries(crashTypes).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </label>
          <label className="block font-medium">Analysis period (years)
            <input className={input} name="years" type="number" min="1" step="1" required />
          </label>
          <label className="block font-medium">Hypothetical baseline crash count
            <input className={input} name="baseline" inputMode="decimal" pattern={decimalPattern} required aria-describedby="decimal-help" />
          </label>
          <label className="block font-medium">Hypothetical CMF
            <input className={input} name="factor" inputMode="decimal" pattern={decimalPattern} required aria-describedby="decimal-help"
              value={factor} onChange={event => setFactor(event.target.value)} />
          </label>
          <p id="decimal-help" className="text-sm">Use up to 12 whole digits and 6 decimal places. The factor must be greater than zero.</p>
          <fieldset className="space-y-2">
            <legend className="font-semibold">Hypothetical factor sensitivity range</legend>
            <p className="text-sm">Optional bounds vary your factor while holding the hypothetical baseline fixed. The range has no statistical confidence level.</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <label>Lower factor<input className={input} name="lower" inputMode="decimal" pattern={decimalPattern}
                value={bounds.lower} onChange={event => setBounds({ ...bounds, lower: event.target.value })} /></label>
              <label>Upper factor<input className={input} name="upper" inputMode="decimal" pattern={decimalPattern}
                value={bounds.upper} onChange={event => setBounds({ ...bounds, upper: event.target.value })} /></label>
            </div>
          </fieldset>
          <button type="submit" disabled={busy} className="rounded-lg bg-indigo-700 px-4 py-2 font-semibold text-white disabled:opacity-60">{busy ? 'Calculating…' : 'Calculate scenario'}</button>
        </form>
        {error && <div role="alert" className="text-red-700 dark:text-red-300">
          {error.code === 'REAL_SITE_BENEFIT_UNAVAILABLE' && <p>REAL_SITE_BENEFIT_UNAVAILABLE</p>}
          <p>{error.status === 422 ? error.problems?.join(' ') || error.message : error.message}</p>
        </div>}
        {result && <div role="status" className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-700">
          <h3 className="font-semibold">Hypothetical results</h3>
          <p>{crashTypes[result.scenario.crash_type]} · {result.scenario.analysis_period.length} {result.scenario.analysis_period.length === 1 ? 'year' : 'years'} · crashes per analysis period</p>
          <p>User-entered hypothetical factor · {result.scenario.cmf.value}</p>
          <dl className="space-y-2">
            <div><dt>Hypothetical baseline crash count</dt><dd className="font-semibold">{result.display.hypothetical_baseline_n}</dd></div>
            <div><dt>Hypothetical after crash count</dt><dd className="font-semibold">{result.display.after_n}</dd></div>
            <div><dt>Hypothetical change in crash count</dt><dd className="font-semibold">{result.display.delta_n} ({change})</dd></div>
          </dl>
          {result.display.sensitivity && <div>
            <h4 className="font-semibold">{result.display.sensitivity.label}</h4>
            <p>After count · {result.display.sensitivity.after_n.lower} to {result.display.sensitivity.after_n.upper}</p>
            <p>Change · {result.display.sensitivity.delta_n.lower} to {result.display.sensitivity.delta_n.upper}</p>
          </div>}
          <p>{result.notice}</p>
        </div>}
      </section>
    </div>
  </article>;
}
