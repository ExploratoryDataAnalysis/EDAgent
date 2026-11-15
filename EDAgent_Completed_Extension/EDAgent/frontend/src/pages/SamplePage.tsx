import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ResultView } from '../components/results/ResultView';
import { apiClient, downloadFile } from '../services/apiClient';
import { authService } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { AnalysisResult } from '../types';

type Provenance = {
  title: string;
  source: string | Record<string, string>;
  interpretation: string;
  approval_date?: string;
  fixture_date?: string;
  run_id?: string;
  scope?: { county: string; period_start: number; period_end: number };
  bundle?: { version: string; manifest_sha256: string; output_sha256: string };
};
type Exercise = { result: AnalysisResult; provenance: Provenance };
const base = '/analyser/samples';
const countyInfo = async (): Promise<Provenance | null> => (await apiClient.get(base)).data.data.county;
const button = 'rounded-lg bg-indigo-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60';

export function CountySampleLink({ showUnavailable = false }: { showUnavailable?: boolean }) {
  const [county, setCounty] = useState<Provenance | null>(null);
  useEffect(() => {
    countyInfo().then(setCounty).catch(() => setCounty(null));
  }, []);
  if (county) return <Link className="underline" to="/analyser/sample/county">Open approved county aggregates</Link>;
  return showUnavailable ? <p className="text-sm">County aggregates require a reviewed release.</p> : null;
}

export function AnalyserStart() {
  const navigate = useNavigate();
  const { startGuest, guestNotice } = useAuth();
  const [guestAvailable, setGuestAvailable] = useState(false);
  const [guestBusy, setGuestBusy] = useState(false);
  const [guestError, setGuestError] = useState('');
  useEffect(() => {
    authService.guestAvailability().then(({ available }) => setGuestAvailable(available)).catch(() => setGuestAvailable(false));
  }, []);
  const beginGuest = async () => {
    setGuestBusy(true);
    setGuestError('');
    try {
      await startGuest();
      navigate('/upload');
    } catch (e) {
      setGuestError((e as Error).message);
      setGuestBusy(false);
    }
  };
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6 sm:py-12">
      <h1 className="text-3xl font-bold">Dataset analyser</h1>
      {guestNotice && <p role="status">{guestNotice}</p>}
      <p>Use a sample or upload your own data. Choose an analysis, inspect the result and download it.</p>
      <section className="space-y-3 rounded-xl border border-slate-300 p-4 dark:border-slate-700">
        <h2 className="text-lg font-semibold">Try a sample</h2>
        <p>Start with twelve invented library return times and calculate their median.</p>
        <p><Link className="underline" to="/analyser/sample/teaching">Open the invented teaching dataset</Link></p>
        <CountySampleLink showUnavailable />
      </section>
      <section className="space-y-3 rounded-xl border border-slate-300 p-4 dark:border-slate-700">
        <h2 className="text-lg font-semibold">Work with your own dataset</h2>
        {guestAvailable && <button className={button} onClick={beginGuest} disabled={guestBusy}>
          {guestBusy ? 'Starting guest session…' : 'Start a private guest session'}
        </button>}
        {guestError && <p role="alert" className="text-red-700 dark:text-red-300">{guestError}</p>}
        <Link className="block underline" to="/upload">Upload with an account</Link>
        <Link className="block underline" to="/login">Sign in to your saved workspace</Link>
      </section>
      <Link className="underline" to="/">Back to the investigation</Link>
    </main>
  );
}

export function SamplePage({ sample }: { sample: 'teaching' | 'county' }) {
  const county = sample === 'county';
  const [release, setRelease] = useState<Provenance | null>(null);
  const [operation, setOperation] = useState('descriptive_stats');
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const identity = release?.bundle?.manifest_sha256;
  const current = exercise?.provenance.bundle?.manifest_sha256 === identity ? exercise : null;

  useEffect(() => {
    if (!county) return;
    let active = true;
    const check = () => countyInfo().catch(() => null).then((value) => {
      if (!active) return;
      setRelease(value);
      setExercise((previous) => value && previous?.provenance.bundle?.manifest_sha256 === value.bundle?.manifest_sha256 ? previous : null);
    });
    // Clear rendered results when a restored or refocused page loses its release.
    const clear = () => { setExercise(null); setRelease(null); };
    void check();
    const interval = window.setInterval(check, 15_000);
    window.addEventListener('pageshow', check);
    window.addEventListener('pagehide', clear);
    window.addEventListener('focus', check);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener('pageshow', check);
      window.removeEventListener('pagehide', clear);
      window.removeEventListener('focus', check);
    };
  }, [county]);

  const params = { operation, manifest_sha256: identity };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setExercise(null);
    setError('');
    setBusy(true);
    try {
      const { data } = await apiClient.post(`${base}/${sample}/analysis`, null, { params });
      setExercise(data.data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const download = async () => {
    setError('');
    try {
      await downloadFile(`${base}/${sample}/download`, 'analysis.json', { ...params, instance_id: current?.result.dataset_id });
    } catch (e) {
      if (county) setExercise(null);
      setError((e as Error).message);
    }
  };

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-6 sm:py-12">
      <nav className="flex flex-wrap gap-4 text-sm">
        <Link className="underline" to="/analyser">Dataset analyser</Link>
        <Link className="underline" to="/">Back to the investigation</Link>
      </nav>
      <h1 className="text-3xl font-bold">{county ? 'Approved county aggregates' : 'Invented teaching dataset'}</h1>
      {county && !release && <p role="status">The reviewed county aggregates are currently unavailable.</p>}
      {county && release?.scope && <p>{release.scope.county}, {release.scope.period_start}–{release.scope.period_end}. {release.interpretation}</p>}
      {!county && <p>Twelve invented library return times, in minutes. Run summary statistics to find the median, or choose a histogram to see their distribution.</p>}
      {(!county || release) && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">
            Analysis
            <select className="rounded-lg border border-slate-400 bg-white p-2 dark:bg-slate-900" value={operation}
              onChange={(event) => { setOperation(event.target.value); setExercise(null); }} disabled={busy}>
              <option value="descriptive_stats">Summary statistics</option>
              <option value="histogram">Histogram</option>
            </select>
          </label>
          <button className={button} disabled={busy}>Run analysis</button>
        </form>
      )}
      <p role="status">{busy ? 'Running analysis…' : current ? 'Analysis complete.' : ''}</p>
      {error && <p role="alert" className="text-red-700 dark:text-red-300">{error}</p>}
      {current && (
        <section aria-label="Sample analysis result" className="space-y-4">
          <ResultView result={current.result} hideExports />
          <details>
            <summary>Sample source and assumptions</summary>
            <p className="text-sm">{current.provenance.interpretation}</p>
            <p className="text-sm break-all">{typeof current.provenance.source === 'string'
              ? current.provenance.source : Object.keys(current.provenance.source).join(', ')}</p>
            {current.provenance.fixture_date && <p className="text-sm">Fixture date {current.provenance.fixture_date}.</p>}
            {current.provenance.bundle && <p className="text-sm break-all">
              Release {current.provenance.bundle.version}, run {current.provenance.run_id}, approved {current.provenance.approval_date}.
              Manifest SHA-256 {current.provenance.bundle.manifest_sha256}.
            </p>}
          </details>
          <button className={button} onClick={download}>Download analysis JSON</button>
        </section>
      )}
    </main>
  );
}
