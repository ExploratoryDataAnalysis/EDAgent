import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/** Sign-in / registration screen. Shown to anyone without a valid session. */
export const LoginPage: React.FC = () => {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === 'login') await login(email.trim(), password);
      else await register(email.trim(), password, fullName.trim() || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  };

  const input =
    'w-full px-3 py-2.5 rounded-xl text-sm bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500';

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
      <div className="w-full max-w-md rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl p-8 space-y-6">
        <div>
          <h1 className="text-xl font-bold">Dataset analyser</h1>
          <p className="text-sm">Sign in to upload, analyse and export your own data.</p>
        </div>

        <div className="flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1 text-xs font-semibold">
          {(['login', 'register'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(null); }}
              className={`flex-1 py-2 rounded-lg transition-colors ${
                mode === m ? 'bg-white dark:bg-slate-700 text-indigo-700 dark:text-indigo-300 shadow-sm' : 'text-slate-500'
              }`}
            >
              {m === 'login' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === 'register' && (
            <div>
              <label htmlFor="full-name" className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1">Name (optional)</label>
              <input id="full-name" className={input} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
            </div>
          )}
          <div>
            <label htmlFor="email" className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1">Email</label>
            <input id="email" className={input} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </div>
          <div>
            <label htmlFor="password" className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1">Password</label>
            <input
              className={input}
              id="password"
              type="password"
              required
              minLength={mode === 'register' ? 8 : 1}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
            {mode === 'register' && <p className="mt-1 text-[11px] text-slate-400">At least 8 characters.</p>}
          </div>

          {error && (
            <div role="alert" className="text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full inline-flex items-center justify-center space-x-2 py-2.5 rounded-xl text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 shadow-lg shadow-indigo-600/25 transition-all"
          >
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{mode === 'login' ? 'Sign in' : 'Create account'}</span>
          </button>
        </form>

        <p className="text-[11px] leading-relaxed text-slate-400">
          Your datasets stay private to your account. If an AI provider is configured, dataset structure and a few
          sanitised sample values are sent to it to plan analyses and explain results; all numbers are computed locally.
        </p>
        <nav className="flex flex-wrap gap-4 text-sm text-indigo-700 dark:text-indigo-300">
          <Link to="/analyser" className="underline">Dataset analyser</Link>
          <Link to="/" className="underline">Back to the investigation</Link>
        </nav>
      </div>
    </main>
  );
};

export default LoginPage;
