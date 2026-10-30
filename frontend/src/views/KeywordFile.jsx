'use client';
import { useMemo, useState } from 'react';
import { useApi } from '../lib/api';
import { fmtInt, timeAgo } from '../lib/format';
import { Empty, ErrorState, LoadingBlock, Pill, Paged } from '../components/ui';
import { Icon } from '../components/Icon';

const VIEWS = [
    { key: 'all', label: 'All' },
    { key: 'opportunity', label: 'Opportunities' },
    { key: 'new', label: 'New this run' },
];
const dash = (v) => (v === null || v === undefined ? '—' : v);

/**
 * Ridhi keyword research, read straight from the workbook in data/ (GET /api/keyword-file).
 * Read-only: nothing is imported into the database and the file is never changed. Figures are shown as the
 * sheet gives them (Semrush estimates, Search Console numbers); blank cells stay blank.
 */
export default function KeywordFile() {
    const { data, error, loading, reload } = useApi('/keyword-file');
    const [view, setView] = useState('all');
    const [cluster, setCluster] = useState('');
    const [q, setQ] = useState('');
    const rows = useMemo(() => {
        const needle = q.trim().toLowerCase();
        return (data?.rows ?? [])
            .filter((r) => (view === 'all' ? true : r[view]))
            .filter((r) => !cluster || r.cluster === cluster)
            .filter((r) => !needle || r.keyword.toLowerCase().includes(needle) || (r.topic ?? '').toLowerCase().includes(needle))
            .sort((a, b) => (b.search_volume ?? -1) - (a.search_volume ?? -1));
    }, [data, view, cluster, q]);
    const counts = useMemo(() => ({
        all: data?.rows.length ?? 0,
        opportunity: data?.rows.filter((r) => r.opportunity).length ?? 0,
        new: data?.rows.filter((r) => r.new).length ?? 0,
    }), [data]);
    return (<section className="card flush mb-16">
      <div className="card-head">
        <div style={{ minWidth: 0 }}>
          <h2 className="card-title"><span className="brand-dot ridhi"/> Ridhi keyword research</h2>
          <div className="card-sub">{data?.found ? <>From <span className="mono">data/{data.file}</span> · file updated {timeAgo(data.modifiedAt)} · read-only</> : 'Read from the keyword workbook in the data folder'}</div>
        </div>
        <button className="btn ghost xs" style={{ marginLeft: 'auto' }} onClick={reload}><Icon name="refresh" size="sm"/>Reload file</button>
      </div>
      <ErrorState error={error} onRetry={reload}/>
      {loading && !data ? <LoadingBlock rows={4}/> : null}
      {data && !data.found ? (<Empty icon="sheet" title="No Ridhi keyword file found">Put a workbook named <span className="mono">{data.pattern}</span> in the <span className="mono">{data.folder}</span> folder of the project. Flowmerce reads the newest one.</Empty>) : null}
      {data?.found && data.error ? <div className="callout crit mb-12" style={{ margin: 16 }}><Icon name="alert"/>{data.error}</div> : null}
      {data?.found && !data.error ? (<>
          <div className="toolbar" style={{ padding: '10px 16px' }}>
            <div className="seg sm" role="group" aria-label="Keyword set">
              {VIEWS.map((v) => <button key={v.key} aria-pressed={view === v.key} onClick={() => setView(v.key)}>{v.label} {counts[v.key]}</button>)}
            </div>
            <select className="select sm" value={cluster} onChange={(e) => setCluster(e.target.value)} aria-label="Cluster">
              <option value="">All clusters</option>
              {data.clusters.map((c) => <option key={c}>{c}</option>)}
            </select>
            <input className="input sm" style={{ maxWidth: 240 }} placeholder="Search keywords" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search keywords"/>
            <span className="spacer"/>
            <span className="muted small">{rows.length} of {counts.all} keywords</span>
          </div>
          <Paged rows={rows} resetKey={view + cluster + q}>{(pageRows) => (<>
<div className="table-wrap">
            <table className="t compact">
              <thead><tr>
                <th>Keyword</th><th className="hide-sm">Intent</th><th className="r">US volume</th><th className="r">KD</th>
                <th className="r hide-md">GSC clicks</th><th className="r hide-md">GSC impr.</th><th className="r hide-md">Avg pos.</th>
                <th>Recommended action</th>
              </tr></thead>
              <tbody>
                {pageRows.map((r) => (<tr key={r.id} title={r.notes ?? undefined}>
                    <td className="title-cell">
                      <span className="ttl">{r.keyword} {r.opportunity ? <Pill tone="ok">Opportunity</Pill> : null} {r.new ? <Pill tone="info">New</Pill> : null}</span>
                      <span className="sub">{[r.topic, r.cluster].filter(Boolean).join(' · ') || '—'}</span>
                    </td>
                    <td className="hide-sm small">{r.intent ?? '—'}</td>
                    <td className="r">{r.search_volume === null ? '—' : fmtInt(r.search_volume)}</td>
                    <td className="r">{dash(r.keyword_difficulty)}</td>
                    <td className="r hide-md">{r.gsc_clicks === null ? '—' : fmtInt(r.gsc_clicks)}</td>
                    <td className="r hide-md">{r.gsc_impressions === null ? '—' : fmtInt(r.gsc_impressions)}</td>
                    <td className="r hide-md">{r.gsc_avg_position === null ? '—' : r.gsc_avg_position.toFixed(1)}</td>
                    <td className="small" style={{ minWidth: 200 }}>{r.recommended_action ?? '—'}{r.confidence ? <span className="faint xs" style={{ display: 'block' }}>Confidence: {r.confidence}</span> : null}</td>
                  </tr>))}
              </tbody>
            </table>
          </div>
</>)}</Paged>
          {!rows.length ? <Empty icon="search" title="No keywords match">Try another set, cluster or search term.</Empty> : null}
          <div className="card-foot"><span className="muted xs">{data.title ?? 'Keyword workbook'}. Volumes are Semrush US free-plan estimates and difficulty is Semrush KD %, as recorded in the file; blank cells mean the file has no value.</span></div>
        </>) : null}
    </section>);
}
