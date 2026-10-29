import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, useApi, qs, download } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtDate, fmtInt, timeAgo } from '../lib/format';
import type { BrandId, Topic } from '../lib/types';
import { BrandTag, Button, Empty, ErrorState, Field, PageHead, Pill, Skeleton, Tabs } from '../components/ui';
import { Dialog, useToast } from '../components/overlays';
import { Icon } from '../components/Icon';

const TOPIC_TONE: Record<string, string> = { proposed: 'neutral', validated: 'info', approved: 'ok', rejected: 'crit', in_production: 'accent', published: 'ok' };
const INTENTS = ['informational', 'commercial', 'transactional', 'navigational'];

export default function Topics() {
  const [sp, setSp] = useSearchParams();
  const tab = sp.get('tab') === 'keywords' ? 'keywords' : 'topics';
  return (
    <>
      <PageHead title="Topics & keywords" sub="Ideas move from proposed → validated (keyword data checked) → approved → in production. Volumes come only from imported keyword data or Search Console — never estimated." />
      <Tabs value={tab} onChange={(t) => { const n = new URLSearchParams(); if (t === 'keywords') n.set('tab', 'keywords'); setSp(n, { replace: true }); }}
        tabs={[{ key: 'topics', label: <><Icon name="topics" size="sm" />Topics</> }, { key: 'keywords', label: <><Icon name="target" size="sm" />Keyword data</> }]} />
      {tab === 'topics' ? <TopicList /> : <KeywordList />}
    </>
  );
}

function TopicList() {
  const brand = useBrandParam();
  const { can, me } = useApp();
  const [sp, setSp] = useSearchParams();
  const status = sp.get('status') ?? '';
  const missing = sp.get('missing') ?? '';
  const focus = Number(sp.get('focus')) || null;
  const [q, setQ] = useState('');
  const list = useApi<Topic[]>(`/topics${qs({ brand, status, missing, q })}`);
  const [editing, setEditing] = useState<Topic | 'new' | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const toast = useToast();
  const nav = useNavigate();

  useEffect(() => {
    if (focus && list.data) {
      const t = list.data.find((x) => x.id === focus);
      if (t) setEditing(t);
    }
  }, [focus, list.data]);

  const decide = async (t: Topic, decision: 'approve' | 'reject' | 'reopen') => {
    setBusy(`${t.id}-${decision}`);
    try { await api.post(`/topics/${t.id}/decision`, { decision }); toast.ok(decision === 'approve' ? 'Topic approved.' : decision === 'reject' ? 'Topic rejected.' : 'Topic reopened.'); list.reload(); } catch (e) { toast.error(e); } finally { setBusy(null); }
  };
  const start = async (t: Topic, mode: 'blank' | 'claude') => {
    setBusy(`${t.id}-${mode}`);
    try {
      const r = await api.post<{ articleId: number }>(`/topics/${t.id}/article`, { mode });
      toast.ok(mode === 'claude' ? 'Claude wrote a first draft.' : 'Article started.');
      nav(`/blogs/${r.articleId}`);
    } catch (e) { toast.error(e); } finally { setBusy(null); }
  };
  const statuses = ['', 'proposed', 'validated', 'approved', 'in_production', 'rejected'];
  const setFilter = (k: string, v: string) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); n.delete('focus'); setSp(n, { replace: true }); };

  return (
    <>
      <div className="toolbar">
        <div className="chips">
          {statuses.map((s) => <button key={s} className="chip" aria-pressed={status === s} onClick={() => setFilter('status', s)}>{s ? s.replace('_', ' ') : 'All'}</button>)}
          <button className="chip" aria-pressed={missing === 'volume'} onClick={() => setFilter('missing', missing ? '' : 'volume')}>No volume data</button>
        </div>
        <span className="spacer" />
        <div className="input-icon" style={{ width: 220 }}><Icon name="search" /><input className="input sm" placeholder="Search topics" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Button size="sm" icon="download" onClick={() => download(`/data/export/topics${qs({ brand, status })}`).catch(toast.error)}>Export</Button>
        {can('topic:write') ? <Button size="sm" variant="primary" icon="plus" onClick={() => setEditing('new')}>New topic</Button> : null}
      </div>
      <ErrorState error={list.error} onRetry={list.reload} />
      <div className="card flush">
        <div className="table-wrap">
          <table className="t">
            <thead>
              <tr>
                <th>Topic</th>{!brand ? <th className="hide-sm">Brand</th> : null}<th className="hide-md">Intent</th><th className="r">Volume</th><th className="r hide-sm">KD</th><th>Status</th><th className="hide-md">Validation</th><th className="r">Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.loading && !list.data ? Array.from({ length: 5 }, (_, i) => <tr key={i}><td colSpan={8}><Skeleton h={14} w={`${70 - i * 8}%`} /></td></tr>) : null}
              {list.data?.map((t) => (
                <tr key={t.id} style={focus === t.id ? { background: 'var(--accent-soft)' } : undefined}>
                  <td className="title-cell">
                    <a href="#" className="ttl" onClick={(e) => { e.preventDefault(); setEditing(t); }}>{t.title}</a>
                    <span className="sub">{t.primary_keyword}{t.secondary_keywords ? ` · ${t.secondary_keywords}` : ''}</span>
                  </td>
                  {!brand ? <td className="hide-sm"><BrandTag id={t.brand_id} brands={me.brands} /></td> : null}
                  <td className="hide-md small">{t.intent}</td>
                  <td className="r">{t.search_volume != null ? <span title={t.volume_source ?? ''}>{fmtInt(t.search_volume)}</span> : <span className="faint" title="No keyword-tool data imported">—</span>}</td>
                  <td className="r hide-sm">{t.keyword_difficulty ?? <span className="faint">—</span>}</td>
                  <td><div className="row-wrap gap-4"><Pill tone={TOPIC_TONE[t.status] ?? 'neutral'} dot>{t.status.replace('_', ' ')}</Pill>{t.source === 'claude' ? <span className="pill outline" title="Proposed by Claude"><Icon name="sparkle" size="sm" /></span> : null}</div></td>
                  <td className="hide-md small" style={{ maxWidth: 300 }}><span className="muted" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{t.validation_note || '—'}</span></td>
                  <td className="r">
                    <div className="row" style={{ justifyContent: 'flex-end' }}>
                      {can('topic:decide') && ['proposed', 'validated'].includes(t.status) ? (
                        <>
                          <Button size="xs" icon="check" loading={busy === `${t.id}-approve`} onClick={() => decide(t, 'approve')}>Approve</Button>
                          <Button size="xs" variant="ghost" icon="x" aria-label="Reject" loading={busy === `${t.id}-reject`} onClick={() => decide(t, 'reject')} />
                        </>
                      ) : null}
                      {t.status === 'rejected' && can('topic:decide') ? <Button size="xs" variant="ghost" onClick={() => decide(t, 'reopen')}>Reopen</Button> : null}
                      {t.status === 'approved' && !t.article_id ? (
                        <>
                          {can('workflow:run') ? <Button size="xs" icon="sparkle" loading={busy === `${t.id}-claude`} onClick={() => start(t, 'claude')} title="Claude writes a first draft">Draft with Claude</Button> : null}
                          {can('article:write') ? <Button size="xs" variant="ghost" loading={busy === `${t.id}-blank`} onClick={() => start(t, 'blank')}>Blank</Button> : null}
                        </>
                      ) : null}
                      {t.article_id ? <Link className="btn xs ghost" to={`/blogs/${t.article_id}`}>Article <Icon name="arrowRight" size="sm" /></Link> : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {list.data && !list.data.length ? (
          <Empty icon="topics" title="No topics here" action={can('topic:write') ? <Button variant="primary" icon="plus" onClick={() => setEditing('new')}>New topic</Button> : null}>
            Run Topic research under Automation to have Claude propose ideas, import a topics workbook, or add one by hand.
          </Empty>
        ) : null}
      </div>
      {editing ? <TopicDialog topic={editing === 'new' ? null : editing} onClose={() => { setEditing(null); if (focus) setFilter('focus', ''); }} onSaved={() => { setEditing(null); list.reload(); }} /> : null}
    </>
  );
}

function TopicDialog({ topic, onClose, onSaved }: { topic: Topic | null; onClose: () => void; onSaved: () => void }) {
  const { me, brand, can } = useApp();
  const [f, setF] = useState({
    brand_id: (topic?.brand_id ?? (brand === 'all' ? 'ridhi' : brand)) as BrandId,
    title: topic?.title ?? '', primary_keyword: topic?.primary_keyword ?? '', secondary_keywords: topic?.secondary_keywords ?? '',
    intent: topic?.intent ?? 'informational', search_volume: topic?.search_volume?.toString() ?? '', keyword_difficulty: topic?.keyword_difficulty?.toString() ?? '',
    volume_source: topic?.volume_source ?? '', notes: topic?.notes ?? '',
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const ro = !can('topic:write');
  const save = async () => {
    setBusy(true); setErr('');
    try {
      if (topic) await api.patch(`/topics/${topic.id}`, f); else await api.post('/topics', f);
      onSaved();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <Dialog wide title={topic ? 'Topic' : 'New topic'} sub={topic ? <>Source: {topic.source} · updated {timeAgo(topic.updated_at)}</> : 'Duplicates are refused: one topic per primary keyword per brand.'} onClose={onClose}
      footer={ro ? <Button onClick={onClose}>Close</Button> : <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={!f.title.trim() || !f.primary_keyword.trim()} onClick={save}>{topic ? 'Save' : 'Add topic'}</Button></>}>
      <div className="form-grid">
        {!topic ? (
          <div className="field full"><label>Brand</label>
            <div className="seg">{me.brands.map((b) => <button key={b.id} aria-pressed={f.brand_id === b.id} onClick={() => set('brand_id', b.id)}><span className={`brand-dot ${b.id}`} />{b.name}</button>)}</div>
          </div>
        ) : null}
        <Field label="Working title" full><input className="input" data-autofocus value={f.title} onChange={(e) => set('title', e.target.value)} readOnly={ro} /></Field>
        <Field label="Primary keyword" hint={topic && ['validated', 'approved'].includes(topic.status) ? 'Changing it sends the topic back through validation.' : undefined}><input className="input" value={f.primary_keyword} onChange={(e) => set('primary_keyword', e.target.value)} readOnly={ro} /></Field>
        <Field label="Intent"><select className="select" value={f.intent} onChange={(e) => set('intent', e.target.value)} disabled={ro}>{INTENTS.map((i) => <option key={i}>{i}</option>)}</select></Field>
        <Field label="Secondary keywords" full hint="Comma-separated"><input className="input" value={f.secondary_keywords} onChange={(e) => set('secondary_keywords', e.target.value)} readOnly={ro} /></Field>
        <Field label="Monthly search volume" hint="From your keyword tool; leave blank if unknown"><input className="input" inputMode="numeric" value={f.search_volume} onChange={(e) => set('search_volume', e.target.value.replace(/\D/g, ''))} readOnly={ro} /></Field>
        <Field label="Keyword difficulty (0–100)"><input className="input" inputMode="numeric" value={f.keyword_difficulty} onChange={(e) => set('keyword_difficulty', e.target.value.replace(/\D/g, '').slice(0, 3))} readOnly={ro} /></Field>
        <Field label="Volume source" hint="e.g. Semrush, Ahrefs — and the date"><input className="input" value={f.volume_source} onChange={(e) => set('volume_source', e.target.value)} readOnly={ro} /></Field>
        <Field label="Brief / notes" full><textarea className="textarea" value={f.notes} onChange={(e) => set('notes', e.target.value)} readOnly={ro} /></Field>
        {topic?.rationale ? <div className="field full"><label>Why Claude proposed it</label><div className="small muted">{topic.rationale}</div></div> : null}
        {topic?.validation_note ? <div className="field full"><label>Validation</label><div className="callout info"><Icon name="info" />{topic.validation_note}</div></div> : null}
      </div>
      {err ? <div className="callout crit mt-12"><Icon name="alert" />{err}</div> : null}
    </Dialog>
  );
}

function KeywordList() {
  const brand = useBrandParam();
  const { can, me } = useApp();
  const list = useApi<any[]>(`/keywords${qs({ brand })}`);
  const [adding, setAdding] = useState(false);
  const toast = useToast();
  return (
    <>
      <div className="callout info mb-12"><Icon name="info" /><div>Keyword volumes cannot be fetched from Google's APIs without an Ads account, so they live here as <b>manually imported</b> data. Import a workbook from your keyword tool in <Link to="/data">Data &amp; reports</Link>. Rows older than 6 months are flagged.</div></div>
      <div className="toolbar">
        <span className="muted small">{list.data ? `${list.data.length} keywords` : ''}</span>
        <span className="spacer" />
        <Button size="sm" icon="download" onClick={() => download(`/data/export/keywords${qs({ brand })}`).catch(toast.error)}>Export</Button>
        {can('topic:write') ? <Button size="sm" variant="primary" icon="plus" onClick={() => setAdding(true)}>Add keyword</Button> : null}
      </div>
      <ErrorState error={list.error} onRetry={list.reload} />
      <div className="card flush">
        <div className="table-wrap">
          <table className="t">
            <thead><tr><th>Keyword</th>{!brand ? <th>Brand</th> : null}<th className="r">Volume</th><th className="r">KD</th><th className="hide-sm">Intent</th><th className="hide-sm">Source</th><th>Data date</th></tr></thead>
            <tbody>
              {list.data?.map((k) => {
                const stale = k.source_date && Date.now() - Date.parse(k.source_date) > 180 * 86400000;
                return (
                  <tr key={k.id}>
                    <td className="strong">{k.keyword}</td>
                    {!brand ? <td><BrandTag id={k.brand_id} brands={me.brands} /></td> : null}
                    <td className="r">{fmtInt(k.search_volume)}</td>
                    <td className="r">{k.keyword_difficulty ?? '—'}</td>
                    <td className="hide-sm small">{k.intent ?? '—'}</td>
                    <td className="hide-sm small">{k.source_tool} <span className="source excel"><span className="sw" />{k.source}</span></td>
                    <td className="small">{fmtDate(k.source_date)}{stale ? <Pill tone="warn">stale</Pill> : null}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {list.data && !list.data.length ? <Empty icon="target" title="No keyword data yet">Download the keywords template from Data &amp; reports, fill it from your keyword tool and import it.</Empty> : null}
      </div>
      {adding ? <KeywordDialog onClose={() => setAdding(false)} onSaved={() => { setAdding(false); list.reload(); }} /> : null}
    </>
  );
}

function KeywordDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { me, brand } = useApp();
  const [f, setF] = useState({ brand_id: brand === 'all' ? 'ridhi' : brand, keyword: '', search_volume: '', keyword_difficulty: '', intent: '', source_tool: '', source_date: new Date().toISOString().slice(0, 10) });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const save = async () => { setBusy(true); setErr(''); try { await api.post('/keywords', f); onSaved(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <Dialog title="Add keyword" onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={!f.keyword.trim() || !f.source_tool.trim()} onClick={save}>Add</Button></>}>
      <div className="form-grid">
        <div className="field full"><label>Brand</label><div className="seg">{me.brands.map((b) => <button key={b.id} aria-pressed={f.brand_id === b.id} onClick={() => set('brand_id', b.id)}><span className={`brand-dot ${b.id}`} />{b.short}</button>)}</div></div>
        <Field label="Keyword" full><input className="input" data-autofocus value={f.keyword} onChange={(e) => set('keyword', e.target.value)} /></Field>
        <Field label="Monthly volume"><input className="input" inputMode="numeric" value={f.search_volume} onChange={(e) => set('search_volume', e.target.value.replace(/\D/g, ''))} /></Field>
        <Field label="Difficulty"><input className="input" inputMode="numeric" value={f.keyword_difficulty} onChange={(e) => set('keyword_difficulty', e.target.value.replace(/\D/g, '').slice(0, 3))} /></Field>
        <Field label="Source tool"><input className="input" value={f.source_tool} onChange={(e) => set('source_tool', e.target.value)} placeholder="Semrush" /></Field>
        <Field label="Data date"><input type="date" className="input" value={f.source_date} onChange={(e) => set('source_date', e.target.value)} /></Field>
      </div>
      {err ? <div className="callout crit mt-12"><Icon name="alert" />{err}</div> : null}
    </Dialog>
  );
}
