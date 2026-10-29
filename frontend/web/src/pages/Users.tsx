import { useState } from 'react';
import { api, useApi } from '../lib/api';
import { useApp } from '../lib/app';
import { timeAgo } from '../lib/format';
import { Button, Card, ErrorState, Field, LoadingBlock, PageHead, Pill } from '../components/ui';
import { Dialog, useToast } from '../components/overlays';
import { Icon } from '../components/Icon';

export default function Users() {
  const q = useApi<any>('/users');
  const { me, can } = useApp();
  const [edit, setEdit] = useState<any | 'new' | null>(null);
  if (!can('users:manage')) return <ErrorState error={new Error('Only admins can manage users.')} />;
  return (
    <>
      <PageHead title="Users & roles" sub="Roles are enforced by the server on every request. Changing a role or deactivating a user signs them out." actions={<Button variant="primary" icon="plus" onClick={() => setEdit('new')}>Add user</Button>} />
      <ErrorState error={q.error} onRetry={q.reload} />
      {!q.data ? <LoadingBlock /> : (
        <div className="col" style={{ gap: 16 }}>
          <div className="card flush">
            <div className="table-wrap">
              <table className="t">
                <thead><tr><th>Name</th><th>Role</th><th className="hide-sm">Last sign-in</th><th>Status</th><th /></tr></thead>
                <tbody>
                  {q.data.users.map((u: any) => (
                    <tr key={u.id} className="clickable" onClick={() => setEdit(u)}>
                      <td className="title-cell"><span className="ttl">{u.name}{u.id === me.user.id ? <span className="faint"> (you)</span> : null}</span><span className="sub">{u.email}</span></td>
                      <td><span className="pill outline">{q.data.roles.find((r: any) => r.key === u.role)?.label}</span></td>
                      <td className="hide-sm small">{u.last_login_at ? timeAgo(u.last_login_at) : <span className="faint">never</span>}</td>
                      <td>{u.active ? <Pill tone="ok" dot>Active</Pill> : <Pill dot>Deactivated</Pill>}</td>
                      <td className="r"><Icon name="chevronRight" size="sm" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <Card title="What each role can do" flush>
            <div className="table-wrap">
              <table className="t compact">
                <thead><tr><th>Permission</th>{q.data.roles.map((r: any) => <th key={r.key} className="r">{r.label}</th>)}</tr></thead>
                <tbody>
                  {Object.entries(q.data.permissions).map(([p, label]) => (
                    <tr key={p}><td className="small">{label as string}</td>{q.data.roles.map((r: any) => <td key={r.key} className="r">{r.permissions.includes(p) ? <Icon name="check" size="sm" className="" /> : <span className="faint">—</span>}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
      {edit ? <UserDialog user={edit === 'new' ? null : edit} roles={q.data?.roles ?? []} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); q.reload(); }} /> : null}
    </>
  );
}

function UserDialog({ user, roles, onClose, onSaved }: { user: any | null; roles: any[]; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: user?.name ?? '', email: user?.email ?? '', role: user?.role ?? 'seo_manager', active: user ? !!user.active : true, password: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const toast = useToast();
  const genPw = () => {
    const a = new Uint8Array(15);
    crypto.getRandomValues(a);
    setF({ ...f, password: btoa(String.fromCharCode(...a)).replace(/[+/=]/g, '').slice(0, 18) });
  };
  const save = async () => {
    setBusy(true); setErr('');
    try {
      if (user) await api.patch(`/users/${user.id}`, { name: f.name, role: f.role, active: f.active, ...(f.password ? { password: f.password } : {}) });
      else await api.post('/users', f);
      toast.ok(user ? 'User updated.' : 'User added. Share the password with them through a private channel.');
      onSaved();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <Dialog title={user ? user.name : 'Add user'} onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={!f.name || (!user && (!f.email || f.password.length < 12))} onClick={save}>{user ? 'Save' : 'Add user'}</Button></>}>
      <div className="form-grid">
        <Field label="Name"><input className="input" data-autofocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Email"><input className="input" type="email" value={f.email} readOnly={!!user} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Role" full>
          <div className="col gap-4">
            {roles.map((r) => (
              <label key={r.key} className="check" style={{ alignItems: 'flex-start', padding: '6px 0' }}>
                <input type="radio" name="role" checked={f.role === r.key} onChange={() => setF({ ...f, role: r.key })} />
                <span><b>{r.label}</b><span className="muted small" style={{ display: 'block' }}>{r.key === 'admin' ? 'Integrations, users, settings, publishing authorization — everything.' : r.key === 'seo_manager' ? 'Topics, keywords, writing and editing, Shopify drafts, publish requests, imports.' : 'Approves content and authorizes or rejects publish requests.'}</span></span>
              </label>
            ))}
          </div>
        </Field>
        <Field label={user ? 'Reset password (optional)' : 'Initial password'} full hint="At least 12 characters. The user can change it from their account menu.">
          <div className="row"><input className="input mono" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" /><Button size="sm" onClick={genPw}>Generate</Button></div>
        </Field>
        {user ? <label className="check full"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} />Active (unchecked = cannot sign in)</label> : null}
      </div>
      {err ? <div className="callout crit mt-12"><Icon name="alert" />{err}</div> : null}
    </Dialog>
  );
}
