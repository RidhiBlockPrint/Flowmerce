'use client';
import Link from 'next/link';
import { Delta, SourceBadge } from './ui';
import { Icon } from './Icon';
import { Sparkline } from './charts';
import { fmtCompact, fmtInt, fmtPct, fmtPos, fmtSeconds, pctChange } from '../lib/format';
export const BRAND_COLOR = { ridhi: 'var(--series-ridhi)', cpc: 'var(--series-cpc)' };
export function Kpi({ label, value, delta, invert, foot, spark, na, icon }) {
    return (<div className="kpi">
      <div className="kpi-label">{icon ? <Icon name={icon} size="sm"/> : null}{label}</div>
      <div className="row" style={{ alignItems: 'flex-end', gap: 10 }}>
        <div className={`kpi-value ${na ? 'na' : ''}`}>{value}</div>
        {spark && spark.length > 2 ? <div className="hide-sm" style={{ flex: 1, minWidth: 0, overflow: 'hidden', display: 'flex', justifyContent: 'flex-end', paddingBottom: 4 }}><Sparkline values={spark} width={72}/></div> : null}
      </div>
      <div className="kpi-foot">{delta !== undefined ? <Delta value={delta} invert={invert}/> : null}{foot}</div>
    </div>);
}
/** Sum brands only when every brand's numbers come from the same kind of source; mixing a live
 * brand with a demo or imported one into one total would misstate the business. */
export function combinable(parts) {
    const kinds = new Set(parts.map((p) => p.source.kind).filter(Boolean));
    return kinds.size <= 1;
}
export function GscKpis({ parts, short }) {
    const withData = parts.filter((p) => p.totals);
    if (!withData.length)
        return <NoMetrics what="Search Console"/>;
    if (!combinable(withData) && withData.length > 1) {
        return <div className="col gap-12">{withData.map((p) => <div key={p.brand}><div className="row mb-8"><span className={`brand-dot ${p.brand}`}/><b className="small">{short(p.brand)}</b><SourceBadge source={p.source}/></div><GscKpis parts={[p]} short={short}/></div>)}</div>;
    }
    const sum = (k, from) => withData.reduce((a, p) => a + (p[from]?.[k] ?? 0), 0);
    const clicks = sum('clicks', 'totals'), impr = sum('impressions', 'totals');
    const pClicks = sum('clicks', 'previous'), pImpr = sum('impressions', 'previous');
    const pos = (from) => {
        const w = withData.reduce((a, p) => a + (p[from]?.position ?? 0) * (p[from]?.impressions ?? 0), 0);
        const i = sum('impressions', from);
        return i ? w / i : null;
    };
    const ctr = impr ? clicks / impr : null;
    const pCtr = pImpr ? pClicks / pImpr : null;
    const daily = (k) => {
        const m = new Map();
        for (const p of withData)
            for (const r of p.series)
                m.set(r.date, (m.get(r.date) ?? 0) + (r[k] ?? 0));
        return [...m.entries()].sort().map(([, v]) => v);
    };
    const src = withData[0].source;
    const foot = <SourceBadge source={src} compact/>;
    return (<div className="kpis">
      <Kpi label="Organic clicks" value={fmtCompact(clicks)} delta={pctChange(clicks, pClicks)} spark={daily('clicks')} foot={foot}/>
      <Kpi label="Impressions" value={fmtCompact(impr)} delta={pctChange(impr, pImpr)} spark={daily('impressions')} foot={foot}/>
      <Kpi label="CTR" value={fmtPct(ctr)} delta={pctChange(ctr, pCtr)} foot={foot}/>
      <Kpi label="Avg. position" value={fmtPos(pos('totals'))} delta={pctChange(pos('totals'), pos('previous'))} invert foot={<><span className="faint">lower is better</span></>}/>
    </div>);
}
export function Ga4Kpis({ parts, short }) {
    const withData = parts.filter((p) => p.totals);
    if (!withData.length)
        return <NoMetrics what="GA4"/>;
    if (!combinable(withData) && withData.length > 1) {
        return <div className="col gap-12">{withData.map((p) => <div key={p.brand}><div className="row mb-8"><span className={`brand-dot ${p.brand}`}/><b className="small">{short(p.brand)}</b><SourceBadge source={p.source}/></div><Ga4Kpis parts={[p]} short={short}/></div>)}</div>;
    }
    const sum = (k, from) => withData.reduce((a, p) => a + (p[from]?.[k] ?? 0), 0);
    const sessions = sum('sessions', 'totals'), pSessions = sum('sessions', 'previous');
    const engaged = sum('engagedSessions', 'totals'), pEngaged = sum('engagedSessions', 'previous');
    const dur = withData.reduce((a, p) => a + (p.totals.avgEngagementSeconds ?? 0) * p.totals.sessions, 0) / (sessions || 1);
    const pDur = withData.reduce((a, p) => a + (p.previous?.avgEngagementSeconds ?? 0) * (p.previous?.sessions ?? 0), 0) / (pSessions || 1);
    const ke = sum('keyEvents', 'totals'), pKe = sum('keyEvents', 'previous');
    const daily = () => {
        const m = new Map();
        for (const p of withData)
            for (const r of p.series)
                m.set(r.date, (m.get(r.date) ?? 0) + r.sessions);
        return [...m.entries()].sort().map(([, v]) => v);
    };
    const foot = <SourceBadge source={withData[0].source} compact/>;
    return (<div className="kpis">
      <Kpi label="Sessions (blog landing)" value={fmtCompact(sessions)} delta={pctChange(sessions, pSessions)} spark={daily()} foot={foot}/>
      <Kpi label="Engagement rate" value={fmtPct(sessions ? engaged / sessions : null)} delta={pctChange(sessions ? engaged / sessions : null, pSessions ? pEngaged / pSessions : null)} foot={foot}/>
      <Kpi label="Avg. engagement time" value={fmtSeconds(sessions ? dur : null)} delta={pctChange(dur, pDur)} foot={foot}/>
      <Kpi label="Key events" value={fmtInt(ke)} delta={pctChange(ke, pKe)} foot={foot}/>
    </div>);
}
export function NoMetrics({ what }) {
    return (<div className="callout info">
      <Icon name="info"/>
      <div>
        <b>No {what} data for this range.</b> Connect {what} under <Link href="/integrations">Integrations</Link>, or import an export in <Link href="/data">Data &amp; reports</Link>. Nothing is estimated or filled in.
      </div>
    </div>);
}
export function seriesFrom(parts, key, label) {
    return parts.filter((p) => p.series.length).map((p) => ({
        key: p.brand,
        label: label(p.brand) + (p.source.kind === 'demo' ? ' (demo)' : ''),
        color: BRAND_COLOR[p.brand],
        dashed: p.source.kind === 'demo',
        points: p.series.map((r) => ({ x: r.date, y: r[key] ?? null })),
    }));
}
