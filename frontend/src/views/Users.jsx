'use client';
import { useApi } from '../lib/api';
import { useApp } from '../lib/app';
import { timeAgo } from '../lib/format';
import { ErrorState, LoadingBlock, PageHead, Pill } from '../components/ui';
import { Icon } from '../components/Icon';
/**
 * Local operator mode: Flowmerce opens without signing in, and every request from this computer acts as the
 * local administrator record. User records stay stored (they are the owners and assignees in the audit log and
 * on articles), but passwords and roles no longer decide who can do what, so this page only lists them.
 */
export default function Users() {
    const q = useApi('/users');
    const { me, can } = useApp();
    if (!can('users:manage'))
        return <ErrorState error={new Error('Only administrators can view users.')}/>;
    return (<>
      <PageHead title="Users" sub="Stored user records, kept for audit history, record ownership and article assignments."/>
      <div className="callout info mb-16" role="note">
        <Icon name="info"/>
        <div>
          <b>Local operator mode.</b> Flowmerce opens without signing in, and everything done from this computer is recorded as{' '}
          <b>{me.user.name}</b> ({me.user.email}). User accounts remain stored, but passwords and role assignments do not
          restrict access in this mode, so they cannot be changed here. Do not expose Flowmerce to other computers or the internet.
        </div>
      </div>
      <ErrorState error={q.error} onRetry={q.reload}/>
      {!q.data ? <LoadingBlock /> : (<div className="card flush">
          <div className="table-wrap">
            <table className="t">
              <thead><tr><th>Name</th><th>Stored role</th><th className="hide-sm">Last recorded sign-in</th><th>Status</th></tr></thead>
              <tbody>
                {q.data.users.map((u) => (<tr key={u.id}>
                    <td className="title-cell">
                      <span className="ttl">{u.name}{u.id === me.user.id ? <span className="faint"> (local operator)</span> : null}</span>
                      <span className="sub">{u.email}</span>
                    </td>
                    <td><span className="pill outline">{q.data.roles.find((r) => r.key === u.role)?.label ?? u.role}</span></td>
                    <td className="hide-sm small">{u.last_login_at ? timeAgo(u.last_login_at) : <span className="faint">never</span>}</td>
                    <td>{u.active ? <Pill tone="ok" dot>Active</Pill> : <Pill dot>Deactivated</Pill>}</td>
                  </tr>))}
              </tbody>
            </table>
          </div>
        </div>)}
    </>);
}
