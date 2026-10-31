'use client';
import { useState } from 'react';
import { api, useApi, qs } from '../lib/api';
import { useApp } from '../lib/app';
import { fmtDateTime, timeAgo } from '../lib/format';
import { FLAGS, GROUPS, MANUAL, MARK_ACTION, TIERS } from '../lib/shipping';
import { Button, Pill } from './ui';
import { Drawer, useToast } from './overlays';
import { Icon } from './Icon';

/** Group chip, with the delay tier next to it when the order is slow. */
export function GroupTag({ group, tier, deliveredBy }) {
    const g = GROUPS[group];
    const t = tier ? TIERS[tier] : null;
    return (<span className="row-wrap gap-4">
      <span className="cat-tag" style={{ '--c': g?.color }}><i/>{g?.label ?? group}</span>
      {deliveredBy === 'amazon_mcf' ? <span className="cat-tag" style={{ '--c': '#c98a0c' }} title="The note says DONE and Amazon delivers it itself; Shopify still shows the order as not fulfilled"><i/>Amazon MCF</span> : null}
      {t ? <span className="cat-tag" style={{ '--c': t.color }}><i/>{t.label}</span> : null}
    </span>);
}

/** Right-hand drawer for one order: its shipments, delay, flags, a team check per shipment and a note. */
export function OrderDrawer({ order, onClose, onChanged }) {
    const { can } = useApp();
    const toast = useToast();
    const q = useApi(`/shipping/orders/detail${qs({ order })}`);
    const o = q.data;
    const [note, setNote] = useState(null);
    const [busy, setBusy] = useState('');
    const noteText = note ?? o?.team_note ?? '';
    const mark = async (s, status) => {
        setBusy(`${s.tracking_number}|${status}`);
        try {
            await api.post('/shipping/shipments/manual', { order_number: o.order_number, tracking_number: s.tracking_number, status });
            toast.ok(`${o.order_number} marked ${MANUAL[status].toLowerCase()}.`);
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
            await api.post('/shipping/notes', { order_number: o.order_number, note: noteText });
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
        {!o ? <div className="muted">Loading…</div> : (<>
            <GroupTag group={o.group} tier={o.tier} deliveredBy={o.delivered_by}/>
            {o.flags.length ? <div className="row-wrap gap-4 mt-8">{o.flags.map((f) => <Pill key={f} tone="crit">{FLAGS[f]}</Pill>)}</div> : null}
            <div className="fact-grid">
              <div className="fact"><span>{o.group === 'delivered' ? 'Transit days' : 'Days in stage'}</span><b>{o.days ?? '—'}</b></div>
              <div className="fact"><span>Shopify status</span><b>{(o.fulfillment_status || '—').replace(/_/g, ' ').toLowerCase()}</b></div>
              <div className="fact"><span>Ordered</span><b>{o.created_at ? fmtDateTime(o.created_at) : '—'}</b></div>
              <div className="fact"><span>Fulfilled</span><b>{o.fulfilled_at ? fmtDateTime(o.fulfilled_at) : 'Not fulfilled'}</b></div>
              <div className="fact"><span>Delivered</span><b>{o.delivered_at ? fmtDateTime(o.delivered_at) : '—'}</b></div>
              <div className="fact"><span>Carrier</span><b>{o.carriers.join(', ') || '—'}</b></div>
            </div>
            <div className="callout info"><Icon name="info"/><div><b>What to do</b><div>{o.action}</div></div></div>
            {o.shopify_url ? <p className="mt-12"><a className="btn sm ghost" href={o.shopify_url} target="_blank" rel="noopener noreferrer"><Icon name="external" size="sm"/>Order in Shopify</a></p> : null}

            <div className="drawer-section">
              <h4>Shipments ({o.shipments.length})</h4>
              {o.shipments.length ? o.shipments.map((s) => (<div key={`${s.fulfillment_id}|${s.tracking_number}`} className="card card-body mb-8" style={{ padding: 12 }}>
                  <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <b className="small">{s.carrier_name || 'No carrier'}</b>
                    {s.tracked ? <span className="mono small">{s.tracking_number}</span> : <Pill tone="warn">No tracking ID</Pill>}
                    <span className="spacer"/>
                    {s.delivered ? <Pill tone="ok">Delivered{s.transit_days !== null ? ` in ${s.transit_days} d` : ''}</Pill> : s.lost ? <Pill tone="crit">{MANUAL[s.mark.status]}</Pill> : <Pill tone="neutral">{(s.status || 'fulfilled').replace(/_/g, ' ')}</Pill>}
                  </div>
                  <div className="muted xs mt-4">{s.fulfilled_at ? `Fulfilled ${fmtDateTime(s.fulfilled_at)}` : 'Not fulfilled'}{s.last_scan_at ? ` · last scan ${fmtDateTime(s.last_scan_at)}` : ''}</div>
                  {s.track_url ? <a className="small" href={s.track_url} target="_blank" rel="noopener noreferrer">Open the carrier tracking page</a> : null}
                  {s.mark ? <div className="muted xs mt-4">Marked {MANUAL[s.mark.status].toLowerCase()} by {s.mark.updated_by || 'the team'} · {timeAgo(s.mark.updated_at)}</div> : null}
                  {s.tracked && can('shipping:update') ? (<div className="row-wrap gap-4 mt-8">
                      {Object.entries(MARK_ACTION).map(([k, label]) => <Button key={k} size="xs" variant={s.mark?.status === k ? 'primary' : 'secondary'} loading={busy === `${s.tracking_number}|${k}`} onClick={() => mark(s, k)}>{label}</Button>)}
                    </div>) : null}
                </div>)) : <p className="muted small">Nothing has been fulfilled on this order yet.</p>}
            </div>

            <div className="drawer-section">
              <h4>Team note</h4>
              <textarea className="textarea" rows={3} value={noteText} readOnly={!can('shipping:update')} onChange={(e) => setNote(e.target.value)} placeholder="Add a note about this order"/>
              {can('shipping:update') ? <div className="row mt-8"><Button size="sm" variant="primary" loading={busy === 'note'} disabled={note === null} onClick={saveNote}>Save note</Button></div> : null}
              {o.note ? <p className="muted xs mt-8">Shopify order note: {o.note}</p> : null}
            </div>
          </>)}
      </div>
    </Drawer>);
}
