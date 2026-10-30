'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useNavigate } from '../lib/nav';
import { api, useApi } from '../lib/api';
import { fmtInt, fmtDate } from '../lib/format';
import { CATS, MCF_LEVEL } from '../lib/shipping';
import { BarList, Columns, Donut } from '../components/charts';
import { Button, Card, Empty, ErrorState, LoadingBlock, PageHead } from '../components/ui';
import { Icon } from '../components/Icon';
import { ExportButton, RunBanner, SyncButton } from '../components/shipping';

const pct = (part, whole) => (whole ? Math.min(100, Math.round((part / whole) * 100)) : 0);

/** Shipping overview: what needs attention today, from the saved shipment records. */
export default function ShippingOverview() {
    const [weekDays, setWeekDays] = useState('');
    const { data, error, loading, reload } = useApi(`/shipping/summary${weekDays ? `?week_days=${weekDays}` : ''}`);
    const [since, setSince] = useState('');
    const [printRows, setPrintRows] = useState(null);
    const nav = useNavigate();
    const k = data?.kpis;
    // "Since your last visit": compare with the figures saved in this browser the last time the page loaded.
    useEffect(() => {
        if (!k)
            return;
        try {
            const cur = { at: Date.now(), active: k.active, crit: k.red, stuck: k.nomove };
            const prev = JSON.parse(localStorage.getItem('fm.ship.snapshot') || 'null');
            localStorage.setItem('fm.ship.snapshot', JSON.stringify(cur));
            if (prev && !since) {
                const hrs = Math.round((cur.at - prev.at) / 3600000);
                const ago = hrs < 1 ? 'less than an hour' : hrs < 48 ? `${hrs} h` : `${Math.round(hrs / 24)} days`;
                const sign = (n) => (n > 0 ? '+' : '') + n.toLocaleString('en-US');
                setSince(`Since your last visit (${ago} ago): critical ${sign(cur.crit - prev.crit)}, stuck ${sign(cur.stuck - prev.stuck)}, active ${sign(cur.active - prev.active)}.`);
            }
        }
        catch { /* storage unavailable: skip the comparison */ }
    }, [k]); // eslint-disable-line react-hooks/exhaustive-deps
    const printSummary = async () => {
        const r = await api.get('/shipping/shipments?view=red&sort=oldest&size=20');
        setPrintRows(r.rows);
        setTimeout(() => window.print(), 250);
    };    return (<>
      <PageHead title="Shipping overview" sub={data && !data.empty ? <>Delayed and at-risk shipments for the Ridhi store · {fmtInt(k.active)} active, {fmtInt(k.delivered)} delivered · data as of {data.run.last ? fmtDate(data.run.last.started_at) : 'the last import'}</> : 'Delayed and at-risk shipments for the Ridhi store'} actions={<>
          <Button size="sm" icon="download" onClick={printSummary}>Print summary</Button>
          <ExportButton kind="escalation" label="Escalation list (CSV)"/>
          <SyncButton onDone={reload}/>
        </>}/>
      <ErrorState error={error} onRetry={reload}/>
      {loading && !data ? <LoadingBlock rows={6}/> : null}
      {data ? <RunBanner run={data.run}/> : null}
      {since ? <div className="callout info mb-12"><Icon name="info"/><div>{since}</div></div> : null}
      {data?.empty ? (<Card><Empty icon="send" title="No shipments saved yet">Run “Sync now” to read open orders from Shopify (needs read_orders and read_fulfillments access), or import an existing shipments file with <span className="mono">python scripts/import_shipping_data.py</span>.</Empty></Card>) : null}
      {data && !data.empty ? (<div className="col" style={{ gap: 16 }}>
          {k.red > 0 ? <div className="callout crit" role="alert"><Icon name="alert"/><div><b>{fmtInt(k.red)} shipment{k.red === 1 ? ' is' : 's are'} 9+ days in stage.</b> Escalate these first.</div></div> : null}
          <div className="ship-hero">
            <section className="card card-body">
              <div className="small muted">Critical shipments</div>
              <div className="hero-num">{fmtInt(k.red)}</div>
              <div className="hero-sub">of {fmtInt(data.confirmed)} confirmed active shipments · Amazon and unknown carriers are counted separately</div>
              <div className="hero-items">
                <Link className="hero-item" href="/shipping/shipments?view=orange"><b style={{ color: CATS.orange.color }}>{fmtInt(k.orange)}</b><span>Orange · 6–8 days</span></Link>
                <Link className="hero-item" href="/shipping/shipments?view=yellow"><b style={{ color: CATS.yellow.color }}>{fmtInt(k.yellow)}</b><span>Yellow · 4–5 days</span></Link>
                <Link className="hero-item" href="/shipping/shipments?view=on_track"><b style={{ color: CATS.on_track.color }}>{fmtInt(k.on_track)}</b><span>On track · 0–3 days</span></Link>
              </div>
            </section>
            <Card title="Shipment health" sub="Active, by aging stage">
              <div className="row" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                <Donut ariaLabel="Active shipments by aging stage" center={fmtInt(data.confirmed)} sub="active" size={150} items={data.health.map((h) => ({ label: CATS[h.key].short, value: h.count, color: CATS[h.key].color, key: h.key }))} onSelect={(i) => nav(`/shipping/shipments?view=${i.key}`)}/>
                <div className="legend-list">
                  <Link href="/shipping/shipments?view=covered" className="row" style={{ gap: 8, color: 'inherit' }} title="Packages marked fulfilled by hand (no tracking) on orders whose tracked packages are all delivered"><i style={{ width: 10, height: 10, borderRadius: 3, background: CATS.covered.color }}/>Fulfilled by hand<b style={{ marginLeft: 'auto' }}>{fmtInt(k.covered)}</b></Link>
                  <Link href="/shipping/shipments?view=delivered" className="row" style={{ gap: 8, color: 'inherit' }}><i style={{ width: 10, height: 10, borderRadius: 3, background: CATS.delivered.color }}/>Delivered<b style={{ marginLeft: 'auto' }}>{fmtInt(k.delivered)}</b></Link>
                  {data.health.map((h) => (<Link key={h.key} href={`/shipping/shipments?view=${h.key}`} className="row" style={{ gap: 8, color: 'inherit' }}><i style={{ width: 10, height: 10, borderRadius: 3, background: CATS[h.key].color }}/>{CATS[h.key].short}<b style={{ marginLeft: 'auto' }}>{fmtInt(h.count)}</b></Link>))}
                </div>
              </div>
            </Card>
            <div className="col" style={{ gap: 12 }}>
              <Link href="/shipping/shipments?view=nomove" className="card card-body stat-card"><div className="small muted">No movement (5+ days)</div><div className="big">{fmtInt(k.nomove)}</div><div className="progress"><i style={{ width: `${pct(k.nomove, k.active)}%`, background: CATS.orange.color }}/></div></Link>
              <Link href="/shipping/shipments?view=exception" className="card card-body stat-card"><div className="small muted">Carrier exceptions</div><div className="big">{fmtInt(k.exception)}</div><div className="progress"><i style={{ width: `${pct(k.exception, k.active)}%`, background: CATS.red.color }}/></div></Link>
              <Link href="/shipping/shipments?view=unconfirmed" className="card card-body stat-card"><div className="small muted">Carrier unconfirmed (Amazon / unknown)</div><div className="big">{fmtInt(k.unconfirmed)}</div><div className="progress"><i style={{ width: `${pct(k.unconfirmed, k.active)}%`, background: CATS.unconfirmed.color }}/></div></Link>
            </div>
          </div>

          <div className="grid cols-2">
            <Card title="Pending by week created" sub="Active shipments, grouped by the week the order was placed" actions={<select className="select sm" style={{ width: 'auto' }} value={weekDays} onChange={(e) => setWeekDays(e.target.value)} aria-label="Date range"><option value="">All dates</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option></select>}>
              <Columns ariaLabel="Active shipments by order week" items={data.weeks.map((w) => ({ label: w.week.slice(5), value: w.count }))}/>
            </Card>
            <Card title="Carriers" sub="Active shipments and how many are critical" actions={<Link className="btn ghost xs" href="/shipping/analytics">Carrier scorecard</Link>}>
              <BarList format={fmtInt} empty="No carriers yet" rows={data.carriers.map((c) => ({ key: c.name, value: c.active, label: <span className="ellipsis">{c.name}</span>, extra: <span className="faint">{fmtInt(c.critical)} critical · {fmtInt(c.stuck)} stuck</span>, onClick: () => nav(`/shipping/shipments?carrier=${encodeURIComponent(c.name)}`) }))}/>
            </Card>
          </div>

          <Card title="Notes say DONE, Shopify not fulfilled" sub={data.mcf.total ? `${fmtInt(data.mcf.total)} orders` : 'Orders whose note says done but Shopify shows them unfulfilled'} flush actions={<Link className="btn ghost xs" href="/shipping/checks">Open checks</Link>}>
            {data.mcf.total ? (<div className="table-wrap">
                <table className="t compact">
                  <thead><tr><th>Order</th><th className="r">Age</th><th>Shopify</th><th>Notes</th><th>Level</th></tr></thead>
                  <tbody>
                    {data.mcf.rows.map((c) => (<tr key={c.order_number}>
                        <td className="strong">{c.order_number}</td><td className="r">{c.age} d</td>
                        <td className="small">{(c.fulfillment_status || 'Not fulfilled').replace(/_/g, ' ').toLowerCase()}</td>
                        <td className="small ellipsis" style={{ maxWidth: 360 }} title={c.note}>{c.note}</td>
                        <td><span className="pill warn">{MCF_LEVEL[c.level]}</span></td>
                      </tr>))}
                  </tbody>
                </table>
              </div>) : <div className="card-body muted small">{data.mcf.total === 0 ? 'No orders need this check right now. Order checks are loaded separately from the shipment records.' : ''}</div>}
          </Card>
        </div>) : null}
          {printRows ? (<div className="print-area">
          <h2>Shipping daily summary</h2>
          <p>{fmtInt(k.active)} active · {fmtInt(k.red)} critical (9+ days) · {fmtInt(k.nomove)} stuck · {fmtInt(k.delivered)} delivered</p>
          <h3>Top {printRows.length} to escalate</h3>
          <table><thead><tr><th>Order</th><th>Carrier</th><th>Tracking</th><th>Days</th><th>Last scan</th></tr></thead><tbody>
            {printRows.map((r) => <tr key={`${r.fulfillment_id}|${r.tracking_number}`}><td>{r.order_number}</td><td>{r.carrier_name || '—'}</td><td>{r.tracking_number || 'Missing'}</td><td>{r.days ?? '—'}</td><td>{r.last_scan_at ? fmtDate(r.last_scan_at) : 'No scan'}</td></tr>)}
          </tbody></table>
        </div>) : null}
    </>);
}
