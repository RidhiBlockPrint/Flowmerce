'use client';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';
import { AppProvider } from '../lib/app';
import { Shell } from './Shell';
import { ToastProvider } from './overlays';
import { LoadingBlock, ErrorState } from './ui';
import { LogoMark } from './Icon';

/**
 * Local operator mode: there is no sign-in. The backend answers /api/auth/me with the local administrator
 * (or refuses with 403 when the page is opened from another computer), and the dashboard opens directly.
 */
export function Providers({ children }) {
  const [me, setMe] = useState(null);
  const [state, setState] = useState('loading');
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    try {
      setMe(await api.get('/auth/me'));
      setState('ready');
    } catch (e) {
      setErr(e);
      setState('error');
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <ToastProvider>
      {state === 'loading' ? <Splash />
        : state === 'error' || !me ? <div style={{ padding: 24 }}><ErrorState error={err} onRetry={load} /></div>
        : (
          <AppProvider me={me} refreshMe={load}>
            <Shell>
              <Suspense fallback={<LoadingBlock rows={6} />}>{children}</Suspense>
            </Shell>
          </AppProvider>
        )}
    </ToastProvider>
  );
}

function Splash() {
  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }} aria-busy="true">
      <div className="col" style={{ alignItems: 'center', gap: 12 }}>
        <LogoMark className="logo-mark" />
        <span className="muted small">Loading Flowmerce…</span>
      </div>
    </div>
  );
}
