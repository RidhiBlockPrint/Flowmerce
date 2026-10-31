'use client';
import Link from 'next/link';
import { useApi } from '../lib/api';
import { useNavigate } from '../lib/nav';
import { fmtDate, fmtInt } from '../lib/format';
import { FLAGS, GROUPS, TIERS } from '../lib/shipping';
import { BarList, Columns } from '../components/charts';
import { Card, Empty, ErrorState, LoadingBlock, PageHead } from '../components/ui';
import { Icon } from '../components/Icon';
import { ExportButton, RunBanner, SyncButton } from '../components/shipping';

const ORDER = ['delivered', 'in_transit', 'delayed', 'unfulfilled', 'needs_action', 'lost_missing', 'no_tracking_id', 'no_carrier'];
const HINT = {
    delivered: 'Shopify says delivered, or a team mark',
    in_transit: 'Fulfilled, within 3 days',
    delayed: 'Fulfilled, 4+ days and not delivered',
    unfulfilled: 'Not fulfilled in Shopify yet. No delay is tracked here',
    needs_action: 'Needs a person: see below',
    lost_missing: 'Marked lost, or no update for 14+ days',
    no_tracking_id: 'Carrier known, no tracking number',
    no_carrier: 'No carrier and no tracking number',
};

/** Shipping overview: every order in one group, the delay tiers, and what needs action. */
export default function ShippingOverview() {
    const { data, error, loading, reload } = useApi('/shipping/orders/overview');
    const nav = useNavigate();
    const c = data?.counts;
    const value = (key) => (key === 'needs_action' ? c.needs_action : c[key]);
    return (<>
      <PageHead title="Shipping overview" sub={data && !data.empty ? <>{fmtInt(c.total)} orders for the Ridhi store, each in one group. Delay is counted in days from the fulfilled date, the same for every carrier.</> : 'Delivery status and delays for the Ridhi store'} actions={<>
          <ExportButton kind="" label="Export orders (CSV)" path="orders/export"/>
          <SyncButton onDone={reload}/>
        </>}/>
      <ErrorState error={error} onRetry={reload}/>
      {loading && !data ? <LoadingBlock rows={6}/> : null}
      {data ? <RunBanner run={data.run}/> : null}
      {data?.empty ? <Card><Empty icon="send" title="No orders saved yet">Run “Sync now”, or import the existing data with <span className="mono">python scripts/import_shipping_data.py</span>.</Empty></Card> : null}
      {data && !data.empty ? (<div className="col" style={{ gap: 16 }}>
          <div className="kpis">
            {ORDER.map((g) => (<Link key={g} href={`/shipping/orders?group=${g}`} className="kpi kpi-btn" style={{ textDecoration: 'none' }}>
                <div className="kpi-label"><span className="sev" style={{ marginTop: 0, background: GROUPS[g].color }}/>{GROUPS[g].label}</div>
                <div className="kpi-value">{fmtInt(value(g))}</div>
                <div className="kpi-foot"><span className="muted xs">{HINT[g]}</span></div>
              </Link>))}
          </div>

          <div className="grid cols-2">
            <Card title="Delayed orders by tier" sub="Days since fulfilled, not delivered. Same days for every carrier." actions={<Link className="btn ghost xs" href="/shipping/orders?group=delayed">Open delayed</Link>}>
              <div className="hero-items" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', marginTop: 0 }}>
                {Object.keys(TIERS).map((t) => (<Link key={t} className="hero-item" href={`/shipping/orders?group=delayed&tier=${t}`}><b style={{ color: TIERS[t].color }}>{fmtInt(c.delayed_tiers[t])}</b><span>{TIERS[t].label}</span></Link>))}
              </div>
            </Card>
            <Card title="Needs action" sub="Orders with something a person should look at" actions={<Link className="btn ghost xs" href="/shipping/orders?group=needs_action">Open list</Link>}>
              <div className="col gap-8">
                {Object.keys(FLAGS).map((f) => (<Link key={f} href={`/shipping/orders?flag=${f}`} className="row" style={{ gap: 8, color: 'inherit' }}><Icon name="alert" size="sm"/>{FLAGS[f]}<b style={{ marginLeft: 'auto' }}>{fmtInt(c.flags[f])}</b></Link>))}
              </div>
            </Card>
          </div>

          <div className="grid cols-2">
            <Card title="Open orders by week fulfilled" sub="In transit and delayed, by the week they were fulfilled">
              <Columns ariaLabel="Open orders by week fulfilled" items={data.weeks.map((w) => ({ label: w.week.slice(5), value: w.count }))}/>
            </Card>
            <Card title="Carriers" sub="Open orders and how many are delayed" actions={<Link className="btn ghost xs" href="/shipping/analytics">Transit times</Link>}>
              <BarList format={fmtInt} empty="No open orders" rows={data.carriers.map((r) => ({ key: r.name, value: r.open, label: <span className="ellipsis">{r.name}</span>, extra: <span className="faint">{fmtInt(r.delayed)} delayed · {fmtInt(r.critical)} critical</span>, onClick: () => nav(`/shipping/orders?carrier=${encodeURIComponent(r.name)}`) }))}/>
            </Card>
          </div>
        </div>) : null}
    </>);
}
