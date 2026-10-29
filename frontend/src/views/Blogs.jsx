'use client';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from '../lib/nav';
import { api, useApi, qs, download } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { ARTICLE_STATUS, fmtDate, timeAgo } from '../lib/format';
import { Button, PageHead, ErrorState, StatusPill, LivePill, BrandTag, Empty, RoleTag, Skeleton } from '../components/ui';
import { Dialog, useToast } from '../components/overlays';
import { Icon } from '../components/Icon';
const GROUPS = [
    { key: '', label: 'All', statuses: '' },
    { key: 'drafts', label: 'Drafts', statuses: 'idea,draft,changes_requested' },
    { key: 'review', label: 'In review', statuses: 'in_review' },
    { key: 'approved', label: 'Approved', statuses: 'approved' },
    { key: 'pending', label: 'Pending publish', statuses: 'publish_requested' },
    { key: 'scheduled', label: 'Scheduled', statuses: 'scheduled' },
    { key: 'published', label: 'Published', statuses: 'published' },
    { key: 'failed', label: 'Failed', statuses: 'failed' },
];
const PAGE = 25;
export default function Blogs() {
    const { can, me } = useApp();
    const brand = useBrandParam();
    const [sp, setSp] = useSearchParams();
    const status = sp.get('status') ?? '';
    const live = sp.get('live') ?? '';
    const sort = sp.get('sort') ?? 'updated';
    const dir = sp.get('dir') ?? 'desc';
    const page = Number(sp.get('page') ?? '0');
    const [q, setQ] = useState(sp.get('q') ?? '');
    const [creating, setCreating] = useState(false);
    const nav = useNavigate();
    const toast = useToast();
    useEffect(() => {
        const t = setTimeout(() => update({ q: q || null, page: null }), 250);
        return () => clearTimeout(t);
    }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
    const update = (patch) => {
        const next = new URLSearchParams(sp);
        for (const [k, v] of Object.entries(patch)) {
            if (v === null || v === '')
                next.delete(k);
            else
                next.set(k, v);
        }
        setSp(next, { replace: true });
    };
    const list = useApi(`/articles${qs({ brand, status, live, q: sp.get('q'), sort, dir, limit: PAGE, offset: page * PAGE })}`);
    const counts = useApi(`/articles/counts${qs({ brand })}`);
    const countFor = (statuses) => (counts.data ?? []).filter((c) => !statuses || statuses.split(',').includes(c.status)).reduce((a, c) => a + c.n, 0);
    const sortBy = (k) => update({ sort: k, dir: sort === k && dir === 'desc' ? 'asc' : 'desc', page: null });
    const SortTh = ({ k, children, className = '' }) => (<th className={`sortable ${className}`} onClick={() => sortBy(k)} aria-sort={sort === k ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      {children}{sort === k ? <Icon name={dir === 'asc' ? 'arrowUp' : 'arrowDown'} size="sm"/> : null}
    </th>);
    const exportList = async () => {
        try {
            await download(`/data/export/articles${qs({ brand, status, q: sp.get('q') })}`);
        }
        catch (e) {
            toast.error(e);
        }
    };
    return (<>
      <PageHead title="Blogs" sub="Every article across both stores — drafts, reviews, Shopify drafts and live posts." actions={<>
          <Button icon="download" onClick={exportList}>Export</Button>
          {can('article:write') ? <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>New article</Button> : null}
        </>}/>
      <div className="toolbar">
        <div className="chips" role="group" aria-label="Status">
          {GROUPS.map((g) => (<button key={g.key} className="chip" aria-pressed={status === g.statuses} onClick={() => update({ status: g.statuses || null, page: null })}>
              {g.label}<span className="n">{counts.data ? countFor(g.statuses) : ''}</span>
            </button>))}
        </div>
        <span className="spacer"/>
        <select className="select sm" style={{ width: 'auto' }} value={live} onChange={(e) => update({ live: e.target.value || null, page: null })} aria-label="Live filter">
          <option value="">Live and not live</option>
          <option value="1">Live on storefront</option>
          <option value="0">Not live</option>
        </select>
        <div className="input-icon" style={{ width: 240, maxWidth: '100%' }}>
          <Icon name="search"/>
          <input className="input sm" placeholder="Title, keyword, tag…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search blogs"/>
        </div>
      </div>
      <ErrorState error={list.error} onRetry={list.reload}/>
      <div className="card flush">
        <div className="table-wrap">
          <table className="t">
            <thead>
              <tr>
                <SortTh k="title">Title</SortTh>
                {!brand ? <th className="hide-sm">Brand</th> : null}
                <SortTh k="status">Status</SortTh>
                <th className="hide-md">Next action</th>
                <th className="hide-md">Assignee</th>
                <SortTh k="updated" className="r">Updated</SortTh>
              </tr>
            </thead>
            <tbody>
              {list.loading && !list.data ? Array.from({ length: 6 }, (_, i) => (<tr key={i}><td colSpan={6}><Skeleton h={14} w={`${70 - i * 6}%`}/></td></tr>)) : null}
              {list.data?.rows.map((a) => (<tr key={a.id} className="clickable" onClick={() => nav(`/blogs/${a.id}`)} tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter')
            nav(`/blogs/${a.id}`); }}>
                  <td className="title-cell">
                    <span className="ttl">{a.title}</span>
                    <span className="sub">{a.primary_keyword ? `${a.primary_keyword} · ` : ''}/{a.handle}</span>
                  </td>
                  {!brand ? <td className="hide-sm"><BrandTag id={a.brand_id} brands={me.brands}/></td> : null}
                  <td>
                    <div className="row-wrap gap-4">
                      <StatusPill status={a.status}/>
                      <LivePill live={a.shopify_published} differs={a.live_differs}/>
                      {a.has_shopify_draft ? <span className="pill outline" title="Saved to Shopify as a hidden draft">Shopify draft</span> : null}
                    </div>
                  </td>
                  <td className="hide-md">
                    <div className="small">{a.next_action.label}</div>
                    <RoleTag role={a.next_action.role}/>
                  </td>
                  <td className="hide-md small">{a.assignee_name ?? <span className="faint">Unassigned</span>}</td>
                  <td className="r small nowrap" title={fmtDate(a.updated_at)}>{timeAgo(a.updated_at)}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
        {list.data && !list.data.rows.length ? (<Empty icon="blogs" title={sp.toString() ? 'No articles match these filters' : 'No articles yet'} action={sp.toString() ? <Button onClick={() => { setQ(''); setSp(new URLSearchParams(), { replace: true }); }}>Clear filters</Button> : null}>
            {sp.toString() ? 'Try another status or search term.' : 'Run Performance tracking under Automation to pull in live articles from both storefronts, or start a new article.'}
          </Empty>) : null}
        {list.data && list.data.total > PAGE ? (<div className="card-foot">
            <span>{page * PAGE + 1}–{Math.min((page + 1) * PAGE, list.data.total)} of {list.data.total}</span>
            <span className="spacer"/>
            <Button size="sm" icon="chevronLeft" disabled={page === 0} onClick={() => update({ page: String(page - 1) })}>Previous</Button>
            <Button size="sm" disabled={(page + 1) * PAGE >= list.data.total} onClick={() => update({ page: String(page + 1) })}>Next <Icon name="chevronRight" size="sm"/></Button>
          </div>) : null}
      </div>
      {creating ? <NewArticle onClose={() => setCreating(false)} onCreated={(id) => nav(`/blogs/${id}`)}/> : null}
    </>);
}
export function NewArticle({ onClose, onCreated, defaults }) {
    const { me, brand } = useApp();
    const [form, setForm] = useState({ brand_id: defaults?.brand_id ?? (brand === 'all' ? 'ridhi' : brand), title: '', primary_keyword: '' });
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState('');
    const submit = async () => {
        setBusy(true);
        setErr('');
        try {
            const a = await api.post('/articles', { ...form, author: me.brands.find((b) => b.id === form.brand_id)?.settings.defaultAuthor });
            onCreated(a.id);
        }
        catch (e) {
            setErr(e.message);
        }
        finally {
            setBusy(false);
        }
    };
    return (<Dialog title="New article" sub="Starts as an idea. Nothing is sent to Shopify." onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={!form.title.trim()} onClick={submit}>Create</Button></>}>
      <div className="col gap-12">
        <div className="field">
          <label>Brand</label>
          <div className="seg" role="group">
            {me.brands.map((b) => <button key={b.id} aria-pressed={form.brand_id === b.id} onClick={() => setForm({ ...form, brand_id: b.id })}><span className={`brand-dot ${b.id}`}/>{b.name}</button>)}
          </div>
        </div>
        <div className="field"><label htmlFor="na-t">Title</label><input id="na-t" data-autofocus className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="How to style a block-print tablecloth for winter"/></div>
        <div className="field"><label htmlFor="na-k">Primary keyword</label><input id="na-k" className="input" value={form.primary_keyword} onChange={(e) => setForm({ ...form, primary_keyword: e.target.value })} placeholder="block print tablecloth"/></div>
        {err ? <div className="callout crit"><Icon name="alert"/>{err}</div> : null}
      </div>
    </Dialog>);
}
export { ARTICLE_STATUS };
