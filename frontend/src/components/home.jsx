'use client';
import Link from 'next/link';
import { Icon } from './Icon';
import { BrandTag, Empty } from './ui';

/** A project on Home: its purpose and the latest report if there is one. */
export function ModuleCard({ module, latest, brands, showBrand }) {
    return (<Link href={module.to} className="card clickable module-card">
      <span className="module-head">
        <span className="module-icon"><Icon name={module.icon}/></span>
        <span className="module-name">{module.label}</span>
      </span>
      <span className="module-purpose">{module.purpose}</span>
      <span className="module-latest">
        <span className="xs muted">Latest report</span>
        {latest ? (<span className="module-latest-row">
            {showBrand ? <BrandTag id={latest.brand} brands={brands}/> : null}
            <span className="small ellipsis">{latest.title}</span>
          </span>) : (<span className="small muted">No reports yet</span>)}
      </span>
    </Link>);
}
/** A titled list on Home with a real empty state and an optional link to the full page. */
export function ListCard({ title, sub, to, linkLabel, emptyTitle, emptyText, icon, children }) {
    const has = !!children && children.length > 0;
    return (<section className="card flush">
      <div className="card-head">
        <div style={{ minWidth: 0 }}>
          <h2 className="card-title">{title}</h2>
          {sub ? <div className="card-sub">{sub}</div> : null}
        </div>
        <div className="row" style={{ marginLeft: 'auto' }}></div>
      </div>
      <div className="card-body">
        {has ? <div className="alert-list">{children}</div> : <Empty icon={icon} title={emptyTitle}>{emptyText}</Empty>}
      </div>
      <div className="card-foot">
        <Link href={to} className="strong">{linkLabel} <Icon name="arrowRight" size="sm"/></Link>
      </div>
    </section>);
}
/** A row inside a ListCard. With `to` the whole row is a link, so it stays keyboard reachable. */
export function ListRow({ icon, tone, title, meta, brand, brands, showBrand, trailing, to }) {
    const inner = (<>
      <span className={`list-icon ${tone ?? ''}`}><Icon name={icon}/></span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span className="strong small" style={{ display: 'block' }}>{title}</span>
        <span className="muted xs" style={{ display: 'block' }}>{meta}</span>
      </span>
      {trailing}
      {showBrand && brand ? <BrandTag id={brand} brands={brands}/> : null}
    </>);
    return to ? <Link href={to} className="alert-item list-row">{inner}</Link> : <div className="alert-item list-row">{inner}</div>;
}
export function brandLabel(filter, brands) {
    if (filter === 'all')
        return brands.map((b) => b.name).join(' and ');
    return brands.find((b) => b.id === filter)?.name ?? filter;
}
