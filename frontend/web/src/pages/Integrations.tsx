import { useState, type ReactNode } from 'react';
import { api, useApi } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtDateTime, timeAgo } from '../lib/format';
import { Button, Card, ErrorState, Kv, LoadingBlock, PageHead, Pill } from '../components/ui';
import { useToast } from '../components/overlays';
import { Icon } from '../components/Icon';

const STATE: Record<string, { label: string; tone: string }> = {
  connected: { label: 'Connected', tone: 'ok' }, error: { label: 'Failing', tone: 'crit' }, pending_setup: { label: 'Pending setup', tone: 'warn' },
  syncing: { label: 'Syncing', tone: 'info' }, not_synced: { label: 'Configured · not synced yet', tone: 'info' }, standby: { label: 'Standby', tone: 'neutral' },
};
const ICON: Record<string, string> = { shopify: 'store', shopify_public: 'store', gsc: 'google', ga4: 'analytics', claude: 'sparkle', workflow_webhook: 'link' };

export default function Integrations() {
  const q = useApi<any>('/integrations');
  const brand = useBrandParam();
  const { can, brandOf } = useApp();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, { ok: boolean; text: string }>>({});

  const test = async (i: any) => {
    const k = i.key + i.brand;
    setBusy('t' + k);
    try {
      const r = await api.post<any>('/integrations/test', { key: i.key, brand: i.brand || undefined });
      setResults((m) => ({ ...m, [k]: { ok: r.ok, text: r.ok ? `OK — ${JSON.stringify(r.result).replace(/[{}"]/g, '').replace(/,/g, ', ').replace(/:/g, ': ')}` : r.error } }));
    } catch (e: any) { setResults((m) => ({ ...m, [k]: { ok: false, text: e.message } })); } finally { setBusy(null); q.reload(); }
  };
  const sync = async (i: any) => {
    const k = i.key + i.brand;
    setBusy('s' + k);
    try { await api.post('/analytics/sync', { brand: i.brand, source: i.key === 'shopify_public' ? 'shopify' : i.key }); toast.ok('Synced.'); } catch (e) { toast.error(e); } finally { setBusy(null); q.reload(); }
  };

  const items = (q.data?.items ?? []).filter((i: any) => !brand || !i.brand || i.brand === brand);
  return (
    <>
      <PageHead title="Integrations" sub="Connection status, last successful sync and setup for every data source. Credentials are set as server environment variables and are never shown or sent to the browser." />
      <ErrorState error={q.error} onRetry={q.reload} />
      {q.loading && !q.data ? <LoadingBlock rows={6} /> : null}
      {q.data ? (
        <>
          <div className="callout info mb-16"><Icon name="shield" /><div>Shopify Admin API version <span className="mono">{q.data.shopifyApiVersion}</span>. Live publishing on this server: <b>{q.data.livePublishing ? 'enabled' : 'disabled'}</b> (ALLOW_LIVE_PUBLISH).</div></div>
          <div className="grid cols-2">
            {items.map((i: any) => {
              const k = i.key + i.brand;
              const st = STATE[i.state] ?? { label: i.state, tone: 'neutral' };
              const syncable = i.brand && ['shopify', 'shopify_public', 'gsc', 'ga4'].includes(i.key) && i.configured && i.state !== 'standby';
              return (
                <section key={k} className="card">
                  <div className="card-head">
                    <Icon name={ICON[i.key] ?? 'plug'} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <h2 className="card-title">{i.label}</h2>
                      {i.brand ? <div className="card-sub row"><span className={`brand-dot ${i.brand}`} />{brandOf(i.brand).name}</div> : <div className="card-sub">All brands</div>}
                    </div>
                    <Pill tone={st.tone} dot>{st.label}</Pill>
                  </div>
                  <div className="card-body col gap-12">
                    <div className="small">{i.provides}</div>
                    <Kv items={[
                      ['Last success', i.status?.last_success_at ? <span title={fmtDateTime(i.status.last_success_at)}>{timeAgo(i.status.last_success_at)}</span> : <span className="faint">never</span>],
                      ['Last attempt', i.status?.last_attempt_at ? timeAgo(i.status.last_attempt_at) : <span className="faint">never</span>],
                      ...(i.status?.details && Object.keys(i.status.details).length && i.state !== 'pending_setup' ? [['Last result', <span className="mono">{Object.entries(i.status.details).map(([a, b]) => `${a}: ${b}`).join(' · ')}</span>] as [string, ReactNode]] : []),
                    ]} />
                    {i.state === 'error' && i.status?.last_error ? <div className="callout crit"><Icon name="alert" /><div style={{ overflowWrap: 'anywhere' }}>{i.status.last_error}</div></div> : null}
                    {i.state === 'pending_setup' || !i.configured ? <div className="callout warn"><Icon name="key" /><div><b>Setup:</b> {i.setup}</div></div> : <details className="small"><summary className="muted" style={{ cursor: 'pointer' }}>Setup details</summary><p className="mt-8">{i.setup}</p></details>}
                    {results[k] ? <div className={`callout ${results[k].ok ? 'ok' : 'crit'}`}><Icon name={results[k].ok ? 'checkCircle' : 'alert'} /><div style={{ overflowWrap: 'anywhere' }}>{results[k].text}</div></div> : null}
                  </div>
                  {(can('integrations:manage') && i.configured && i.key !== 'workflow_webhook') || (can('analytics:sync') && syncable) ? (
                    <div className="card-foot">
                      {can('integrations:manage') && i.configured && i.key !== 'workflow_webhook' ? <Button size="sm" icon="plug" loading={busy === 't' + k} onClick={() => test(i)}>Test connection</Button> : null}
                      {can('analytics:sync') && syncable ? <Button size="sm" icon="refresh" loading={busy === 's' + k} onClick={() => sync(i)}>Sync now</Button> : null}
                    </div>
                  ) : null}
                </section>
              );
            })}
          </div>
          <Card title="Where each metric comes from" className="mt-16" flush>
            <div className="table-wrap">
              <table className="t compact">
                <thead><tr><th>Metric</th><th>Source</th><th>Access needed</th><th className="hide-md">If unavailable</th></tr></thead>
                <tbody>
                  {[
                    ['Articles, drafts, SEO fields, publish state', 'Shopify Admin GraphQL (articles, blogs)', 'Custom app token: read_content, write_content', 'Public feed (live articles only) · Excel blog records'],
                    ['Products & images for links and featured images', 'Shopify Admin (products) or storefront /products.json', 'read_products, or none for public', '—'],
                    ['Clicks, impressions, CTR, position, queries', 'Search Console Search Analytics API', 'Service account added to the property', 'Excel import of Search Console exports'],
                    ['Sessions, engagement, key events (conversions)', 'GA4 Data API runReport (landingPage)', 'Service account with Viewer on the property', 'Excel import of GA4 Explore exports'],
                    ['Keyword volume & difficulty', 'Not available from Google APIs without Ads', '—', 'Excel import from Semrush / Ahrefs / Keyword Planner'],
                    ['Topic ideas, first drafts', 'Claude Messages API (this server)', 'ANTHROPIC_API_KEY', 'Write manually'],
                    ['Status of Claude agents running elsewhere', 'Not exposed by any API', '—', 'Agents POST to /api/hooks/workflow'],
                    ['Shopify store analytics (sales, sessions)', 'Not used: blog attribution comes from GA4', '—', '—'],
                  ].map((r) => <tr key={r[0]}><td className="strong small">{r[0]}</td><td className="small">{r[1]}</td><td className="small">{r[2]}</td><td className="small hide-md muted">{r[3]}</td></tr>)}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}
    </>
  );
}
