'use client';
import { useState } from 'react';
import Link from 'next/link';
import { api, useApi, qs } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtDateTime, timeAgo } from '../lib/format';
import { BrandTag, Button, Card, Empty, ErrorState, LoadingBlock, PageHead, Pill } from '../components/ui';
import { useToast } from '../components/overlays';
import { Icon } from '../components/Icon';
import { AuthorizeDialog, MODE_LABEL, RejectDialog } from '../components/publish';
export default function Publishing() {
    const brand = useBrandParam();
    const { can, me } = useApp();
    const q = useApi(`/publishing${qs({ brand })}`);
    const toast = useToast();
    const [auth, setAuth] = useState(null);
    const [reject, setReject] = useState(null);
    const d = q.data;
    const open = d?.requests.filter((r) => r.status === 'pending') ?? [];
    const failed = d?.requests.filter((r) => r.status === 'failed') ?? [];
    const history = d?.requests.filter((r) => !['pending', 'failed'].includes(r.status)) ?? [];
    const withdraw = async (r) => { try {
        await api.post(`/publish-requests/${r.id}/cancel`);
        toast.ok('Request withdrawn.');
        q.reload();
    }
    catch (e) {
        toast.error(e);
    } };
    const mayAuthorize = (r) => can('publish:authorize') && (r.requested_by !== me.user.id || me.user.role === 'admin');
    return (<>
      <PageHead title="Publishing" sub="Nothing reaches a storefront without an approved request, a second person's authorization and a typed confirmation."/>
      {d ? (d.livePublishingEnabled
            ? <div className="callout ok mb-16"><Icon name="shield"/><div><b>Live publishing is enabled on this server.</b> Authorizing a request changes the live storefront.</div></div>
            : <div className="callout warn mb-16"><Icon name="lock"/><div><b>Live publishing is switched off on this server</b> (ALLOW_LIVE_PUBLISH is not set). Requests can be made and reviewed; authorizing them is refused and nothing is sent to Shopify. Hidden drafts still work.</div></div>) : null}
      <ErrorState error={q.error} onRetry={q.reload}/>
      {q.loading && !d ? <LoadingBlock rows={6}/> : null}
      {d ? (<div className="col" style={{ gap: 16 }}>
          {failed.length ? (<Card title={`Failed · ${failed.length}`} sub="Shopify refused or could not be reached. The text has not changed since approval, so a retry is safe.">
              <div className="col gap-12">{failed.map((r) => <RequestRow key={r.id} r={r} actions={<>
                  {mayAuthorize(r) ? <Button size="sm" variant="primary" icon="refresh" onClick={() => setAuth({ req: r, retry: true })}>Retry…</Button> : null}
                  {can('publish:authorize') ? <Button size="sm" onClick={() => setReject(r)}>Reject</Button> : null}
                </>}/>)}</div>
            </Card>) : null}

          <Card title={`Waiting for authorization · ${open.length}`} flush={!open.length}>
            {open.length ? (<div className="col gap-12">{open.map((r) => <RequestRow key={r.id} r={r} actions={<>
                  {mayAuthorize(r) ? <Button size="sm" variant="primary" icon="shield" onClick={() => setAuth({ req: r })}>Authorize…</Button> : null}
                  {can('publish:authorize') ? <Button size="sm" onClick={() => setReject(r)}>Reject</Button> : null}
                  {r.requested_by === me.user.id || me.user.role === 'admin' ? <Button size="sm" variant="ghost" onClick={() => withdraw(r)}>Withdraw</Button> : null}
                  {r.requested_by === me.user.id && me.user.role !== 'admin' ? <span className="muted xs">Needs another person to authorize</span> : null}
                </>}/>)}</div>) : <Empty icon="checkCircle" title="No requests waiting">Approved articles can be put forward from their Publishing tab.</Empty>}
          </Card>

          <div className="grid cols-3">
            <Card title={`Ready to request · ${d.readyForRequest.length}`} sub="Approved, current version" flush>
              <List rows={d.readyForRequest} empty="Nothing approved and waiting." render={(a) => <><Link href={`/blogs/${a.id}?tab=publish`} className="strong small ellipsis">{a.title}</Link><span className="muted xs">v{a.version} · approved {timeAgo(a.approved_at)}{a.shopify_published ? ' · update to live article' : ''}</span></>}/>
            </Card>
            <Card title={`Scheduled · ${d.scheduled.length}`} flush>
              <List rows={d.scheduled} empty="Nothing scheduled." render={(a) => <><Link href={`/blogs/${a.id}`} className="strong small ellipsis">{a.title}</Link><span className="muted xs"><Icon name="clock" size="sm"/> {fmtDateTime(a.publish_at)}</span></>}/>
            </Card>
            <Card title={`Hidden Shopify drafts · ${d.drafts.length}`} sub="Saved to Shopify, not visible" flush>
              <List rows={d.drafts} empty="No hidden drafts." render={(a) => <><Link href={`/blogs/${a.id}`} className="strong small ellipsis">{a.title}</Link><span className="muted xs">v{a.version} · saved {timeAgo(a.shopify_synced_at)}</span></>}/>
            </Card>
          </div>

          <Card title="History" flush>
            {history.length ? (<div className="table-wrap">
                <table className="t compact">
                  <thead><tr><th>Article</th>{!brand ? <th className="hide-sm">Brand</th> : null}<th>Mode</th><th>Outcome</th><th className="hide-md">Requested</th><th className="hide-md">Decided</th></tr></thead>
                  <tbody>
                    {history.map((r) => (<tr key={r.id}>
                        <td className="title-cell"><Link className="ttl" href={`/blogs/${r.article_id}?tab=publish`}>{r.title}</Link><span className="sub">v{r.version}</span></td>
                        {!brand ? <td className="hide-sm"><BrandTag id={r.brand_id} brands={me.brands}/></td> : null}
                        <td className="small">{MODE_LABEL[r.mode]}</td>
                        <td><Pill tone={r.status === 'executed' ? 'ok' : r.status === 'rejected' ? 'crit' : 'neutral'}>{r.status === 'executed' ? (r.mode === 'schedule' ? 'scheduled' : 'published') : r.status}</Pill></td>
                        <td className="hide-md small">{r.requested_by_name ?? '—'} · {fmtDateTime(r.requested_at)}</td>
                        <td className="hide-md small">{r.decided_by_name ?? '—'}{r.decision_note ? `: ${r.decision_note}` : ''}</td>
                      </tr>))}
                  </tbody>
                </table>
              </div>) : <div className="card-body muted small">No completed requests yet.</div>}
          </Card>
        </div>) : null}
      {auth ? <AuthorizeDialog req={auth.req} retry={auth.retry} onClose={() => setAuth(null)} onDone={() => { setAuth(null); q.reload(); }}/> : null}
      {reject ? <RejectDialog req={reject} onClose={() => setReject(null)} onDone={() => { setReject(null); q.reload(); }}/> : null}
    </>);
}
function RequestRow({ r, actions }) {
    const { me } = useApp();
    return (<div className="row-wrap" style={{ border: '1px solid var(--line)', borderRadius: 12, padding: '12px 14px', gap: 12, alignItems: 'flex-start' }}>
      <div style={{ flex: '1 1 300px', minWidth: 0 }}>
        <div className="row-wrap gap-4 mb-8">
          <BrandTag id={r.brand_id} brands={me.brands}/>
          <Pill tone="accent">{MODE_LABEL[r.mode]}{r.publish_at ? ` · ${fmtDateTime(r.publish_at)}` : ''}</Pill>
          <span className="pill outline">v{r.version}</span>
          {r.stale ? <Pill tone="crit">Content changed since request</Pill> : null}
          {r.attempts ? <span className="muted xs">{r.attempts} attempt{r.attempts > 1 ? 's' : ''}</span> : null}
        </div>
        <Link href={`/blogs/${r.article_id}?tab=publish`} className="strong">{r.title}</Link>
        <div className="muted small">Requested by {r.requested_by_name ?? '—'} {timeAgo(r.requested_at)}{r.note ? ` — “${r.note}”` : ''}</div>
        {r.error ? <div className="callout crit mt-8"><Icon name="alert"/><div style={{ overflowWrap: 'anywhere' }}>{r.error}</div></div> : null}
      </div>
      <div className="row-wrap" style={{ marginLeft: 'auto' }}>
        <Link className="btn sm ghost" href={`/blogs/${r.article_id}?tab=preview`}><Icon name="eye" size="sm"/>Preview</Link>
        {actions}
      </div>
    </div>);
}
function List({ rows, render, empty }) {
    if (!rows.length)
        return <div className="card-body muted small">{empty}</div>;
    return <div className="alert-list">{rows.map((r) => <div key={r.id} className="alert-item"><span className={`brand-dot ${r.brand_id}`} style={{ marginTop: 6 }}/><span className="col gap-4" style={{ minWidth: 0 }}>{render(r)}</span></div>)}</div>;
}
