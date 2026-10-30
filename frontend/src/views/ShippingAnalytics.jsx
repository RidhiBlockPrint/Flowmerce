'use client';
import { useNavigate } from '../lib/nav';
import { useApi } from '../lib/api';
import { fmtInt } from '../lib/format';
import { CATS } from '../lib/shipping';
import { Columns, Donut } from '../components/charts';
import { Kpi } from '../components/metrics';
import { Card, Empty, ErrorState, LoadingBlock, PageHead, Paged, Pill } from '../components/ui';
import { Icon } from '../components/Icon';

const money = (v, cur) => {
    try {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: cur || 'USD', maximumFractionDigits: 0 }).format(v);
    }
    catch {
        return fmtInt(Math.round(v));
    }
};
const HEALTH_TONE = { 'Needs action': 'crit', Watch: 'warn', Healthy: 'ok' };
const HEAT = ['red', 'orange', 'yellow', 'grey', 'on_track', 'no_scan'];

/** Shipping analytics from the saved shipment records: aging, weeks, carriers, stages and what to do today. */
export default function ShippingAnalytics() {
    const { data, error, loading, reload } = useApi('/shipping/analytics');
    const nav = useNavigate();
    const k = data?.kpis;
    const maxCell = Math.max(1, ...(data?.carriers ?? []).slice(0, 8).flatMap((c) => Object.values(c.cats)));
    return (<>
      <PageHead title="Shipping analytics" sub="Computed from the saved shipments. Numbers change when new data is synced or imported."/>
      <ErrorState error={error} onRetry={reload}/>
      {loading && !data ? <LoadingBlock rows={6}/> : null}
      {data?.empty ? <Card><Empty icon="analytics" title="No shipments to analyse yet">Sync or import shipments first.</Empty></Card> : null}
      {data && !data.empty ? (<div className="col" style={{ gap: 16 }}>
          <div className="kpis">
            <Kpi label="Active shipments" value={fmtInt(k.active)}/>
            <Kpi label="Critical (9+ days)" value={`${fmtInt(k.critical)} (${k.critical_pct}%)`}/>
            <Kpi label="On track share" value={`${k.on_track_pct}%`}/>
            <Kpi label="Avg days in stage" value={`${k.avg_days} d`}/>
            <Kpi label="Stuck (no scan 5+ d)" value={fmtInt(k.stuck)}/>
            <Kpi label="Carriers in use" value={fmtInt(k.carriers)}/>
            <Kpi label="Value at risk (critical orders)" value={k.value_at_risk === null ? '—' : money(k.value_at_risk, k.value_currency)} na={k.value_at_risk === null} foot={k.value_at_risk === null ? <span className="muted xs">Needs order totals (order checks)</span> : null}/>
          </div>

          <div className="grid cols-2">
            <Card title="Aging distribution" sub="Click a bar to open those shipments">
              <Columns ariaLabel="Active shipments by aging stage" items={data.aging.map((a) => ({ label: CATS[a.key].short, value: a.count, color: CATS[a.key].color }))}/>
              <div className="row-wrap gap-8 mt-8">{data.aging.map((a) => <button key={a.key} className="btn ghost xs" onClick={() => nav(`/shipping/shipments?view=${a.key}`)}>{CATS[a.key].short}</button>)}</div>
            </Card>
            <Card title="Pending by week created" sub="Active shipments, by the week the order was placed">
              <Columns ariaLabel="Active shipments by order week" items={data.weeks.map((w) => ({ label: w.week.slice(5), value: w.count }))}/>
            </Card>
            <Card title="Stage mix" sub="All saved shipments">
              <div className="row" style={{ gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
                <Donut ariaLabel="Shipments by stage" size={150} center={fmtInt(data.stages.pre_dispatch + data.stages.dispatched)} sub="total" items={[
                    { label: 'Not dispatched', value: data.stages.pre_dispatch, color: '#8b8279' },
                    { label: 'Dispatched', value: data.stages.dispatched, color: '#d9661a' },
                    { label: 'Delivered', value: data.stages.delivered, color: '#2f5d8a' },
                ]}/>
                <div className="legend-list">
                  {[['Not dispatched', data.stages.pre_dispatch, '#8b8279'], ['Dispatched', data.stages.dispatched, '#d9661a'], ['Delivered', data.stages.delivered, '#2f5d8a']].map(([l, v, c]) => <div key={l} className="row" style={{ gap: 8 }}><i style={{ width: 10, height: 10, borderRadius: 3, background: c }}/>{l}<b style={{ marginLeft: 'auto' }}>{fmtInt(v)}</b></div>)}
                </div>
              </div>
            </Card>
            <Card title="Dispatch day" sub="Active shipments by the weekday they were dispatched">
              <Columns ariaLabel="Active shipments by dispatch weekday" items={data.dispatch_days.map((d) => ({ label: d.day, value: d.critical + d.other, color: d.critical > d.other ? CATS.red.color : 'var(--ridhi)' }))}/>
            </Card>
          </div>

          <Card title="Carrier scorecard" sub="Active shipments per carrier" flush>
            <div className="table-wrap">
              <table className="t compact">
                <thead><tr><th>Carrier</th><th className="r">Active</th><th className="r">Critical</th><th className="r">Critical %</th><th className="r">Stuck</th><th className="r">Exceptions</th><th className="r">Avg days</th><th>Health</th></tr></thead>
                <tbody>
                  {data.carriers.map((c) => (<tr key={c.name} className="clickable" onClick={() => nav(`/shipping/shipments?carrier=${encodeURIComponent(c.name)}`)}>
                      <td className="strong">{c.name}</td><td className="r">{fmtInt(c.active)}</td><td className="r">{fmtInt(c.critical)}</td><td className="r">{c.critical_pct}%</td>
                      <td className="r">{fmtInt(c.stuck)}</td><td className="r">{fmtInt(c.exceptions)}</td><td className="r">{c.avg_days} d</td>
                      <td><Pill tone={HEALTH_TONE[c.health]}>{c.health}</Pill></td>
                    </tr>))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Aging heatmap" sub="Carrier by aging stage. Click a cell to open those shipments" flush>
            <div className="table-wrap">
              <table className="t compact">
                <thead><tr><th>Carrier</th>{HEAT.map((h) => <th key={h} className="r">{CATS[h].short}</th>)}</tr></thead>
                <tbody>
                  {data.carriers.slice(0, 8).map((c) => (<tr key={c.name}>
                      <td className="strong">{c.name}</td>
                      {HEAT.map((h) => {
                        const n = c.cats[h] ?? 0;
                        return (<td key={h} className="r heat-cell" style={{ cursor: n ? 'pointer' : 'default', background: n ? `color-mix(in srgb, ${CATS[h].color} ${Math.round((0.12 + 0.7 * n / maxCell) * 100)}%, transparent)` : undefined }} onClick={n ? () => nav(`/shipping/shipments?view=${h}&carrier=${encodeURIComponent(c.name)}`) : undefined}>{n || '·'}</td>);
                      })}
                    </tr>))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="What to do today">
            {data.tips.length ? <ul className="brief-list">{data.tips.map((t) => <li key={t}><Icon name="arrowRight" size="sm"/><span>{t}</span></li>)}</ul> : <p className="muted small" style={{ margin: 0 }}>Nothing urgent right now.</p>}
          </Card>
        </div>) : null}
    </>);
}
