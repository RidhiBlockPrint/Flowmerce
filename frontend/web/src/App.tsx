import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api, ApiError, setUnauthorizedHandler } from './lib/api';
import { AppProvider } from './lib/app';
import type { Me } from './lib/types';
import { Shell } from './components/Shell';
import { LoadingBlock, ErrorState, Empty } from './components/ui';
import { LogoMark } from './components/Icon';
import { Login } from './pages/Login';

const Overview = lazy(() => import('./pages/Overview'));
const Workspace = lazy(() => import('./pages/Workspace'));
const Blogs = lazy(() => import('./pages/Blogs'));
const ArticleEditor = lazy(() => import('./pages/ArticleEditor'));
const Topics = lazy(() => import('./pages/Topics'));
const Publishing = lazy(() => import('./pages/Publishing'));
const Analytics = lazy(() => import('./pages/Analytics'));
const Automation = lazy(() => import('./pages/Automation'));
const DataReports = lazy(() => import('./pages/DataReports'));
const Integrations = lazy(() => import('./pages/Integrations'));
const Audit = lazy(() => import('./pages/Audit'));
const Users = lazy(() => import('./pages/Users'));

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<'loading' | 'in' | 'out' | 'error'>('loading');
  const [err, setErr] = useState<Error | null>(null);
  const nav = useNavigate();
  const loc = useLocation();

  const load = useCallback(async () => {
    try {
      const m = await api.get<Me>('/auth/me');
      setMe(m);
      setState('in');
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setState('out');
      else { setErr(e as Error); setState('error'); }
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => setUnauthorizedHandler(() => { setMe(null); setState('out'); }), []);

  if (state === 'loading') return <Splash />;
  if (state === 'error') return <div style={{ padding: 24 }}><ErrorState error={err} onRetry={load} /></div>;
  if (state === 'out' || !me) {
    if (loc.pathname !== '/login') return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
    return <Login onSignedIn={async () => { await load(); const next = new URLSearchParams(loc.search).get('next'); nav(next && next.startsWith('/') ? next : '/', { replace: true }); }} />;
  }
  if (loc.pathname === '/login') return <Navigate to="/" replace />;

  return (
    <AppProvider me={me} refreshMe={load}>
      <Shell>
        <Suspense fallback={<LoadingBlock rows={6} />}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/workspace/:brand" element={<Workspace />} />
            <Route path="/blogs" element={<Blogs />} />
            <Route path="/blogs/:id" element={<ArticleEditor />} />
            <Route path="/topics" element={<Topics />} />
            <Route path="/publishing" element={<Publishing />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/automation" element={<Automation />} />
            <Route path="/data" element={<DataReports />} />
            <Route path="/integrations" element={<Integrations />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/users" element={<Users />} />
            <Route path="*" element={<Empty icon="search" title="Page not found">That address does not match any page in the dashboard.</Empty>} />
          </Routes>
        </Suspense>
      </Shell>
    </AppProvider>
  );
}

function Splash() {
  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }} aria-busy="true">
      <div className="col" style={{ alignItems: 'center', gap: 12 }}>
        <LogoMark className="logo-mark" />
        <span className="muted small">Loading Blog Ops…</span>
      </div>
    </div>
  );
}
