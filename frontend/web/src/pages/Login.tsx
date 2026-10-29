import { useState, type FormEvent } from 'react';
import { api } from '../lib/api';
import { Button } from '../components/ui';
import { Icon, LogoMark } from '../components/Icon';

/* A repeating block-print motif drawn in SVG for the sign-in panel. */
function Pattern() {
  return (
    <svg className="pattern" aria-hidden>
      <defs>
        <pattern id="bp" width="64" height="64" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="#EFB34C" strokeWidth="1.4">
            <circle cx="32" cy="32" r="5" />
            <path d="M32 14c4 4 4 9 0 12-4-3-4-8 0-12zM32 50c4-4 4-9 0-12-4 3-4 8 0 12zM14 32c4-4 9-4 12 0-3 4-8 4-12 0zM50 32c-4-4-9-4-12 0 3 4 8 4 12 0z" />
          </g>
          <g fill="#B8432F"><circle cx="0" cy="0" r="2" /><circle cx="64" cy="0" r="2" /><circle cx="0" cy="64" r="2" /><circle cx="64" cy="64" r="2" /></g>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#bp)" />
    </svg>
  );
}

export function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      await api.post('/auth/login', { email, password });
      onSignedIn();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login">
      <div className="login-art">
        <Pattern />
        <div className="row gap-12">
          <LogoMark />
          <span className="serif" style={{ fontSize: 20 }}>Blog Ops</span>
        </div>
        <div>
          <p className="serif" style={{ fontSize: 34, lineHeight: 1.2, margin: '0 0 14px', maxWidth: 520 }}>One desk for every story told about hand block-printed cotton.</p>
          <div className="row-wrap gap-12" style={{ opacity: 0.85 }}>
            <span className="row"><span className="brand-dot" style={{ background: '#EFB34C' }} />Ridhi Block Print</span>
            <span className="row"><span className="brand-dot" style={{ background: '#F1D3C1' }} />Cotton Print Club</span>
          </div>
        </div>
        <p className="small" style={{ opacity: 0.6, margin: 0 }}>Topics, drafts, reviews, Shopify publishing and search performance — with nothing going live without an authorized sign-off.</p>
      </div>
      <div className="login-form">
        <form className="login-card col gap-16" onSubmit={submit}>
          <div>
            <h1 className="page-title">Sign in</h1>
            <p className="page-sub">Use the account an admin created for you.</p>
          </div>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {err ? <div className="callout crit" role="alert"><Icon name="alert" />{err}</div> : null}
          <Button type="submit" variant="primary" loading={busy} style={{ height: 40 }}>Sign in</Button>
          <p className="muted xs" style={{ margin: 0 }}>First run? The admin password is in <span className="mono">data/initial-admin.txt</span> on the server, unless ADMIN_PASSWORD was set.</p>
        </form>
      </div>
    </div>
  );
}
