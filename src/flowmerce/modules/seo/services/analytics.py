"""Search Console and GA4 reporting, kept apart on purpose: Search Console counts Google search clicks
per URL; GA4 counts sessions that landed on a URL from any channel. They are never merged.

For each brand and range the source is chosen once: live API rows if any, otherwise manually imported
rows, otherwise demo fixtures. Every response says which one it used."""
from __future__ import annotations

from ..db import Row, all_rows, get
from ..integrations.status import status_of
from ..util import add_days, days_between, page_path

LABEL = {"api": "Live API", "excel": "Manual import (Excel)", "demo": "Demo fixture — not real data"}


def _pick_source(table: str, brand_id: str, frm: str, to: str) -> dict:
    for kind in ("api", "excel", "demo"):
        r = get(f"SELECT MIN(date) mn, MAX(date) mx, MAX(imported_at) ts FROM {table} WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ?",
                brand_id, kind, frm, to)
        if r and r["mn"]:
            integ = status_of("gsc" if table.startswith("gsc") else "ga4", brand_id) if kind == "api" else None
            return {"kind": kind, "label": LABEL[kind], "syncedAt": (integ or {}).get("last_success_at") or r["ts"],
                    "coverage": {"from": r["mn"], "to": r["mx"]}}
    return {"kind": None, "label": "No data", "syncedAt": None, "coverage": {"from": None, "to": None}}


def _article_index(brand_id: str) -> dict[str, dict]:
    return {page_path(a["live_url"]): {"id": a["id"], "title": a["title"]}
            for a in all_rows("SELECT id, title, live_url FROM articles WHERE brand_id = ? AND live_url IS NOT NULL", brand_id)}


def _prev(frm: str, to: str) -> dict:
    n = days_between(frm, to) + 1
    return {"from": add_days(frm, -n), "to": add_days(frm, -1)}


def _gsc_totals(brand_id: str, src: str, frm: str, to: str) -> dict:
    r = get("SELECT SUM(clicks) c, SUM(impressions) i, SUM(position * impressions) pw FROM gsc_page_daily WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ?",
            brand_id, src, frm, to) or {}
    c, i = r.get("c") or 0, r.get("i") or 0
    return {"clicks": c, "impressions": i, "ctr": c / i if i else None, "position": (r.get("pw") or 0) / i if i else None}


def gsc_report(brand_id: str, frm: str, to: str) -> dict:
    source = _pick_source("gsc_page_daily", brand_id, frm, to)
    if not source["kind"]:
        return {"brand": brand_id, "source": source, "totals": None, "previous": None, "series": [], "pages": [], "queries": None, "declining": [], "opportunities": []}
    src, prev = source["kind"], _prev(frm, to)
    series = all_rows("""SELECT date, SUM(clicks) clicks, SUM(impressions) impressions, SUM(position*impressions)/NULLIF(SUM(impressions),0) position
                         FROM gsc_page_daily WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ? GROUP BY date ORDER BY date""", brand_id, src, frm, to)
    idx = _article_index(brand_id)

    def page_rows(f: str, t: str) -> list[Row]:
        return all_rows("""SELECT page, SUM(clicks) clicks, SUM(impressions) impressions, SUM(position*impressions)/NULLIF(SUM(impressions),0) position
                           FROM gsc_page_daily WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ? GROUP BY page""", brand_id, src, f, t)

    before = {p["page"]: p for p in page_rows(prev["from"], prev["to"])}
    pages = sorted(({**p, "ctr": p["clicks"] / p["impressions"] if p["impressions"] else None,
                     "prevClicks": (before.get(p["page"]) or {}).get("clicks", 0), "article": idx.get(p["page"])}
                    for p in page_rows(frm, to)), key=lambda p: (-p["clicks"], -p["impressions"]))
    declining = sorted(({**p, "change": p["clicks"] - p["prevClicks"]} for p in pages if p["prevClicks"] >= 5 and p["clicks"] < p["prevClicks"] * 0.75),
                       key=lambda p: p["change"])[:10]
    qp = get("""SELECT start_date, end_date FROM gsc_query_period WHERE brand_id = ? AND source = ?
                GROUP BY start_date, end_date ORDER BY end_date DESC LIMIT 1""", brand_id, src)
    queries, opportunities = None, []
    if qp:
        rows = all_rows("""SELECT query, SUM(clicks) clicks, SUM(impressions) impressions, SUM(position*impressions)/NULLIF(SUM(impressions),0) position
                           FROM gsc_query_period WHERE brand_id = ? AND source = ? AND start_date = ? AND end_date = ? GROUP BY query
                           ORDER BY clicks DESC, impressions DESC LIMIT 50""", brand_id, src, qp["start_date"], qp["end_date"])
        queries = {"period": {"from": qp["start_date"], "to": qp["end_date"]},
                   "rows": [{**q, "ctr": q["clicks"] / q["impressions"] if q["impressions"] else None} for q in rows]}
        # "Striking distance": already on page 1–2 with real impressions; a better title, section or
        # internal links can move the page up.
        opportunities = [{**o, "ctr": o["clicks"] / o["impressions"] if o["impressions"] else None, "article": idx.get(o["page"])}
                         for o in all_rows("""SELECT query, page, clicks, impressions, position FROM gsc_query_period
                                              WHERE brand_id = ? AND source = ? AND start_date = ? AND end_date = ? AND position BETWEEN 4 AND 20 AND impressions >= 20
                                              ORDER BY impressions DESC LIMIT 12""", brand_id, src, qp["start_date"], qp["end_date"])]
    return {"brand": brand_id, "source": source, "totals": _gsc_totals(brand_id, src, frm, to), "previous": _gsc_totals(brand_id, src, prev["from"], prev["to"]),
            "previousRange": prev, "series": series, "pages": pages[:100], "queries": queries, "declining": declining, "opportunities": opportunities}


def _ga4_totals(brand_id: str, src: str, frm: str, to: str) -> dict:
    r = get("""SELECT SUM(sessions) s, SUM(engaged_sessions) e, SUM(avg_engagement_seconds*sessions) d, SUM(key_events) k
               FROM ga4_page_daily WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ?""", brand_id, src, frm, to) or {}
    sessions = r.get("s") or 0
    return {"sessions": sessions, "engagedSessions": r.get("e") or 0,
            "engagementRate": (r.get("e") or 0) / sessions if sessions else None,
            "avgEngagementSeconds": (r.get("d") or 0) / sessions if sessions else None, "keyEvents": r.get("k") or 0}


def ga4_report(brand_id: str, frm: str, to: str) -> dict:
    source = _pick_source("ga4_page_daily", brand_id, frm, to)
    if not source["kind"]:
        return {"brand": brand_id, "source": source, "totals": None, "previous": None, "series": [], "pages": []}
    src, prev, idx = source["kind"], _prev(frm, to), _article_index(brand_id)
    series = all_rows("""SELECT date, SUM(sessions) sessions, SUM(engaged_sessions) engaged, SUM(key_events) key_events FROM ga4_page_daily
                         WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ? GROUP BY date ORDER BY date""", brand_id, src, frm, to)
    pages = [{**p, "engagementRate": p["engaged"] / p["sessions"] if p["sessions"] else None, "article": idx.get(p["page_path"])}
             for p in all_rows("""SELECT page_path, SUM(sessions) sessions, SUM(engaged_sessions) engaged,
                                         SUM(avg_engagement_seconds*sessions)/NULLIF(SUM(sessions),0) avg_seconds, SUM(key_events) key_events
                                  FROM ga4_page_daily WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ? GROUP BY page_path ORDER BY sessions DESC LIMIT 100""",
                               brand_id, src, frm, to)]
    return {"brand": brand_id, "source": source, "totals": _ga4_totals(brand_id, src, frm, to), "previous": _ga4_totals(brand_id, src, prev["from"], prev["to"]),
            "previousRange": prev, "series": series, "pages": pages}


def article_performance(brand_id: str, frm: str, to: str) -> dict:
    """One row per article. Columns from a source with no data stay None ("—"), never 0."""
    g = _pick_source("gsc_page_daily", brand_id, frm, to)
    a = _pick_source("ga4_page_daily", brand_id, frm, to)
    gsc = {r["page"]: r for r in all_rows("""SELECT page, SUM(clicks) clicks, SUM(impressions) impressions, SUM(position*impressions)/NULLIF(SUM(impressions),0) position
                                             FROM gsc_page_daily WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ? GROUP BY page""",
                                          brand_id, g["kind"], frm, to)} if g["kind"] else {}
    ga = {r["page_path"]: r for r in all_rows("""SELECT page_path, SUM(sessions) sessions, SUM(engaged_sessions) engaged, SUM(key_events) key_events
                                                 FROM ga4_page_daily WHERE brand_id = ? AND source = ? AND date BETWEEN ? AND ? GROUP BY page_path""",
                                              brand_id, a["kind"], frm, to)} if a["kind"] else {}
    rows = []
    for r in all_rows("SELECT id, title, status, live_url, published_at, shopify_published FROM articles WHERE brand_id = ? AND live_url IS NOT NULL ORDER BY published_at DESC", brand_id):
        p = page_path(r["live_url"])
        sc, an = gsc.get(p), ga.get(p)
        rows.append({
            "id": r["id"], "title": r["title"], "status": r["status"], "url": r["live_url"], "published_at": r["published_at"], "live": bool(r["shopify_published"]),
            "clicks": (sc or {}).get("clicks", 0) if g["kind"] else None,
            "impressions": (sc or {}).get("impressions", 0) if g["kind"] else None,
            "ctr": sc["clicks"] / sc["impressions"] if g["kind"] and sc and sc["impressions"] else None,
            "position": sc["position"] if g["kind"] and sc else None,
            "sessions": (an or {}).get("sessions", 0) if a["kind"] else None,
            "engagementRate": an["engaged"] / an["sessions"] if a["kind"] and an and an["sessions"] else None,
            "keyEvents": (an or {}).get("key_events", 0) if a["kind"] else None,
        })
    return {"brand": brand_id, "sources": {"gsc": g, "ga4": a}, "rows": rows}


def article_queries(brand_id: str, url: str) -> dict | None:
    p = page_path(url)
    qp = get("""SELECT source, start_date, end_date FROM gsc_query_period WHERE brand_id = ? AND page = ?
                ORDER BY CASE source WHEN 'api' THEN 0 WHEN 'excel' THEN 1 ELSE 2 END, end_date DESC LIMIT 1""", brand_id, p)
    if not qp:
        return None
    return {"source": qp["source"], "period": {"from": qp["start_date"], "to": qp["end_date"]},
            "rows": all_rows("""SELECT query, clicks, impressions, position FROM gsc_query_period WHERE brand_id = ? AND page = ? AND source = ? AND start_date = ? AND end_date = ?
                                ORDER BY clicks DESC, impressions DESC LIMIT 25""", brand_id, p, qp["source"], qp["start_date"], qp["end_date"])}
