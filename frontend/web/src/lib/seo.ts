/* Editorial SEO checks run in the browser while editing. They are guidance, not gates: the server
 * enforces only what must be true (body, meta description and keyword before review). */
export interface Check { id: string; label: string; state: 'pass' | 'warn' | 'fail'; detail?: string; weight: number }

const strip = (h: string) => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
const has = (text: string, kw: string) => !!kw && text.toLowerCase().includes(kw.toLowerCase());

export function seoChecks(a: { title: string; meta_title: string; meta_description: string; body_html: string; primary_keyword: string; handle: string; image_url: string; image_alt: string }, storefrontHost: string): { checks: Check[]; score: number; words: number } {
  const kw = a.primary_keyword.trim();
  const body = a.body_html || '';
  const text = strip(body);
  const words = text ? text.split(' ').length : 0;
  const firstP = strip((body.match(/<p[^>]*>([\s\S]*?)<\/p>/i) || [])[1] || '');
  const h2s = [...body.matchAll(/<h2[^>]*>([\s\S]*?)<\/h2>/gi)].map((m) => strip(m[1]));
  const links = [...body.matchAll(/<a\s[^>]*href="([^"]+)"/gi)].map((m) => m[1]);
  const internal = links.filter((l) => l.startsWith('/') || l.includes(storefrontHost));
  const imgs = [...body.matchAll(/<img\b[^>]*>/gi)].map((m) => m[0]);
  const imgsNoAlt = imgs.filter((i) => !/\balt="[^"]+"/i.test(i));
  const metaTitle = a.meta_title || a.title;
  const md = a.meta_description;
  const c: Check[] = [];
  const add = (id: string, label: string, state: Check['state'], weight: number, detail?: string) => c.push({ id, label, state, weight, detail });

  add('kw', 'Primary keyword set', kw ? 'pass' : 'fail', 2, kw ? undefined : 'Add the phrase this article should rank for.');
  add('title-len', 'Title length', a.title.length >= 30 && a.title.length <= 70 ? 'pass' : 'warn', 1, `${a.title.length} characters (aim for 30–70)`);
  add('kw-title', 'Keyword in title', has(a.title, kw) ? 'pass' : 'fail', 2);
  add('meta-title', 'SEO title fits in results', metaTitle.length <= 60 ? (a.meta_title ? 'pass' : 'warn') : 'fail', 1, a.meta_title ? `${metaTitle.length}/60 characters` : 'Not set — Shopify will use the article title');
  add('meta-desc', 'Meta description length', md.length >= 120 && md.length <= 160 ? 'pass' : md ? 'warn' : 'fail', 2, md ? `${md.length} characters (aim for 120–160)` : 'Missing');
  add('kw-meta', 'Keyword in meta description', has(md, kw) ? 'pass' : 'warn', 1);
  add('kw-first', 'Keyword in the first paragraph', has(firstP, kw) ? 'pass' : 'warn', 1);
  add('kw-h2', 'Keyword in a subheading', h2s.some((h) => has(h, kw)) ? 'pass' : 'warn', 1);
  add('h2', 'Structured with subheadings', h2s.length >= 2 ? 'pass' : h2s.length ? 'warn' : 'fail', 1, `${h2s.length} H2 headings`);
  add('no-h1', 'No H1 in the body', /<h1\b/i.test(body) ? 'fail' : 'pass', 1, 'The theme already renders the title as H1');
  add('length', 'Length', words >= 900 ? 'pass' : words >= 400 ? 'warn' : 'fail', 2, `${words.toLocaleString()} words (aim for 900+)`);
  add('internal', 'Internal links', internal.length >= 2 ? 'pass' : internal.length ? 'warn' : 'fail', 2, `${internal.length} link${internal.length === 1 ? '' : 's'} to the store`);
  add('img-alt', 'Images have alt text', imgsNoAlt.length ? 'fail' : 'pass', 1, imgs.length ? `${imgs.length - imgsNoAlt.length}/${imgs.length} with alt` : 'No inline images');
  add('featured', 'Featured image with alt text', a.image_url && a.image_alt ? 'pass' : a.image_url ? 'warn' : 'fail', 1);
  add('handle', 'Short, readable URL', a.handle.length <= 75 && (!kw || kw.toLowerCase().split(/\s+/).some((w) => w.length > 3 && a.handle.includes(w))) ? 'pass' : 'warn', 1, `/${a.handle}`);

  const total = c.reduce((s, x) => s + x.weight, 0);
  const got = c.reduce((s, x) => s + (x.state === 'pass' ? x.weight : x.state === 'warn' ? x.weight / 2 : 0), 0);
  return { checks: c, score: Math.round((got / total) * 100), words };
}
