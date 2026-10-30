/**
 * The Flowmerce destinations that work today. The sidebar and Home's quick navigation read from here.
 * Only implemented pages are listed: unbuilt projects have no entry, and their old addresses show the
 * normal not-found page.
 */
export const HOME = { to: '/', label: 'Home', icon: 'home', purpose: 'Last night’s runs, alerts, approvals waiting and key figures.' };

/** Projects that are built. SEO & Blog Content is the only one. */
export const MODULES = [
  { id: 'seo', to: '/seo', label: 'SEO & Blog Content', icon: 'blogs', purpose: 'Help customers discover us through organic search and AI-assisted search.' },
];

/** Links on Home's quick navigation. */
export const QUICK_LINKS = [
  { to: '/shipping', label: 'Shipping overview', icon: 'send' },
  { to: '/shipping/shipments', label: 'Shipments', icon: 'send' },
  { to: '/seo', label: 'SEO & Blog Content', icon: 'blogs' },
  { to: '/blogs', label: 'Blogs', icon: 'blogs' },
  { to: '/topics', label: 'Topics & keywords', icon: 'topics' },
  { to: '/publishing', label: 'Publishing', icon: 'publish' },
  { to: '/analytics', label: 'SEO & traffic', icon: 'analytics' },
  { to: '/automation', label: 'Automation', icon: 'automation' },
  { to: '/data', label: 'Data & reports', icon: 'sheet' },
  { to: '/integrations', label: 'Integrations', icon: 'plug' },
];

/** Pages of the SEO & Blog area (the sidebar expands its sub-menu on these). */
export const SEO_PATHS = ['/seo', '/workspace', '/blogs', '/topics', '/publishing', '/analytics', '/automation', '/data', '/integrations', '/audit'];

export function isSeoPath(pathname) {
  return SEO_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
