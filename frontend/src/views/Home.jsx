'use client';
import Link from 'next/link';
import { useApp } from '../lib/app';
import { useHomeData } from '../lib/home';
import { fmtDate, fmtInt, timeAgo } from '../lib/format';
import { MODULES, QUICK_LINKS } from '../lib/routes';
import { BrandTag, Card, Empty, ErrorState, LoadingBlock, PageHead, Pill, SourceBadge } from '../components/ui';
import { Icon } from '../components/Icon';
import { Kpi } from '../components/metrics';
import { ListCard, ListRow, ModuleCard, brandLabel } from '../components/home';
const MODULE_NAME = Object.fromEntries(MODULES.map((m) => [m.id, m.label]));
const MODULE_ICON = Object.fromEntries(MODULES.map((m) => [m.id, m.icon]));
const SEVERITY = {
    critical: { tone: 'crit', label: 'Critical' },
    warning: { tone: 'warn', label: 'Warning' },
    info: { tone: 'info', label: 'Info' },
};
const RUN = {
    succeeded: { tone: 'ok', icon: 'checkCircle', label: 'Succeeded' },
    failed: { tone: 'crit', icon: 'xCircle', label: 'Failed' },
    running: { tone: 'info', icon: 'refresh', label: 'Running' },
    waiting: { tone: 'warn', icon: 'clock', label: 'Waiting' },
    skipped: { tone: undefined, icon: 'pause', label: 'Skipped' },
};
const runInfo = (status) => RUN[status] ?? { tone: undefined, icon: 'info', label: status };
const SYNC = {
    connected: { tone: 'ok', label: 'Connected' },
    error: { tone: 'crit', label: 'Error' },
    syncing: { tone: 'info', label: 'Syncing' },
};
const syncInfo = (status) => SYNC[status] ?? { tone: undefined, label: status };
const isIso = (v) => !!v && /^\d{4}-\d{2}-\d{2}T/.test(v);
const ago = (v, none) => (v ? (isIso(v) ? timeAgo(v) : v) : none);
/** Home / Morning Brief. Real SEO & Blog records. */
export default function Home() {
    const { brand, me } = useApp();
    const { data, loading, error, reload } = useHomeData(brand);
    const showBrand = brand === 'all';
    const brands = me.brands;
    const brandsInMetrics = ['ridhi', 'cpc'].filter((b) => data.metrics.some((m) => m.brand === b));
    const common = { brands, showBrand };
    const win = data.window;
    return (<>
      <PageHead title="Morning Brief" sub={<>Live SEO &amp; Blog Content records for {brandLabel(brand, brands)}.</>}/>

      <ErrorState error={error} onRetry={reload}/>

      {loading ? <LoadingBlock rows={6}/> : error ? null : (<>
          <Card title="Morning Brief" sub="A short summary of the latest records" >
            {data.brief.length ? (<ul className="brief-list">
                {data.brief.map((p) => (<li key={p.module + (p.brand ?? '') + p.text}>
                    <Pill tone="outline">{(MODULE_NAME[p.module] ?? p.module)}</Pill>
                    {showBrand && p.brand ? <BrandTag id={p.brand} brands={brands}/> : null}
                    <span>{p.text}</span>
                  </li>))}
              </ul>) : (<Empty icon="inbox" title="Nothing needs attention">
                No approvals are waiting for your role and there are no critical alerts in the SEO &amp; Blog records.
              </Empty>)}
          </Card>

          <h2 className="section-title">Projects</h2>
          <div className="module-grid">
            {MODULES.map((m) => (<ModuleCard key={m.id} module={m} latest={data.reports.find((r) => r.module === m.id)} {...common}/>))}
          </div>

          <h2 className="section-title">
            Key metrics
            {win ? <span className="muted xs" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 500 }}>{fmtDate(win.from)} – {fmtDate(win.to)} · {win.days} days, ending 3 days ago</span> : null}
          </h2>
          {brandsInMetrics.length ? (<div className="col gap-16">
              {brandsInMetrics.map((b) => (<div key={b} className="col gap-12">
                  {showBrand ? <div className="row"><BrandTag id={b} brands={brands}/></div> : null}
                  <div className="kpis">
                    {data.metrics.filter((m) => m.brand === b).map((m) => (<Kpi key={b + m.key} label={m.label} icon={MODULE_ICON[m.module]} value={m.value === null ? '—' : fmtInt(m.value)} na={m.value === null} foot={<><SourceBadge source={m.source}/><span>{m.withheld ? 'Withheld: synthetic' : m.note}</span></>}/>))}
                  </div>
                </div>))}
            </div>) : (<Card>
              <Empty icon="analytics" title="No figures to show">
                Key figures appear here once Search Console or Analytics data has been connected and synced.
              </Empty>
            </Card>)}

          <div className="grid cols-2 mt-24">
            <ListCard title="Pending approvals" sub={data.approvalsTotal > data.approvals.length ? `Decisions for your role · showing ${data.approvals.length} of ${data.approvalsTotal}` : 'Decisions waiting for your role'} to="/publishing" linkLabel="Open Publishing" icon="checkCircle" emptyTitle="Nothing waiting for you" emptyText="No review, publishing or topic decisions are waiting for your role. SEO & Blog decisions are on the Blogs, Topics and Publishing pages.">
              {data.approvals.length ? data.approvals.map((a) => (<ListRow key={a.id} icon="checkCircle" title={a.title} to={a.to} brand={a.brand} {...common} meta={`${a.label} · ${isIso(a.since) ? `waiting ${timeAgo(a.since).replace(' ago', '')}` : a.since}`}/>)) : null}
            </ListCard>
            <ListCard title="Alerts" sub="Unresolved issues, most serious first" to="/seo" linkLabel="Open SEO overview" icon="alert" emptyTitle="No alerts" emptyText="The SEO & Blog records show nothing needing attention.">
              {data.alerts.length ? data.alerts.map((a) => (<ListRow key={a.id} icon="alert" tone={SEVERITY[a.severity]?.tone} title={a.title} to={a.to ?? undefined} {...common} meta={`${MODULE_NAME[a.module] ?? a.module}${a.detail ? ` · ${a.detail}` : ''}`} trailing={<Pill tone={SEVERITY[a.severity]?.tone ?? 'neutral'}>{SEVERITY[a.severity]?.label ?? a.severity}</Pill>}/>)) : null}
            </ListCard>
          </div>

          <div className="grid cols-2 mt-16">
            <ListCard title="Latest reports" sub="Most recent report from each project" to={MODULES[0].to} linkLabel="Open SEO & Blog Content" icon="sheet" emptyTitle="No reports yet" emptyText={data.reportsNote ?? 'No dated reports have been produced yet.'}>
              {data.reports.length ? data.reports.map((r) => (<ListRow key={r.id} icon="sheet" title={r.title} to={MODULES.find((m) => m.id === r.module).to} meta={`${MODULE_NAME[r.module] ?? r.module} · ${r.date} · ${r.summary}`} brand={r.brand} {...common}/>)) : null}
            </ListCard>
            <ListCard title="Job and sync activity" sub="Recent pipeline runs and data syncs" to="/automation" linkLabel="Open Automation" icon="clock" emptyTitle="No runs or syncs recorded" emptyText="Nothing has run yet. Pipeline runs and data syncs appear here once they exist.">
              {data.jobs.length || data.syncs.length ? [
                ...data.jobs.map((j) => (<ListRow key={`job-${j.id}`} icon={runInfo(j.status).icon} tone={runInfo(j.status).tone} title={j.name} brand={j.brand} {...common} meta={`started ${ago(j.startedAt, 'at an unknown time')} · last success: ${ago(j.lastSuccessAt, 'none recorded')}`} trailing={<Pill tone={runInfo(j.status).tone ?? 'neutral'}>{runInfo(j.status).label}</Pill>}/>)),
                ...data.syncs.map((x) => (<ListRow key={`sync-${x.key}-${x.brand}`} icon="refresh" tone={syncInfo(x.status).tone} title={`${x.label} sync`} brand={x.brand} {...common} meta={`last success: ${ago(x.lastSuccessAt, 'none recorded')}`} trailing={<Pill tone={syncInfo(x.status).tone ?? 'neutral'}>{syncInfo(x.status).label}</Pill>}/>)),
            ] : null}
            </ListCard>
          </div>
        </>)}

      <h2 className="section-title">Quick navigation</h2>
      <nav aria-label="Quick navigation" className="quicknav">
        {QUICK_LINKS.map((e) => (<Link key={e.to} href={e.to} className="quick-link">
            <Icon name={e.icon}/>
            <span className="ellipsis">{e.label}</span>
          </Link>))}
      </nav>
    </>);
}
