/* Storefront-style article preview, rendered into a sandboxed iframe (no scripts run). Fonts and
 * colours follow each live theme: Ridhi's "Petal" theme (Libre Caslon Text headings, Plus Jakarta
 * Sans body, crimson accent band) and CPC's theme (system serif throughout, paper #F5F4F4, umber). */
import type { BrandId } from './types';

const esc = (s: string) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

export function previewDoc(brand: BrandId, a: { title: string; body_html: string; summary_html: string; image_url: string; image_alt: string; author: string; tags: string; published_at?: string | null }, storefront: string): string {
  const ridhi = brand === 'ridhi';
  const date = new Date(a.published_at || Date.now()).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  const css = ridhi
    ? `body{font-family:'Plus Jakarta Sans',system-ui,sans-serif;color:#222;background:#fff}
       h1,h2,h3{font-family:'Libre Caslon Text',Georgia,serif;font-weight:400;color:#111}
       .bar{background:#850000;color:#fff}.hdr .mark{font-family:'Libre Caslon Text',serif;color:#850000;letter-spacing:.12em}
       a{color:#850000}.tag{border-color:#efb34c;color:#7a4d00}`
    : `body{font-family:'New York','Iowan Old Style','Apple Garamond',Baskerville,'Times New Roman',serif;color:#000;background:#f5f4f4}
       h1,h2,h3{font-weight:400;color:#000}.bar{background:#000;color:#fff}.hdr{background:#fff}.hdr .mark{font-family:inherit;color:#000;letter-spacing:.02em}
       a{color:#7d6557}.tag{border-color:#7d6557;color:#7d6557}`;
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Text:wght@400;700&family=Plus+Jakarta+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box}body{margin:0;line-height:1.7;font-size:17px}
.bar{font:600 12px/1 system-ui,sans-serif;text-align:center;padding:9px;letter-spacing:.04em}
.hdr{display:flex;align-items:center;justify-content:space-between;padding:16px 28px;border-bottom:1px solid #eee}
.hdr .mark{font-size:22px}.hdr nav{display:flex;gap:18px;font:500 13px system-ui,sans-serif;color:#555}
.wrap{max-width:760px;margin:0 auto;padding:36px 22px 80px}
.crumb{font:500 12px system-ui,sans-serif;color:#888;text-transform:uppercase;letter-spacing:.08em}
h1{font-size:clamp(28px,5vw,42px);line-height:1.2;margin:10px 0 12px}
.meta{font:400 13px system-ui,sans-serif;color:#777;margin-bottom:26px}
.hero{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:4px;margin-bottom:28px;background:#eee}
h2{font-size:28px;line-height:1.3;margin:1.6em 0 .5em}h3{font-size:21px;margin:1.3em 0 .4em}
p{margin:0 0 1.1em}img{max-width:100%;height:auto}blockquote{margin:1.4em 0;padding:.2em 1.2em;border-left:3px solid currentColor;font-style:italic}
.tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:36px}.tag{border:1px solid;border-radius:999px;padding:3px 12px;font:500 12px system-ui,sans-serif}
.note{position:fixed;bottom:10px;right:10px;background:#1e1a17;color:#fff;font:600 11px system-ui,sans-serif;padding:6px 10px;border-radius:6px;opacity:.85}
@media(max-width:600px){.hdr nav{display:none}.hdr{padding:14px 18px}body{font-size:16px}}
${css}
</style></head><body>
<div class="bar">${ridhi ? 'FREE WORLDWIDE SHIPPING' : 'HAND PRINTED FABRIC, MADE BY ARTISANS'}</div>
<header class="hdr"><span class="mark">${ridhi ? 'RIDHI' : 'Cotton Print Club'}</span><nav><span>Shop</span><span>Collections</span><span>Our Story</span><span>Blog</span></nav></header>
<main class="wrap">
<div class="crumb">Blog</div>
<h1>${esc(a.title) || 'Untitled article'}</h1>
<div class="meta">${esc(date)}${a.author ? ` · ${esc(a.author)}` : ''}</div>
${a.image_url ? `<img class="hero" src="${esc(a.image_url)}" alt="${esc(a.image_alt)}">` : ''}
<article>${a.body_html || '<p style="color:#999">No body yet.</p>'}</article>
${a.tags ? `<div class="tags">${a.tags.split(',').map((t) => t.trim()).filter(Boolean).map((t) => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : ''}
</main>
<div class="note">Preview · ${esc(storefront.replace('https://', ''))} theme approximation · not live</div>
</body></html>`;
}
