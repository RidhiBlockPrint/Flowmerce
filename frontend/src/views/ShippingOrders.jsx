'use client';
import { useEffect, useState } from 'react';
import { useSearchParams } from '../lib/nav';
import { useApi, qs } from '../lib/api';
import { fmtDateTime, fmtInt } from '../lib/format';
import { FLAGS, GROUPS, TIERS } from '../lib/shipping';
import { Button, Card, Empty, ErrorState, PageHead, Pill, Skeleton } from '../components/ui';
import { Icon } from '../components/Icon';
import { ExportButton, LookupButton, RunBanner, SyncButton } from '../components/shipping';
import { GroupTag, OrderDrawer } from '../components/order-drawer';

const CHIPS = ['', 'delivered', 'in_transit', 'delayed', 'stale', 'unfulfilled', 'needs_action', 'lost_missing', 'no_tracking_id', 'no_carrier'];
const SORTS = [['priority', 'Sort: most delayed first'], ['newest', 'Sort: newest first'], ['order', 'Sort: order number']];
const SIZES = [10, 25, 50];

/** Every order, in one group at a time, with delay tier chips, filters, paging and a detail drawer. */
export default function ShippingOrders() {
    const [sp, setSp] = useSearchParams();
    const group = sp.get('group') ?? '';
    const tier = sp.get('tier') ?? '';
    const flag = sp.get('flag') ?? '';
    const carrier = sp.get('carrier') ?? '';
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
    const params = { group, tier, flag, carrier, sort, q: sp.get('q') ?? '' };
    const list = useApi(`/shipping/orders${qs({ ...params, page, size })}`);
    const runs = useApi('/shipping/runs');
    const d = list.data;
    const count = (g) => (!d ? '' : g === '' ? d.counts.total : g === 'needs_action' ? d.counts.needs_action : d.counts[g]);
    const filtersOn = group || tier || flag || carrier || sp.get('q');
    const reloadAll = () => { list.reload(); runs.reload(); };
    return (<>
      <PageHead title="Orders" sub="Each order sits in one group. Delay is counted in days from the fulfilled date, the same for every carrier." actions={<>
          <ExportButton kind="" label="Export CSV" path="orders/export" params={params}/>
          <LookupButton onDone={reloadAll}/>
          <SyncButton onDone={reloadAll}/>
        </>}/>
      <RunBanner run={runs.data}/>
      <ErrorState error={list.error} onRetry={list.reload}/>

      <div className="pipeline-summary" role="group" aria-label="Order groups">
        {CHIPS.map((g) => (<button key={g} type="button" className="pipe-stage" aria-pressed={group === g && !flag} onClick={() => update({ group: g, tier: null, flag: null, page: null })}>
            <span className="n">{d ? fmtInt(count(g)) : '—'}</span>
            <span className="l">{g === '' ? 'All orders' : GROUPS[g].label}</span>
          </button>))}
      </div>
      {group === 'delayed' ? (<div className="pipeline-summary" role="group" aria-label="Delay tiers">
          <button type="button" className="pipe-stage" style={{ flex: '0 0 auto' }} aria-pressed={!tier} onClick={() => update({ tier: null, page: null })}><span className="l">All delayed</span></button>
          {Object.keys(TIERS).map((t) => (<button key={t} type="button" className="pipe-stage" style={{ flex: '0 0 auto' }} aria-pressed={tier === t} onClick={() => update({ tier: t, page: null })}><span className="l">{TIERS[t].label} · {d ? fmtInt(d.counts.delayed_tiers[t]) : '—'}</span></button>))}
        </div>) : null}
      {flag ? <div className="callout info mb-12"><Icon name="info"/><div>Showing orders flagged: <b>{FLAGS[flag]}</b>.</div></div> : null}

      <div className="toolbar">
        <div className="input-icon" style={{ width: 240 }}><Icon name="search"/><input className="input sm" placeholder="Search order or tracking number" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search order or tracking number"/></div>
        <select className="select sm" style={{ width: 'auto' }} value={carrier} onChange={(e) => update({ carrier: e.target.value, page: null })} aria-label="Carrier">
          <option value="">All carriers</option>{(d?.facets.carriers ?? []).map((c) => <option key={c}>{c}</option>)}
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
            <thead><tr><th>Order</th><th>Carrier</th><th className="hide-sm">Tracking ID</th><th className="hide-md">Fulfilled</th><th className="hide-md">Delivered</th><th className="r">Days</th><th>Group</th><th className="hide-md">What to do</th></tr></thead>
            <tbody>
              {list.loading && !d ? Array.from({ length: 6 }, (_, i) => <tr key={i}><td colSpan={8}><Skeleton h={14} w={`${70 - i * 6}%`}/></td></tr>) : null}
              {d?.rows.map((o) => (<tr key={o.order_number} className="clickable" tabIndex={0} onClick={() => setOpen(o.order_number)} onKeyDown={(e) => { if (e.key === 'Enter')
                setOpen(o.order_number); }}>
                  <td className="title-cell"><span className="ttl">{o.order_number}</span>{o.shipments.length > 1 ? <span className="sub">{o.shipments.length} shipments</span> : null}</td>
                  <td className="small">{o.carriers.join(', ') || <span className="faint">—</span>}</td>
                  <td className="hide-sm small mono" style={{ maxWidth: 200, overflowWrap: 'anywhere' }}>{o.tracking_numbers.length ? o.tracking_numbers.slice(0, 2).join(', ') + (o.tracking_numbers.length > 2 ? ` +${o.tracking_numbers.length - 2}` : '') : <span className="faint">—</span>}</td>
                  <td className="hide-md small nowrap">{o.fulfilled_at ? fmtDateTime(o.fulfilled_at) : <span className="faint">Not fulfilled</span>}</td>
                  <td className="hide-md small nowrap">{o.delivered_at ? fmtDateTime(o.delivered_at) : <span className="faint">—</span>}</td>
                  <td className="r">{o.days ?? '—'}</td>
                  <td><div className="col gap-4"><GroupTag group={o.group} tier={o.tier} deliveredBy={o.delivered_by}/>{o.flags.length ? <div className="row-wrap gap-4">{o.flags.map((f) => <Pill key={f} tone="crit">{FLAGS[f]}</Pill>)}</div> : null}</div></td>
                  <td className="hide-md small" style={{ minWidth: 220 }}>{o.action}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
        {d && !d.total ? (d.empty ? <Empty icon="send" title="No orders saved yet">Run “Sync now”, or import the existing data.</Empty> : <Empty icon="search" title="No orders match">Try another group or clear the filters.</Empty>) : null}
        {d && d.total > 0 ? (<div className="card-foot pager">
            <span className="muted small">{page * d.size + 1}–{Math.min((page + 1) * d.size, d.total)} of {fmtInt(d.total)}</span>
            <span className="spacer"/>
            <select className="select sm" style={{ width: 'auto' }} value={size} onChange={(e) => update({ size: e.target.value, page: null })} aria-label="Rows per page">{SIZES.map((n) => <option key={n} value={n}>{n} rows</option>)}</select>
            <Button size="sm" icon="chevronLeft" disabled={d.page === 0} onClick={() => update({ page: String(d.page - 1) })}>Previous</Button>
            <span className="small muted">Page {d.page + 1} of {d.pages}</span>
            <Button size="sm" disabled={d.page >= d.pages - 1} onClick={() => update({ page: String(d.page + 1) })}>Next <Icon name="chevronRight" size="sm"/></Button>
          </div>) : null}
      </Card>
      {open ? <OrderDrawer order={open} onClose={() => setOpen(null)} onChanged={reloadAll}/> : null}
    </>);
}
