"""Pull data from connected services into the local database.

Shopify: with an Admin token every article (drafts included) and products are read; without one the
storefront's public feed is used, which only shows live articles. Remote content never overwrites a
working copy with unpublished edits: it only replaces the local copy when that copy was identical to
what was live before (i.e. someone edited the article in Shopify admin directly)."""
from __future__ import annotations

import json

from ..audit import audit
from ..config import config
from ..db import Row, all_rows, get, now, run, tx
from ..integrations import shopify
from ..integrations.google import ga4_configured, ga4_report, gsc_configured, gsc_query
from ..integrations.shopify_public import fetch_public_articles, fetch_public_products
from ..integrations.status import mark_attempt, mark_error, mark_pending, mark_success
from ..util import add_days, page_path, parse_iso, sanitize_html, today
from .articles import CONTENT_FIELDS, content_of, create_article, hash_content
from .brands import brand


def _incoming_content(i: dict, base: dict | None) -> dict:
    return {
        "title": i["title"], "handle": i["handle"],
        "primary_keyword": (base or {}).get("primary_keyword", ""),
        "meta_title": i["meta_title"] if i.get("meta_title") is not None else (base or {}).get("meta_title", ""),
        "meta_description": i["meta_description"] if i.get("meta_description") is not None else (base or {}).get("meta_description", ""),
        "summary_html": sanitize_html(i["summary"]), "body_html": sanitize_html(i["body"]),
        "tags": i["tags"], "author": i["author"], "image_url": i["image_url"], "image_alt": i["image_alt"],
    }


def _upsert_articles(brand_id: str, items: list[dict], origin: str) -> dict:
    inserted = updated = refreshed = 0
    t = now()
    with tx():
        for i in items:
            local = (i["shopify_id"] and get("SELECT * FROM articles WHERE brand_id = ? AND shopify_article_id = ?", brand_id, i["shopify_id"])) \
                or get("SELECT * FROM articles WHERE brand_id = ? AND handle = ?", brand_id, i["handle"])
            if not local:
                a = create_article(None, brand_id, _incoming_content(i, None), origin, "published" if i["is_published"] else "draft")
                run("UPDATE articles SET shopify_article_id=?, shopify_published=?, live_hash=?, live_url=?, published_at=?, shopify_synced_at=? WHERE id=?",
                    i["shopify_id"], 1 if i["is_published"] else 0, a["content_hash"] if i["is_published"] else None, i["url"], i["published_at"], t, a["id"])
                inserted += 1
                continue
            now_live = (local["status"] == "scheduled" and i["is_published"] and i["published_at"]
                        and parse_iso(i["published_at"]).timestamp() <= parse_iso(t).timestamp())
            run("""UPDATE articles SET shopify_article_id=COALESCE(?, shopify_article_id), shopify_published=?, live_url=?,
                     published_at=COALESCE(?, published_at), shopify_synced_at=?, status=? WHERE id=?""",
                i["shopify_id"], 1 if i["is_published"] else 0, i["url"], i["published_at"], t,
                "published" if now_live else local["status"], local["id"])
            refreshed += 1
            if origin != "shopify_admin":
                continue  # the public feed has no SEO fields; never use it to replace content
            remote = _incoming_content(i, content_of(local))
            rh = hash_content(remote)
            clean = local["content_hash"] == local["live_hash"] or (local["status"] == "published" and not local["live_hash"])
            if i["is_published"] and rh != local["content_hash"] and clean and local["status"] == "published":
                v = local["version"] + 1
                run(f"UPDATE articles SET {', '.join(f + '=?' for f in CONTENT_FIELDS)}, content_hash=?, live_hash=?, approved_hash=?, version=?, updated_at=? WHERE id=?",
                    *[remote[f] for f in CONTENT_FIELDS], rh, rh, rh, v, t, local["id"])
                run("INSERT INTO article_revisions (article_id, version, data_json, content_hash, user_id, note, created_at) VALUES (?,?,?,?,?,?,?)",
                    local["id"], v, json.dumps(remote, ensure_ascii=False), rh, None, "Synced: edited directly in Shopify admin", t)
                audit(None, "article.synced_from_shopify", "article", local["id"], brand_id, i["title"])
                updated += 1
            elif i["is_published"] and local["live_hash"] != rh:
                run("UPDATE articles SET live_hash=? WHERE id=?", rh, local["id"])
    return {"inserted": inserted, "updated": updated, "refreshed": refreshed}


def _upsert_products(brand_id: str, items: list[dict], source: str) -> None:
    t = now()
    with tx():
        for p in items:
            run("""INSERT INTO products (brand_id, handle, title, url, image_url, product_type, synced_at, source) VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(brand_id, handle) DO UPDATE SET title=excluded.title, url=excluded.url, image_url=excluded.image_url,
                     product_type=excluded.product_type, synced_at=excluded.synced_at, source=excluded.source""",
                brand_id, p["handle"], p["title"], p["url"], p["image"], p["type"], t, source)
        if items:
            run("DELETE FROM products WHERE brand_id = ? AND synced_at < ?", brand_id, t)


def sync_shopify(brand_id: str) -> dict:
    b = brand(brand_id)
    if shopify.configured(b):
        mark_attempt("shopify", brand_id, "admin_api")
        try:
            blog = shopify.find_blog(b)
            lst = shopify.list_articles(b, blog["id"])
            items = [{
                "shopify_id": a["id"], "handle": a["handle"], "title": a["title"], "body": a.get("body") or "",
                "summary": a.get("summary") or "", "tags": ", ".join(a.get("tags") or []), "author": (a.get("author") or {}).get("name", ""),
                "image_url": (a.get("image") or {}).get("url", ""), "image_alt": (a.get("image") or {}).get("altText") or "",
                "meta_title": (a.get("seoTitle") or {}).get("value"), "meta_description": (a.get("seoDescription") or {}).get("value"),
                "is_published": a["isPublished"], "published_at": a.get("publishedAt"),
                "url": f"https://{b.storefront_domain}/blogs/{blog['handle']}/{a['handle']}",
            } for a in lst]
            res = _upsert_articles(brand_id, items, "shopify_admin")
            run("UPDATE articles SET shopify_blog_id = ? WHERE brand_id = ? AND shopify_blog_id IS NULL", blog["id"], brand_id)
            products = shopify.list_products(b)
            _upsert_products(brand_id, products, "shopify_admin")
            mark_success("shopify", brand_id, "admin_api", {"blog": blog["handle"], "articles": len(lst), "products": len(products)})
            return {"mode": "admin_api", "articles": len(lst), "products": len(products), **res}
        except Exception as e:
            mark_error("shopify", brand_id, "admin_api", getattr(e, "message", e))
            raise
    mark_pending("shopify", brand_id, f"Set {brand_id.upper()}_SHOPIFY_ADMIN_TOKEN to manage drafts and publishing.")
    if not config.public_feed_sync:
        raise RuntimeError("Shopify Admin API is not set up and the public feed sync is turned off.")
    mark_attempt("shopify_public", brand_id, "public_feed")
    try:
        lst = fetch_public_articles(b)
        items = [{
            "shopify_id": None, "handle": a["handle"], "title": a["title"], "body": a["body_html"], "summary": a["summary_html"],
            "tags": ", ".join(a["tags"]), "author": a["author"], "image_url": "", "image_alt": "", "meta_title": None,
            "meta_description": None, "is_published": True, "published_at": a["published_at"] or None, "url": a["url"],
        } for a in lst]
        res = _upsert_articles(brand_id, items, "shopify_public")
        products = fetch_public_products(b)
        _upsert_products(brand_id, products, "shopify_public")
        mark_success("shopify_public", brand_id, "public_feed", {"articles": len(lst), "products": len(products)})
        return {"mode": "public_feed", "articles": len(lst), "products": len(products), **res}
    except Exception as e:
        mark_error("shopify_public", brand_id, "public_feed", e)
        raise


def sync_gsc(brand_id: str) -> dict:
    """Search Console data is final ~3 days after the day it describes, so the window ends 3 days ago.
    The first sync takes 16 months; later syncs re-read the last 10 days."""
    b = brand(brand_id)
    if not gsc_configured(b):
        mark_pending("gsc", brand_id, "Set GOOGLE_SERVICE_ACCOUNT_FILE and add the service account to the Search Console property.")
        raise RuntimeError("Search Console is not set up for this brand.")
    mark_attempt("gsc", brand_id, "api")
    try:
        end = add_days(today(), -3)
        has = get("SELECT 1 FROM gsc_page_daily WHERE brand_id = ? AND source = 'api' LIMIT 1", brand_id)
        start = add_days(end, -10 if has else -480)
        rows = gsc_query(b, start, end, ["date", "page"])
        q_start = add_days(end, -27)
        q_rows = gsc_query(b, q_start, end, ["page", "query"])
        t = now()
        with tx():
            run("DELETE FROM gsc_page_daily WHERE brand_id = ? AND source = 'api' AND date BETWEEN ? AND ?", brand_id, start, end)
            for r in rows:
                run("""INSERT OR REPLACE INTO gsc_page_daily (brand_id, date, page, clicks, impressions, ctr, position, source, source_timestamp, imported_at)
                       VALUES (?,?,?,?,?,?,?,'api',?,?)""", brand_id, r["keys"][0], page_path(r["keys"][1]), r["clicks"], r["impressions"], r["ctr"], r["position"], t, t)
            run("DELETE FROM gsc_query_period WHERE brand_id = ? AND source = 'api'", brand_id)
            for r in q_rows:
                run("""INSERT OR REPLACE INTO gsc_query_period (brand_id, start_date, end_date, page, query, clicks, impressions, ctr, position, source, source_timestamp, imported_at)
                       VALUES (?,?,?,?,?,?,?,?,?,'api',?,?)""", brand_id, q_start, end, page_path(r["keys"][0]), r["keys"][1], r["clicks"], r["impressions"], r["ctr"], r["position"], t, t)
        mark_success("gsc", brand_id, "api", {"start": start, "end": end, "pageRows": len(rows), "queryRows": len(q_rows)})
        return {"start": start, "end": end, "pageRows": len(rows), "queryRows": len(q_rows)}
    except Exception as e:
        mark_error("gsc", brand_id, "api", getattr(e, "message", e))
        raise


def sync_ga4(brand_id: str) -> dict:
    b = brand(brand_id)
    if not ga4_configured(b):
        mark_pending("ga4", brand_id, f"Set {brand_id.upper()}_GA4_PROPERTY_ID and give the service account Viewer access.")
        raise RuntimeError("GA4 is not set up for this brand.")
    mark_attempt("ga4", brand_id, "api")
    try:
        end = add_days(today(), -1)
        has = get("SELECT 1 FROM ga4_page_daily WHERE brand_id = ? AND source = 'api' LIMIT 1", brand_id)
        start = add_days(end, -7 if has else -480)
        rows = ga4_report(b, start, end)
        merged: dict[tuple[str, str], dict] = {}  # several landing-page variants per path are summed
        for r in rows:
            m = merged.setdefault((r["date"], r["path"]), {"s": 0.0, "e": 0.0, "d": 0.0, "k": 0.0})
            m["s"] += r["sessions"]; m["e"] += r["engaged"]; m["d"] += r["duration"]; m["k"] += r["key_events"]
        t = now()
        with tx():
            run("DELETE FROM ga4_page_daily WHERE brand_id = ? AND source = 'api' AND date BETWEEN ? AND ?", brand_id, start, end)
            for (d, p), m in merged.items():
                run("""INSERT OR REPLACE INTO ga4_page_daily (brand_id, date, page_path, sessions, engaged_sessions, engagement_rate, avg_engagement_seconds, key_events, source, source_timestamp, imported_at)
                       VALUES (?,?,?,?,?,?,?,?,'api',?,?)""",
                    brand_id, d, p, int(m["s"]), int(m["e"]), m["e"] / m["s"] if m["s"] else 0, m["d"] / m["s"] if m["s"] else 0, m["k"], t, t)
        mark_success("ga4", brand_id, "api", {"start": start, "end": end, "rows": len(merged)})
        return {"start": start, "end": end, "rows": len(merged)}
    except Exception as e:
        mark_error("ga4", brand_id, "api", getattr(e, "message", e))
        raise


def products_for(brand_id: str) -> list[Row]:
    return all_rows("SELECT handle, title, url, image_url, product_type, source FROM products WHERE brand_id = ? ORDER BY title", brand_id)
