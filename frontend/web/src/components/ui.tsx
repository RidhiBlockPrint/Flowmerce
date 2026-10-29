import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Icon } from './Icon';
import { ARTICLE_STATUS, fmtDate, fmtDateTime, timeAgo } from '../lib/format';
import type { ApiError } from '../lib/api';
import type { BrandId, SourceInfo } from '../lib/types';

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'xs' | 'sm' | 'md';
  icon?: string;
  loading?: boolean;
  iconOnly?: boolean;
};

export function Button({ variant = 'secondary', size = 'md', icon, loading, iconOnly, children, className = '', disabled, ...rest }: BtnProps) {
  const cls = ['btn', variant !== 'secondary' && variant, size !== 'md' && size, iconOnly && 'icon-only', className].filter(Boolean).join(' ');
  return (
    <button type="button" className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <Icon name="loader" className="spin" size={size === 'md' ? undefined : 'sm'} /> : icon ? <Icon name={icon} size={size === 'md' ? undefined : 'sm'} /> : null}
      {iconOnly ? null : children}
    </button>
  );
}

export function Pill({ tone = 'neutral', dot, children, title }: { tone?: string; dot?: boolean; children: ReactNode; title?: string }) {
  return <span className={`pill ${tone}`} title={title}>{dot ? <span className="dot" /> : null}{children}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const s = ARTICLE_STATUS[status] ?? { label: status, tone: 'neutral' };
  return <Pill tone={s.tone} dot>{s.label}</Pill>;
}

export function LivePill({ live, differs }: { live: boolean; differs?: boolean }) {
  if (!live) return null;
  return <Pill tone="live" title={differs ? 'The working copy has changes that are not live yet' : 'Visible on the storefront'}>Live{differs ? ' · edits pending' : ''}</Pill>;
}

export function BrandTag({ id, brands }: { id: BrandId; brands?: { id: string; short: string }[] }) {
  const short = brands?.find((b) => b.id === id)?.short ?? (id === 'ridhi' ? 'Ridhi' : 'CPC');
  return <span className={`pill ${id}`}><span className={`brand-dot ${id}`} />{short}</span>;
}

/** Where a number came from. Every metric on screen carries one of these. */
export function SourceBadge({ source, kind, label, at, period, compact }: { source?: SourceInfo | null; kind?: string; label?: string; at?: string | null; period?: { from: string | null; to: string | null } | null; compact?: boolean }) {
  const k = kind ?? source?.kind ?? 'none';
  const text = label ?? (compact
    ? (k === 'api' ? 'Live' : k === 'excel' ? 'Excel' : k === 'demo' ? 'Demo' : 'No data')
    : (k === 'api' ? 'Live API' : k === 'excel' ? 'Excel import' : k === 'demo' ? 'Demo data — not real' : 'No data'));
  const when = at ?? source?.syncedAt ?? null;
  const per = period ?? source?.coverage ?? null;
  const tip = [text, when ? `synced ${fmtDateTime(when)}` : '', per?.from ? `covers ${fmtDate(per.from)} – ${fmtDate(per.to)}` : ''].filter(Boolean).join(' · ');
  return (
    <span className={`source ${k ?? 'none'}`} title={tip}>
      <span className="sw" />
      {text}
      {when && k !== 'demo' && !compact ? <span className="faint">· {timeAgo(when)}</span> : null}
    </span>
  );
}

export function Card({ title, sub, actions, children, foot, className = '', flush, onClick }: { title?: ReactNode; sub?: ReactNode; actions?: ReactNode; children: ReactNode; foot?: ReactNode; className?: string; flush?: boolean; onClick?: () => void }) {
  return (
    <section className={`card ${flush ? 'flush' : ''} ${onClick ? 'clickable' : ''} ${className}`} onClick={onClick}>
      {title || actions ? (
        <div className="card-head">
          <div style={{ minWidth: 0 }}>
            {title ? <h2 className="card-title">{title}</h2> : null}
            {sub ? <div className="card-sub">{sub}</div> : null}
          </div>
          {actions ? <div className="row" style={{ marginLeft: 'auto' }}>{actions}</div> : null}
        </div>
      ) : null}
      <div className="card-body">{children}</div>
      {foot ? <div className="card-foot">{foot}</div> : null}
    </section>
  );
}

export function PageHead({ title, sub, actions, crumbs }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; crumbs?: ReactNode }) {
  return (
    <div className="page-head">
      <div style={{ minWidth: 0 }}>
        {crumbs ? <div className="crumbs">{crumbs}</div> : null}
        <h1 className="page-title">{title}</h1>
        {sub ? <p className="page-sub">{sub}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
  );
}

export function Empty({ icon = 'inbox', title, children, action }: { icon?: string; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} />
      <h3>{title}</h3>
      {children ? <p>{children}</p> : null}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError | Error | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="callout crit" role="alert">
      <Icon name="alert" />
      <div style={{ flex: 1 }}>
        <b>Could not load this.</b> {error.message}
      </div>
      {onRetry ? <Button size="sm" onClick={onRetry} icon="refresh">Retry</Button> : null}
    </div>
  );
}

export function Skeleton({ h = 16, w = '100%', r }: { h?: number; w?: number | string; r?: number }) {
  return <div className="skeleton" style={{ height: h, width: w, borderRadius: r }} aria-hidden />;
}

export function LoadingBlock({ rows = 4 }: { rows?: number }) {
  return (
    <div className="col gap-12" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} h={i === 0 ? 22 : 14} w={i === 0 ? '40%' : `${90 - i * 9}%`} />)}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { key: T; label: ReactNode }[]; value: T; onChange: (k: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" className="tab" aria-selected={t.key === value} onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  );
}

export function Field({ label, hint, children, counter, full }: { label: ReactNode; hint?: ReactNode; children: ReactNode; counter?: { n: number; min?: number; max: number }; full?: boolean }) {
  let cls = '';
  if (counter) cls = counter.n > counter.max || (counter.min !== undefined && counter.n > 0 && counter.n < counter.min) ? 'bad' : counter.n >= (counter.min ?? 1) ? 'good' : '';
  return (
    <div className={`field ${full ? 'full' : ''}`}>
      <label>
        {label}
        {counter ? <span className={`counter ${cls}`}>{counter.n}{counter.min !== undefined ? ` / ${counter.min}–${counter.max}` : ` / ${counter.max}`}</span> : null}
      </label>
      {children}
      {hint ? <div className="hint">{hint}</div> : null}
    </div>
  );
}

export function Delta({ value, invert }: { value: number | null; invert?: boolean }) {
  if (value === null || !Number.isFinite(value)) return <span className="delta flat">—</span>;
  const good = invert ? value < 0 : value > 0;
  const flat = Math.abs(value) < 0.005;
  return (
    <span className={`delta ${flat ? 'flat' : good ? 'up' : 'down'}`} title="Change against the previous period of equal length">
      {flat ? null : <Icon name={value > 0 ? 'arrowUp' : 'arrowDown'} size="sm" />}
      {Math.abs(value * 100).toFixed(Math.abs(value) < 0.1 ? 1 : 0)}%
    </span>
  );
}

export function Menu({ trigger, children, align = 'right', up }: { trigger: (open: () => void) => ReactNode; children: (close: () => void) => ReactNode; align?: 'left' | 'right'; up?: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-flex' }}>
      {trigger(() => setOpen((o) => !o))}
      {open ? <div className="menu" role="menu" style={{ [up ? 'bottom' : 'top']: 'calc(100% + 6px)', [align]: 0 }}>{children(() => setOpen(false))}</div> : null}
    </div>
  );
}

export function Kv({ items }: { items: [ReactNode, ReactNode][] }) {
  return <dl className="kv">{items.map(([k, v], i) => <div key={i} style={{ display: 'contents' }}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

export function RoleTag({ role }: { role: string }) {
  if (!role) return <span className="faint">—</span>;
  const label = role === 'seo_manager' ? 'SEO Manager' : role === 'reviewer' ? 'Reviewer' : role === 'admin' ? 'Admin' : role;
  return <span className="pill outline">{label}</span>;
}
