"""Demo fixtures: synthetic Search Console and GA4 rows so the analytics screens can be tried before
Google is connected. Rows are stored with source = 'demo', labelled "Demo — not real data" on every
screen, never exported, and analytics prefers live or imported rows whenever any exist. Load and clear
are admin-only and audited."""
from __future__ import annotations

import math

from ..audit import audit
from ..db import all_rows, get, now, run, tx
from ..util import add_days, page_path, today

QUERIES = ["block print tablecloth", "how to wash block print fabric", "hand block printing india", "round tablecloth size guide", "cotton napkins set",
           "boho table setting ideas", "christmas tablescape ideas", "block print bedding", "floral table runner", "quilted placemats"]


def _rng(seed: int):
    state = [seed & 0xFFFFFFFF]

    def nxt() -> float:
        state[0] = (state[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        return state[0] / 4294967296
    return nxt


def load_demo(user: dict) -> dict:
    end = add_days(today(), -3)
    t = now()
    rows = 0
    with tx():
        for bi, b in enumerate(("ridhi", "cpc")):
            pages = [page_path(r["live_url"]) for r in all_rows("SELECT live_url FROM articles WHERE brand_id = ? AND live_url IS NOT NULL LIMIT 20", b)]
            pages = pages or ["/blogs/demo/sample-article-one", "/blogs/demo/sample-article-two", "/blogs/demo/sample-article-three"]
            rand = _rng(42 + bi)
            for pi, page in enumerate(pages):
                base = 6 + rand() * 60 * (1 / (pi + 1))
                pos0 = 6 + rand() * 18
                for d in range(179, -1, -1):
                    day = add_days(end, -d)
                    trend = 1 + (179 - d) / 300
                    weekly = 1 + 0.15 * math.sin((d / 7) * math.pi * 2)
                    impressions = max(0, round(base * 9 * trend * weekly * (0.7 + rand() * 0.6)))
                    position = max(1.0, pos0 - (179 - d) / 60 + (rand() - 0.5) * 2)
                    ctr = min(0.35, 0.28 / position ** 0.9)
                    clicks = min(impressions, round(impressions * ctr * (0.7 + rand() * 0.6)))
                    run("""INSERT OR REPLACE INTO gsc_page_daily (brand_id, date, page, clicks, impressions, ctr, position, source, source_timestamp, imported_at)
                           VALUES (?,?,?,?,?,?,?, 'demo', ?, ?)""", b, day, page, clicks, impressions, clicks / impressions if impressions else 0, position, t, t)
                    sessions = round(clicks * (1.3 + rand() * 0.8))
                    engaged = round(sessions * (0.45 + rand() * 0.3))
                    run("""INSERT OR REPLACE INTO ga4_page_daily (brand_id, date, page_path, sessions, engaged_sessions, engagement_rate, avg_engagement_seconds, key_events, source, source_timestamp, imported_at)
                           VALUES (?,?,?,?,?,?,?,?, 'demo', ?, ?)""",
                        b, day, page, sessions, engaged, engaged / sessions if sessions else 0, 40 + rand() * 90, round(sessions * 0.012 * rand() * 10) / 10, t, t)
                    rows += 2
                for q in QUERIES[: 4 + int(rand() * 6)]:
                    impressions = round(50 + rand() * 900)
                    position = 2 + rand() * 18
                    clicks = round(impressions * min(0.3, 0.25 / position) * (0.6 + rand()))
                    run("""INSERT OR REPLACE INTO gsc_query_period (brand_id, start_date, end_date, page, query, clicks, impressions, ctr, position, source, source_timestamp, imported_at)
                           VALUES (?,?,?,?,?,?,?,?,?, 'demo', ?, ?)""", b, add_days(end, -27), end, page, q, clicks, impressions, clicks / impressions, position, t, t)
                    rows += 1
    audit(user, "demo.load", summary=f"{rows} demo metric rows loaded")
    return {"rows": rows}


def clear_demo(user: dict) -> dict:
    with tx():
        n = (run("DELETE FROM gsc_page_daily WHERE source = 'demo'").changes + run("DELETE FROM ga4_page_daily WHERE source = 'demo'").changes
             + run("DELETE FROM gsc_query_period WHERE source = 'demo'").changes)
    audit(user, "demo.clear", summary=f"{n} demo metric rows removed")
    return {"removed": n}


def demo_loaded() -> bool:
    return bool(get("SELECT 1 FROM gsc_page_daily WHERE source = 'demo' LIMIT 1"))
