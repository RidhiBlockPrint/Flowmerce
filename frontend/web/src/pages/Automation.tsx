import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, useApi, qs } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtDateTime, timeAgo } from '../lib/format';
import { Button, Card, ErrorState, LoadingBlock, PageHead, Pill, BrandTag } from '../components/ui';
import { Dialog, useToast } from '../components/overlays';
import { Icon } from '../components/Icon';

const STATE: Record<string, { label: string; tone: string }> = {
  ok: { label: 'OK', tone: 'ok' }, needs_action: { label: 'Needs action', tone: 'warn' }, failed: { label: 'Failed', tone: 'crit' },
  running: { label: 'Running', tone: 'info' }, paused: { label: 'Paused', tone: 'neutral' }, pending_setup: { label: 'Pending setup', tone: 'outline' }, idle: { label: 'Not run yet', tone: 'neutral' },
};
const RUN_TONE: Record<string, string> = { succeeded: 'ok', failed: 'crit', running: 'info', waiting: 'warn', skipped: 'neutral' };
const STAGE_LINK: Record<string, string> = {
  keyword_validation: '/topics?status=proposed', topic_approval: '/topics?status=validated', content_generation: '/topics?status=approved',
  content_approval: '/blogs?status=in_review', image_selection: '/blogs?status=draft,in_review,approved', shopify_draft: '/blogs?status=approved', publication_approval: '/publishing',
};

export default function Automation() {
  const brand = useBrandParam();
  const { can, brandOf, me } = useApp();
  const q = useApi<any>(`/automation${qs({ brand })}`);
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [pause, setPause] = useState<string | null>(null);

  const runStage = async (b: string, stage: string, label: string) => {
    setBusy(`${b}:${stage}`);
    try {
      const r = await api.post<any>(`/automation/${b}/stages/${stage}/run`);
      if (r.status === 'failed') toast.error(`${label} failed: ${r.error}`); else toast.ok(`${label}: ${r.message}`);
    } catch (e) { toast.error(e); } finally { setBusy(null); q.reload(); }
  };
  const retry = async (id: number) => {
    setBusy(`run:${id}`);
    try { const r = await api.post<any>(`/automation/runs/${id}/retry`); if (r.status === 'failed') toast.error(r.error); else toast.ok(r.message); } catch (e) { toast.error(e); } finally { setBusy(null); q.reload(); }
  };
  const resume = async (b: string) => { try { await api.post(`/automation/${b}/resume`); toast.ok('Automation resumed.'); q.reload(); } catch (e) { toast.error(e); } };

  return (
    <>
      <PageHead title="Automation" sub="Topic research → keyword validation → topic approval → content generation → content approval → image selection → Shopify draft → publication approval → performance tracking. Automated stages run only when someone starts them; the background job only refreshes data." />
      <ErrorState error={q.error} onRetry={q.reload} />
      {q.loading && !q.data ? <LoadingBlock rows={8} /> : null}
      {q.data ? (
        <div className="col" style={{ gap: 20 }}>
          {!q.data.configured.claude ? <div className="callout warn"><Icon name="plug" /><div><b>Claude is pending setup.</b> Topic research and content generation need ANTHROPIC_API_KEY on the server. Everything else works. <Link to="/integrations">Integrations</Link></div></div> : null}
          {q.data.brands.map((b: any) => (
            <section key={b.brand}>
              <div className="row-wrap mb-12">
                <span className={`brand-dot ${b.brand}`} />
                <h2 className="serif" style={{ fontSize: 20 }}>{brandOf(b.brand).name}</h2>
                {b.paused ? <Pill tone="neutral" dot>Paused {b.pause?.paused_by_name ? `by ${b.pause.paused_by_name}` : ''} {timeAgo(b.pause?.paused_at)}{b.pause?.reason ? ` — ${b.pause.reason}` : ''}</Pill> : <Pill tone="ok" dot>Active</Pill>}
                <span className="spacer" />
                {can('workflow:run') ? (b.paused
                  ? <Button size="sm" icon="play" onClick={() => resume(b.brand)}>Resume automation</Button>
                  : <Button size="sm" icon="pause" onClick={() => setPause(b.brand)}>Pause automation</Button>) : null}
              </div>
              <div className="stages">
                {b.stages.map((s: any, i: number) => (
                  <div key={s.key} className={`stage ${s.state}`}>
                    <div className="row">
                      <span className="stage-num">{i + 1}</span>
                      <span className="strong" style={{ flex: 1 }}>{s.label}</span>
                      <Pill tone={STATE[s.state]?.tone ?? 'neutral'} dot>{STATE[s.state]?.label ?? s.state}</Pill>
                    </div>
                    <div className="muted small">{s.description}</div>
                    <div className="row-wrap xs muted">
                      <span className="row gap-4"><Icon name={s.kind === 'human' ? 'users' : 'automation'} size="sm" />{s.kind === 'human' ? 'Person' : 'Automated'} · {s.owner}</span>
                      {s.lastRun ? <span title={fmtDateTime(s.lastRun.started_at)}>· last run {timeAgo(s.lastRun.started_at)} ({s.lastRun.trigger})</span> : null}
                    </div>
                    {s.lastRun?.message && s.lastRun.status !== 'failed' ? <div className="small">{s.lastRun.message}</div> : null}
                    {s.state === 'failed' ? <div className="err"><b>Error:</b> {s.lastRun?.error}</div> : null}
                    {s.setupGap ? <div className="small" style={{ color: 'var(--warn)' }}><Icon name="plug" size="sm" /> {s.setupGap}</div> : null}
                    {s.humanAction ? (
                      <Link to={STAGE_LINK[s.key] ?? '#'} className="callout warn" style={{ padding: '7px 10px', textDecoration: 'none' }}>
                        <Icon name="arrowRight" size="sm" /><span className="small"><b>{s.pending} waiting:</b> {s.humanAction}</span>
                      </Link>
                    ) : null}
                    {s.kind === 'automated' && can('workflow:run') ? (
                      <div className="row-wrap mt-4">
                        {s.state === 'failed' && s.lastRun ? <Button size="sm" variant="primary" icon="refresh" loading={busy === `run:${s.lastRun.id}`} disabled={b.paused} onClick={() => retry(s.lastRun.id)}>Retry</Button> : null}
                        <Button size="sm" icon="play" loading={busy === `${b.brand}:${s.key}`} disabled={b.paused || !!s.setupGap || s.state === 'running'} onClick={() => runStage(b.brand, s.key, s.label)}>Run now</Button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>
          ))}

          <Card title="Run history" sub="Runs started here, by the background refresh, or reported by external agents through the webhook" flush>
            <div className="table-wrap">
              <table className="t compact">
                <thead><tr><th>Started</th><th>Stage</th>{!brand ? <th className="hide-sm">Brand</th> : null}<th>Result</th><th className="hide-md">Message</th><th className="hide-sm">By</th><th /></tr></thead>
                <tbody>
                  {q.data.runs.map((r: any) => (
                    <tr key={r.id}>
                      <td className="nowrap small" title={r.finished_at ? `finished ${fmtDateTime(r.finished_at)}` : ''}>{fmtDateTime(r.started_at)}</td>
                      <td className="small">{r.stage.replace(/_/g, ' ')}</td>
                      {!brand ? <td className="hide-sm"><BrandTag id={r.brand_id} brands={me.brands} /></td> : null}
                      <td><Pill tone={RUN_TONE[r.status] ?? 'neutral'}>{r.status}</Pill>{r.retry_of ? <span className="faint xs"> retry</span> : null}</td>
                      <td className="hide-md small" style={{ maxWidth: 420, overflowWrap: 'anywhere' }}>{r.error ? <span style={{ color: 'var(--crit)' }}>{r.error}</span> : r.message}</td>
                      <td className="hide-sm small">{r.user_name ?? (r.trigger_kind === 'scheduler' ? 'Scheduler' : r.trigger_kind === 'webhook' ? 'Webhook' : 'System')}</td>
                      <td className="r">{r.status === 'failed' && can('workflow:run') ? <Button size="xs" icon="refresh" loading={busy === `run:${r.id}`} onClick={() => retry(r.id)}>Retry</Button> : null}</td>
                    </tr>
                  ))}
                  {!q.data.runs.length ? <tr><td colSpan={7} className="muted small" style={{ padding: 16 }}>No runs yet. Start with “Performance tracking” to pull articles and products from both storefronts.</td></tr> : null}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      ) : null}
      {pause ? <PauseDialog brand={pause} onClose={() => setPause(null)} onDone={() => { setPause(null); q.reload(); }} /> : null}
    </>
  );
}

function PauseDialog({ brand, onClose, onDone }: { brand: string; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const go = async () => { setBusy(true); try { await api.post(`/automation/${brand}/pause`, { reason }); toast.ok('Automation paused.'); onDone(); } catch (e) { toast.error(e); } finally { setBusy(false); } };
  return (
    <Dialog title="Pause automation" sub="Stops the background refresh and blocks automated stages for this brand until resumed. Manual editing, reviews and publishing are unaffected." onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} onClick={go}>Pause</Button></>}>
      <div className="field"><label htmlFor="pr">Reason (shown to the team)</label><input id="pr" data-autofocus className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Holiday content freeze" /></div>
    </Dialog>
  );
}
