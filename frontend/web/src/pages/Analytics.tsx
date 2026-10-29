import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, useApi, qs, download } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtCompact, fmtDate, fmtInt, fmtPct, fmtPos, fmtSeconds, pctChange } from '../lib/format';
import type { BrandId } from '../lib/types';
import { Button, Card, Delta, ErrorState, LoadingBlock, PageHead, SourceBadge, Tabs, BrandTag } from '../components/ui';
import { useToast } from '../components/overlays';
import { Icon } from '../components/Icon';
import { LineChart, BarList } from '../components/charts';
import { GscKpis, Ga4Kpis, seriesFrom, NoMetrics } from '../components/metrics';

type Tab = 'gsc' | 'ga4' | 'articles' | 'compare';

export default function Analytics() {
  const [sp, setSp] = useSearchParams();
  const tab = (sp.get('tab') as Tab) || 'gsc';
  const brand = useBrandParam();
  const { range, can, me } = useApp();
  const toast = useToast();
  const [syncing, setSyncing] = useState<string | null>(null);
  const [rk, setRk] = useState(0);
  const sync = async (source: 'gsc' | 'ga4' | 'shopify') => {
    setSyncing(source);
    try {
      for (const b of brand ? [brand] : me.brands.map((x) => x.id)) await api.post('/analytics/sync', { brand: b, source });
      toast.ok('Refreshed.');
    } catch (e) { toast.error(e); } finally { setSyncing(null); setRk((k) => k + 1); }
  };
  return (
    <>
      <PageHead title="SEO & traffic" sub={<>Search Console and GA4 are reported separately: Search Console counts Google search clicks; GA4 counts sessions from every channel. {fmtDate(range.from)} – {fmtDate(range.to)}, compared with the previous period of equal length.</>}
        actions={can('analytics:sync') ? <>
          <Button size="sm" icon="refresh" loading={syncing === 'gsc'} onClick={() => sync('gsc')}>Sync Search Console</Button>
          <Button size="sm" icon="refresh" loading={syncing === 'ga4'} onClick={() => sync('ga4')}>Sync GA4</Button>
        </> : null} />
      <Tabs<Tab> value={tab} onChange={(t) => { const n = new URLSearchParams(sp); n.set('tab', t); setSp(n, { replace: true }); }} tabs={[
        { key: 'gsc', label: <><Icon name="google" size="sm" />Search Console</> },
        { key: 'ga4', label: <><Icon name="analytics" size="sm" />GA4</> },
        { key: 'articles', label: 'By article' },
        ...(!brand ? [{ key: 'compare' as Tab, label: 'Compare brands' }] : []),
      ]} />
      {tab === 'gsc' ? <GscTab key={rk} /> : tab === 'ga4' ? <Ga4Tab key={rk} /> : tab === 'articles' ? <ArticlesTab key={rk} /> : <CompareTab key={rk} />}
      <div className="muted xs mt-24">Export analytics workbooks from <Link to="/data">Data &amp; reports</Link>. <button className="btn ghost xs" onClick={() => download(`/data/export/gsc_pages${qs({ brand, from: range.from, to: range.to })}`).catch(toast.error)}>Export Search Console pages</button></div>
    </>
  );
}

function useReport(kind: 'gsc' | 'ga4' | 'articles') {
  const brand = useBrandParam();
  const { range } = useApp();
  return useApi<any>(`/analytics/${kind}${qs({ brand, from: range.from, to: range.to })}`);
}

function GscTab() {
  const r = useReport('gsc');
  const { brandOf } = useApp();
  const nav = useNavigate();
  const short = (b: BrandId) => brandOf(b).short;
  if (r.error) return <ErrorState error={r.error} onRetry={r.reload} />;
  if (!r.data) return <LoadingBlock rows={6} />;
  const brands = r.data.brands as any[];
  const any = brands.some((b) => b.totals);
  return (
    <div className="col" style={{ gap: 16 }}>
      <GscKpis parts={brands} short={short} />
      {any ? (
        <>
          <div className="grid cols-2">
            <Card title="Clicks per day" actions={<Sources brands={brands} />}><LineChart ariaLabel="Clicks per day" series={seriesFrom(brands, 'clicks', short)} /></Card>
            <Card title="Impressions per day" actions={<Sources brands={brands} />}><LineChart ariaLabel="Impressions per day" series={seriesFrom(brands, 'impressions', short)} /></Card>
          </div>
          <Card title="Average position per day" sub="Lower is better; weighted by impressions"><LineChart ariaLabel="Average position per day" series={seriesFrom(brands, 'position', short)} yFormat={(n) => n.toFixed(0)} invertY height={180} /></Card>
          <div className="grid cols-2">
            <Card title="Top blog pages" sub="Clicks" flush>
              <div style={{ padding: 8 }}>
                <BarList rows={brands.flatMap((b) => b.pages.map((p: any) => ({ ...p, brand: b.brand }))).sort((a: any, b: any) => b.clicks - a.clicks).slice(0, 12).map((p: any) => ({
                  key: p.brand + p.page, value: p.clicks,
                  label: <span className="row"><span className={`brand-dot ${p.brand}`} /><span className="ellipsis">{p.article?.title ?? p.page}</span></span>,
                  extra: <span className="faint">{fmtCompact(p.impressions)} impr.</span>,
                  onClick: p.article ? () => nav(`/blogs/${p.article.id}?tab=performance`) : undefined,
                }))} format={fmtInt} />
              </div>
            </Card>
            <Card title="Top queries" sub={brands.find((b) => b.queries)?.queries ? `${fmtDate(brands.find((b) => b.queries).queries.period.from)} – ${fmtDate(brands.find((b) => b.queries).queries.period.to)} (fixed period from the latest sync)` : 'No query data'} flush>
              <div className="table-wrap" style={{ maxHeight: 420 }}>
                <table className="t compact">
                  <thead><tr><th>Query</th><th className="r">Clicks</th><th className="r">Impr.</th><th className="r hide-sm">CTR</th><th className="r">Pos.</th></tr></thead>
                  <tbody>
                    {brands.flatMap((b) => (b.queries?.rows ?? []).map((q: any) => ({ ...q, brand: b.brand }))).sort((a: any, b: any) => b.clicks - a.clicks || b.impressions - a.impressions).slice(0, 30).map((q: any) => (
                      <tr key={q.brand + q.query}><td><span className={`brand-dot ${q.brand}`} /> {q.query}</td><td className="r">{fmtInt(q.clicks)}</td><td className="r">{fmtInt(q.impressions)}</td><td className="r hide-sm">{fmtPct(q.ctr)}</td><td className="r">{fmtPos(q.position)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
          <div className="grid cols-2">
            <Card title="Declining pages" sub="Clicks down 25%+ against the previous period (min. 5 clicks before)" flush>
              <PageTable rows={brands.flatMap((b) => b.declining.map((p: any) => ({ ...p, brand: b.brand })))} empty="No page lost a quarter of its clicks." cols="decline" />
            </Card>
            <Card title="Optimization opportunities" sub="Queries ranking 4–20 with 20+ impressions: improve title, headings or internal links" flush>
              <div className="table-wrap">
                <table className="t compact">
                  <thead><tr><th>Query → page</th><th className="r">Impr.</th><th className="r">Pos.</th></tr></thead>
                  <tbody>
                    {brands.flatMap((b) => b.opportunities.map((o: any) => ({ ...o, brand: b.brand }))).sort((a: any, b: any) => b.impressions - a.impressions).slice(0, 12).map((o: any, i: number) => (
                      <tr key={i} className={o.article ? 'clickable' : ''} onClick={() => o.article && nav(`/blogs/${o.article.id}`)}>
                        <td className="title-cell"><span className="ttl"><span className={`brand-dot ${o.brand}`} /> {o.query}</span><span className="sub">{o.article?.title ?? o.page}</span></td>
                        <td className="r">{fmtInt(o.impressions)}</td><td className="r">{fmtPos(o.position)}</td>
                      </tr>
                    ))}
                    {!brands.some((b) => b.opportunities.length) ? <tr><td colSpan={3} className="muted small" style={{ padding: 14 }}>None found in the latest query data.</td></tr> : null}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}

function PageTable({ rows, empty }: { rows: any[]; empty: string; cols: 'decline' }) {
  const nav = useNavigate();
  if (!rows.length) return <div className="card-body muted small">{empty}</div>;
  return (
    <div className="table-wrap">
      <table className="t compact">
        <thead><tr><th>Page</th><th className="r">Clicks</th><th className="r">Before</th><th className="r">Change</th></tr></thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.brand + p.page} className={p.article ? 'clickable' : ''} onClick={() => p.article && nav(`/blogs/${p.article.id}?tab=performance`)}>
              <td className="title-cell"><span className="ttl"><span className={`brand-dot ${p.brand}`} /> {p.article?.title ?? p.page}</span></td>
              <td className="r">{fmtInt(p.clicks)}</td><td className="r">{fmtInt(p.prevClicks)}</td><td className="r"><Delta value={pctChange(p.clicks, p.prevClicks)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Sources({ brands }: { brands: any[] }) {
  const kinds = [...new Set(brands.filter((b) => b.source.kind).map((b) => b.source.kind))];
  return <span className="row">{kinds.map((k) => <SourceBadge key={k} source={brands.find((b) => b.source.kind === k).source} />)}</span>;
}

function Ga4Tab() {
  const r = useReport('ga4');
  const { brandOf } = useApp();
  const nav = useNavigate();
  const short = (b: BrandId) => brandOf(b).short;
  if (r.error) return <ErrorState error={r.error} onRetry={r.reload} />;
  if (!r.data) return <LoadingBlock rows={6} />;
  const brands = r.data.brands as any[];
  const any = brands.some((b) => b.totals);
  return (
    <div className="col" style={{ gap: 16 }}>
      <div className="callout info"><Icon name="info" />GA4 counts sessions whose landing page is a blog URL, from any channel (search, social, email, direct). Use Search Console for Google search clicks specifically.</div>
      <Ga4Kpis parts={brands} short={short} />
      {any ? (
        <>
          <Card title="Sessions per day" actions={<Sources brands={brands} />}><LineChart ariaLabel="Sessions per day" series={seriesFrom(brands, 'sessions', short)} /></Card>
          <Card title="Blog landing pages" flush>
            <div className="table-wrap">
              <table className="t compact">
                <thead><tr><th>Landing page</th><th className="r">Sessions</th><th className="r hide-sm">Engagement</th><th className="r hide-sm">Avg. time</th><th className="r">Key events</th></tr></thead>
                <tbody>
                  {brands.flatMap((b) => b.pages.map((p: any) => ({ ...p, brand: b.brand }))).sort((a: any, b: any) => b.sessions - a.sessions).slice(0, 40).map((p: any) => (
                    <tr key={p.brand + p.page_path} className={p.article ? 'clickable' : ''} onClick={() => p.article && nav(`/blogs/${p.article.id}?tab=performance`)}>
                      <td className="title-cell"><span className="ttl"><span className={`brand-dot ${p.brand}`} /> {p.article?.title ?? p.page_path}</span><span className="sub">{p.page_path}</span></td>
                      <td className="r">{fmtInt(p.sessions)}</td><td className="r hide-sm">{fmtPct(p.engagementRate)}</td><td className="r hide-sm">{fmtSeconds(p.avg_seconds)}</td><td className="r">{fmtInt(p.key_events)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function ArticlesTab() {
  const r = useReport('articles');
  const nav = useNavigate();
  const { me } = useApp();
  const [sort, setSort] = useState<{ k: string; d: 1 | -1 }>({ k: 'clicks', d: -1 });
  if (r.error) return <ErrorState error={r.error} onRetry={r.reload} />;
  if (!r.data) return <LoadingBlock rows={6} />;
  const brands = r.data.brands as any[];
  const rows = brands.flatMap((b) => b.rows.map((x: any) => ({ ...x, brand: b.brand }))).sort((a: any, b: any) => ((a[sort.k] ?? -1) > (b[sort.k] ?? -1) ? 1 : -1) * sort.d);
  const Th = ({ k, children, cls = '' }: { k: string; children: string; cls?: string }) => <th className={`r sortable ${cls}`} onClick={() => setSort({ k, d: sort.k === k ? (-sort.d as 1 | -1) : -1 })}>{children}{sort.k === k ? <Icon name={sort.d === 1 ? 'arrowUp' : 'arrowDown'} size="sm" /> : null}</th>;
  return (
    <Card flush title="Published articles" sub="Columns stay blank (—) where a source has no data; nothing is estimated."
      actions={<span className="row-wrap">{brands.map((b) => <span key={b.brand} className="row xs"><span className={`brand-dot ${b.brand}`} />GSC <SourceBadge source={b.sources.gsc} /> GA4 <SourceBadge source={b.sources.ga4} /></span>)}</span>}>
      <div className="table-wrap">
        <table className="t compact">
          <thead>
            <tr className="group-head"><th /><th colSpan={4} style={{ color: 'var(--info)' }}>Search Console</th><th colSpan={3} className="hide-sm" style={{ color: 'var(--ok)' }}>GA4</th></tr>
            <tr><th>Article</th><Th k="clicks">Clicks</Th><Th k="impressions">Impr.</Th><Th k="ctr" cls="hide-sm">CTR</Th><Th k="position">Pos.</Th><Th k="sessions" cls="hide-sm">Sessions</Th><Th k="engagementRate" cls="hide-sm">Engaged</Th><Th k="keyEvents" cls="hide-sm">Key ev.</Th></tr>
          </thead>
          <tbody>
            {rows.map((a: any) => (
              <tr key={a.id} className="clickable" onClick={() => nav(`/blogs/${a.id}?tab=performance`)}>
                <td className="title-cell"><span className="ttl">{a.title}</span><span className="sub row"><BrandTag id={a.brand} brands={me.brands} /> {fmtDate(a.published_at)}</span></td>
                <td className="r">{fmtInt(a.clicks)}</td><td className="r">{fmtCompact(a.impressions)}</td><td className="r hide-sm">{fmtPct(a.ctr)}</td><td className="r">{fmtPos(a.position)}</td>
                <td className="r hide-sm">{fmtInt(a.sessions)}</td><td className="r hide-sm">{fmtPct(a.engagementRate)}</td><td className="r hide-sm">{fmtInt(a.keyEvents)}</td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={8} className="muted small" style={{ padding: 16 }}>No live articles synced yet.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function CompareTab() {
  const g = useReport('gsc');
  const a = useReport('ga4');
  const { brandOf } = useApp();
  if (g.error || a.error) return <ErrorState error={g.error || a.error} />;
  if (!g.data || !a.data) return <LoadingBlock rows={6} />;
  const gb = g.data.brands as any[];
  const ab = a.data.brands as any[];
  const short = (b: BrandId) => brandOf(b).short;
  const metric = (label: string, get: (b: any) => number | null, fmt: (n: number | null) => string, prev?: (b: any) => number | null, invert?: boolean, src?: 'g' | 'a') => (
    <tr>
      <td className="strong">{label}</td>
      {(src === 'a' ? ab : gb).map((b) => (
        <td key={b.brand} className="r">{b.totals ? <>{fmt(get(b.totals))} {prev && b.previous ? <Delta value={pctChange(get(b.totals), prev(b.previous))} invert={invert} /> : null}</> : <span className="faint">—</span>}</td>
      ))}
    </tr>
  );
  return (
    <div className="col" style={{ gap: 16 }}>
      <Card title="Side by side" flush>
        <div className="table-wrap">
          <table className="t">
            <thead><tr><th>Metric</th>{gb.map((b) => <th key={b.brand} className="r"><span className="row" style={{ justifyContent: 'flex-end' }}><span className={`brand-dot ${b.brand}`} />{brandOf(b.brand).name}</span></th>)}</tr></thead>
            <tbody>
              <tr className="group-head"><th colSpan={3} style={{ textAlign: 'left', color: 'var(--info)' }}>Search Console</th></tr>
              {metric('Clicks', (t) => t.clicks, fmtInt, (t) => t.clicks)}
              {metric('Impressions', (t) => t.impressions, fmtCompact, (t) => t.impressions)}
              {metric('CTR', (t) => t.ctr, fmtPct, (t) => t.ctr)}
              {metric('Avg. position', (t) => t.position, fmtPos, (t) => t.position, true)}
              <tr><td className="muted small">Source</td>{gb.map((b) => <td key={b.brand} className="r"><SourceBadge source={b.source} /></td>)}</tr>
              <tr className="group-head"><th colSpan={3} style={{ textAlign: 'left', color: 'var(--ok)' }}>GA4</th></tr>
              {metric('Sessions', (t) => t.sessions, fmtInt, (t) => t.sessions, false, 'a')}
              {metric('Engagement rate', (t) => t.engagementRate, fmtPct, (t) => t.engagementRate, false, 'a')}
              {metric('Key events', (t) => t.keyEvents, fmtInt, (t) => t.keyEvents, false, 'a')}
              <tr><td className="muted small">Source</td>{ab.map((b) => <td key={b.brand} className="r"><SourceBadge source={b.source} /></td>)}</tr>
            </tbody>
          </table>
        </div>
      </Card>
      {gb.some((b) => b.series.length) ? (
        <Card title="Clicks per day by brand" sub="Each line in its brand colour"><LineChart ariaLabel="Clicks per day by brand" series={seriesFrom(gb, 'clicks', short)} /></Card>
      ) : <NoMetrics what="Search Console" />}
    </div>
  );
}
