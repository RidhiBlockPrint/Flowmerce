/**
 * The single list of Flowmerce destinations. The sidebar, the router and the "planned" pages all read
 * from here, so a page cannot appear in one place and be missing from another.
 *
 * Statuses are deliberately honest:
 *  - available: the page exists and works today (only the SEO & Blog area).
 *  - planned:   described in docs/product/Flowmerce_Project_Handoff.md, not built yet.
 *  - future:    future scope, not part of the current build plan.
 *
 * Purposes are quoted from the handoff (sections 2.1 and A.3); do not add claims that are not there.
 */
export type RouteStatus = 'available' | 'planned' | 'future';
export type ModuleId = 'seo' | 'shipping' | 'meta' | 'creative' | 'landing' | 'cro';

export interface NavEntry {
  to: string;
  label: string;
  icon: string;
  status: RouteStatus;
  /** One-line purpose, from the handoff. */
  purpose: string;
  /** Optional extra context shown on the planned page. */
  note?: string;
}

export interface ModuleEntry extends NavEntry {
  id: ModuleId;
}

export const HOME: NavEntry = { to: '/', label: 'Home', icon: 'home', status: 'available', purpose: 'Last night’s runs, alerts, approvals waiting and one set of key figures per project.' };

/** The six core projects, in the handoff's build order. */
export const MODULES: ModuleEntry[] = [
  { id: 'seo', to: '/seo', label: 'SEO & Blog Content', icon: 'blogs', status: 'available', purpose: 'Help customers discover us through organic search and AI-assisted search.' },
  { id: 'shipping', to: '/shipping', label: 'Shipping & Customer Experience', icon: 'send', status: 'planned', purpose: 'Shipment visibility, exception alerts and the full return and replacement experience.' },
  { id: 'meta', to: '/meta', label: 'Meta & Google Ads Performance', icon: 'target', status: 'planned', purpose: 'Ad performance, controlled experiments and approved, evidence-based budget decisions.' },
  { id: 'creative', to: '/creative', label: 'Creative Strategist', icon: 'sparkle', status: 'planned', purpose: 'Research, concepts and briefs, tested and improved in a repeatable loop.' },
  { id: 'landing', to: '/landing', label: 'Landing Page Automation', icon: 'monitor', status: 'planned', purpose: 'Brand-consistent, Shopify-ready campaign pages.' },
  { id: 'cro', to: '/cro', label: 'Conversion Rate Optimization', icon: 'filter', status: 'planned', purpose: 'Improve the journey from landing-page entry to conversion.' },
];

/** Shared operational pages that sit across all projects. */
export const OPERATIONS: NavEntry[] = [
  { to: '/approvals', label: 'Approvals', icon: 'checkCircle', status: 'planned', purpose: 'Every pending action, with the platform, record, change, whether it is reversible and how it was checked.', note: 'The SEO & Blog area has its own publishing approvals today (Publishing page).' },
  { to: '/runs', label: 'Runs & Schedules', icon: 'clock', status: 'planned', purpose: 'The job timeline, status and logs, running a job on request, and editing the schedule.', note: 'The SEO & Blog area has its own Automation page today.' },
  { to: '/alerts', label: 'Alerts', icon: 'alert', status: 'planned', purpose: 'Alert history, acknowledging or resolving alerts, and alert rules.' },
  { to: '/activity', label: 'Activity Log', icon: 'history', status: 'planned', purpose: 'Every action that has run, filterable by brand, project and person.', note: 'The SEO & Blog area has its own Audit log today.' },
  { to: '/library', label: 'Library', icon: 'library', status: 'planned', purpose: 'Brand guidelines, voice documents, design references and past pages that AI jobs read.' },
  { to: '/settings', label: 'Settings', icon: 'settings', status: 'planned', purpose: 'Brands, team and roles, connections and tokens, and schedules.', note: 'The SEO & Blog area has its own Integrations and Users & roles pages today.' },
];

export const MERCHANDISING: NavEntry = {
  to: '/merchandising',
  label: 'Merchandising Automation',
  icon: 'store',
  status: 'future',
  purpose: 'A possible next stage: season sales, inventory, campaign products, colours and mix-and-match.',
  note: 'Future scope, not a current priority. How it links to the other projects is still to be confirmed.',
};

/** Pages that only exist because the SEO & Blog area was built first. They keep their original addresses. */
export const SEO_PATHS = ['/seo', '/workspace', '/blogs', '/topics', '/publishing', '/analytics', '/automation', '/data', '/integrations', '/audit', '/users'];

export function isSeoPath(pathname: string): boolean {
  return SEO_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Every route that is not built yet, for the router. */
export const PLANNED_ROUTES: NavEntry[] = [...MODULES.filter((m) => m.status !== 'available'), ...OPERATIONS, MERCHANDISING];

export function entryFor(pathname: string): NavEntry | undefined {
  return PLANNED_ROUTES.find((r) => r.to === pathname);
}

export const STATUS_LABEL: Record<RouteStatus, string> = { available: 'Available', planned: 'Planned', future: 'Future scope' };
