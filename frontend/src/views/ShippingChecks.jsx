'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useApi } from '../lib/api';
import { fmtInt } from '../lib/format';
import { MCF_LEVEL, MANUAL } from '../lib/shipping';
import { Card, Empty, ErrorState, LoadingBlock, PageHead, Paged, Pill } from '../components/ui';
import { Icon } from '../components/Icon';
import { CatTag, ExportButton, ShipmentDrawer } from '../components/shipping';

const MCF_TONE = { critical: 'crit', watch: 'warn', alert: 'warn' };
const money = (v, cur) => {
    if (v === null || v === undefined)
        return '—';
    try {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: cur || 'USD', maximumFractionDigits: 0 }).format(v);
    }
    catch {
        return fmtInt(Math.round(v));
    }
};
const Tile = ({ n, label, color }) => <div className="kpi"><div className="kpi-label"><span className="sev" style={{ marginTop: 0, background: color }}/>{label}</div><div className="kpi-value">{fmtInt(n)}</div></div>;

/** Team checks: Amazon / unknown carriers to verify, and orders whose notes say DONE while Shopify is unfulfilled. */
export default function ShippingChecks() {
    const { data, error, loading, reload } = useApi('/shipping/checks');
    const [open, setOpen] = useState(null);
    const c = data?.checklist;
    return (<>
      <PageHead title="Shipping checks" sub="Work the team does by hand because carriers or Shopify notes cannot be read automatically." actions={<>
          <ExportButton kind="verify" label="Amazon / unknown verify list (CSV)"/>
          <ExportButton kind="escalation" label="Escalation list (CSV)" variant="primary"/>
        </>}/>
      <ErrorState error={error} onRetry={reload}/>
      {loading && !data ? <LoadingBlock rows={6}/> : null}
      {data ? (<div className="col" style={{ gap: 16 }}>
          <div className="callout info"><Icon name="info"/><div>Lost, missing-tracking and could-not-deliver shipments are not counted here or anywhere else in the totals. They are listed on <Link href="/shipping/issues">Lost &amp; missing</Link>.</div></div>
          <Card title="Amazon / unknown carriers to verify" sub="These carriers send no delivery event to Shopify. Open each parcel, check it, and mark the result." flush>
            <div className="kpis" style={{ padding: 16 }}>
              <Tile n={c.total} label="Total to verify" color="#6b4fbb"/>
              <Tile n={c.delivered} label="Delivered (checked)" color="#2d6a3e"/>
              <Tile n={c.in_transit} label="Still in transit" color="#2f5d8a"/>
              <Tile n={c.unchecked} label="Not checked yet" color="#8b8279"/>
              <Tile n={c.covered} label="Covered (fulfilled by hand)" color="#4a7a8c"/>
            </div>
            {data.unconfirmed.length ? (<Paged rows={data.unconfirmed}>{(rows) => (<div className="table-wrap">
                  <table className="t compact">
                    <thead><tr><th>Order</th><th>Carrier</th><th>Tracking</th><th className="r">Days</th><th>Status</th></tr></thead>
                    <tbody>
                      {rows.map((r) => (<tr key={`${r.fulfillment_id}|${r.tracking_number}`} className="clickable" onClick={() => setOpen({ order: r.order_number, key: `${r.fulfillment_id}|${r.tracking_number}` })}>
                          <td className="strong">{r.order_number}</td><td className="small">{r.carrier_name || 'Unknown'}</td>
                          <td className="small">{r.tracking_missing ? <span className="pill crit">Tracking missing</span> : r.tracking_number}</td>
                          <td className="r">{r.days ?? '—'}</td>
                          <td>{r.manual ? <Pill tone="ok">{MANUAL[r.manual.status]}</Pill> : <span className="faint small">Not checked</span>}</td>
                        </tr>))}
                    </tbody>
                  </table>
                </div>)}</Paged>) : <div className="card-body muted small">No Amazon or unknown-carrier shipments are waiting for a check.</div>}
          </Card>

          <Card title="Notes say DONE, Shopify not fulfilled" sub={data.mcf.length ? `${fmtInt(data.mcf.length)} orders, oldest first` : 'Order notes that say done while Shopify still shows the order unfulfilled'} flush>
            {data.mcf.length ? (<>
                <div className="kpis" style={{ padding: 16 }}>
                  {Object.entries(MCF_LEVEL).map(([k, label]) => <Tile key={k} n={data.mcf_counts[k] ?? 0} label={label} color={k === 'critical' ? '#b42318' : '#c98a0c'}/>)}
                </div>
                <Paged rows={data.mcf}>{(rows) => (<div className="table-wrap">
                    <table className="t compact">
                      <thead><tr><th>Order</th><th className="r">Age</th><th>Shopify</th><th>Notes</th><th className="r">Total</th><th>Level</th></tr></thead>
                      <tbody>
                        {rows.map((m) => (<tr key={m.order_number}>
                            <td className="strong">{m.order_number}</td><td className="r">{m.age} d</td>
                            <td className="small">{(m.fulfillment_status || 'Not fulfilled').replace(/_/g, ' ').toLowerCase()}</td>
                            <td className="small" style={{ maxWidth: 420, overflowWrap: 'anywhere' }}>{m.note}</td>
                            <td className="r small">{money(m.order_total, m.order_currency)}</td>
                            <td><Pill tone={MCF_TONE[m.level]}>{m.level_label}</Pill></td>
                          </tr>))}
                      </tbody>
                    </table>
                  </div>)}</Paged>
              </>) : <Empty icon="checkCircle" title="Nothing to check here">No orders have a “done” note while Shopify shows them unfulfilled. This list uses the order checks data, which is loaded separately from the shipments.</Empty>}
          </Card>
        </div>) : null}
      {open ? <ShipmentDrawer order={open.order} keyId={open.key} onClose={() => setOpen(null)} onChanged={reload}/> : null}
    </>);
}
