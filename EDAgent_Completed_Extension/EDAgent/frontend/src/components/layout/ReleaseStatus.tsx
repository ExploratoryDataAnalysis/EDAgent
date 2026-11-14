import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { RoadSafetyError } from '../../services/roadSafetyService';

type RequestState<T> = { kind: 'loading' | 'unavailable' | 'error' } | { kind: 'ready'; data: T };

export function useReleaseRequest<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<RequestState<T>>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const request = new AbortController();
    load(request.signal).then(data => {
      if (!request.signal.aborted) setState({ kind: 'ready', data });
    }).catch((error: RoadSafetyError) => {
      // A superseded request cannot restore figures after retry or navigation.
      if (request.signal.aborted) return;
      setState({ kind: error.status === 503 && error.code === 'OVERVIEW_UNAVAILABLE' ? 'unavailable' : 'error' });
      request.abort();
    });
    return () => request.abort();
  }, [load, attempt]);

  function retry() {
    if (state.kind === 'loading') return;
    setState({ kind: 'loading' });
    setAttempt(attempt => attempt + 1);
  }
  return { state, retry };
}

const messages = {
  loading: ['Checking the release', 'Checking whether the reviewed findings are available.'],
  unavailable: ['Reviewed findings unavailable', 'Findings and downloads open after the release is approved and its files pass verification. Methods explains what the record covers.'],
  error: ['Could not check the findings', 'The release check did not complete. Try again or read Methods while the connection recovers.'],
  ready: ['Reviewed findings available', 'The release passed verification. Open the record to see the figures and their sources.'],
};

export function ReleaseStatus({ kind, retry, recordLink = false }: {
  kind: keyof typeof messages; retry: () => void; recordLink?: boolean;
}) {
  const [title, message] = messages[kind];
  return <section className="public-status" data-state={kind} aria-label="Evidence status">
    <div role="status" aria-atomic="true">
      <h2>{title}</h2>
      <p>{message}</p>
    </div>
    <div className="public-actions">
      <Link to="/methods">Read the Methods</Link>
      {recordLink && <Link to="/road-safety">Open the crash record</Link>}
      {kind !== 'ready' && <button type="button" aria-disabled={kind === 'loading'} onClick={retry}>
        {kind === 'loading' ? 'Checking…' : 'Retry release check'}
      </button>}
    </div>
  </section>;
}
