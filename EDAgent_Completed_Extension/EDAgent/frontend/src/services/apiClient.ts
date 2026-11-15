/**
 * Central HTTP client. Adds the bearer token to every request, turns backend errors into
 * readable messages, and signs the user out when the token is rejected.
 */

import axios, { AxiosError, AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const TOKEN_KEY = 'edagent_token';
const GUEST_TOKEN_KEY = 'edagent_guest_token';

export const tokenStore = {
  get: (): string | null => sessionStorage.getItem(GUEST_TOKEN_KEY) ?? localStorage.getItem(TOKEN_KEY),
  isGuest: () => sessionStorage.getItem(GUEST_TOKEN_KEY) !== null,
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  setGuest: (token: string) => sessionStorage.setItem(GUEST_TOKEN_KEY, token),
  clear: () => {
    if (sessionStorage.getItem(GUEST_TOKEN_KEY)) sessionStorage.removeItem(GUEST_TOKEN_KEY);
    else localStorage.removeItem(TOKEN_KEY);
  },
};

type UnauthorizedHandler = () => void;
export type ValidationProblem = { loc: (string | number)[]; msg: string; type: string };
let onUnauthorized: UnauthorizedHandler | null = null;
export const setUnauthorizedHandler = (fn: UnauthorizedHandler | null) => {
  onUnauthorized = fn;
};

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 120000, // analyses on large files can take a while; the server enforces its own limits
});

apiClient.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Pulls the most useful message out of any backend error shape. */
export function errorMessage(error: unknown): string {
  const e = error as AxiosError<any>;
  const data = e?.response?.data;
  if (data) {
    if (Array.isArray(data.errors) && data.errors.length > 1) return data.errors.join(' ');
    if (typeof data.message === 'string' && data.message) return data.message;
    if (typeof data.detail === 'string') return data.detail;
  }
  if (e?.code === 'ECONNABORTED') return 'The request took too long. Try again or narrow the analysis.';
  if (e?.message === 'Network Error') return 'Cannot reach the EDAgent server. Is the backend running?';
  return (error as Error)?.message || 'An unexpected error occurred.';
}

apiClient.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    const url = error.config?.url || '';
    const token = tokenStore.get();
    // A request from a previous session can finish after a different user signs in.
    if (error.response?.status === 401 && token && error.config?.headers.Authorization === `Bearer ${token}`
      && !url.includes('/auth/login') && !url.includes('/auth/register')) {
      if (onUnauthorized) onUnauthorized();
      else tokenStore.clear();
    }
    const body = error.response?.data as {
      detail?: { code?: string } | ValidationProblem[];
      errors?: string[];
    } | undefined;
    const detail = body?.detail;
    return Promise.reject(Object.assign(new Error(errorMessage(error)), {
      status: error.response?.status,
      code: Array.isArray(detail) ? undefined : detail?.code,
      validation: Array.isArray(detail) ? detail : undefined,
      problems: Array.isArray(body?.errors) ? body.errors : undefined,
    }));
  }
);

/** Downloads a protected file (the browser cannot attach the bearer header to a plain link). */
export async function downloadFile(path: string, fallbackName: string, params?: Record<string, unknown>): Promise<void> {
  const token = tokenStore.get();
  const res = await apiClient.get(path, { params, responseType: 'blob' });
  if (tokenStore.get() !== token) return;
  const disposition = (res.headers['content-disposition'] as string | undefined) || '';
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const name = match ? match[1] : fallbackName;
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
