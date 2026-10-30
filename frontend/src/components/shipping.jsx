'use client';
import { useState } from 'react';
import Link from 'next/link';
import { api, download, useApi, qs } from '../lib/api';
import { useApp } from '../lib/app';
import { fmtDateTime, timeAgo } from '../lib/format';
import { CATS, MANUAL, MARK_ACTION } from '../lib/shipping';
import { Button, Pill } from './ui';
import { Drawer, useToast } from './overlays';
import { Icon } from './Icon';

export function CatTag({ cat, label }) {
    const c = CATS[cat];
    return <span className="cat-tag" style={{ '--c': c?.color }}><i/>{label ?? c?.label ?? cat}</span>;
}

/** Warning from the last sync (failed or stale), or nothing. */
export function RunBanner({ run }) {
    const w = run?.warning;
    if (!w)
        return null;
    return <div className={`callout ${w.level === 'error' ? 'crit' : 'warn'} mb-12`} role="alert"><Icon name="alert"/><div>{w.message}</div></div>;
}

/** "Sync now": reads Shopify orders and fulfilments (read-only) and saves them. */
export function SyncButton({ onDone }) {
    const { can } = useApp();
    const toast = useToast();
    const [busy, setBusy] = useState(false);
    if (!can('analytics:sync'))
        return null;
    const go = async () => {
        setBusy(true);
        try {
            const r = await api.post('/shipping/sync');
            if (r.sync_status === 'failed')
                toast.error(new Error(r.error_summary || 'Sync failed.'));
            else
                toast.ok(`Sync ${r.sync_status}: ${r.orders_processed} orders read, ${r.shipments_created} new, ${r.shipments_updated} updated.`);
            onDone?.();
        }
        catch (e) {
            toast.error(e);
        }
        finally {
            setBusy(false);
        }
    };
    return <Button size="sm" icon="refresh" loading={busy} onClick={go} title="Reads Shopify orders and fulfilments (read-only) and saves them here">Sync now</Button>;
}

export function ExportButton({ kind, label, params = {}, icon = 'download', variant = 'secondary' }) {
    const toast = useToast();
    return <Button size="sm" variant={variant} icon={icon} onClick={() => download(`/shipping/export/${kind}${qs(params)}`).catch(toast.error)}>{label}</Button>;
}

const Fact = ({ label, children }) => <div className="fact"><span>{label}</span><b>{children}</b></div>;

/** Right-hand drawer for one shipment: timeline, recommended action, team check, packages and a note. */
export function ShipmentDrawer({ order, keyId, onClose, onChanged }) {
    const { can } = useApp();
    const toast = useToast();
    const q = useApi(`/shipping/shipments/detail${qs({ order, key: keyId })}`);
    const d = q.data;
    const s = d?.shipment;
    const [note, setNote] = useState(null);
    const [busy, setBusy] = useState('');
    const noteText = note ?? s?.note ?? '';
    const mark = async (status) => {
        setBusy(status);
        try {
            await api.post('/shipping/shipments/manual', { order_number: s.order_number, tracking_number: s.tracking_number, status });
            toast.ok(`${s.order_number} marked ${MANUAL[status].toLowerCase()}.`);
            q.reload();
            onChanged?.();
        }
        catch (e) {
            toast.error(e);
        }
        finally {
            setBusy('');
        }
    };
    const saveNote = async () => {
        setBusy('note');
        try {
            await api.post('/shipping/notes', { order_number: s.order_number, note: noteText });
            toast.ok('Note saved.');
            setNote(null);
            q.reload();
        }
        catch (e) {
            toast.error(e);
        }
        finally {
            setBusy('');
        }
    };
    return (<Drawer title={order} onClose={onClose}>
      <div style={{ padding: 18 }}>
        {q.error ? <div className="callout crit"><Icon name="alert"/>{q.error.message}</div> : null}
        {!s ? <div className="muted">Loading…</div> : (<>
            <div className="row-wrap gap-8">
              <CatTag cat={s.cat}/>
              {s.exception ? <Pill tone="crit">Exception: {s.exception.replace(/_/g, ' ')}</Pill> : null}
              {s.no_move ? <Pill tone="warn">No movement {s.scan_age}d</Pill> : null}
            </div>
            <div className="fact-grid">
              <Fact label="Days in stage">{s.days ?? '—'}</Fact>
              <Fact label="Stage">{s.stage === 'dispatched' ? 'Dispatched' : s.stage === 'pre_dispatch' ? 'Not dispatched' : '—'}</Fact>
              <Fact label="Carrier">{s.carrier_name || '—'}</Fact>
              <Fact label="Tracking">{s.tracking_number || 'Missing'}</Fact>
              <Fact label="Ordered">{fmtDateTime(s.order_created_at)}</Fact>
              <Fact label="Dispatched">{s.fulfilled_at ? fmtDateTime(s.fulfilled_at) : '—'}</Fact>
            </div>
            <div className="timeline">
              <div className="tl-step"><i style={{ background: 'var(--ok)' }}/><div><b>Ordered</b><small>{fmtDateTime(s.order_created_at)}</small></div></div>
              <div className="tl-step"><i style={{ background: s.fulfilled_at ? 'var(--ok)' : undefined }}/><div><b>Dispatched</b><small>{s.fulfilled_at ? fmtDateTime(s.fulfilled_at) : 'Not dispatched yet'}</small></div></div>
              <div className="tl-step"><i style={{ background: s.last_scan_at ? 'var(--info)' : undefined }}/><div><b>Last carrier scan</b><small>{s.last_scan_at ? `${fmtDateTime(s.last_scan_at)}${s.last_scan_description ? ` · ${s.last_scan_description}` : ''}` : 'No scan data yet'}</small></div></div>
            </div>
            <div className="callout info"><Icon name="info"/><div><b>Recommended action</b><div>{s.action}</div></div></div>
            <div className="row-wrap gap-8 mt-12">
              {s.track_url ? <a className="btn sm" href={s.track_url} target="_blank" rel="noopener noreferrer"><Icon name="external" size="sm"/>Carrier tracking page</a> : null}
              {s.shopify_url ? <a className="btn sm ghost" href={s.shopify_url} target="_blank" rel="noopener noreferrer"><Icon name="external" size="sm"/>Order in Shopify</a> : null}
            </div>
            {s.tracking_missing ? <div className="callout crit mt-12"><Icon name="alert"/><div><b>Tracking number missing in Shopify</b><div>Add the tracking number on this order in Shopify, then sync will pick it up. {s.shopify_url ? <a href={s.shopify_url} target="_blank" rel="noopener noreferrer">Open order in Shopify</a> : null}</div></div></div> : null}

            {s.unconfirmed ? (<div className="drawer-section">
                <h4>Team check</h4>
                <p className="muted small" style={{ margin: '0 0 8px' }}>{s.manual ? `Marked ${MANUAL[s.manual.status].toLowerCase()} by ${s.manual.updated_by || 'the team'} · ${timeAgo(s.manual.updated_at)}.` : 'Amazon and unknown carriers send no delivery event to Shopify. Open the carrier page, then mark the result here.'}</p>
                {can('shipping:update') ? (<div className="row-wrap gap-8">
                    {Object.entries(MARK_ACTION).map(([k, label]) => <Button key={k} size="sm" variant={s.manual?.status === k || (!s.manual && k === 'delivered') ? 'primary' : 'secondary'} loading={busy === k} onClick={() => mark(k)}>{label}</Button>)}
                  </div>) : null}
              </div>) : null}

            {d.packages.length > 1 ? (<div className="drawer-section">
                <h4>All packages in this order</h4>
                <div className="alert-list">
                  {d.packages.map((p) => (<div key={p.id} className="alert-item" style={{ borderTop: 'none', padding: '6px 0' }}>
                      <span style={{ flex: 1, minWidth: 0 }}><span className="small strong">{p.tracking_number || 'No tracking'}</span> <span className="muted xs">{p.carrier_name}</span></span>
                      <CatTag cat={p.cat}/>
                    </div>))}
                </div>
              </div>) : null}

            <div className="drawer-section">
              <h4>Team note</h4>
              <textarea className="textarea" rows={3} value={noteText} readOnly={!can('shipping:update')} onChange={(e) => setNote(e.target.value)} placeholder="Add a note about this order"/>
              {can('shipping:update') ? <div className="row mt-8"><Button size="sm" variant="primary" loading={busy === 'note'} disabled={note === null} onClick={saveNote}>Save note</Button></div> : null}
            </div>
            <p className="mt-16">{s.issue ? <Link href="/shipping/issues" className="small">See it on Lost &amp; missing</Link> : <Link href={`/shipping/shipments?q=${encodeURIComponent(s.order_number)}`} className="small">See this order in the list</Link>}</p>
          </>)}
      </div>
    </Drawer>);
}

/** Small Home card: critical / stuck counts from the saved shipments. Shown only when shipments exist. */
export function ShippingHomeCard() {
    const { data } = useApi('/shipping/summary');
    if (!data || data.empty)
        return null;
    const k = data.kpis;
    return (<Link href="/shipping" className="card clickable module-card">
      <span className="module-head"><span className="module-icon"><Icon name="send"/></span><span className="module-name">Shipping</span></span>
      <span className="module-purpose">Delayed and at-risk shipments for the Ridhi store.</span>
      <span className="module-latest">
        <span className="row-wrap gap-8"><Pill tone={k.red ? 'crit' : 'ok'}>{k.red} critical</Pill><Pill tone={k.nomove ? 'warn' : 'neutral'}>{k.nomove} stuck</Pill><Pill tone="neutral">{k.active} active</Pill></span>
      </span>
    </Link>);
}
