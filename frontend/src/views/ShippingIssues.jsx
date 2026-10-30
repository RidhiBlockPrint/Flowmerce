'use client';
import { useState } from 'react';
import { api, useApi } from '../lib/api';
import { useApp } from '../lib/app';
import { fmtDateTime, fmtInt } from '../lib/format';
import { CATS } from '../lib/shipping';
import { Button, Card, Empty, ErrorState, LoadingBlock, PageHead, Paged, Pill } from '../components/ui';
import { useToast } from '../components/overlays';
import { CatTag, ExportButton, ShipmentDrawer } from '../components/shipping';

const SECTIONS = [
    { key: 'missing', title: 'Missing tracking', color: '#b42318', sub: 'No tracking number on the Shopify order, so nothing can be tracked. Add one in Shopify; the next sync picks it up.', empty: 'Every open shipment has a tracking number.' },
    { key: 'lost', title: 'Lost', color: CATS.lost.color, sub: 'Packages your team marked as lost.', empty: 'No shipments are marked lost.' },
    { key: 'undeliverable', title: "Couldn't deliver", color: CATS.failed.color, sub: "Packages your team marked “couldn't deliver”, or where the carrier reported a failed delivery.", empty: "No shipments are marked as couldn't deliver." },
];

/** Problem shipments in three separate sections: missing tracking, lost, and could not deliver. */
export default function ShippingIssues() {
    const { data, error, loading, reload } = useApi('/shipping/issues');
    const [open, setOpen] = useState(null);
    const [busy, setBusy] = useState(false);
    const { can } = useApp();
    const toast = useToast();
    // Ask Shopify again (read-only) about the orders listed as missing a tracking number.
    const recheck = async () => {
        setBusy(true);
        try {
            const r = await api.post('/shipping/issues/recheck');
            if (r.sync_status === 'failed')
                toast.error(new Error(r.error_summary || 'Re-check failed.'));
            else
                toast.ok(`Shopify checked ${r.requested} orders: ${r.fixed} now have a tracking number, ${r.still_missing ?? 0} still do not.`);
            reload();
        }
        catch (e) {
            toast.error(e);
        }
        finally {
            setBusy(false);
        }
    };
    return (<>
      <PageHead title="Lost, missing and undeliverable" sub="Kept out of every total, list and chart elsewhere. Open one to mark it, add a note or jump to the Shopify order." actions={<ExportButton kind="issues" label="Export CSV"/>}/>
      <ErrorState error={error} onRetry={reload}/>
      {loading && !data ? <LoadingBlock rows={6}/> : null}
      {data ? (<div className="col" style={{ gap: 16 }}>
          <div className="kpis">
            {SECTIONS.map((s) => (<a key={s.key} href={`#${s.key}`} className="kpi kpi-btn" style={{ textDecoration: 'none' }}>
                <div className="kpi-label"><span className="sev" style={{ marginTop: 0, background: s.color }}/>{s.title}</div>
                <div className="kpi-value">{fmtInt(data.counts[s.key])}</div>
              </a>))}
          </div>
          {SECTIONS.map((s) => (<div key={s.key} id={s.key}>
              <Card title={s.title} sub={s.sub} flush actions={<>{s.key === 'missing' && can('analytics:sync') && data.counts.missing ? <Button size="sm" icon="refresh" loading={busy} onClick={recheck} title="Asks Shopify again (read-only) whether these orders now have a tracking number">Re-check in Shopify</Button> : null}<Pill tone={data.counts[s.key] ? 'crit' : 'ok'}>{fmtInt(data.counts[s.key])}</Pill></>}>
                {data[s.key].length ? (<Paged rows={data[s.key]}>{(rows) => (<div className="table-wrap">
                      <table className="t compact">
                        <thead><tr><th>Order</th><th>Carrier</th><th>Tracking</th><th className="r">Days</th><th>Status</th><th className="hide-md">Last update</th></tr></thead>
                        <tbody>
                          {rows.map((r) => (<tr key={`${r.fulfillment_id}|${r.tracking_number}`} className="clickable" tabIndex={0} onClick={() => setOpen({ order: r.order_number, key: `${r.fulfillment_id}|${r.tracking_number}` })} onKeyDown={(e) => { if (e.key === 'Enter')
                            setOpen({ order: r.order_number, key: `${r.fulfillment_id}|${r.tracking_number}` }); }}>
                              <td className="strong">{r.order_number}</td>
                              <td className="small">{r.carrier_name || '—'}</td>
                              <td className="small">{r.tracking_number || <span className="faint">Missing</span>}</td>
                              <td className="r">{r.days ?? '—'}</td>
                              <td><div className="row-wrap gap-4"><CatTag cat={r.cat}/>{r.exception ? <Pill tone="crit">{r.exception.replace(/_/g, ' ')}</Pill> : null}</div></td>
                              <td className="hide-md small">{r.manual ? `Marked by ${r.manual.updated_by || 'the team'}` : r.last_scan_at ? fmtDateTime(r.last_scan_at) : 'No scan'}</td>
                            </tr>))}
                        </tbody>
                      </table>
                    </div>)}</Paged>) : <Empty icon="checkCircle" title="Nothing here">{s.empty}</Empty>}
              </Card>
            </div>))}
        </div>) : null}
      {open ? <ShipmentDrawer order={open.order} keyId={open.key} onClose={() => setOpen(null)} onChanged={reload}/> : null}
    </>);
}
