import { Fragment, useEffect, useState } from 'react';
import { api, qs, download } from '../lib/api';
import { useApp, useBrandParam } from '../lib/app';
import { fmtDateTime } from '../lib/format';
import { Button, Empty, ErrorState, PageHead, BrandTag } from '../components/ui';
import { useToast } from '../components/overlays';
import { Icon } from '../components/Icon';

const GROUPS = [['', 'All actions'], ['article', 'Content edits & reviews'], ['publish', 'Publishing'], ['shopify', 'Shopify drafts'], ['data', 'Imports & exports'], ['integration', 'Integration failures & tests'], ['workflow', 'Automation'], ['auth', 'Sign-ins'], ['user', 'Users']];

export default function Audit() {
  const brand = useBrandParam();
  const { me, range } = useApp();
  const toast = useToast();
  const [action, setAction] = useState('');
  const [user, setUser] = useState('');
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [more, setMore] = useState(true);
  const [open, setOpen] = useState<number | null>(null);

  const load = async (before?: number) => {
    setLoading(true); setError(null);
    try {
      const r = await api.get<any[]>(`/audit${qs({ brand, action, user, before })}`);
      setRows((prev) => (before ? [...prev, ...r] : r));
      setMore(r.length === 100);
    } catch (e: any) { setError(e); } finally { setLoading(false); }
  };
  useEffect(() => { const t = setTimeout(() => void load(), 200); return () => clearTimeout(t); }, [brand, action, user]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <PageHead title="Audit log" sub="Append-only record of edits, approvals, publishing, imports, exports, sign-ins and integration failures."
        actions={<Button icon="download" onClick={() => download(`/data/export/audit${qs({ brand, from: range.from, to: range.to })}`).catch(toast.error)}>Export range</Button>} />
      <div className="toolbar">
        <select className="select sm" style={{ width: 'auto' }} value={action} onChange={(e) => setAction(e.target.value)} aria-label="Action">{GROUPS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <div className="input-icon" style={{ width: 220 }}><Icon name="search" /><input className="input sm" placeholder="Filter by user email" value={user} onChange={(e) => setUser(e.target.value)} /></div>
      </div>
      <ErrorState error={error} onRetry={() => load()} />
      <div className="card flush">
        <div className="table-wrap">
          <table className="t compact">
            <thead><tr><th>Time</th><th>Who</th><th>Action</th>{!brand ? <th className="hide-sm">Brand</th> : null}<th>Summary</th><th /></tr></thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.id}>
                  <tr className="clickable" onClick={() => setOpen(open === r.id ? null : r.id)}>
                    <td className="nowrap small">{fmtDateTime(r.ts)}</td>
                    <td className="small">{r.user_email ?? 'system'}</td>
                    <td><span className={`pill ${r.action.includes('fail') ? 'crit' : r.action.startsWith('publish') ? 'accent' : 'neutral'}`}>{r.action}</span></td>
                    {!brand ? <td className="hide-sm">{r.brand_id ? <BrandTag id={r.brand_id} brands={me.brands} /> : null}</td> : null}
                    <td className="small" style={{ maxWidth: 480, overflowWrap: 'anywhere' }}>{r.summary || <span className="faint">{r.entity_type} {r.entity_id}</span>}</td>
                    <td><Icon name={open === r.id ? 'chevronDown' : 'chevronRight'} size="sm" /></td>
                  </tr>
                  {open === r.id ? (
                    <tr><td colSpan={6} style={{ background: 'var(--surface-2)' }}>
                      <div className="code-block">{JSON.stringify({ entity: `${r.entity_type} ${r.entity_id}`.trim(), ip: r.ip, ...r.details }, null, 2)}</div>
                    </td></tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !rows.length ? <Empty icon="audit" title="No entries match">Try another action type.</Empty> : null}
        {more && rows.length ? <div className="card-foot"><Button size="sm" loading={loading} onClick={() => load(rows[rows.length - 1].id)}>Load older entries</Button></div> : null}
      </div>
    </>
  );
}
