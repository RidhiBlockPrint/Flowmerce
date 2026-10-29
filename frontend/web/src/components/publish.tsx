import { useState } from 'react';
import { api } from '../lib/api';
import { useApp } from '../lib/app';
import { fmtDateTime } from '../lib/format';
import { ConfirmDialog, Dialog, useToast } from './overlays';
import { Button, Kv } from './ui';
import { Icon } from './Icon';

export const MODE_LABEL: Record<string, string> = { publish_now: 'Publish now', schedule: 'Schedule', update_live: 'Update live article' };

/** The final gate before anything goes live: shows exactly what will happen, requires the typed
 * phrase, and states up front when the server has live publishing switched off. */
export function AuthorizeDialog({ req, retry, onClose, onDone }: { req: any; retry?: boolean; onClose: () => void; onDone: () => void }) {
  const { me, brandOf } = useApp();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const brand = brandOf(req.brand_id);
  const go = async (typed: string) => {
    setBusy(true); setError('');
    try {
      await api.post(`/publish-requests/${req.id}/${retry ? 'retry' : 'authorize'}`, { confirm: typed, note });
      toast.ok(req.mode === 'schedule' ? 'Scheduled on Shopify.' : 'Published to the storefront.');
      onDone();
    } catch (e: any) {
      setError(e.message);
    } finally { setBusy(false); }
  };
  const what = req.mode === 'schedule' ? `be scheduled to go live on ${brand.name} at ${fmtDateTime(req.publish_at)}` : req.mode === 'update_live' ? `replace the live article on ${brand.name}` : `go live on ${brand.name} immediately`;
  return (
    <ConfirmDialog
      title={retry ? 'Retry publishing' : 'Authorize publishing'}
      confirmLabel={retry ? 'Retry publish' : req.mode === 'schedule' ? 'Authorize & schedule' : 'Authorize & publish'}
      phrase="PUBLISH"
      busy={busy}
      onClose={onClose}
      onConfirm={go}
    >
      <p style={{ margin: 0 }}>“<b>{req.title}</b>” (version {req.version}) will {what}.</p>
      <Kv items={[
        ['Requested by', req.requested_by_name ?? '—'],
        ['Request note', req.note || <span className="faint">none</span>],
        ['Storefront', <a href={brand.blogUrl} target="_blank" rel="noopener">{brand.blogUrl.replace('https://', '')}</a>],
      ]} />
      {!me.livePublishing ? (
        <div className="callout warn"><Icon name="lock" /><div><b>Live publishing is switched off on this server.</b> The server will refuse this until an admin sets ALLOW_LIVE_PUBLISH=true. Nothing will be sent to Shopify.</div></div>
      ) : null}
      {req.stale ? <div className="callout crit"><Icon name="alert" />The article changed after this request. It will be refused and needs a fresh review.</div> : null}
      {!retry ? (
        <div className="field"><label htmlFor="auth-note">Note (optional)</label><input id="auth-note" className="input" value={note} onChange={(e) => setNote(e.target.value)} /></div>
      ) : null}
      {error ? <div className="callout crit" role="alert"><Icon name="alert" />{error}</div> : null}
    </ConfirmDialog>
  );
}

export function RejectDialog({ req, onClose, onDone }: { req: any; onClose: () => void; onDone: () => void }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const go = async () => {
    setBusy(true);
    try { await api.post(`/publish-requests/${req.id}/reject`, { note }); toast.ok('Request rejected.'); onDone(); } catch (e) { toast.error(e); } finally { setBusy(false); }
  };
  return (
    <Dialog title="Reject publish request" onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="danger" loading={busy} disabled={!note.trim()} onClick={go}>Reject</Button></>}>
      <div className="field">
        <label htmlFor="rej">Reason — the requester sees this</label>
        <textarea id="rej" data-autofocus className="textarea" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
    </Dialog>
  );
}
