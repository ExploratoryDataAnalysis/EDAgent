import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Modal } from '../ui/Modal';

export function GuestSessionStatus() {
  const { user, clearGuest } = useAuth();
  const navigate = useNavigate();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const policy = user?.guest;
  if (!policy) return null;
  const deadline = new Date(policy.expires_at * 1000);

  const clear = async () => {
    setBusy(true);
    setError('');
    try {
      await clearGuest();
      navigate('/analyser', { replace: true });
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <section aria-label="Private guest session" className="border-b border-indigo-200 bg-indigo-50 p-3 text-sm dark:border-indigo-900 dark:bg-indigo-950">
      <p className="font-semibold">Private guest session</p>
      <p>Expires <time dateTime={deadline.toISOString()}>{deadline.toLocaleString()}</time>.</p>
      <p>Up to {policy.max_datasets} CSV or TSV files, {(policy.max_upload_bytes / 1024 / 1024).toLocaleString()} MiB each, 10,000 rows and 16 columns per file. {policy.max_actions} processing attempts per session.</p>
      <div className="mt-2 flex flex-wrap gap-3">
        <button className="font-semibold underline" onClick={() => setConfirm(true)}>Clear guest session</button>
        <Link className="underline" to="/">Back to the investigation</Link>
      </div>
      <Modal isOpen={confirm} onClose={() => { if (!busy) setConfirm(false); }} title="Clear private guest session?" maxWidth="sm">
        <p className="text-sm">This removes your uploads, analysis history and generated reports from this workspace.</p>
        {error && <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</p>}
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <button disabled={busy} onClick={() => setConfirm(false)}>Cancel</button>
          <button disabled={busy} onClick={clear} className="rounded-lg bg-red-700 px-3 py-2 text-white">
            {busy ? 'Clearing…' : 'Clear session'}
          </button>
        </div>
      </Modal>
    </section>
  );
}
