import { useCallback, useEffect, useRef, useState } from 'react';

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, message: string, code = 'error', details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function request<T>(method: string, path: string, body?: unknown, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'X-Requested-With': 'blog-ops', Accept: 'application/json' };
  let payload: BodyInit | undefined;
  if (body instanceof ArrayBuffer || body instanceof Blob) {
    headers['Content-Type'] = 'application/octet-stream';
    payload = body as BodyInit;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch('/api' + path, { method, headers: { ...headers, ...(init.headers as Record<string, string>) }, body: payload, credentials: 'same-origin', signal: init.signal });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'Cannot reach the server. Check your connection and that the API is running.', 'network');
  }
  if (res.status === 401 && path !== '/auth/login' && onUnauthorized) onUnauthorized();
  const text = await res.text();
  const json = text ? (() => { try { return JSON.parse(text); } catch { return null; } })() : null;
  if (!res.ok) throw new ApiError(res.status, json?.error || `Request failed (${res.status})`, json?.code, json?.details);
  return json as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, { signal }),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) => request<T>('POST', path, body ?? {}, { headers }),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
};

export function qs(params: Record<string, string | number | undefined | null | false>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '' && v !== false) p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : '';
}

/** Fetch on mount and whenever `path` changes. A null path skips the request. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const [tick, setTick] = useState(0);
  const first = useRef(true);
  useEffect(() => {
    if (!path) { setLoading(false); return; }
    const ctl = new AbortController();
    setLoading(true);
    setError(null);
    api.get<T>(path, ctl.signal)
      .then((d) => { setData(d); first.current = false; })
      .catch((e) => { if (e.name !== 'AbortError') setError(e instanceof ApiError ? e : new ApiError(0, String(e))); })
      .finally(() => { if (!ctl.signal.aborted) setLoading(false); });
    return () => ctl.abort();
  }, [path, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, setData, initialLoading: loading && first.current };
}

export async function download(path: string) {
  const res = await fetch('/api' + path, { credentials: 'same-origin', headers: { 'X-Requested-With': 'blog-ops' } });
  if (!res.ok) {
    const j = await res.json().catch(() => null);
    throw new ApiError(res.status, j?.error || 'Download failed');
  }
  const cd = res.headers.get('Content-Disposition') || '';
  const name = (cd.match(/filename="([^"]+)"/) || [])[1] || 'download.xlsx';
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
