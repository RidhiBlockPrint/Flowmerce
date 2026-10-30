'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useNavigate } from '../lib/nav';
import { Icon, LogoMark } from './Icon';
import { Button, Menu, BrandTag } from './ui';
import { Dialog, Drawer } from './overlays';
import { api, useApi, qs } from '../lib/api';
import { useApp, presetRange } from '../lib/app';
import { fmtDate, timeAgo } from '../lib/format';
import { isSeoPath } from '../lib/routes';
export function Shell({ children }) {
    const { me, can, brand } = useApp();
    const [navOpen, setNavOpen] = useState(false);
    const [tasksOpen, setTasksOpen] = useState(false);
    const loc = { pathname: usePathname() ?? '/' };
    const inSeo = isSeoPath(loc.pathname);
    // Tasks are SEO & Blog work for the signed-in role, so they only matter on SEO pages and on Home.
    // /publishing only feeds the SEO sidebar count. Neither request is made anywhere else (a null path skips the request).
    const showTasks = inSeo || loc.pathname === '/';
    useEffect(() => { setNavOpen(false); setTasksOpen(false); }, [loc.pathname]);
    const counts = useApi(inSeo ? `/publishing${qs({ brand: brand === 'all' ? undefined : brand })}` : null);
    const tasks = useApi(showTasks ? '/tasks' : null);
    const lastPath = useRef(loc.pathname);
    useEffect(() => {
        // Refresh after moving between pages of an area that is already loaded; entering an area fetches by itself.
        const was = lastPath.current;
        lastPath.current = loc.pathname;
        if (was === loc.pathname)
            return;
        if (inSeo && isSeoPath(was))
            counts.reload();
        if (showTasks && (isSeoPath(was) || was === '/'))
            tasks.reload();
    }, [loc.pathname]); // eslint-disable-line react-hooks/exhaustive-deps
    const pendingPublish = counts.data?.requests.filter((r) => r.status === 'pending' || r.status === 'failed').length ?? 0;
    return (<>
      <a className="skip-link" href="#main">Skip to content</a>
      {me.demoLoaded ? <div className="banner-demo">Demo analytics fixtures are loaded — figures marked “Demo” are synthetic, not business data</div> : null}
      <div className="shell">
        {navOpen ? <div className="sidebar-scrim" onClick={() => setNavOpen(false)}/> : null}
        <aside className={`sidebar ${navOpen ? 'open' : ''}`} aria-label="Main navigation">
          <Link href="/" className="logo">
            <LogoMark />
            <span>
              <span className="logo-text">Flowmerce</span>
              <span className="logo-sub" style={{ display: 'block' }}>Ecommerce in a Flow</span>
            </span>
          </Link>
          <nav>
            <NavItem to="/" icon="home" end>Home</NavItem>
            <div className="nav-group">
              <div className="nav-label">SEO &amp; Blog</div>
              <Link href="/seo" className={`nav-item entry ${inSeo ? 'active' : ''}`} aria-current={loc.pathname === '/seo' ? 'page' : undefined} title="Help customers discover us through organic search and AI-assisted search.">
                <Icon name="blogs"/><span className="nav-text">SEO &amp; Blog Content</span>
              </Link>
              {inSeo ? (<div className="nav-sub" role="group" aria-label="SEO & Blog Content pages">
                  {me.brands.map((b) => (<NavItem key={b.id} to={`/workspace/${b.id}`}>
                      <span className={`brand-dot ${b.id}`} style={{ margin: '0 4px' }}/>{b.name}
                    </NavItem>))}
                  <NavItem to="/blogs" icon="blogs">Blogs</NavItem>
                  <NavItem to="/topics" icon="topics">Topics &amp; keywords</NavItem>
                  <NavItem to="/publishing" icon="publish" count={pendingPublish} alert={counts.data?.requests.some((r) => r.status === 'failed')}>Publishing</NavItem>
                  <NavItem to="/analytics" icon="analytics">SEO &amp; traffic</NavItem>
                  <NavItem to="/automation" icon="automation">Automation</NavItem>
                  <NavItem to="/data" icon="sheet">Data &amp; reports</NavItem>
                  <NavItem to="/integrations" icon="plug">Integrations</NavItem>
                  {can('audit:view') ? <NavItem to="/audit" icon="audit">Audit log</NavItem> : null}
                </div>) : null}
            </div>
          </nav>
          <div className="sidebar-foot">
            <LocalOperatorBadge />
          </div>
        </aside>
        <div className="main">
          <header className="topbar">
            <Button className="menu-btn" variant="ghost" iconOnly icon="menu" aria-label="Open navigation" onClick={() => setNavOpen(true)}/>
            <BrandSwitch />
            {inSeo ? <GlobalSearch /> : null}
            <div className="row" style={{ marginLeft: 'auto' }}>
              {inSeo ? <RangePicker /> : null}
              {showTasks ? (<Button variant="ghost" icon="tasks" onClick={() => setTasksOpen(true)} aria-label={`My tasks (${tasks.data?.length ?? 0})`}>
                  <span className="hide-sm">Tasks</span>
                  {tasks.data?.length ? <span className="pill accent" style={{ height: 18, padding: '0 6px' }}>{tasks.data.length}</span> : null}
                </Button>) : null}
            </div>
          </header>
          <main className="content" id="main" tabIndex={-1}>
            {loc.pathname !== '/' ? <div className="page-back"><BackButton /></div> : null}
            {children}
          </main>
        </div>
      </div>
      {tasksOpen && showTasks ? <TasksDrawer tasks={tasks.data ?? []} loading={tasks.loading} onClose={() => setTasksOpen(false)}/> : null}
    </>);
}
/** Goes back one page; when this tab has no earlier page (opened directly), goes to the parent section or Home. */
function BackButton() {
    const router = useRouter();
    const pathname = usePathname() ?? '/';
    const back = () => {
        if (window.history.length > 1)
            router.back();
        else
            router.push(pathname.split('/').length > 2 ? `/${pathname.split('/')[1] === 'workspace' ? 'seo' : pathname.split('/')[1]}` : '/');
    };
    return <Button variant="ghost" size="sm" icon="chevronLeft" onClick={back} aria-label="Go back" title="Back to the previous page">Back</Button>;
}
function NavItem({ to, icon, children, count, alert, end }) {
    const pathname = usePathname() ?? '/';
    const active = end ? pathname === to : pathname === to || pathname.startsWith(`${to}/`);
    return (<Link href={to} className={`nav-item ${active ? 'active' : ''}`} aria-current={active ? 'page' : undefined}>
      {icon ? <Icon name={icon}/> : null}
      {children}
      {count ? <span className={`count ${alert ? 'alert' : ''}`}>{count}</span> : null}
    </Link>);
}
function BrandSwitch() {
    const { brand, setBrand, me } = useApp();
    const opts = [{ key: 'all', label: 'All' }, ...me.brands.map((b) => ({ key: b.id, label: b.short }))];
    return (<div className="seg" role="group" aria-label="Brand">
      {opts.map((o) => (<button key={o.key} aria-pressed={brand === o.key} onClick={() => setBrand(o.key)}>
          {o.key !== 'all' ? <span className={`brand-dot ${o.key}`}/> : null}
          {o.label}
        </button>))}
    </div>);
}
function RangePicker() {
    const { range, setRange } = useApp();
    const [custom, setCustom] = useState(false);
    const presets = [['7d', 'Last 7 days'], ['28d', 'Last 28 days'], ['3m', 'Last 3 months'], ['6m', 'Last 6 months'], ['12m', 'Last 12 months']];
    const label = range.preset === 'custom' ? `${fmtDate(range.from, { day: 'numeric', month: 'short' })} – ${fmtDate(range.to, { day: 'numeric', month: 'short' })}` : presets.find((p) => p[0] === range.preset)?.[1] ?? 'Range';
    return (<>
      <Menu trigger={(toggle) => (<Button variant="secondary" size="sm" icon="calendar" onClick={toggle} title={`${range.from} to ${range.to} (Search Console data is final ~3 days after the day)`}>
          <span className="hide-sm">{label}</span>
        </Button>)}>
        {(close) => (<>
            {presets.map(([k, l]) => (<button key={k} className="menu-item" onClick={() => { setRange(presetRange(k)); close(); }}>
                {range.preset === k ? <Icon name="check" size="sm"/> : <span style={{ width: 14 }}/>}{l}
              </button>))}
            <div className="menu-sep"/>
            <button className="menu-item" onClick={() => { setCustom(true); close(); }}><Icon name="calendar" size="sm"/>Custom range…</button>
            <div className="muted xs" style={{ padding: '6px 10px', maxWidth: 220 }}>Ranges end 3 days ago, when Search Console data is final.</div>
          </>)}
      </Menu>
      {custom ? <CustomRange onClose={() => setCustom(false)}/> : null}
    </>);
}
function CustomRange({ onClose }) {
    const { range, setRange } = useApp();
    const [from, setFrom] = useState(range.from);
    const [to, setTo] = useState(range.to);
    const bad = !from || !to || from > to;
    return (<Dialog title="Custom date range" onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={bad} onClick={() => { setRange({ from, to, preset: 'custom' }); onClose(); }}>Apply</Button></>}>
      <div className="form-grid">
        <div className="field"><label htmlFor="rf">From</label><input id="rf" type="date" className="input" value={from} max={to} onChange={(e) => setFrom(e.target.value)}/></div>
        <div className="field"><label htmlFor="rt">To</label><input id="rt" type="date" className="input" value={to} min={from} onChange={(e) => setTo(e.target.value)}/></div>
      </div>
      {bad ? <p className="small" style={{ color: 'var(--crit)' }}>The start date must be on or before the end date.</p> : null}
    </Dialog>);
}
function GlobalSearch() {
    const [q, setQ] = useState('');
    const [open, setOpen] = useState(false);
    const [active, setActive] = useState(0);
    const [hits, setHits] = useState([]);
    const nav = useNavigate();
    const box = useRef(null);
    const input = useRef(null);
    useEffect(() => {
        const onKey = (e) => {
            if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !e.target.closest('input,textarea,[contenteditable="true"]'))) {
                e.preventDefault();
                input.current?.focus();
            }
        };
        const onDoc = (e) => { if (box.current && !box.current.contains(e.target))
            setOpen(false); };
        document.addEventListener('keydown', onKey);
        document.addEventListener('mousedown', onDoc);
        return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onDoc); };
    }, []);
    useEffect(() => {
        if (q.trim().length < 2) {
            setHits([]);
            return;
        }
        const ctl = new AbortController();
        const t = setTimeout(async () => {
            try {
                const [a, t2] = await Promise.all([
                    api.get(`/articles${qs({ q, limit: 6 })}`, ctl.signal),
                    api.get(`/topics${qs({ q })}`, ctl.signal),
                ]);
                setHits([
                    ...a.rows.map((r) => ({ type: 'Article', id: r.id, title: r.title, sub: r.primary_keyword || r.handle, brand: r.brand_id, to: `/blogs/${r.id}` })),
                    ...t2.slice(0, 5).map((r) => ({ type: 'Topic', id: r.id, title: r.title, sub: r.primary_keyword, brand: r.brand_id, to: `/topics?focus=${r.id}` })),
                ]);
                setActive(0);
            }
            catch { /* ignore aborted */ }
        }, 180);
        return () => { clearTimeout(t); ctl.abort(); };
    }, [q]);
    const go = (to) => { setOpen(false); setQ(''); nav(to); };
    return (<div className="search hide-sm" ref={box}>
      <div className="input-icon">
        <Icon name="search"/>
        <input ref={input} className="input sm" placeholder="Search articles and topics" value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, hits.length - 1));
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
            }
            if (e.key === 'Enter' && hits[active])
                go(hits[active].to);
            if (e.key === 'Escape') {
                setOpen(false);
                e.target.blur();
            }
        }} aria-label="Search articles and topics" role="combobox" aria-expanded={open && hits.length > 0}/>
        <span className="kbd" style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)' }}>/</span>
      </div>
      {open && q.trim().length >= 2 ? (<div className="search-results" role="listbox">
          {hits.length ? hits.map((h, i) => (<a key={h.type + h.id} className={`search-hit ${i === active ? 'active' : ''}`} href={h.to} onClick={(e) => { e.preventDefault(); go(h.to); }} role="option" aria-selected={i === active}>
              <Icon name={h.type === 'Article' ? 'blogs' : 'topics'}/>
              <span style={{ minWidth: 0, flex: 1 }}>
                <span className="ellipsis strong" style={{ display: 'block' }}>{h.title}</span>
                <span className="ellipsis muted small" style={{ display: 'block' }}>{h.type} · {h.sub}</span>
              </span>
              <span className={`brand-dot ${h.brand}`}/>
            </a>)) : <div className="muted small" style={{ padding: 10 }}>No matches for “{q}”.</div>}
        </div>) : null}
    </div>);
}
/**
 * Local operator mode: there is no account menu, password change or sign-out. This only states the mode and who
 * actions are recorded as; it is not a control.
 */
function LocalOperatorBadge() {
    const { me } = useApp();
    return (<div className="user-chip" role="status" style={{ cursor: 'default', background: 'none' }} title={`Local operator mode: no sign-in, this computer only. Actions are recorded as ${me.user.name} (${me.user.email}).`}>
      <span className="avatar"><Icon name="shield" size="sm"/></span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span className="strong small" style={{ display: 'block' }}>Local operator mode</span>
        <span className="muted xs" style={{ display: 'block' }}>This computer only · no sign-in</span>
      </span>
    </div>);
}
function TasksDrawer({ tasks, loading, onClose }) {
    const nav = useNavigate();
    const { me } = useApp();
    return (<Drawer title={`My tasks · ${tasks.length}`} onClose={onClose}>
      {loading && !tasks.length ? <div style={{ padding: 18 }} className="muted">Loading…</div> : null}
      {!loading && !tasks.length ? (<div className="empty"><Icon name="checkCircle"/><h3>Nothing waiting on you</h3><p>Reviews, publish approvals and returned drafts for your role ({me.user.roleLabel}) will appear here.</p></div>) : null}
      <div className="alert-list">
        {tasks.map((t, i) => (<a key={i} className="alert-item" href={t.link} onClick={(e) => { e.preventDefault(); onClose(); nav(t.link); }}>
            <Icon name={t.kind === 'review' ? 'eye' : t.kind === 'authorize' ? 'shield' : t.kind === 'failed' ? 'alert' : t.kind === 'topic' ? 'topics' : 'edit'}/>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span className="strong small" style={{ display: 'block' }}>{t.action}</span>
              <span className="ellipsis small" style={{ display: 'block' }}>{t.title}</span>
              <span className="muted xs">waiting {timeAgo(t.since).replace(' ago', '')}</span>
            </span>
            <BrandTag id={t.brand} brands={me.brands}/>
          </a>))}
      </div>
    </Drawer>);
}
