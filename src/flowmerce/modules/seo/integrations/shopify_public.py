"""Read-only data every Shopify storefront publishes without credentials: the blog Atom feed and
/products.json. It only sees articles that are already live, so no drafts or SEO fields; the dashboard
labels it "Public feed" for that reason."""
from __future__ import annotations

import html
import re

import httpx

from ..config import BrandConfig

UA = {"User-Agent": "BlogOps-Dashboard/1.0 (+internal SEO operations)"}


def _tag_text(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}(?:\s[^>]*)?>([\s\S]*?)</{tag}>", xml, re.I)
    if not m:
        return ""
    inner = m.group(1).strip()
    cdata = re.fullmatch(r"<!\[CDATA\[([\s\S]*?)\]\]>", inner)
    return cdata.group(1) if cdata else html.unescape(inner)


def parse_atom(xml: str) -> list[dict]:
    out = []
    for e in re.findall(r"<entry>[\s\S]*?</entry>", xml):
        m = re.search(r'<link[^>]*rel="alternate"[^>]*href="([^"]+)"', e) or re.search(r'<link[^>]*href="([^"]+)"', e)
        url = html.unescape(m.group(1)) if m else _tag_text(e, "id")
        author_block = re.search(r"<author>([\s\S]*?)</author>", e)
        summary = re.sub(r'<p><a class="read-more"[\s\S]*?</p>', "", _tag_text(e, "summary")).strip()
        item = {
            "url": url,
            "handle": [p for p in url.split("/") if p][-1] if url else "",
            "title": _tag_text(e, "title"),
            "published_at": _tag_text(e, "published"),
            "updated_at": _tag_text(e, "updated"),
            "author": _tag_text(author_block.group(1), "name") if author_block else "",
            "summary_html": summary,
            "body_html": _tag_text(e, "content"),
            "tags": [html.unescape(t) for t in re.findall(r'<category[^>]*term="([^"]+)"', e)],
        }
        if item["handle"] and item["title"]:
            out.append(item)
    return out


def fetch_public_articles(b: BrandConfig) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for page in range(1, 21):
        res = httpx.get(f"https://{b.storefront_domain}/blogs/{b.blog_handle}.atom", params={"page": page},
                        headers={**UA, "Accept": "application/atom+xml"}, timeout=20, follow_redirects=True)
        if res.status_code == 404:
            raise RuntimeError(f"No public blog at /blogs/{b.blog_handle} on {b.storefront_domain}. Check the blog handle in settings.")
        if res.status_code >= 300:
            raise RuntimeError(f"Storefront feed {res.status_code} from {b.storefront_domain}")
        batch = parse_atom(res.text)
        fresh = [i for i in batch if i["url"] not in seen]
        seen.update(i["url"] for i in fresh)
        items.extend(fresh)
        if len(batch) < 50 or not fresh:
            break
    return items


def fetch_public_products(b: BrandConfig) -> list[dict]:
    out = []
    for page in range(1, 11):
        res = httpx.get(f"https://{b.storefront_domain}/products.json", params={"limit": 250, "page": page},
                        headers={**UA, "Accept": "application/json"}, timeout=20, follow_redirects=True)
        if res.status_code >= 300:
            raise RuntimeError(f"Storefront products.json {res.status_code} from {b.storefront_domain}")
        items = res.json().get("products") or []
        for p in items:
            out.append({"handle": p["handle"], "title": p["title"], "type": p.get("product_type") or "",
                        "url": f"https://{b.storefront_domain}/products/{p['handle']}",
                        "image": (p.get("images") or [{}])[0].get("src", "")})
        if len(items) < 250:
            break
    return out
