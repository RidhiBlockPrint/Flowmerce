import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from './Icon';
import { BrandTag, Empty, Pill, SourceBadge } from './ui';
import { STATUS_LABEL, type ModuleEntry, type RouteStatus } from '../lib/routes';
import type { ReportRow } from '../lib/home';
import type { Brand, BrandFilter, BrandId } from '../lib/types';

const STATUS_TONE: Record<RouteStatus, string> = { available: 'ok', planned: 'neutral', future: 'outline' };
const STATUS_HINT: Record<RouteStatus, string> = {
  available: 'The page exists and works, but has not been verified against live data.',
  planned: 'Described in the product handoff and not built yet.',
  future: 'Future scope, not part of the current build plan.',
};

/** Whether a page exists, is planned, or is future scope. Always the real status, never demo data. */
export function StatusChip({ status }: { status: RouteStatus }) {
  return <Pill tone={STATUS_TONE[status]} title={STATUS_HINT[status]}>{STATUS_LABEL[status]}</Pill>;
}

/** One of the six core projects on Home: its purpose, real status, and the latest report if there is one. */
export function ModuleCard({ module, latest, brands, showBrand }: { module: ModuleEntry; latest?: ReportRow; brands: Brand[]; showBrand: boolean }) {
  return (
    <Link to={module.to} className="card clickable module-card">
      <span className="module-head">
        <span className="module-icon"><Icon name={module.icon} /></span>
        <span className="module-name">{module.label}</span>
        <StatusChip status={module.status} />
      </span>
      <span className="module-purpose">{module.purpose}</span>
      <span className="module-latest">
        <span className="xs muted">Latest report</span>
        {latest ? (
          <span className="module-latest-row">
            <SourceBadge kind="demo" compact />
            {showBrand ? <BrandTag id={latest.brand} brands={brands} /> : null}
            <span className="small ellipsis">{latest.title}</span>
          </span>
        ) : (
          <span className="small muted">No reports yet</span>
        )}
      </span>
    </Link>
  );
}

/** A titled list on Home with a real empty state and an optional link to the full page. */
export function ListCard({ title, sub, demo, to, linkLabel, emptyTitle, emptyText, icon, children }: {
  title: string; sub?: string; demo: boolean; to: string; linkLabel: string; emptyTitle: string; emptyText: string; icon: string; children: ReactNode[] | null;
}) {
  const has = !!children && children.length > 0;
  return (
    <section className="card flush">
      <div className="card-head">
        <div style={{ minWidth: 0 }}>
          <h2 className="card-title">{title}</h2>
          {sub ? <div className="card-sub">{sub}</div> : null}
        </div>
        <div className="row" style={{ marginLeft: 'auto' }}>{demo && has ? <SourceBadge kind="demo" compact /> : null}</div>
      </div>
      <div className="card-body">
        {has ? <div className="alert-list">{children}</div> : <Empty icon={icon} title={emptyTitle}>{emptyText}</Empty>}
      </div>
      <div className="card-foot">
        <Link to={to} className="strong">{linkLabel} <Icon name="arrowRight" size="sm" /></Link>
      </div>
    </section>
  );
}

/** A row inside a ListCard. With `to` the whole row is a link, so it stays keyboard reachable. */
export function ListRow({ icon, tone, title, meta, brand, brands, showBrand, trailing, to }: {
  icon: string; tone?: 'ok' | 'warn' | 'crit' | 'info'; title: ReactNode; meta: ReactNode; brand?: BrandId; brands: Brand[]; showBrand: boolean; trailing?: ReactNode; to?: string;
}) {
  const inner = (
    <>
      <span className={`list-icon ${tone ?? ''}`}><Icon name={icon} /></span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span className="strong small" style={{ display: 'block' }}>{title}</span>
        <span className="muted xs" style={{ display: 'block' }}>{meta}</span>
      </span>
      {trailing}
      {showBrand && brand ? <BrandTag id={brand} brands={brands} /> : null}
    </>
  );
  return to ? <Link to={to} className="alert-item list-row">{inner}</Link> : <div className="alert-item list-row">{inner}</div>;
}

export function brandLabel(filter: BrandFilter, brands: Brand[]): string {
  if (filter === 'all') return brands.map((b) => b.name).join(' and ');
  return brands.find((b) => b.id === filter)?.name ?? filter;
}
