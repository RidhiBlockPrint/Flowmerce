'use client';
import { useEffect, useState } from 'react';
import { useSearchParams } from '../lib/nav';
import { useApi, qs } from '../lib/api';
import { fmtDateTime, fmtInt } from '../lib/format';
import { CATS } from '../lib/shipping';
import { Button, Card, Empty, ErrorState, PageHead, Pill, Skeleton } from '../components/ui';
import { Icon } from '../components/Icon';
import { CatTag, ExportButton, RunBanner, ShipmentDrawer, SyncButton } from '../components/shipping';

const VIEWS = [
    { key: '', label: 'Active' },
    { key: 'red', label: 'Critical 9+' },
    { key: 'nomove', label: 'Stuck (5+ days)' },
    { key: 'noscan', label: 'Scan missing' },
    { key: 'exception', label: 'Exceptions' },
    { key: 'unconfirmed', label: 'Carrier unconfirmed' },
];
const KPI_TILES = [
    ['', 'Total active', 'active', 'var(--ink)'],
    ['on_track', 'On track (0-3 days)', 'on_track', CATS.on_track.color],
    ['grey', 'Grey 2-3 days', 'grey', CATS.grey.color],
    ['yellow', 'Yellow 4-5 days', 'yellow', CATS.yellow.color],
    ['orange', 'Orange 6-8 days', 'orange', CATS.orange.color],
    ['red', 'Red 9+ days', 'red', CATS.red.color],
    ['unconfirmed', 'Carrier unconfirmed', 'unconfirmed', CATS.unconfirmed.color],
    ['exception', 'Carrier exceptions', 'exception', CATS.red.color],
    ['nomove', 'No movement (5+ days)', 'nomove', CATS.orange.color],
];
const SORTS = [['priority', 'Sort: priority'], ['oldest', 'Sort: oldest first'], ['stuck', 'Sort: stuck first'], ['order', 'Sort: order number']];
const SIZES = [10, 25, 50];

/** All shipments with filters, quick views, paging, CSV export and a detail drawer. */
export default function ShippingShipments() {
    const [sp, setSp] = useSearchParams();
    const view = sp.get('view') ?? '';
    const carrier = sp.get('carrier') ?? '';
    const status = sp.get('status') ?? '';
    const days = sp.get('days') ?? '';
    const sort = sp.get('sort') ?? 'priority';
    const size = Number(sp.get('size') ?? '10') || 10;
    const page = Number(sp.get('page') ?? '0') || 0;
    const [q, setQ] = useState(sp.get('q') ?? '');
    const [open, setOpen] = useState(null);
    const update = (patch) => {
        const next = new URLSearchParams(sp);
        for (const [k, v] of Object.entries(patch)) {
            if (v === null || v === '' || v === undefined)
                next.delete(k);
            else
                next.set(k, v);
        }
        setSp(next, { replace: true });
    };
    useEffect(() => {
        const t = setTimeout(() => update({ q: q || null, page: null }), 250);
        return () => clearTimeout(t);
    }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
    const params = { view, carrier, status, days, sort, q: sp.get('q') ?? '' };
    const list = useApi(`/shipping/shipments${qs({ ...params, page, size })}`);
    const runs = useApi('/shipping/runs');
    const d = list.data;
    const filtersOn = view || carrier || status || days || sp.get('q');
    const reloadAll = () => { list.reload(); runs.reload(); };
    return (<>
      <PageHead title="Shipments" sub="Every active shipment with its aging stage. Delivered shipments leave the list." actions={<>
          <ExportButton kind="filtered" label="Export CSV" params={params}/>
          <SyncButton onDone={reloadAll}/>
        </>}/>
      <RunBanner run={runs.data}/>
      <ErrorState error={list.error} onRetry={list.reload}/>
      {d && !d.empty ? (<div className="kpis mb-16">
          {KPI_TILES.map(([key, label, field, color]) => (<button key={label} type="button" className="kpi kpi-btn" aria-pressed={view === key} onClick={() => update({ view: key, page: null })}>
              <div className="kpi-label"><span className="sev" style={{ marginTop: 0, background: color }}/>{label}</div>
              <div className="kpi-value">{fmtInt(d.counts[field])}</div>
            </button>))}
        </div>) : null}

      <div className="pipeline-summary" role="group" aria-label="Quick views">
        {VIEWS.map((v) => (<button key={v.key} type="button" className="pipe-stage" style={{ flex: '0 0 auto', minWidth: 0, flexDirection: 'row', alignItems: 'center' }} aria-pressed={view === v.key} onClick={() => update({ view: v.key, page: null })}><span className="l">{v.label}</span></button>))}
      </div>

      <div className="toolbar">
        <div className="input-icon" style={{ width: 240 }}><Icon name="search"/><input className="input sm" placeholder="Search order or tracking number" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search order or tracking number"/></div>
        <select className="select sm" style={{ width: 'auto' }} value={carrier} onChange={(e) => update({ carrier: e.target.value, page: null })} aria-label="Carrier">
          <option value="">All carriers</option>{(d?.facets.carriers ?? []).map((c) => <option key={c}>{c}</option>)}
        </select>
        <select className="select sm" style={{ width: 'auto' }} value={status} onChange={(e) => update({ status: e.target.value, page: null })} aria-label="Tracking status">
          <option value="">All tracking statuses</option>{(d?.facets.statuses ?? []).map((c) => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
        </select>
        <select className="select sm" style={{ width: 'auto' }} value={days} onChange={(e) => update({ days: e.target.value, page: null })} aria-label="Order date">
          <option value="">Any order date</option><option value="7">Ordered in the last 7 days</option><option value="30">Ordered in the last 30 days</option><option value="90">Ordered in the last 90 days</option>
        </select>
        <select className="select sm" style={{ width: 'auto' }} value={sort} onChange={(e) => update({ sort: e.target.value, page: null })} aria-label="Sort">
          {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <span className="spacer"/>
        {filtersOn ? <Button size="sm" variant="ghost" onClick={() => { setQ(''); setSp(new URLSearchParams(), { replace: true }); }}>Clear filters</Button> : null}
      </div>

      <Card flush>
        <div className="table-wrap">
          <table className="t">
            <thead><tr><th>Order</th><th>Tracking</th><th className="hide-sm">Carrier</th><th className="hide-md">Dispatched</th><th>Last scan</th><th className="r">Days</th><th>Stage</th><th className="hide-md">Action</th></tr></thead>
            <tbody>
              {list.loading && !d ? Array.from({ length: 6 }, (_, i) => <tr key={i}><td colSpan={8}><Skeleton h={14} w={`${70 - i * 6}%`}/></td></tr>) : null}
              {d?.rows.map((r) => (<tr key={`${r.fulfillment_id}|${r.tracking_number}`} className="clickable" tabIndex={0} onClick={() => setOpen({ order: r.order_number, key: `${r.fulfillment_id}|${r.tracking_number}` })} onKeyDown={(e) => { if (e.key === 'Enter')
                setOpen({ order: r.order_number, key: `${r.fulfillment_id}|${r.tracking_number}` }); }}>
                  <td className="title-cell"><span className="ttl">{r.order_number}</span>{r.packages > 1 ? <span className="sub">{r.packages} packages</span> : null}</td>
                  <td className="small">{r.tracking_number || <span className="faint">Missing</span>}{r.track_url ? <> · <a href={r.track_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>Track</a></> : null}</td>
                  <td className="hide-sm small">{r.carrier_name || '—'}</td>
                  <td className="hide-md small nowrap">{r.fulfilled_at ? fmtDateTime(r.fulfilled_at) : <span className="faint">Not dispatched</span>}</td>
                  <td className="small">{r.last_scan_at ? fmtDateTime(r.last_scan_at) : <span className="faint">No scan from Shopify</span>}{r.last_scan_description ? <span className="muted xs" style={{ display: 'block' }}>{r.last_scan_description}</span> : null}</td>
                  <td className="r">{r.days ?? '—'}</td>
                  <td><div className="row-wrap gap-4"><CatTag cat={r.cat}/>{r.exception ? <Pill tone="crit">{r.exception.replace(/_/g, ' ')}</Pill> : null}{r.no_move ? <Pill tone="warn">No movement {r.scan_age}d</Pill> : null}</div></td>
                  <td className="hide-md small" style={{ minWidth: 220 }}>{r.action}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
        {d && !d.total ? (d.empty ? <Empty icon="send" title="No shipments saved yet">Run “Sync now”, or import a shipments file with <span className="mono">python scripts/import_shipping_data.py</span>.</Empty> : <Empty icon="search" title="No shipments match these filters">Try another quick view or clear the filters.</Empty>) : null}
        {d && d.total > 0 ? (<div className="card-foot pager">
            <span className="muted small">{page * d.size + 1}–{Math.min((page + 1) * d.size, d.total)} of {fmtInt(d.total)}</span>
            <span className="spacer"/>
            <select className="select sm" style={{ width: 'auto' }} value={size} onChange={(e) => update({ size: e.target.value, page: null })} aria-label="Rows per page">{SIZES.map((n) => <option key={n} value={n}>{n} rows</option>)}</select>
            <Button size="sm" icon="chevronLeft" disabled={d.page === 0} onClick={() => update({ page: String(d.page - 1) })}>Previous</Button>
            <span className="small muted">Page {d.page + 1} of {d.pages}</span>
            <Button size="sm" disabled={d.page >= d.pages - 1} onClick={() => update({ page: String(d.page + 1) })}>Next <Icon name="chevronRight" size="sm"/></Button>
          </div>) : null}
      </Card>
      {open ? <ShipmentDrawer order={open.order} keyId={open.key} onClose={() => setOpen(null)} onChanged={reloadAll}/> : null}
    </>);
}
