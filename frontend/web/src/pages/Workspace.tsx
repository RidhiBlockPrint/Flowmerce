import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, useApi, qs } from '../lib/api';
import { useApp } from '../lib/app';
import { fmtDate, timeAgo } from '../lib/format';
import type { Article, BrandId, Topic } from '../lib/types';
import { Button, Card, ErrorState, Field, LivePill, LoadingBlock, Pill, RoleTag } from '../components/ui';
import { useToast } from '../components/overlays';
import { Icon } from '../components/Icon';
import { GscKpis, Ga4Kpis } from '../components/metrics';
import { NewArticle } from './Blogs';

const COLUMNS: { key: string; label: string; statuses: string[] }[] = [
  { key: 'ideas', label: 'Ideas & drafts', statuses: ['idea', 'draft', 'changes_requested'] },
  { key: 'review', label: 'In review', statuses: ['in_review'] },
  { key: 'approved', label: 'Approved', statuses: ['approved'] },
  { key: 'publishing', label: 'Publishing', statuses: ['publish_requested', 'scheduled', 'failed'] },
  { key: 'live', label: 'Published', statuses: ['published'] },
];

export default function Workspace() {
  const { brand: param } = useParams();
  const { me, brandOf, range, setBrand, can } = useApp();
  const nav = useNavigate();
  const valid = me.brands.some((b) => b.id === param);
  const id = (valid ? param : 'ridhi') as BrandId;
  const b = brandOf(id);
  useEffect(() => { if (valid) setBrand(id); }, [id, valid, setBrand]);
  const arts = useApi<{ rows: Article[]; total: number }>(`/articles${qs({ brand: id, limit: 300, sort: 'updated' })}`);
  const topics = useApi<Topic[]>(`/topics${qs({ brand: id })}`);
  const ov = useApi<any>(`/overview${qs({ brand: id, from: range.from, to: range.to })}`);
  const [creating, setCreating] = useState(false);
  if (!valid) return <ErrorState error={new Error('Unknown brand workspace.')} />;
  const bo = ov.data?.brands?.[0];

  return (
    <div data-brand={id}>
      <section className={`card brand-card ${id}`} style={{ marginBottom: 16, overflow: 'hidden' }}>
        <div style={{ background: id === 'ridhi' ? 'var(--ridhi)' : '#1e1a17', color: '#fff', fontSize: 11.5, fontWeight: 650, letterSpacing: '0.06em', padding: '6px 18px', textTransform: 'uppercase' }}>
          {id === 'ridhi' ? 'Handcrafted block print home decor' : 'Hand printed fabric, made by artisans'}
        </div>
        <div className="card-body row-wrap" style={{ gap: 16, alignItems: 'flex-end' }}>
          <div style={{ minWidth: 0 }}>
            <h1 className="page-title" style={{ fontSize: 30, color: id === 'ridhi' ? 'var(--ridhi)' : 'var(--ink)' }}>{b.name}</h1>
            <div className="row-wrap small muted mt-4">
              <a href={b.storefrontUrl} target="_blank" rel="noopener">{b.storefrontUrl.replace('https://', '')} <Icon name="external" size="sm" /></a>
              <span>·</span><span className="mono">{b.shopDomain}</span>
              <span>·</span><a href={b.blogUrl} target="_blank" rel="noopener">/blogs/{b.blogHandle}</a>
            </div>
          </div>
          <div className="page-actions">
            <Link className="btn" to="/automation"><Icon name="automation" />Automation</Link>
            {can('article:write') ? <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>New article</Button> : null}
          </div>
        </div>
        <div className="card-foot">
          <span className="row gap-4"><span className="sev" style={{ marginTop: 0, background: b.configured.shopifyAdmin ? 'var(--ok)' : 'var(--saffron)' }} />Shopify Admin {b.configured.shopifyAdmin ? 'connected' : 'pending setup (public feed in use)'}</span>
          <span className="row gap-4"><span className="sev" style={{ marginTop: 0, background: b.configured.gsc ? 'var(--ok)' : 'var(--saffron)' }} />Search Console {b.configured.gsc ? 'configured' : 'pending setup'}</span>
          <span className="row gap-4"><span className="sev" style={{ marginTop: 0, background: b.configured.ga4 ? 'var(--ok)' : 'var(--saffron)' }} />GA4 {b.configured.ga4 ? 'configured' : 'pending setup'}</span>
        </div>
      </section>

      <div className="section-title">Blog pipeline <span className="faint">{arts.data ? `${arts.data.total} articles` : ''}</span></div>
      <ErrorState error={arts.error} onRetry={arts.reload} />
      {arts.loading && !arts.data ? <LoadingBlock /> : (
        <div className="board">
          {COLUMNS.map((c) => {
            const items = (arts.data?.rows ?? []).filter((a) => c.statuses.includes(a.status));
            return (
              <div key={c.key} className="board-col">
                <div className="board-col-head">{c.label}<span className="faint">{items.length}</span></div>
                {items.slice(0, 12).map((a) => (
                  <Link key={a.id} to={`/blogs/${a.id}`} className="board-card">
                    <span className="t1">{a.title}</span>
                    <span className="row-wrap gap-4">
                      {c.key === 'publishing' || c.key === 'ideas' ? <span className="pill neutral" style={{ height: 20 }}>{a.status.replace('_', ' ')}</span> : null}
                      <LivePill live={a.shopify_published} differs={a.live_differs} />
                    </span>
                    <span className="row xs muted"><RoleTag role={a.next_action.role} /><span className="spacer" />{timeAgo(a.updated_at)}</span>
                  </Link>
                ))}
                {items.length > 12 ? <Link className="btn ghost sm" to={`/blogs?status=${c.statuses.join(',')}`}>+{items.length - 12} more</Link> : null}
                {!items.length ? <div className="faint xs" style={{ padding: '6px 4px' }}>Empty</div> : null}
              </div>
            );
          })}
          <div className="board-col">
            <div className="board-col-head">Topics queue<span className="faint">{topics.data?.filter((t) => ['proposed', 'validated', 'approved'].includes(t.status)).length ?? ''}</span></div>
            {(topics.data ?? []).filter((t) => ['validated', 'approved', 'proposed'].includes(t.status)).slice(0, 8).map((t) => (
              <Link key={t.id} to={`/topics?focus=${t.id}`} className="board-card">
                <span className="t1">{t.title}</span>
                <span className="row xs"><Pill tone={t.status === 'approved' ? 'ok' : t.status === 'validated' ? 'info' : 'neutral'}>{t.status}</Pill><span className="muted ellipsis">{t.primary_keyword}</span></span>
              </Link>
            ))}
            <Link className="btn ghost sm" to="/topics">All topics</Link>
          </div>
        </div>
      )}

      <div className="section-title">Search & traffic · {fmtDate(range.from)} – {fmtDate(range.to)}</div>
      {bo ? (
        <div className="grid cols-2">
          <Card title="Search Console"><GscKpis parts={[{ brand: id, ...bo.gsc }]} short={() => b.short} /></Card>
          <Card title="GA4"><Ga4Kpis parts={[{ brand: id, ...bo.ga4 }]} short={() => b.short} /></Card>
        </div>
      ) : <LoadingBlock rows={3} />}

      <div className="section-title">Brand settings</div>
      <BrandSettings id={id} />
      {creating ? <NewArticle defaults={{ brand_id: id }} onClose={() => setCreating(false)} onCreated={(aid) => nav(`/blogs/${aid}`)} /> : null}
    </div>
  );
}

function BrandSettings({ id }: { id: BrandId }) {
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
    try { await api.patch(`/brands/${id}`, f); toast.ok('Brand settings saved.'); refreshMe(); } catch (e) { toast.error(e); } finally { setBusy(false); }
  };
  return (
    <Card title="Voice and automation" sub={ro ? 'Only admins can change these.' : 'Used by Claude for topic research and drafts. Credentials are not set here — see Integrations.'}
      actions={!ro ? <Button variant="primary" size="sm" disabled={!dirty} loading={busy} onClick={save}>Save settings</Button> : null}>
      <div className="form-grid">
        <Field label="Brand voice" full><textarea className="textarea" rows={2} value={f.voice} readOnly={ro} onChange={(e) => setF({ ...f, voice: e.target.value })} /></Field>
        <Field label="Audience"><textarea className="textarea" rows={2} value={f.audience} readOnly={ro} onChange={(e) => setF({ ...f, audience: e.target.value })} /></Field>
        <Field label="Never write"><textarea className="textarea" rows={2} value={f.avoid} readOnly={ro} onChange={(e) => setF({ ...f, avoid: e.target.value })} /></Field>
        <Field label="Research focus" full><input className="input" value={f.researchFocus} readOnly={ro} onChange={(e) => setF({ ...f, researchFocus: e.target.value })} /></Field>
        <Field label="Default author"><input className="input" value={f.defaultAuthor} readOnly={ro} onChange={(e) => setF({ ...f, defaultAuthor: e.target.value })} /></Field>
        <div className="row gap-12">
          <Field label="Topics per research run"><input className="input" type="number" min={1} max={15} value={f.topicsPerRun} readOnly={ro} onChange={(e) => setF({ ...f, topicsPerRun: Number(e.target.value) })} /></Field>
          <Field label="Drafts per generation run"><input className="input" type="number" min={1} max={5} value={f.draftsPerRun} readOnly={ro} onChange={(e) => setF({ ...f, draftsPerRun: Number(e.target.value) })} /></Field>
        </div>
      </div>
    </Card>
  );
}
