'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
export class ApiError extends Error {
    status;
    code;
    details;
    constructor(status, message, code = 'error', details) {
        super(message);
        this.status = status;
        this.code = code;
        this.details = details;
    }
}
async function request(method, path, body, init = {}) {
    const headers = { 'X-Requested-With': 'blog-ops', Accept: 'application/json' };
    let payload;
    if (body instanceof ArrayBuffer || body instanceof Blob) {
        headers['Content-Type'] = 'application/octet-stream';
        payload = body;
    }
    else if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        payload = JSON.stringify(body);
    }
    let res;
    try {
        res = await fetch('/api' + path, { method, headers: { ...headers, ...init.headers }, body: payload, credentials: 'same-origin', signal: init.signal });
    }
    catch (e) {
        if (e.name === 'AbortError')
            throw e;
        throw new ApiError(0, 'Cannot reach the server. Check your connection and that the API is running.', 'network');
    }
    const text = await res.text();
    const json = text ? (() => { try {
        return JSON.parse(text);
    }
    catch {
        return null;
    } })() : null;
    if (!res.ok)
        throw new ApiError(res.status, json?.error || `Request failed (${res.status})`, json?.code, json?.details);
    return json;
}
export const api = {
    get: (path, signal) => request('GET', path, undefined, { signal }),
    post: (path, body, headers) => request('POST', path, body ?? {}, { headers }),
    patch: (path, body) => request('PATCH', path, body),
};
export function qs(params) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params))
        if (v !== undefined && v !== null && v !== '' && v !== false)
            p.set(k, String(v));
    const s = p.toString();
    return s ? `?${s}` : '';
}
/** Fetch on mount and whenever `path` changes. A null path skips the request. */
export function useApi(path) {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(!!path);
    const [tick, setTick] = useState(0);
    const first = useRef(true);
    useEffect(() => {
        if (!path) {
            setLoading(false);
            return;
        }
        const ctl = new AbortController();
        setLoading(true);
        setError(null);
        api.get(path, ctl.signal)
            .then((d) => { setData(d); first.current = false; })
            .catch((e) => { if (e.name !== 'AbortError')
            setError(e instanceof ApiError ? e : new ApiError(0, String(e))); })
            .finally(() => { if (!ctl.signal.aborted)
            setLoading(false); });
        return () => ctl.abort();
    }, [path, tick]);
    const reload = useCallback(() => setTick((t) => t + 1), []);
    return { data, error, loading, reload, setData, initialLoading: loading && first.current };
}
export async function download(path) {
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
