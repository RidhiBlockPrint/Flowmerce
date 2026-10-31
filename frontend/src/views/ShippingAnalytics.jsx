'use client';
import { useNavigate } from '../lib/nav';
import { useApi } from '../lib/api';
import { fmtInt } from '../lib/format';
import { TIERS } from '../lib/shipping';
import { Columns } from '../components/charts';
import { Kpi } from '../components/metrics';
import { Card, Empty, ErrorState, LoadingBlock, PageHead } from '../components/ui';

/** Transit time (fulfilled to delivered) per carrier and the spread of delivery times. */
export default function ShippingAnalytics() {
    const { data, error, loading, reload } = useApi('/shipping/orders/analytics');
    const nav = useNavigate();
    const c = data?.counts;
    return (<>
      <PageHead title="Shipping analytics" sub="How long deliveries take, from the fulfilled date to the delivered date. Delivery times come from Shopify's delivered status, so carriers Shopify cannot track are missing here."/>
      <ErrorState error={error} onRetry={reload}/>
      {loading && !data ? <LoadingBlock rows={6}/> : null}
      {data?.empty ? <Card><Empty icon="analytics" title="No orders to analyse yet">Sync or import orders first.</Empty></Card> : null}
      {data && !data.empty ? (<div className="col" style={{ gap: 16 }}>
          <div className="kpis">
            <Kpi label="Orders" value={fmtInt(c.total)}/>
            <Kpi label="Delivered shipments measured" value={fmtInt(data.delivered_shipments)}/>
            <Kpi label="Average transit time" value={data.avg_transit_days === null ? '—' : `${data.avg_transit_days} days`} na={data.avg_transit_days === null}/>
            <Kpi label="Delayed now" value={fmtInt(c.delayed)} foot={<span className="muted xs">{fmtInt(c.delayed_tiers.critical)} critical</span>}/>
            <Kpi label="Needs action" value={fmtInt(c.needs_action)}/>
            <Kpi label="Lost / missing" value={fmtInt(c.lost_missing)}/>
          </div>
          <div className="grid cols-2">
            <Card title="Delivery time" sub="Delivered shipments, by days from fulfilled to delivered">
              <Columns ariaLabel="Delivered shipments by transit days" items={data.distribution.map((d) => ({ label: `${d.label} d`, value: d.count }))}/>
            </Card>
            <Card title="Delayed orders by tier" sub="Open orders past the expected time. Click a tier to open them." >
              <div className="hero-items" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', marginTop: 0 }}>
                {Object.keys(TIERS).map((t) => (<button key={t} type="button" className="hero-item" style={{ textAlign: 'left', cursor: 'pointer' }} onClick={() => nav(`/shipping/orders?group=delayed&tier=${t}`)}><b style={{ color: TIERS[t].color }}>{fmtInt(c.delayed_tiers[t])}</b><span>{TIERS[t].label}</span></button>))}
              </div>
            </Card>
          </div>
          <Card title="Carrier transit times" sub="Delivered shipments only. Slow = 4+ days." flush>
            <div className="table-wrap">
              <table className="t compact">
                <thead><tr><th>Carrier</th><th className="r">Delivered</th><th className="r">Average days</th><th className="r">Median</th><th className="r">90% within</th><th className="r">Slow (4+ d)</th><th className="r">13+ days</th></tr></thead>
                <tbody>
                  {data.carriers.map((r) => (<tr key={r.name} className="clickable" onClick={() => nav(`/shipping/orders?carrier=${encodeURIComponent(r.name)}`)}>
                      <td className="strong">{r.name}</td><td className="r">{fmtInt(r.delivered)}</td><td className="r">{r.avg_days}</td><td className="r">{r.median_days}</td>
                      <td className="r">{r.p90_days} d</td><td className="r">{fmtInt(r.slow)} ({r.slow_pct}%)</td><td className="r">{fmtInt(r.late)}</td>
                    </tr>))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>) : null}
    </>);
}
