/**
 * Data behind the Home / Morning Brief page.
 *
 * There are two sources and they are never combined:
 *  - real records from GET /api/home (the SEO & Blog project is the only built project, so it is the only
 *    one that contributes), shown when demo mode is off, which is the default;
 *  - synthetic demonstration data, shown only after the user switches demo mode on, and then it is the
 *    only data on the page.
 * Unbuilt projects have no data in either source: they appear on Home as Planned, with nothing invented.
 */
import { useCallback, useMemo, useState } from 'react';
import { qs, useApi, type ApiError } from './api';
import type { BrandFilter, BrandId, SourceInfo } from './types';
import type { ModuleId } from './routes';

export type Severity = 'critical' | 'warning' | 'info';
/** The SEO pipeline can also report `waiting` and `skipped`; unknown values fall back to a neutral display. */
export type RunStatus = 'succeeded' | 'failed' | 'running' | 'waiting' | 'skipped';

export interface BriefPoint { module: ModuleId; brand: BrandId | null; text: string }
/** `value` is null when the source has no data, or when only synthetic fixtures exist (`withheld`). */
export interface Metric { brand: BrandId; module: ModuleId; key: string; label: string; value: number | null; withheld: boolean; note: string; source: SourceInfo }
export interface Approval { id: string; brand: BrandId; module: ModuleId; kind: string; label: string; title: string; action: string; to: string; since: string }
export interface AlertRow { id: string; module: ModuleId; severity: Severity; title: string; detail: string; to: string | null }
export interface ReportRow { id: string; brand: BrandId; module: ModuleId; date: string; title: string; summary: string }
export interface JobRow { id: number | string; brand: BrandId; module: ModuleId; name: string; status: RunStatus | string; trigger: string; startedAt: string | null; finishedAt: string | null; lastSuccessAt: string | null }
export interface SyncRow { key: string; label: string; brand: BrandId; status: string; lastSuccessAt: string | null; lastAttemptAt: string | null }

export interface HomeData {
  /** 'api' = real records from the backend; 'demo' = made-up illustration; 'none' = nothing to show. */
  kind: 'api' | 'demo' | 'none';
  window?: { from: string; to: string; days: number };
  /** True when synthetic analytics fixtures sit in the SEO data; their figures are withheld from Home. */
  demoFixturesLoaded?: boolean;
  brief: BriefPoint[];
  metrics: Metric[];
  approvals: Approval[];
  approvalsTotal: number;
  alerts: AlertRow[];
  reports: ReportRow[];
  reportsNote?: string;
  jobs: JobRow[];
  syncs: SyncRow[];
}

/* ---------- demonstration data (synthetic; only shown while demo mode is on) ---------- */

const DEMO_SOURCE: SourceInfo = { kind: 'demo', label: 'Demo data — not real', syncedAt: null, coverage: { from: null, to: null } };
const demoMetric = (brand: BrandId, key: string, label: string, value: number, note: string): Metric =>
  ({ brand, module: 'seo', key, label, value, withheld: false, note, source: DEMO_SOURCE });

/** Only the SEO & Blog project is shown: it is the only built project. Every row says "Sample". */
const DEMO: HomeData = {
  kind: 'demo',
  brief: [
    { module: 'seo', brand: 'ridhi', text: 'Sample: one article is waiting for review.' },
    { module: 'seo', brand: 'cpc', text: 'Sample: one topic is waiting for a decision.' },
  ],
  metrics: [
    demoMetric('ridhi', 'gsc_clicks', 'Search clicks', 12480, 'Sample figure'),
    demoMetric('ridhi', 'gsc_impressions', 'Search impressions', 301200, 'Sample figure'),
    demoMetric('ridhi', 'ga4_sessions', 'Sessions', 9210, 'Sample figure'),
    demoMetric('cpc', 'gsc_clicks', 'Search clicks', 7915, 'Sample figure'),
    demoMetric('cpc', 'gsc_impressions', 'Search impressions', 188400, 'Sample figure'),
    demoMetric('cpc', 'ga4_sessions', 'Sessions', 5480, 'Sample figure'),
  ],
  approvals: [
    { id: 'd-a1', brand: 'ridhi', module: 'seo', kind: 'review', label: 'Content approval', title: 'Sample article awaiting review', action: 'Review content', to: '/blogs', since: 'Sample' },
    { id: 'd-a2', brand: 'cpc', module: 'seo', kind: 'topic', label: 'Topic approval', title: 'Sample topic awaiting a decision', action: 'Approve or reject topic', to: '/topics', since: 'Sample' },
  ],
  approvalsTotal: 2,
  alerts: [
    { id: 'd-l1', module: 'seo', severity: 'warning', title: 'Sample alert: live publishing is switched off', detail: 'Illustrative only.', to: '/publishing' },
  ],
  reports: [
    { id: 'd-r1', brand: 'ridhi', module: 'seo', date: 'Sample date', title: 'Sample SEO report', summary: 'Illustrates where a dated report would appear. No such reports exist yet.' },
  ],
  reportsNote: 'Sample data only.',
  jobs: [
    { id: 'd-j1', brand: 'ridhi', module: 'seo', name: 'Performance tracking', status: 'succeeded', trigger: 'sample', startedAt: null, finishedAt: null, lastSuccessAt: null },
    { id: 'd-j2', brand: 'cpc', module: 'seo', name: 'Content approval', status: 'waiting', trigger: 'sample', startedAt: null, finishedAt: null, lastSuccessAt: null },
  ],
  syncs: [
    { key: 'gsc', label: 'Search Console', brand: 'ridhi', status: 'connected', lastSuccessAt: null, lastAttemptAt: null },
  ],
};

const EMPTY: HomeData = { kind: 'none', brief: [], metrics: [], approvals: [], approvalsTotal: 0, alerts: [], reports: [], jobs: [], syncs: [] };

/* ---------- demo mode switch (per browser; off unless the user turned it on) ---------- */

const DEMO_KEY = 'fm.demo';

function readDemo(): boolean {
  try { return localStorage.getItem(DEMO_KEY) === 'on'; } catch { return false; }
}

export function useDemoMode(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(readDemo);
  const set = useCallback((v: boolean) => {
    setOn(v);
    try { localStorage.setItem(DEMO_KEY, v ? 'on' : 'off'); } catch { /* private mode: keep it in memory only */ }
  }, []);
  return [on, set];
}

export interface HomeState { data: HomeData; loading: boolean; error: ApiError | null; reload: () => void }

/**
 * Home data for the selected brand. Demo mode on: the synthetic sample only, and no request is made. Demo
 * mode off: the real GET /api/home response only. The two are never merged.
 */
export function useHomeData(brand: BrandFilter, demo: boolean): HomeState {
  const live = useApi<Omit<HomeData, 'kind'>>(demo ? null : `/home${qs({ brand: brand === 'all' ? undefined : brand })}`);
  const sample = useMemo<HomeData>(() => {
    const keep = <T extends { brand: BrandId | null }>(rows: T[]) => (brand === 'all' ? rows : rows.filter((r) => r.brand === brand));
    const approvals = keep(DEMO.approvals);
    return { ...DEMO, brief: keep(DEMO.brief), metrics: keep(DEMO.metrics), approvals, approvalsTotal: approvals.length, reports: keep(DEMO.reports), jobs: keep(DEMO.jobs), syncs: keep(DEMO.syncs) };
  }, [brand]);
  const real = useMemo<HomeData>(() => (live.data ? { ...live.data, kind: 'api' } : EMPTY), [live.data]);
  if (demo) return { data: sample, loading: false, error: null, reload: () => undefined };
  return { data: real, loading: live.loading || (!live.data && !live.error), error: live.error, reload: live.reload };
}
