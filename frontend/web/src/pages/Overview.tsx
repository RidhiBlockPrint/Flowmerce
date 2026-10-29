import { Link, useNavigate } from 'react-router-dom';
import { useApi, qs } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtDate, fmtCompact, fmtInt, timeAgo } from '../lib/format';
import { Card, PageHead, ErrorState, LoadingBlock, SourceBadge, Pill, Skeleton } from '../components/ui';
import { Icon } from '../components/Icon';
import { LineChart } from '../components/charts';
import { GscKpis, Ga4Kpis, seriesFrom } from '../components/metrics';
import type { BrandId } from '../lib/types';

const STATE_LABEL: Record<string, string> = { ok: 'OK', needs_action: 'Needs action', failed: 'Failed', running: 'Running', paused: 'Paused', pending_setup: 'Pending setup', idle: 'Not run yet' };

export default function Overview() {
  const { range, me, brandOf, setBrand } = useApp();
  const brand = useBrandParam();
  const { data, error, loading, reload } = useApi<any>(`/overview${qs({ brand, from: range.from, to: range.to })}`);
  const nav = useNavigate();
  const short = (b: BrandId) => brandOf(b).short;

  return (
    <>
      <PageHead
        title="Overview"
        sub={<>Blog pipeline and search performance for {brand ? brandOf(brand).name : 'Ridhi Block Print and Cotton Print Club'} · {fmtDate(range.from)} – {fmtDate(range.to)}</>}
      />
      <ErrorState error={error} onRetry={reload} />
      {loading && !data ? <OverviewSkeleton /> : null}
      {data ? (
        <div className="col" style={{ gap: 16 }}>
          <div className={`grid ${data.brands.length > 1 ? 'cols-2' : ''}`}>
            {data.brands.map((b: any) => (
              <section key={b.brand} className={`card brand-card ${b.brand}`}>
                <div className="card-head">
                  <div>
                    <h2 className="brand-name">{brandOf(b.brand).name}</h2>
                    <a className="small muted" href={brandOf(b.brand).blogUrl} target="_blank" rel="noopener">{brandOf(b.brand).blogUrl.replace('https://', '')} <Icon name="external" size="sm" /></a>
                  </div>
                  <div className="row" style={{ marginLeft: 'auto' }}>
                    {b.paused ? <Pill tone="neutral" dot>Automation paused</Pill> : null}
                    <Link className="btn sm" to={`/workspace/${b.brand}`}>Open workspace <Icon name="arrowRight" size="sm" /></Link>
                  </div>
                </div>
                <div className="card-body col gap-12">
                  <div className="stat-row">
                    <Link className="stat" to="/blogs" onClick={() => setBrand(b.brand)}><div className="v">{fmtInt(b.counts.total)}</div><div className="l">Total blogs</div></Link>
                    <Link className="stat" to="/blogs?live=1" onClick={() => setBrand(b.brand)}><div className="v">{fmtInt(b.counts.live)}</div><div className="l">Published (live)</div></Link>
                    <Link className="stat" to="/blogs?status=idea,draft,changes_requested" onClick={() => setBrand(b.brand)}><div className="v">{fmtInt(b.counts.drafts)}</div><div className="l">Drafts</div></Link>
                    <Link className={`stat ${b.pendingApprovals ? 'warn' : ''}`} to="/blogs?status=in_review,publish_requested" onClick={() => setBrand(b.brand)}><div className="v">{fmtInt(b.pendingApprovals)}</div><div className="l">Pending approval</div></Link>
                    <Link className={`stat ${b.failedWorkflows ? 'alert' : ''}`} to="/automation" onClick={() => setBrand(b.brand)}><div className="v">{fmtInt(b.failedWorkflows)}</div><div className="l">Failed workflows</div></Link>
                  </div>
                  <div>
                    <div className="row small muted mb-8"><span>Automation pipeline</span><span className="spacer" />{b.counts.scheduled ? <span>{b.counts.scheduled} scheduled</span> : null}</div>
                    <div className="mini-pipe" role="list" aria-label="Pipeline stages">
                      {b.stages.map((s: any) => (
                        <span key={s.key} role="listitem" className={`st-${s.state}`} title={`${s.label}: ${STATE_LABEL[s.state] ?? s.state}${s.pending ? ` · ${s.pending} waiting` : ''}`} />
                      ))}
                    </div>
                  </div>
                </div>
              </section>
            ))}
          </div>

          <div className="grid main-side">
            <div className="col" style={{ gap: 16, minWidth: 0 }}>
              <Card title="Google Search Console" sub="Blog URLs (/blogs/…) · Google search only" actions={<Link className="btn ghost sm" to="/analytics">Details <Icon name="arrowRight" size="sm" /></Link>}>
                <GscKpis parts={data.brands.map((b: any) => ({ brand: b.brand, ...b.gsc }))} short={short} />
                {data.brands.some((b: any) => b.gsc.series.length) ? (
                  <div className="grid cols-2 mt-16">
                    <div>
                      <div className="small strong mb-8">Clicks per day</div>
                      <LineChart ariaLabel="Organic clicks per day" series={seriesFrom(data.brands.map((b: any) => ({ brand: b.brand, ...b.gsc })), 'clicks', short)} height={190} />
                    </div>
                    <div>
                      <div className="small strong mb-8">Impressions per day</div>
                      <LineChart ariaLabel="Impressions per day" series={seriesFrom(data.brands.map((b: any) => ({ brand: b.brand, ...b.gsc })), 'impressions', short)} height={190} />
                    </div>
                  </div>
                ) : null}
              </Card>

              <Card title="Google Analytics 4" sub="Sessions that landed on a blog URL · all channels — not comparable 1:1 with Search Console clicks" actions={<Link className="btn ghost sm" to="/analytics?tab=ga4">Details <Icon name="arrowRight" size="sm" /></Link>}>
                <Ga4Kpis parts={data.brands.map((b: any) => ({ brand: b.brand, ...b.ga4 }))} short={short} />
              </Card>

              <Card title="Top blog pages" sub="By Search Console clicks in this range" flush>
                <div className="table-wrap">
                  <table className="t">
                    <thead><tr><th>Page</th><th className="hide-sm">Brand</th><th className="r">Clicks</th><th className="r">Impr.</th><th className="r hide-sm">Source</th></tr></thead>
                    <tbody>
                      {data.brands.flatMap((b: any) => b.gsc.top.map((p: any) => ({ ...p, brand: b.brand, source: b.gsc.source }))).sort((a: any, b: any) => b.clicks - a.clicks).slice(0, 8).map((p: any) => (
                        <tr key={p.brand + p.page} className={p.article ? 'clickable' : ''} onClick={() => p.article && nav(`/blogs/${p.article.id}?tab=performance`)}>
                          <td className="title-cell"><span className="ttl">{p.article?.title ?? p.page}</span><span className="sub">{p.page}</span></td>
                          <td className="hide-sm"><span className={`brand-dot ${p.brand}`} /> {short(p.brand)}</td>
                          <td className="r">{fmtInt(p.clicks)}</td>
                          <td className="r">{fmtCompact(p.impressions)}</td>
                          <td className="r hide-sm"><SourceBadge source={p.source} /></td>
                        </tr>
                      ))}
                      {!data.brands.some((b: any) => b.gsc.top.length) ? <tr><td colSpan={5} className="muted small" style={{ padding: 16 }}>No Search Console rows in this range.</td></tr> : null}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>

            <div className="col" style={{ gap: 16, minWidth: 0 }}>
              <Card title="Alerts" sub={data.alerts.length ? `${data.alerts.length} need attention` : 'All clear'} flush>
                <div className="alert-list">
                  {data.alerts.length ? data.alerts.map((a: any, i: number) => (
                    <Link key={i} className="alert-item" to={a.link || '#'}>
                      <span className={`sev ${a.level}`} />
                      <span style={{ minWidth: 0 }}>
                        <span className="strong small" style={{ display: 'block' }}>{a.title}</span>
                        <span className="muted xs" style={{ display: 'block', overflowWrap: 'anywhere' }}>{a.detail}</span>
                      </span>
                    </Link>
                  )) : <div className="alert-item"><Icon name="checkCircle" /><span className="small muted">No failures, stale data or blocked approvals.</span></div>}
                </div>
              </Card>

              <Card title="Integration health" flush actions={<Link className="btn ghost xs" to="/integrations">Manage</Link>}>
                <div className="alert-list">
                  {data.integrations.filter((i: any) => i.state !== 'standby').map((i: any) => (
                    <div key={i.key + i.brand} className="alert-item">
                      <span className={`sev ${i.state === 'error' ? 'critical' : i.state === 'connected' ? 'ok' : i.state === 'pending_setup' ? 'warning' : 'info'}`} style={i.state === 'connected' ? { background: 'var(--ok)' } : undefined} />
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <span className="small strong">{i.label}</span>{i.brand ? <span className="muted small"> · {short(i.brand)}</span> : null}
                        <span className="muted xs" style={{ display: 'block' }}>
                          {i.state === 'pending_setup' ? 'Pending setup' : i.state === 'error' ? `Error · last success ${timeAgo(i.status?.last_success_at)}` : i.status?.last_success_at ? `Last sync ${timeAgo(i.status.last_success_at)}` : i.state === 'connected' ? 'Connected' : 'Not synced yet'}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </Card>

              <Card title="Recent activity" flush actions={me.permissions.includes('audit:view') ? <Link className="btn ghost xs" to="/audit">Audit log</Link> : null}>
                <div className="alert-list">
                  {data.activity.map((a: any) => (
                    <div key={a.id} className="alert-item">
                      <Icon name={a.action.startsWith('publish') ? 'publish' : a.action.startsWith('article') ? 'edit' : a.action.startsWith('integration') ? 'plug' : a.action.startsWith('workflow') ? 'automation' : 'history'} size="sm" />
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <span className="small"><b>{a.user_email === 'system' || !a.user_email ? 'System' : a.user_email.split('@')[0]}</b> · {a.action.replace(/[._]/g, ' ')}</span>
                        {a.summary ? <span className="muted xs ellipsis" style={{ display: 'block' }}>{a.summary}</span> : null}
                      </span>
                      <span className="faint xs nowrap">{timeAgo(a.ts)}</span>
                    </div>
                  ))}
                  {!data.activity.length ? <div className="alert-item muted small">No activity yet.</div> : null}
                </div>
              </Card>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function OverviewSkeleton() {
  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="grid cols-2">{[0, 1].map((i) => <div key={i} className="card card-body"><LoadingBlock rows={3} /></div>)}</div>
      <div className="kpis">{[0, 1, 2, 3].map((i) => <div key={i} className="kpi"><Skeleton h={12} w="50%" /><Skeleton h={26} w="70%" /></div>)}</div>
      <div className="card card-body"><Skeleton h={190} /></div>
    </div>
  );
}
