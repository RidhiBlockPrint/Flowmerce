import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, useApi, qs, download } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtDateTime, fmtInt, timeAgo } from '../lib/format';
import { Button, Card, ErrorState, Field, LoadingBlock, PageHead, Pill } from '../components/ui';
import { ConfirmDialog, useToast } from '../components/overlays';
import { Icon } from '../components/Icon';

type Kind = { key: string; title: string; description: string; importable: boolean; fields: { key: string; header: string; type: string; required?: boolean; values?: string[]; description: string }[] };

export default function DataReports() {
  const kinds = useApi<Kind[]>('/data/kinds');
  const health = useApi<any>('/data/health');
  const { can, me, refreshMe } = useApp();
  const toast = useToast();
  const [demo, setDemo] = useState<'load' | 'clear' | null>(null);
  const [busy, setBusy] = useState(false);
  const runDemo = async () => {
    setBusy(true);
    try { const r = await api.post<any>('/admin/demo', { action: demo }); toast.ok(demo === 'load' ? `${fmtInt(r.rows)} demo rows loaded.` : `${fmtInt(r.removed)} demo rows removed.`); setDemo(null); refreshMe(); } catch (e) { toast.error(e); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHead title="Data & reports" sub="Excel workbooks for data that cannot be fetched live — keyword volumes, offline review notes, and Search Console / GA4 exports when the APIs are not connected — plus filtered report exports." />
      <ErrorState error={kinds.error || health.error} onRetry={() => { kinds.reload(); health.reload(); }} />
      {!kinds.data ? <LoadingBlock rows={6} /> : (
        <div className="col" style={{ gap: 16 }}>
          <div className="grid main-side">
            <div className="col" style={{ gap: 16, minWidth: 0 }}>
              {can('data:import') ? <Importer kinds={kinds.data.filter((k) => k.importable)} onImported={() => health.reload()} /> : null}
              <Exporter kinds={kinds.data} />
            </div>
            <div className="col" style={{ gap: 16, minWidth: 0 }}>
              <Card title="Data health" sub="Stale or incomplete records" flush>
                {health.data ? (
                  <div className="alert-list">
                    {health.data.flags.length ? health.data.flags.map((f: any, i: number) => (
                      <Link key={i} className="alert-item" to={f.link || '#'}>
                        <span className={`sev ${f.severity === 'warning' ? 'warning' : 'info'}`} />
                        <span className="small"><b>{f.count}</b> {f.message}<span className="muted xs" style={{ display: 'block' }}>{f.area}</span></span>
                      </Link>
                    )) : <div className="alert-item small muted"><Icon name="checkCircle" />No stale or incomplete records found.</div>}
                  </div>
                ) : <div className="card-body"><LoadingBlock rows={3} /></div>}
              </Card>
              <Card title="Import history" flush>
                <div className="alert-list">
                  {health.data?.imports.map((i: any) => (
                    <div key={i.id} className="alert-item">
                      <Icon name="sheet" size="sm" />
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <span className="small strong ellipsis" style={{ display: 'block' }}>{i.filename}</span>
                        <span className="muted xs">{i.kind} · {i.user_name ?? '—'} · {timeAgo(i.created_at)}</span>
                        <span className="xs" style={{ display: 'block' }}>{i.inserted} new · {i.updated} updated · {i.duplicates} duplicates · {i.rejected ? <span style={{ color: 'var(--crit)' }}>{i.rejected} rejected</span> : '0 rejected'}</span>
                      </span>
                    </div>
                  ))}
                  {health.data && !health.data.imports.length ? <div className="alert-item small muted">No imports yet.</div> : null}
                </div>
              </Card>
              {can('demo:manage') ? (
                <Card title="Demo fixtures" sub="Synthetic Search Console and GA4 rows for trying the analytics screens before Google is connected">
                  <div className="col gap-12 small">
                    <div className="callout demo"><Icon name="info" /><div>Demo rows are stored separately, labelled “Demo — not real” everywhere, never exported, and ignored whenever live or imported data exists for the same brand and range.</div></div>
                    <div className="row-wrap">
                      {me.demoLoaded ? <Button icon="close" onClick={() => setDemo('clear')}>Clear demo data</Button> : <Button icon="sparkle" onClick={() => setDemo('load')}>Load demo data</Button>}
                    </div>
                  </div>
                </Card>
              ) : null}
            </div>
          </div>
          <Card title="Templates & field schemas" sub="Each workbook has a Data sheet with dropdowns and number checks, a Fields sheet describing every column, and an About sheet">
            <div className="grid cols-3">
              {kinds.data.map((k) => (
                <div key={k.key} className="stage" style={{ gap: 6 }}>
                  <div className="row"><Icon name="sheet" /><span className="strong" style={{ flex: 1 }}>{k.title}</span>{k.importable ? <Pill tone="info">import</Pill> : <Pill>report</Pill>}</div>
                  <div className="muted small">{k.description}</div>
                  <details className="small">
                    <summary style={{ cursor: 'pointer' }} className="strong">{k.fields.length} columns · {k.fields.filter((f) => f.required).length} required</summary>
                    <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                      {k.fields.map((f) => <li key={f.key}><span className="mono">{f.header}</span>{f.required ? <b> *</b> : null} <span className="muted">{f.type}{f.values ? `: ${f.values.join(' / ')}` : ''}</span></li>)}
                    </ul>
                  </details>
                  {k.importable ? <div><Button size="sm" icon="download" onClick={() => download(`/data/templates/${k.key}`).catch(toast.error)}>Template</Button></div> : null}
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
      {demo ? (
        <ConfirmDialog title={demo === 'load' ? 'Load demo fixtures?' : 'Clear demo fixtures?'} confirmLabel={demo === 'load' ? 'Load demo data' : 'Clear demo data'} busy={busy} onClose={() => setDemo(null)} onConfirm={runDemo}>
          <p style={{ margin: 0 }}>{demo === 'load' ? 'Adds 180 days of synthetic Search Console and GA4 rows for the synced articles. A banner stays on every screen while they are loaded.' : 'Removes every demo row. Live and imported data are not touched.'}</p>
        </ConfirmDialog>
      ) : null}
    </>
  );
}

function Importer({ kinds, onImported }: { kinds: Kind[]; onImported: () => void }) {
  const [kind, setKind] = useState(kinds[0]?.key ?? '');
  const [file, setFile] = useState<File | null>(null);
  const [buf, setBuf] = useState<ArrayBuffer | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [dup, setDup] = useState<'skip' | 'update'>('skip');
  const [busy, setBusy] = useState<'preview' | 'commit' | null>(null);
  const [err, setErr] = useState('');
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const choose = async (f: File | null) => {
    setPreview(null); setErr('');
    if (!f) return;
    if (!/\.xlsx$/i.test(f.name)) { setErr('Choose an .xlsx workbook.'); return; }
    if (f.size > 20 * 1024 * 1024) { setErr('The file is larger than 20 MB.'); return; }
    setFile(f);
    const b = await f.arrayBuffer();
    setBuf(b);
    await validate(b, f.name);
  };
  const validate = async (b: ArrayBuffer, name: string, k = kind) => {
    setBusy('preview'); setErr('');
    try { setPreview(await api.post<any>(`/data/import/${k}${qs({ mode: 'preview' })}`, b, { 'X-Filename': encodeURIComponent(name) })); }
    catch (e: any) { setErr(e.message); setPreview(null); } finally { setBusy(null); }
  };
  const commit = async () => {
    if (!buf || !file) return;
    setBusy('commit');
    try {
      const r = await api.post<any>(`/data/import/${kind}${qs({ mode: 'commit', duplicates: dup })}`, buf, { 'X-Filename': encodeURIComponent(file.name) });
      toast.ok(`Imported: ${r.inserted} new, ${r.updated} updated, ${r.duplicates} duplicates skipped, ${r.rejected} rejected.`);
      setFile(null); setBuf(null); setPreview(null); onImported();
    } catch (e: any) { setErr(e.message); } finally { setBusy(null); }
  };
  const s = preview?.summary;
  const importable = s ? s.valid - s.duplicatesInFile - (dup === 'skip' ? s.duplicatesExisting : 0) : 0;
  return (
    <Card title="Import a workbook" sub="Step 1 validates every row; nothing is saved until you confirm step 2.">
      <div className="col gap-12">
        <Field label="What does the file contain?">
          <select className="select" value={kind} onChange={(e) => { setKind(e.target.value); if (buf && file) void validate(buf, file.name, e.target.value); }}>
            {kinds.map((k) => <option key={k.key} value={k.key}>{k.title}</option>)}
          </select>
        </Field>
        <div className={`dropzone ${over ? 'over' : ''}`} role="button" tabIndex={0}
          onClick={() => input.current?.click()} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') input.current?.click(); }}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); void choose(e.dataTransfer.files[0] ?? null); }}>
          <Icon name="upload" size="lg" />
          <div className="strong mt-8">{file ? file.name : 'Drop an .xlsx file here or click to choose'}</div>
          <div className="muted small">Use the matching template; extra columns are ignored.</div>
          <input ref={input} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden onChange={(e) => { void choose(e.target.files?.[0] ?? null); e.target.value = ''; }} />
        </div>
        {busy === 'preview' ? <div className="row muted small"><Icon name="loader" className="spin" size="sm" />Validating…</div> : null}
        {err ? <div className="callout crit" role="alert"><Icon name="alert" />{err}</div> : null}
        {s ? (
          <>
            <div className="stat-row" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))' }}>
              <div className="stat"><div className="v">{s.total}</div><div className="l">Rows</div></div>
              <div className="stat"><div className="v" style={{ color: 'var(--ok)' }}>{s.valid}</div><div className="l">Valid</div></div>
              <div className={`stat ${s.invalid ? 'alert' : ''}`}><div className="v">{s.invalid}</div><div className="l">With errors</div></div>
              <div className={`stat ${s.duplicatesInFile + s.duplicatesExisting ? 'warn' : ''}`}><div className="v">{s.duplicatesInFile + s.duplicatesExisting}</div><div className="l">Duplicates</div></div>
              <div className="stat"><div className="v">{s.withWarnings}</div><div className="l">Warnings</div></div>
            </div>
            {preview.warnings.map((w: string, i: number) => <div key={i} className="callout warn"><Icon name="alert" />{w}</div>)}
            {preview.rows.some((r: any) => r.errors.length || r.warnings.length || r.duplicate) ? (
              <div className="table-wrap" style={{ maxHeight: 300, border: '1px solid var(--line)', borderRadius: 10 }}>
                <table className="t compact">
                  <thead><tr><th>Row</th><th>Problem</th></tr></thead>
                  <tbody>
                    {preview.rows.filter((r: any) => r.errors.length || r.warnings.length || r.duplicate).map((r: any) => (
                      <tr key={r.row}>
                        <td className="mono">{r.row}</td>
                        <td className="small">
                          {r.errors.map((e: string, i: number) => <div key={i} style={{ color: 'var(--crit)' }}>✕ {e}</div>)}
                          {r.duplicate === 'file' ? <div style={{ color: 'var(--warn)' }}>Duplicate of an earlier row in this file — skipped</div> : null}
                          {r.duplicate === 'existing' ? <div style={{ color: 'var(--warn)' }}>Already in the dashboard — {dup === 'update' ? 'will be updated' : 'will be skipped'}</div> : null}
                          {r.warnings.map((w: string, i: number) => <div key={i} className="muted">⚠ {w}</div>)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="callout ok"><Icon name="checkCircle" />Every row passed validation.</div>}
            {s.duplicatesExisting ? (
              <div className="row-wrap">
                <span className="small strong">Rows already in the dashboard:</span>
                <div className="seg sm"><button aria-pressed={dup === 'skip'} onClick={() => setDup('skip')}>Skip them</button><button aria-pressed={dup === 'update'} onClick={() => setDup('update')}>Update them</button></div>
              </div>
            ) : null}
            <div className="row-wrap">
              <Button variant="primary" icon="upload" loading={busy === 'commit'} disabled={importable <= 0} onClick={commit}>
                Import {importable} row{importable === 1 ? '' : 's'}
              </Button>
              <span className="muted small">Rows with errors are not imported. Each import is recorded in the audit log.</span>
            </div>
          </>
        ) : null}
      </div>
    </Card>
  );
}

function Exporter({ kinds }: { kinds: Kind[] }) {
  const brand = useBrandParam();
  const { range, can, me } = useApp();
  const [kind, setKind] = useState('articles');
  const [b, setB] = useState<string>(brand ?? '');
  const [useRange, setUseRange] = useState(true);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const dated = ['gsc_pages', 'ga4_pages', 'audit'].includes(kind);
  const go = async () => {
    setBusy(true);
    try { await download(`/data/export/${kind}${qs({ brand: b, status, from: dated && useRange ? range.from : undefined, to: dated && useRange ? range.to : undefined })}`); }
    catch (e) { toast.error(e); } finally { setBusy(false); }
  };
  return (
    <Card title="Export a report" sub="Exports use the same layout as the templates, so they can be edited and re-imported.">
      <div className="form-grid">
        <Field label="Report"><select className="select" value={kind} onChange={(e) => { setKind(e.target.value); setStatus(''); }}>{kinds.filter((k) => k.key !== 'audit' || can('audit:view')).map((k) => <option key={k.key} value={k.key}>{k.title}</option>)}</select></Field>
        <Field label="Brand"><select className="select" value={b} onChange={(e) => setB(e.target.value)}><option value="">Both brands</option>{me.brands.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
        {kind === 'articles' ? (
          <Field label="Status"><select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option><option value="idea,draft,changes_requested">Drafts</option><option value="in_review">In review</option><option value="approved">Approved</option><option value="published">Published</option><option value="failed">Failed</option>
          </select></Field>
        ) : null}
        {kind === 'topics' ? (
          <Field label="Status"><select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option><option value="proposed">Proposed</option><option value="validated">Validated</option><option value="approved">Approved</option><option value="rejected">Rejected</option>
          </select></Field>
        ) : null}
        {dated ? <label className="check full"><input type="checkbox" checked={useRange} onChange={(e) => setUseRange(e.target.checked)} />Only the selected date range ({range.from} – {range.to})</label> : null}
      </div>
      <div className="row-wrap mt-16">
        <Button variant="primary" icon="download" loading={busy} onClick={go}>Download .xlsx</Button>
        <span className="muted small">Generated {fmtDateTime(new Date().toISOString())}; the About sheet records filters and sources.</span>
      </div>
    </Card>
  );
}
