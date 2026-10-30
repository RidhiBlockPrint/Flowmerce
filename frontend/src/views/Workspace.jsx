'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useNavigate, useParams } from '../lib/nav';
import { api, useApi, qs } from '../lib/api';
import { useApp } from '../lib/app';
import { fmtDate, timeAgo } from '../lib/format';
import { Button, Card, Empty, ErrorState, Field, LivePill, LoadingBlock, Pill, RoleTag, StatusPill, Paged } from '../components/ui';
import { useToast } from '../components/overlays';
import { Icon } from '../components/Icon';
import { GscKpis, Ga4Kpis } from '../components/metrics';
import { NewArticle } from './Blogs';
const COLUMNS = [
    { key: 'ideas', label: 'Ideas & drafts', statuses: ['idea', 'draft', 'changes_requested'] },
    { key: 'review', label: 'In review', statuses: ['in_review'] },
    { key: 'approved', label: 'Approved', statuses: ['approved'] },
    { key: 'publishing', label: 'Publishing', statuses: ['publish_requested', 'scheduled', 'failed'] },
    { key: 'live', label: 'Published', statuses: ['published'] },
];
const EMPTY_NOTE = {
    ideas: 'No ideas or drafts right now. New articles start here.',
    review: 'Nothing is waiting for review.',
    approved: 'No approved articles are waiting to be published.',
    publishing: 'No publish requests, scheduled posts or failures.',
    live: 'No articles are live on the storefront yet.',
};
export default function Workspace() {
    const { brand: param } = useParams();
    const { me, brandOf, range, setBrand, can } = useApp();
    const nav = useNavigate();
    const valid = me.brands.some((b) => b.id === param);
    const id = (valid ? param : 'ridhi');
    const b = brandOf(id);
    useEffect(() => { if (valid)
        setBrand(id); }, [id, valid, setBrand]);
    const arts = useApi(`/articles${qs({ brand: id, limit: 300, sort: 'updated' })}`);
    const topics = useApi(`/topics${qs({ brand: id })}`);
    const ov = useApi(`/overview${qs({ brand: id, from: range.from, to: range.to })}`);
    const [creating, setCreating] = useState(false);
    const [stage, setStage] = useState(null);
    if (!valid)
        return <ErrorState error={new Error('Unknown brand workspace.')}/>;
    const bo = ov.data?.brands?.[0];
    const rows = arts.data?.rows ?? [];
    const counts = Object.fromEntries(COLUMNS.map((c) => [c.key, rows.filter((a) => c.statuses.includes(a.status)).length]));
    // Open on the first stage that has articles (the one the owner can act on), or the first stage when all are empty.
    const activeStage = COLUMNS.find((c) => c.key === stage) ?? COLUMNS.find((c) => counts[c.key]) ?? COLUMNS[0];
    const stageItems = rows.filter((a) => activeStage.statuses.includes(a.status));
    const queue = (topics.data ?? []).filter((t) => ['proposed', 'validated', 'approved'].includes(t.status));
    return (<div data-brand={id}>
      <section className={`card brand-card ${id}`} style={{ marginBottom: 16, overflow: 'hidden' }}>
        <div style={{ background: id === 'ridhi' ? 'var(--ridhi)' : '#1e1a17', color: '#fff', fontSize: 11.5, fontWeight: 650, letterSpacing: '0.06em', padding: '6px 18px', textTransform: 'uppercase' }}>
          {id === 'ridhi' ? 'Handcrafted block print home decor' : 'Hand printed fabric, made by artisans'}
        </div>
        <div className="card-body row-wrap" style={{ gap: 16, alignItems: 'flex-end' }}>
          <div style={{ minWidth: 0 }}>
            <h1 className="page-title" style={{ fontSize: 30, color: id === 'ridhi' ? 'var(--ridhi)' : 'var(--ink)' }}>{b.name}</h1>
            <div className="row-wrap small muted mt-4">
              <a href={b.storefrontUrl} target="_blank" rel="noopener">{b.storefrontUrl.replace('https://', '')} <Icon name="external" size="sm"/></a>
              <span>·</span><span className="mono">{b.shopDomain}</span>
              <span>·</span><a href={b.blogUrl} target="_blank" rel="noopener">/blogs/{b.blogHandle}</a>
            </div>
          </div>
          <div className="page-actions">
            <Link className="btn" href="/automation"><Icon name="automation"/>Automation</Link>
            {can('article:write') ? <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>New article</Button> : null}
          </div>
        </div>
        <div className="card-foot">
          <span className="row gap-4"><span className="sev" style={{ marginTop: 0, background: b.configured.shopifyAdmin ? 'var(--ok)' : 'var(--saffron)' }}/>Shopify Admin {b.configured.shopifyAdmin ? 'connected' : 'pending setup (public feed in use)'}</span>
          <span className="row gap-4"><span className="sev" style={{ marginTop: 0, background: b.configured.gsc ? 'var(--ok)' : 'var(--saffron)' }}/>Search Console {b.configured.gsc ? 'configured' : 'pending setup'}</span>
          <span className="row gap-4"><span className="sev" style={{ marginTop: 0, background: b.configured.ga4 ? 'var(--ok)' : 'var(--saffron)' }}/>GA4 {b.configured.ga4 ? 'configured' : 'pending setup'}</span>
        </div>
      </section>

      <div className="section-title">Blog pipeline <span className="faint">{arts.data ? `${arts.data.total} articles` : ''}</span></div>
      <ErrorState error={arts.error} onRetry={arts.reload}/>
      {arts.loading && !arts.data ? <LoadingBlock /> : arts.data ? (<>
          <div className="pipeline-summary" role="group" aria-label="Pipeline stages">
            {COLUMNS.map((c) => (<button key={c.key} type="button" className={`pipe-stage ${counts[c.key] ? '' : 'zero'}`} aria-pressed={activeStage.key === c.key} onClick={() => setStage(c.key)}>
                <span className="n">{counts[c.key]}</span>
                <span className="l">{c.label}</span>
              </button>))}
          </div>
          <div className={queue.length ? 'workspace-main' : ''}>
            <section className="card flush" style={{ minWidth: 0 }}>
              <div className="card-head">
                <h2 className="card-title">{activeStage.label}</h2>
                <span className="faint small">{stageItems.length} {stageItems.length === 1 ? 'article' : 'articles'}</span>
                {stageItems.length ? <Link className="btn ghost xs" style={{ marginLeft: 'auto' }} href={`/blogs?status=${activeStage.statuses.join(',')}`}>Open in Blogs <Icon name="arrowRight" size="sm"/></Link> : null}
              </div>
              {stageItems.length ? (<Paged rows={stageItems} resetKey={activeStage.key}>{(pageRows) => (<>
<div className="table-wrap">
                  <table className="t">
                    <thead><tr><th>Article</th><th>Status</th><th className="hide-md">Next step</th><th className="hide-md">Assignee</th><th className="r">Updated</th></tr></thead>
                    <tbody>
                      {pageRows.map((a) => (<tr key={a.id} className="clickable" onClick={() => nav(`/blogs/${a.id}`)} tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') nav(`/blogs/${a.id}`); }}>
                          <td className="title-cell">
                            <Link className="ttl" href={`/blogs/${a.id}`} onClick={(e) => e.stopPropagation()}>{a.title}</Link>
                            <span className="sub">{a.primary_keyword ? `${a.primary_keyword} · ` : ''}/{a.handle}</span>
                          </td>
                          <td><div className="row-wrap gap-4"><StatusPill status={a.status}/><LivePill live={a.shopify_published} differs={a.live_differs}/></div></td>
                          <td className="hide-md"><div className="small">{a.next_action.label}</div><RoleTag role={a.next_action.role}/></td>
                          <td className="hide-md small">{a.assignee_name ?? <span className="faint">Unassigned</span>}</td>
                          <td className="r small nowrap" title={fmtDate(a.updated_at)}>{timeAgo(a.updated_at)}</td>
                        </tr>))}
                    </tbody>
                  </table>
                </div>
</>)}</Paged>) : (<Empty icon="blogs" title={`Nothing in “${activeStage.label}”`}>{EMPTY_NOTE[activeStage.key]}</Empty>)}
            </section>
            {queue.length ? (<Card title="Topics queue" sub={`${queue.length} waiting`} flush actions={<Link className="btn ghost xs" href="/topics">All topics</Link>}>
                <div className="alert-list">
                  {queue.slice(0, 8).map((t) => (<Link key={t.id} href={`/topics?focus=${t.id}`} className="alert-item">
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <span className="small strong" style={{ display: 'block' }}>{t.title}</span>
                        <span className="row xs"><Pill tone={t.status === 'approved' ? 'ok' : t.status === 'validated' ? 'info' : 'neutral'}>{t.status}</Pill><span className="muted ellipsis">{t.primary_keyword}</span></span>
                      </span>
                    </Link>))}
                </div>
              </Card>) : null}
          </div>
          {!queue.length && topics.data ? <p className="muted small mt-8">No topics are waiting in the queue. <Link href="/topics">Open Topics &amp; keywords</Link></p> : null}
        </>) : null}

      <div className="section-title">Search & traffic · {fmtDate(range.from)} – {fmtDate(range.to)}</div>
      {bo ? (<div className="grid cols-2">
          <Card title="Search Console"><GscKpis parts={[{ brand: id, ...bo.gsc }]} short={() => b.short}/></Card>
          <Card title="GA4"><Ga4Kpis parts={[{ brand: id, ...bo.ga4 }]} short={() => b.short}/></Card>
        </div>) : <LoadingBlock rows={3}/>}

      <div className="section-title">Brand settings</div>
      <BrandSettings id={id}/>
      {creating ? <NewArticle defaults={{ brand_id: id }} onClose={() => setCreating(false)} onCreated={(aid) => nav(`/blogs/${aid}`)}/> : null}
    </div>);
}
function BrandSettings({ id }) {
    const { brandOf, can, refreshMe } = useApp();
    const s = brandOf(id).settings;
    const [f, setF] = useState(s);
    const [busy, setBusy] = useState(false);
    const toast = useToast();
    useEffect(() => setF(s), [s]);
    const ro = !can('integrations:manage');
    const dirty = JSON.stringify(f) !== JSON.stringify(s);
    const save = async () => {
        setBusy(true);
        try {
            await api.patch(`/brands/${id}`, f);
            toast.ok('Brand settings saved.');
            refreshMe();
        }
        catch (e) {
            toast.error(e);
        }
        finally {
            setBusy(false);
        }
    };
    return (<Card title="Voice and automation" sub={ro ? 'Only admins can change these.' : 'Used by Claude for topic research and drafts. Credentials are not set here — see Integrations.'} actions={!ro ? <Button variant="primary" size="sm" disabled={!dirty} loading={busy} onClick={save}>Save settings</Button> : null}>
      <div className="form-grid">
        <Field label="Brand voice" full><textarea className="textarea" rows={2} value={f.voice} readOnly={ro} onChange={(e) => setF({ ...f, voice: e.target.value })}/></Field>
        <Field label="Audience"><textarea className="textarea" rows={2} value={f.audience} readOnly={ro} onChange={(e) => setF({ ...f, audience: e.target.value })}/></Field>
        <Field label="Never write"><textarea className="textarea" rows={2} value={f.avoid} readOnly={ro} onChange={(e) => setF({ ...f, avoid: e.target.value })}/></Field>
        <Field label="Research focus" full><input className="input" value={f.researchFocus} readOnly={ro} onChange={(e) => setF({ ...f, researchFocus: e.target.value })}/></Field>
        <Field label="Default author"><input className="input" value={f.defaultAuthor} readOnly={ro} onChange={(e) => setF({ ...f, defaultAuthor: e.target.value })}/></Field>
        <div className="row gap-12">
          <Field label="Topics per research run"><input className="input" type="number" min={1} max={15} value={f.topicsPerRun} readOnly={ro} onChange={(e) => setF({ ...f, topicsPerRun: Number(e.target.value) })}/></Field>
          <Field label="Drafts per generation run"><input className="input" type="number" min={1} max={5} value={f.draftsPerRun} readOnly={ro} onChange={(e) => setF({ ...f, draftsPerRun: Number(e.target.value) })}/></Field>
        </div>
      </div>
    </Card>);
}
