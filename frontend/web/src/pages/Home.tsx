import { Link } from 'react-router-dom';
import { useApp } from '../lib/app';
import { useDemoMode, useHomeData, type Severity } from '../lib/home';
import { fmtDate, fmtInt, timeAgo } from '../lib/format';
import { MERCHANDISING, MODULES, OPERATIONS } from '../lib/routes';
import { Button, BrandTag, Card, Empty, ErrorState, LoadingBlock, PageHead, Pill, SourceBadge } from '../components/ui';
import { Icon } from '../components/Icon';
import { Kpi } from '../components/metrics';
import { ListCard, ListRow, ModuleCard, StatusChip, brandLabel } from '../components/home';
import type { BrandId } from '../lib/types';

const MODULE_NAME = Object.fromEntries(MODULES.map((m) => [m.id, m.label])) as Record<string, string>;
const MODULE_ICON = Object.fromEntries(MODULES.map((m) => [m.id, m.icon])) as Record<string, string>;
const SEVERITY: Record<Severity, { tone: 'crit' | 'warn' | 'info'; label: string }> = {
  critical: { tone: 'crit', label: 'Critical' },
  warning: { tone: 'warn', label: 'Warning' },
  info: { tone: 'info', label: 'Info' },
};
type Tone = 'ok' | 'warn' | 'crit' | 'info' | undefined;
const RUN: Record<string, { tone: Tone; icon: string; label: string }> = {
  succeeded: { tone: 'ok', icon: 'checkCircle', label: 'Succeeded' },
  failed: { tone: 'crit', icon: 'xCircle', label: 'Failed' },
  running: { tone: 'info', icon: 'refresh', label: 'Running' },
  waiting: { tone: 'warn', icon: 'clock', label: 'Waiting' },
  skipped: { tone: undefined, icon: 'pause', label: 'Skipped' },
};
const runInfo = (status: string) => RUN[status] ?? { tone: undefined as Tone, icon: 'info', label: status };
const SYNC: Record<string, { tone: Tone; label: string }> = {
  connected: { tone: 'ok', label: 'Connected' },
  error: { tone: 'crit', label: 'Error' },
  syncing: { tone: 'info', label: 'Syncing' },
};
const syncInfo = (status: string) => SYNC[status] ?? { tone: undefined as Tone, label: status };
const isIso = (v: string | null) => !!v && /^\d{4}-\d{2}-\d{2}T/.test(v);
const ago = (v: string | null, none: string) => (v ? (isIso(v) ? timeAgo(v) : v) : none);

/** Home / Morning Brief. Real SEO & Blog records by default; synthetic sample data only when demo mode is switched on. */
export default function Home() {
  const { brand, me } = useApp();
  const [demo, setDemo] = useDemoMode();
  const { data, loading, error, reload } = useHomeData(brand, demo);
  const showBrand = brand === 'all';
  const brands = me.brands;
  const brandsInMetrics = (['ridhi', 'cpc'] as BrandId[]).filter((b) => data.metrics.some((m) => m.brand === b));
  const common = { brands, showBrand };
  const win = data.window;

  return (
    <>
      <PageHead
        title="Morning Brief"
        sub={demo
          ? <>A sample layout for {brandLabel(brand, brands)}. Every figure on this page is synthetic.</>
          : <>Live SEO &amp; Blog Content records for {brandLabel(brand, brands)}. The other projects are not built yet, so they add no data here.</>}
        actions={
          <Button size="sm" icon="eye" aria-pressed={demo} onClick={() => setDemo(!demo)}>
            {demo ? 'Hide demonstration data' : 'Show demonstration data'}
          </Button>
        }
      />

      {demo ? (
        <div className="callout demo mb-16" role="note">
          <Icon name="info" />
          <div><b>Demonstration data.</b> Everything marked “Demo” or “Sample” is made up to show the layout. It is not business data, and no job, sync or approval has run. Real records are hidden while this is on.</div>
        </div>
      ) : null}
      {!demo && data.demoFixturesLoaded ? (
        <div className="callout warn mb-16" role="note">
          <Icon name="alert" />
          <div><b>Demo analytics fixtures are loaded in the SEO data.</b> Their synthetic figures are withheld from this page; metrics from a demo source show as unavailable. Clear them under Data &amp; reports once real data is connected.</div>
        </div>
      ) : null}
      <ErrorState error={error} onRetry={reload} />

      {loading ? <LoadingBlock rows={6} /> : error ? null : (
        <>
          <Card title="Morning Brief" sub="A short summary of the latest records" actions={demo && data.brief.length ? <SourceBadge kind="demo" compact /> : null}>
            {data.brief.length ? (
              <ul className="brief-list">
                {data.brief.map((p) => (
                  <li key={p.module + (p.brand ?? '') + p.text}>
                    <Pill tone="outline">{MODULE_NAME[p.module]}</Pill>
                    {showBrand && p.brand ? <BrandTag id={p.brand} brands={brands} /> : null}
                    <span>{p.text}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty icon="inbox" title="Nothing needs attention">
                No approvals are waiting for your role and there are no critical alerts in the SEO &amp; Blog records. Dated reports are not produced yet, and the other projects are not built.
              </Empty>
            )}
          </Card>

          <h2 className="section-title">Projects</h2>
          <div className="module-grid">
            {MODULES.map((m) => (
              <ModuleCard key={m.id} module={m} latest={data.reports.find((r) => r.module === m.id)} {...common} />
            ))}
          </div>
          <p className="muted small mt-8">
            <Icon name="info" size="sm" /> {MERCHANDISING.label} is future scope and not an operational project. <Link to={MERCHANDISING.to}>Read more</Link>
          </p>

          <h2 className="section-title">
            Key metrics
            {win && !demo ? <span className="muted xs" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 500 }}>{fmtDate(win.from)} – {fmtDate(win.to)} · {win.days} days, ending 3 days ago</span> : null}
          </h2>
          {brandsInMetrics.length ? (
            <div className="col gap-16">
              {brandsInMetrics.map((b) => (
                <div key={b} className="col gap-12">
                  {showBrand ? <div className="row"><BrandTag id={b} brands={brands} /></div> : null}
                  <div className="kpis">
                    {data.metrics.filter((m) => m.brand === b).map((m) => (
                      <Kpi
                        key={b + m.key} label={m.label} icon={MODULE_ICON[m.module]}
                        value={m.value === null ? '—' : fmtInt(m.value)} na={m.value === null}
                        foot={<><SourceBadge source={m.source} compact={demo} /><span>{m.withheld ? 'Withheld: synthetic' : m.note}</span></>}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Card>
              <Empty icon="analytics" title="No figures to show">
                Key figures appear here when a project reports real data with a stated source. Turn on demonstration data to preview the layout.
              </Empty>
            </Card>
          )}

          <div className="grid cols-2 mt-24">
            <ListCard
              title="Pending approvals" sub={data.approvalsTotal > data.approvals.length ? `Decisions for your role · showing ${data.approvals.length} of ${data.approvalsTotal}` : 'Decisions waiting for your role'}
              demo={demo} to="/approvals" linkLabel="Open approvals" icon="checkCircle"
              emptyTitle="Nothing waiting for you" emptyText="No review, publishing or topic decisions are waiting for your role. The shared approvals area is not built yet; SEO & Blog decisions are on its Blogs, Topics and Publishing pages."
            >
              {data.approvals.length ? data.approvals.map((a) => (
                <ListRow
                  key={a.id} icon="checkCircle" title={a.title} to={a.to} brand={a.brand} {...common}
                  meta={`${a.label} · ${isIso(a.since) ? `waiting ${timeAgo(a.since).replace(' ago', '')}` : a.since}`}
                />
              )) : null}
            </ListCard>
            <ListCard
              title="Alerts" sub="Unresolved issues, most serious first" demo={demo} to="/alerts" linkLabel="Open alerts" icon="alert"
              emptyTitle="No alerts" emptyText="The SEO & Blog records show nothing needing attention. Shared alerting is not built yet."
            >
              {data.alerts.length ? data.alerts.map((a) => (
                <ListRow
                  key={a.id} icon="alert" tone={SEVERITY[a.severity]?.tone} title={a.title} to={a.to ?? undefined} {...common}
                  meta={`${MODULE_NAME[a.module]}${a.detail ? ` · ${a.detail}` : ''}`}
                  trailing={<Pill tone={SEVERITY[a.severity]?.tone ?? 'neutral'}>{SEVERITY[a.severity]?.label ?? a.severity}</Pill>}
                />
              )) : null}
            </ListCard>
          </div>

          <div className="grid cols-2 mt-16">
            <ListCard
              title="Latest reports" sub="Most recent report from each project" demo={demo} to={MODULES[0].to} linkLabel="Open SEO & Blog Content" icon="sheet"
              emptyTitle="No reports yet" emptyText={data.reportsNote ?? 'No project produces dated reports yet.'}
            >
              {data.reports.length ? data.reports.map((r) => (
                <ListRow
                  key={r.id} icon="sheet" title={r.title} to={MODULES.find((m) => m.id === r.module)!.to}
                  meta={`${MODULE_NAME[r.module]} · ${r.date} · ${r.summary}`} brand={r.brand} {...common}
                />
              )) : null}
            </ListCard>
            <ListCard
              title="Job and sync activity" sub="Recent pipeline runs and data syncs" demo={demo} to="/runs" linkLabel="Open runs and schedules" icon="clock"
              emptyTitle="No runs or syncs recorded" emptyText="Nothing has run yet. SEO & Blog pipeline runs and data syncs appear here once they exist; the other projects are not built, so they have no jobs."
            >
              {data.jobs.length || data.syncs.length ? [
                ...data.jobs.map((j) => (
                  <ListRow
                    key={`job-${j.id}`} icon={runInfo(j.status).icon} tone={runInfo(j.status).tone} title={j.name} brand={j.brand} {...common}
                    meta={j.trigger === 'sample' ? 'Sample' : `started ${ago(j.startedAt, 'at an unknown time')} · last success: ${ago(j.lastSuccessAt, 'none recorded')}`}
                    trailing={<Pill tone={runInfo(j.status).tone ?? 'neutral'}>{runInfo(j.status).label}</Pill>}
                  />
                )),
                ...data.syncs.map((x) => (
                  <ListRow
                    key={`sync-${x.key}-${x.brand}`} icon="refresh" tone={syncInfo(x.status).tone} title={`${x.label} sync`} brand={x.brand} {...common}
                    meta={demo ? 'Sample' : `last success: ${ago(x.lastSuccessAt, 'none recorded')}`}
                    trailing={<Pill tone={syncInfo(x.status).tone ?? 'neutral'}>{syncInfo(x.status).label}</Pill>}
                  />
                )),
              ] : null}
            </ListCard>
          </div>
        </>
      )}

      <h2 className="section-title">Quick navigation</h2>
      <nav aria-label="Quick navigation" className="quicknav">
        {[...MODULES, ...OPERATIONS, MERCHANDISING].map((e) => (
          <Link key={e.to} to={e.to} className="quick-link">
            <Icon name={e.icon} />
            <span className="ellipsis">{e.label}</span>
            {e.status !== 'available' ? <StatusChip status={e.status} /> : null}
          </Link>
        ))}
      </nav>
    </>
  );
}
