/**
 * Central HTTP client. Adds the bearer token to every request, turns backend errors into
 * readable messages, and signs the user out when the token is rejected.
 */

import axios, { AxiosError, AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const TOKEN_KEY = 'edagent_token';

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

type UnauthorizedHandler = () => void;
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
    if (error.response?.status === 401 && !url.includes('/auth/login') && !url.includes('/auth/register')) {
      tokenStore.clear();
      onUnauthorized?.();
    }
    const body = error.response?.data as { detail?: { code?: string }; errors?: string[] } | undefined;
    return Promise.reject(Object.assign(new Error(errorMessage(error)), {
      status: error.response?.status,
      code: body?.detail?.code,
      problems: Array.isArray(body?.errors) ? body.errors : undefined,
    }));
  }
);

/** Downloads a protected file (the browser cannot attach the bearer header to a plain link). */
export async function downloadFile(path: string, fallbackName: string, params?: Record<string, unknown>): Promise<void> {
  const res = await apiClient.get(path, { params, responseType: 'blob' });
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
