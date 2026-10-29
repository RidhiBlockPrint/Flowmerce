const nf = new Intl.NumberFormat('en-US');
const nfCompact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });

export const fmtInt = (n: number | null | undefined) => (n === null || n === undefined || Number.isNaN(n) ? '—' : nf.format(Math.round(n)));
export const fmtCompact = (n: number | null | undefined) => (n === null || n === undefined ? '—' : Math.abs(n) >= 10000 ? nfCompact.format(n) : nf.format(Math.round(n)));
export const fmtPct = (n: number | null | undefined, digits = 1) => (n === null || n === undefined || Number.isNaN(n) ? '—' : `${(n * 100).toFixed(digits)}%`);
export const fmtPos = (n: number | null | undefined) => (n === null || n === undefined ? '—' : n.toFixed(1));
export const fmtSeconds = (s: number | null | undefined) => {
  if (s === null || s === undefined) return '—';
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return m ? `${m}m ${String(r).padStart(2, '0')}s` : `${r}s`;
};

export function fmtDate(iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!iso) return '—';
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('en-GB', opts);
}
export const fmtDay = (iso: string) => fmtDate(iso, { day: 'numeric', month: 'short' });
export function fmtDateTime(iso: string | null | undefined) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 0) return 'in ' + timeAgoAbs(-s);
  if (s < 45) return 'just now';
  return timeAgoAbs(s) + ' ago';
}
function timeAgoAbs(s: number) {
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min`;
  if (s < 86400) return `${Math.round(s / 3600)} h`;
  if (s < 86400 * 30) return `${Math.round(s / 86400)} d`;
  if (s < 86400 * 365) return `${Math.round(s / (86400 * 30))} mo`;
  return `${Math.round(s / (86400 * 365))} y`;
}

export function pctChange(cur: number | null | undefined, prev: number | null | undefined): number | null {
  if (cur === null || cur === undefined || prev === null || prev === undefined || prev === 0) return null;
  return (cur - prev) / prev;
}

export const ARTICLE_STATUS: Record<string, { label: string; tone: string }> = {
  idea: { label: 'Idea', tone: 'neutral' },
  draft: { label: 'Draft', tone: 'neutral' },
  in_review: { label: 'In review', tone: 'info' },
  changes_requested: { label: 'Changes requested', tone: 'warn' },
  approved: { label: 'Approved', tone: 'ok' },
  publish_requested: { label: 'Awaiting publish OK', tone: 'accent' },
  scheduled: { label: 'Scheduled', tone: 'info' },
  published: { label: 'Published', tone: 'ok' },
  failed: { label: 'Publish failed', tone: 'crit' },
};

export const ROLE_LABEL: Record<string, string> = { admin: 'Admin', seo_manager: 'SEO Manager', reviewer: 'Reviewer', '': '—' };

export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join('') || '?';
}

export function isoDay(d: Date) {
  return d.toISOString().slice(0, 10);
}
export function addDays(iso: string, n: number) {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return isoDay(d);
}
