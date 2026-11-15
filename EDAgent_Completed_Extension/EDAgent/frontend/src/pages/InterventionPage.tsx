import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { apiClient, type ValidationProblem } from '../services/apiClient';
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
  scenario: {
    hypothetical_baseline_n: string; crash_type: CrashType; analysis_period: { length: number };
    cmf: { value: string; bounds: Interval | null };
  };
  exact: { delta_n: string };
  display: { after_n: string; delta_n: string;
    sensitivity: { label: string; after_n: Interval; delta_n: Interval } | null };
};
const emptyInputs = { crashType: 'ALL', years: '', baseline: '', factor: '', lower: '', upper: '' };
const inventedInputs = { crashType: 'ALL', years: '5', baseline: '40', factor: '0.80', lower: '0.70', upper: '0.95' };
type Inputs = typeof emptyInputs;
type Field = keyof Inputs | 'bounds';
type FieldErrors = Partial<Record<Field, string>>;
type CalculationError = RoadSafetyError & { validation?: ValidationProblem[] };

const input = 'block w-full rounded border border-[var(--muted)] bg-[#fffcf4] px-3 py-2 font-normal aria-[invalid=true]:border-[var(--rust)]';
const primary = 'rounded bg-[var(--teal)] px-4 py-2 font-semibold text-white';
const sourceRepo = 'https://github.com/ExploratoryDataAnalysis/EDAgent/blob/53dc033a1f4a53c7ff19e615c1e4301982a8b8ab/';

function fieldError(problem: ValidationProblem): [Field, string] | undefined {
  if (problem.type === 'invalid_factor_bounds') return ['bounds', 'Set the lower factor at or below your CMF and the upper factor at or above it.'];
  if (problem.type === 'crash_type_mismatch') return ['crashType', 'Use the same crash type for the baseline and factor.'];
  const field = problem.loc[problem.loc.length - 1];
  switch (field) {
    case 'hypothetical_baseline_n':
      return ['baseline', 'Enter a crash count of zero or more, using up to 12 whole digits and 6 decimal places.'];
    case 'value':
    case 'lower':
    case 'upper': {
      const message = 'Enter a positive decimal with up to 12 whole digits and 6 decimal places.';
      return field === 'value'
        ? ['factor', message]
        : [field, message + ' Enter both bounds or leave both blank.'];
    }
    case 'crash_type':
      return ['crashType', 'Choose a shared crash type.'];
  }
}

export function InterventionPage() {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [evidenceError, setEvidenceError] = useState<RoadSafetyError | null>(null);
  const [reference, setReference] = useState('');
  const [inputs, setInputs] = useState(emptyInputs);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<CalculationError | null>(null);
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
    // The aborted signal guards against late completions after edits, reset or a newer request.
    pending.current?.abort();
    setBusy(false);
    setResult(null);
    setError(null);
    setFieldErrors({});
  }

  async function calculate({ crashType, years, baseline, factor, lower, upper }: Inputs) {
    clearResult();
    const length = Number(years);
    if (!Number.isSafeInteger(length) || length < 1) {
      setFieldErrors({ years: 'Enter a positive whole number of years.' });
      return;
    }
    const request = new AbortController();
    pending.current = request;
    setBusy(true);
    try {
      // Schema 1 uses one period and requires matching crash types. Keep decimals as typed.
      const response = await apiClient.post<{ data: Result }>('/interventions/scenarios', {
        schema_version: '1', scenario_kind: 'HYPOTHETICAL', hypothetical_baseline_n: baseline,
        crash_type: crashType, analysis_period: { length, unit: 'YEARS' }, units: 'CRASHES_PER_ANALYSIS_PERIOD',
        cmf: { origin: 'USER_ENTERED_HYPOTHETICAL', crash_type: crashType, value: factor,
          ...(lower || upper ? { bounds: { lower, upper } } : {}) },
      }, { signal: request.signal, timeout: 15000 });
      if (!request.signal.aborted) setResult(response.data.data);
    } catch (caught) {
      if (request.signal.aborted) return;
      const failure = caught as CalculationError;
      const errors: FieldErrors = {};
      for (const problem of failure.validation ?? []) {
        const entry = fieldError(problem);
        if (entry) errors[entry[0]] = entry[1];
      }
      if (Object.keys(errors).length) setFieldErrors(errors);
      else setError(failure);
    } finally {
      if (!request.signal.aborted) {
        pending.current = null;
        setBusy(false);
      }
    }
  }

  function control(field: keyof Inputs) {
    const invalid = Boolean(fieldErrors[field] || (field === 'lower' || field === 'upper') && fieldErrors.bounds);
    const descriptions = [
      field === 'baseline' || field === 'factor' ? 'decimal-help' : '',
      fieldErrors[field] ? field + '-error' : '',
      (field === 'lower' || field === 'upper') && fieldErrors.bounds ? 'bounds-error' : '',
    ];
    return {
      name: field, value: inputs[field], className: input,
      'aria-invalid': invalid || undefined,
      'aria-describedby': descriptions.filter(Boolean).join(' ') || undefined,
      onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const value = event.target.value;
        clearResult();
        setInputs(previous => ({ ...previous, [field]: value }));
      },
    };
  }

  function message(field: Field) {
    return fieldErrors[field] && <span id={field + '-error'} className="block text-sm font-normal text-[var(--rust)]">{fieldErrors[field]}</span>;
  }

  function decimalField(field: 'baseline' | 'factor' | 'lower' | 'upper', label: string) {
    return <div>
      <label className="block font-medium">{label}
        <input {...control(field)} inputMode="decimal" required={field === 'baseline' || field === 'factor'} />
      </label>
      {message(field)}
    </div>;
  }

  const retry = error && !error.code && (error.status === undefined || error.status >= 500);
  const referenceEntry = evidence?.records.find(record => record.EVIDENCE_ID === reference);
  const delta = result?.exact.delta_n;
  const change = delta === undefined ? '' : Number(delta) === 0 ? 'no change' : delta.startsWith('-') ? 'more hypothetical crashes' : 'fewer hypothetical crashes';
  const years = result?.scenario.analysis_period.length ?? 0;
  const period = years + (years === 1 ? ' year' : ' years');
  const sensitivity = result?.display.sensitivity;

  return <article className="public-document public-measure">
    <header className="public-hero">
      <p className="public-kicker">Hypothetical scenario</p>
      <h1>What-if calculator</h1>
      <p className="public-lede">See how an assumed crash modification factor (CMF) changes a hypothetical crash count over a fixed period.</p>
      <button type="button" className={primary + ' mt-4'} onClick={() => {
        setInputs(inventedInputs);
        void calculate(inventedInputs);
      }}>Run an invented example</button>
    </header>
    <div role="status" aria-atomic="true">
      {busy && <p>Calculating hypothetical results…</p>}
      {result && <section className="public-status space-y-2 [overflow-wrap:anywhere]" aria-labelledby="scenario-result">
        <h2 id="scenario-result" tabIndex={-1}>Hypothetical results</h2>
        <p>{crashTypes[result.scenario.crash_type]} · {period}</p>
        <p>Baseline × factor = after count</p>
        <p className="text-xl font-semibold">
          {result.scenario.hypothetical_baseline_n} × {result.scenario.cmf.value} → {result.display.after_n} hypothetical crashes over {period}
        </p>
        <p>Baseline − after = signed change (positive means a reduction).</p>
        <p className="font-semibold">{result.display.delta_n} ({change})</p>
        {sensitivity && result.scenario.cmf.bounds && <div>
          <h3 className="font-semibold">{sensitivity.label}</h3>
          <p>After count · {sensitivity.after_n.lower} to {sensitivity.after_n.upper} crashes over {period}</p>
          <p>Signed change · {sensitivity.delta_n.lower} to {sensitivity.delta_n.upper} crashes</p>
          <p>The same baseline is multiplied by factors from {result.scenario.cmf.bounds.lower} to {result.scenario.cmf.bounds.upper}. The range describes sensitivity to those inputs and has no statistical confidence level.</p>
        </div>}
        <p className="text-sm">{result.notice}</p>
      </section>}
    </div>
    <section className="public-section" aria-labelledby="calculator">
      <h2 id="calculator">Enter hypothetical inputs</h2>
      <p className="mb-4">Use the same crash type and analysis period for the baseline and factor.</p>
      <form className="space-y-4" noValidate onSubmit={event => {
        event.preventDefault();
        void calculate(inputs);
      }} onReset={() => {
        clearResult();
        setInputs(emptyInputs);
      }}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="scenario-crash-type" className="block font-medium">Shared crash type</label>
            <select id="scenario-crash-type" {...control('crashType')}>
              {Object.entries(crashTypes).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
            {message('crashType')}
          </div>
          <div>
            <label className="block font-medium">Analysis period (years)
              <input {...control('years')} type="number" min="1" step="1" required />
            </label>
            {message('years')}
          </div>
          {decimalField('baseline', 'Hypothetical baseline crash count')}
          {decimalField('factor', 'Hypothetical CMF')}
        </div>
        <p id="decimal-help" className="text-sm">Use up to 12 whole digits and 6 decimal places. The factor must be greater than zero.</p>
        <fieldset className="space-y-2">
          <legend className="font-semibold">Hypothetical factor sensitivity range</legend>
          <p className="text-sm">Optional. Enter both bounds to vary the factor while holding the hypothetical baseline fixed.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {decimalField('lower', 'Lower factor')}
            {decimalField('upper', 'Upper factor')}
          </div>
          {message('bounds')}
        </fieldset>
        <div role="alert" className="text-[var(--rust)]">
          {Object.keys(fieldErrors).length > 0 && <p>Check the highlighted inputs. {Object.values(fieldErrors).join(' ')}</p>}
          {error?.code === 'REAL_SITE_BENEFIT_UNAVAILABLE' && <p>REAL_SITE_BENEFIT_UNAVAILABLE</p>}
          {error && <p>{retry ? 'The calculator could not complete the request. Your inputs are still here.' : error.message}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <button type="submit" className={primary}>{retry ? 'Retry calculation' : 'Calculate scenario'}</button>
          <button type="reset" className="rounded border border-[var(--muted)] px-4 py-2 font-semibold">Reset inputs</button>
          {result && <a href="#scenario-result">View hypothetical results</a>}
        </div>
      </form>
    </section>
    <section className="public-section space-y-3" aria-labelledby="references">
        <h2 id="references" className="text-lg font-bold">Treatment references</h2>
        {evidenceError ? <p role="alert">{evidenceError.message}</p>
          : !evidence ? <p role="status">Loading treatment references…</p> : !evidence.records.length ? <p>No treatment references are available.</p> : <>
          <p>{evidence.applicability_notice}</p>
          <label className="block font-medium">Select a treatment reference
            <select className={input} value={reference} onChange={event => setReference(event.target.value)}>
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
              const href = source.urls?.[0] ?? (source.path && sourceRepo + source.path);
              return <li key={id}>
                {href ? <a href={href}>{source.citation}</a> : source.citation}
              </li>;
            })}</ul>
            <p>This treatment reference has no approved numeric factor. You can enter a hypothetical factor in illustrative mode.</p>
          </div>}
        </>}
      </section>
  </article>;
}
