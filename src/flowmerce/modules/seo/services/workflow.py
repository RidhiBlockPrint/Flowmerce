"""The blogging pipeline, stage by stage. Each stage is either run by this server (Claude calls, checks,
Shopify drafts, analytics syncs) or waits on a person. Stage health comes from real records: the last
run, its error, and how many items are waiting at that stage."""
from __future__ import annotations

import json
from urllib.parse import urlparse

from ..audit import audit
from ..config import config
from ..db import all_rows, get, now, run, tx
from ..integrations import claude, shopify
from ..integrations.google import ga4_configured, gsc_configured
from ..util import HttpError, norm_keyword, s, similarity
from .articles import content_of, create_article, hash_content
from .brands import brand, brand_settings
from .publishing import save_shopify_draft
from .runs import last_run, record_run
from .sync import sync_ga4, sync_gsc, sync_shopify

STAGES = [
    {"key": "topic_research", "label": "Topic research", "kind": "automated", "owner": "Claude", "description": "Claude proposes topics from the catalogue, existing articles and Search Console queries."},
    {"key": "keyword_validation", "label": "Keyword validation", "kind": "automated", "owner": "Dashboard", "description": "Checks each proposed keyword against imported keyword data, Search Console and existing articles for overlap."},
    {"key": "topic_approval", "label": "Topic approval", "kind": "human", "owner": "SEO Manager", "description": "A person approves or rejects validated topics."},
    {"key": "content_generation", "label": "Content generation", "kind": "automated", "owner": "Claude", "description": "Claude writes a first draft for approved topics, with internal links to real products."},
    {"key": "content_approval", "label": "Content approval", "kind": "human", "owner": "Reviewer", "description": "A reviewer approves the draft or sends it back with notes."},
    {"key": "image_selection", "label": "Image selection", "kind": "automated", "owner": "Dashboard", "description": "Picks a featured image from the product a draft links to; editors can change it."},
    {"key": "shopify_draft", "label": "Shopify draft", "kind": "automated", "owner": "Dashboard", "description": "Saves approved articles to Shopify as hidden drafts. Never publishes."},
    {"key": "publication_approval", "label": "Publication approval", "kind": "human", "owner": "Reviewer / Admin", "description": "An authorized person approves the publish request and confirms it."},
    {"key": "performance_tracking", "label": "Performance tracking", "kind": "automated", "owner": "Dashboard", "description": "Refreshes Shopify, Search Console and GA4 data."},
]

HUMAN_ACTION = {
    "keyword_validation": "Import keyword volumes for topics the check could not size",
    "topic_approval": "Approve or reject validated topics",
    "content_generation": "Generate drafts for approved topics",
    "content_approval": "Review drafts waiting for approval",
    "image_selection": "Choose featured images",
    "shopify_draft": "Save approved articles as Shopify drafts",
    "publication_approval": "Authorize or reject publish requests",
}


def is_paused(brand_id: str) -> bool:
    return bool(get("SELECT paused FROM automation_state WHERE brand_id = ? AND paused = 1", brand_id))


def set_paused(user: dict, brand_id: str, paused: bool, reason: str) -> None:
    run("""INSERT INTO automation_state (brand_id, paused, paused_by, paused_at, reason) VALUES (?,?,?,?,?)
           ON CONFLICT(brand_id) DO UPDATE SET paused=excluded.paused, paused_by=excluded.paused_by, paused_at=excluded.paused_at, reason=excluded.reason""",
        brand_id, 1 if paused else 0, user["id"], now(), s(reason, 500))
    audit(user, "automation.pause" if paused else "automation.resume", "automation", brand_id, brand_id, reason)


def _setup_gap(stage: str, brand_id: str) -> str | None:
    b = brand(brand_id)
    if stage in ("topic_research", "content_generation"):
        return None if claude.configured() else "ANTHROPIC_API_KEY is not set on the server."
    if stage == "shopify_draft":
        return None if shopify.configured(b) else f"Shopify Admin API token for {b.name} is not set."
    return None


def _pending(stage: str, brand_id: str) -> int:
    q = {
        "keyword_validation": "SELECT COUNT(*) n FROM topics WHERE brand_id = ? AND status = 'proposed'",
        "topic_approval": "SELECT COUNT(*) n FROM topics WHERE brand_id = ? AND status = 'validated'",
        "content_generation": "SELECT COUNT(*) n FROM topics t WHERE brand_id = ? AND status = 'approved' AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.topic_id = t.id)",
        "content_approval": "SELECT COUNT(*) n FROM articles WHERE brand_id = ? AND status = 'in_review'",
        "image_selection": "SELECT COUNT(*) n FROM articles WHERE brand_id = ? AND status IN ('draft','changes_requested','in_review','approved') AND image_url = ''",
        "shopify_draft": "SELECT COUNT(*) n FROM articles WHERE brand_id = ? AND status = 'approved' AND shopify_article_id IS NULL",
        "publication_approval": "SELECT COUNT(*) n FROM publish_requests WHERE brand_id = ? AND status IN ('pending','failed')",
    }.get(stage)
    return int(get(q, brand_id)["n"]) if q else 0


def pipeline(brand_id: str) -> list[dict]:
    paused = is_paused(brand_id)
    out = []
    for st in STAGES:
        last = last_run(brand_id, st["key"])
        pending = _pending(st["key"], brand_id)
        gap = _setup_gap(st["key"], brand_id)
        if gap:
            state = "pending_setup"
        elif last and last["status"] == "running":
            state = "running"
        elif last and last["status"] == "failed":
            state = "failed"
        elif paused and st["kind"] == "automated":
            state = "paused"
        elif pending > 0:
            state = "needs_action"
        elif last:
            state = "ok"
        else:
            state = "idle"
        out.append({
            **st, "state": state, "pending": pending, "setupGap": gap,
            "humanAction": HUMAN_ACTION.get(st["key"]) if pending > 0 else None,
            "lastRun": {"id": last["id"], "status": last["status"], "started_at": last["started_at"], "finished_at": last["finished_at"],
                        "message": last["message"], "error": last["error"], "trigger": last["trigger_kind"]} if last else None,
        })
    return out


# ---------------- stage runners ----------------

def _topic_research(brand_id: str, user: dict | None) -> dict:
    b, st = brand(brand_id), brand_settings(brand_id)
    titles = [r["title"] for r in all_rows("SELECT title FROM articles WHERE brand_id = ? UNION SELECT title FROM topics WHERE brand_id = ?", brand_id, brand_id)]
    products = [r["title"] for r in all_rows("SELECT title FROM products WHERE brand_id = ? LIMIT 80", brand_id)]
    queries = [r["query"] for r in all_rows("SELECT query, SUM(impressions) imp FROM gsc_query_period WHERE brand_id = ? AND source != 'demo' GROUP BY query ORDER BY imp DESC LIMIT 40", brand_id)]
    data, model = claude.research_topics(b, st, titles, products, queries, st["topicsPerRun"], st["researchFocus"])
    added = dupes = 0
    with tx():
        for t in data.get("topics", []):
            norm = norm_keyword(t["primary_keyword"])
            if not norm or get("SELECT 1 FROM topics WHERE brand_id = ? AND keyword_norm = ?", brand_id, norm):
                dupes += 1
                continue
            run("""INSERT INTO topics (brand_id, title, primary_keyword, keyword_norm, secondary_keywords, intent, rationale, status, source, created_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?, 'proposed', 'claude', ?, ?, ?)""",
                brand_id, s(t["title"], 255), s(t["primary_keyword"], 200), norm, ", ".join(t.get("secondary_keywords") or []),
                t["intent"], s(t.get("rationale"), 2000), user["id"] if user else None, now(), now())
            added += 1
    msg = f"{added} topic{'' if added == 1 else 's'} proposed" + (f", {dupes} duplicate{'' if dupes == 1 else 's'} skipped" if dupes else "")
    return {"message": msg, "details": {"model": model, "added": added, "dupes": dupes}}


def _keyword_validation(brand_id: str) -> dict:
    topics = all_rows("SELECT * FROM topics WHERE brand_id = ? AND status = 'proposed'", brand_id)
    arts = all_rows("SELECT id, title, primary_keyword FROM articles WHERE brand_id = ?", brand_id)
    validated = unsized = overlaps = 0
    with tx():
        for t in topics:
            kw = get("SELECT * FROM keywords WHERE brand_id = ? AND keyword_norm = ?", brand_id, t["keyword_norm"])
            g = get("SELECT SUM(impressions) imp, SUM(clicks) clk FROM gsc_query_period WHERE brand_id = ? AND source != 'demo' AND lower(query) = lower(?)", brand_id, t["primary_keyword"])
            clash = max(((a, max(similarity(a["title"], t["title"]), similarity(a["primary_keyword"] or a["title"], t["primary_keyword"]))) for a in arts),
                        key=lambda x: x[1], default=(None, 0.0))
            notes: list[str] = []
            vol, kd, vsrc = t["search_volume"], t["keyword_difficulty"], t["volume_source"]
            if kw and kw["search_volume"] is not None:
                vol, kd = kw["search_volume"], kw["keyword_difficulty"]
                vsrc = kw["source_tool"] + (f" · {kw['source_date']}" if kw["source_date"] else "")
                notes.append(f"Volume {kw['search_volume']}/mo from {kw['source_tool']}.")
            if g and g["imp"]:
                notes.append(f"Search Console: {g['imp']} impressions, {g['clk']} clicks in the last 28 days already.")
            overlapping = clash[0] is not None and clash[1] >= 0.5
            if overlapping:
                notes.append(f"Overlaps “{clash[0]['title']}” (similarity {round(clash[1] * 100)}%). Consider updating that article instead.")
                overlaps += 1
            sized = vol is not None or bool(g and g["imp"])
            if not sized:
                notes.append("No volume data yet: import it from your keyword tool (Data & Reports → Keywords).")
                unsized += 1
            status = "validated" if sized and not overlapping else "proposed"
            validated += status == "validated"
            run("UPDATE topics SET status=?, search_volume=?, keyword_difficulty=?, volume_source=?, validation_note=?, updated_at=? WHERE id=?",
                status, vol, kd, vsrc, " ".join(notes), now(), t["id"])
    msg = (f"{validated} of {len(topics)} validated · {unsized} need volume data · {overlaps} overlap existing articles"
           if topics else "No proposed topics to check")
    return {"message": msg, "details": {"checked": len(topics), "validated": validated, "unsized": unsized, "overlaps": overlaps},
            "status": "waiting" if topics and validated < len(topics) else "succeeded"}


def _content_generation(brand_id: str, user: dict | None, topic_id: int | None) -> dict:
    b, st = brand(brand_id), brand_settings(brand_id)
    if topic_id:
        topics = all_rows("SELECT * FROM topics WHERE id = ? AND brand_id = ? AND status = 'approved'", topic_id, brand_id)
    else:
        topics = all_rows("""SELECT * FROM topics t WHERE brand_id = ? AND status = 'approved' AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.topic_id = t.id)
                             ORDER BY COALESCE(search_volume, 0) DESC LIMIT ?""", brand_id, st["draftsPerRun"])
    if not topics:
        return {"message": "That topic is not approved yet" if topic_id else "No approved topics waiting for a draft", "status": "skipped"}
    links = all_rows("SELECT title, url FROM products WHERE brand_id = ? LIMIT 60", brand_id) + \
        all_rows("SELECT title, live_url AS url FROM articles WHERE brand_id = ? AND shopify_published = 1 AND live_url IS NOT NULL LIMIT 20", brand_id)
    created = []
    for t in topics:
        data, model = claude.generate_draft(b, st, t, links)
        a = create_article(user, brand_id, {
            "title": data["title"], "handle": data["handle"], "primary_keyword": t["primary_keyword"], "meta_title": data["meta_title"],
            "meta_description": data["meta_description"], "summary_html": data["summary_html"], "body_html": data["body_html"],
            "tags": data["tags"], "author": st["defaultAuthor"], "image_alt": data["image_alt"], "topic_id": t["id"],
        }, "claude", "draft")
        run("UPDATE topics SET status='in_production', updated_at=? WHERE id=?", now(), t["id"])
        run("UPDATE article_revisions SET note=? WHERE article_id=? AND version=1", f"First draft by Claude ({model})", a["id"])
        created.append(a["id"])
    return {"message": f"{len(created)} draft{'' if len(created) == 1 else 's'} written", "details": {"articleIds": created}}


def _image_selection(brand_id: str) -> dict:
    """Only drafts are touched: an image is part of the content, so picking one for an article under
    review or approved would void that review. Those are left for a person to choose."""
    arts = all_rows("SELECT * FROM articles WHERE brand_id = ? AND status IN ('draft','changes_requested') AND image_url = ''", brand_id)
    products = all_rows("SELECT title, url, image_url FROM products WHERE brand_id = ? AND image_url != ''", brand_id)
    if not products:
        return {"message": "No product images synced yet — run Performance tracking (Shopify sync) first", "status": "waiting"}
    picked = 0
    with tx():
        for a in arts:
            best = next((p for p in products if p["url"] in a["body_html"] or urlparse(p["url"]).path in a["body_html"]), None)
            if not best:
                scored = sorted(((p, similarity(p["title"], a["primary_keyword"] + " " + a["title"])) for p in products), key=lambda x: -x[1])
                best = scored[0][0] if scored and scored[0][1] > 0.15 else None
            if not best:
                continue
            c = {**content_of(a), "image_url": best["image_url"], "image_alt": a["image_alt"] or best["title"]}
            h, v = hash_content(c), a["version"] + 1
            run("UPDATE articles SET image_url=?, image_alt=?, content_hash=?, version=?, updated_at=? WHERE id=?", c["image_url"], c["image_alt"], h, v, now(), a["id"])
            run("INSERT INTO article_revisions (article_id, version, data_json, content_hash, user_id, note, created_at) VALUES (?,?,?,?,?,?,?)",
                a["id"], v, json.dumps(c, ensure_ascii=False), h, None, f"Featured image picked from “{best['title']}”", now())
            picked += 1
    waiting = _pending("image_selection", brand_id)
    return {"message": f"{picked} of {len(arts)} drafts given an image" + (f" · {waiting} still need one chosen by an editor" if waiting else ""),
            "details": {"picked": picked, "considered": len(arts)}, "status": "waiting" if waiting else "succeeded"}


def _shopify_drafts(brand_id: str, user: dict | None) -> dict:
    arts = all_rows("SELECT id FROM articles WHERE brand_id = ? AND status = 'approved' AND approved_hash = content_hash AND shopify_published = 0", brand_id)
    if not arts:
        return {"message": "No approved articles waiting for a Shopify draft", "status": "skipped"}
    if not user:
        raise RuntimeError("Shopify drafts are only created when a person starts this stage.")
    ok, errors = 0, []
    for a in arts:
        try:
            save_shopify_draft(user, a["id"])
            ok += 1
        except Exception as e:  # noqa: BLE001
            errors.append(getattr(e, "message", None) or str(e))
    if errors and not ok:
        raise RuntimeError(errors[0])
    return {"message": f"{ok} hidden draft{'' if ok == 1 else 's'} saved to Shopify" + (f", {len(errors)} failed" if errors else ""), "details": {"ok": ok, "errors": errors}}


def _performance_tracking(brand_id: str) -> dict:
    b = brand(brand_id)
    parts, errors = [], []

    def attempt(label: str, fn) -> None:
        try:
            fn(brand_id)
            parts.append(f"{label} ✓")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{label}: {getattr(e, 'message', None) or e}")

    attempt("Shopify", sync_shopify)
    if gsc_configured(b):
        attempt("Search Console", sync_gsc)
    else:
        parts.append("Search Console not set up")
    if ga4_configured(b):
        attempt("GA4", sync_ga4)
    else:
        parts.append("GA4 not set up")
    if errors and not any(p.endswith("✓") for p in parts):
        raise RuntimeError(" · ".join(errors))
    return {"message": " · ".join(parts + errors), "details": {"errors": errors}, "status": "failed" if errors else "succeeded"}


def run_stage(stage: str, brand_id: str, user: dict | None, trigger: str, topic_id: int | None = None, retry_of: int | None = None) -> dict:
    d = next((x for x in STAGES if x["key"] == stage), None)
    if not d:
        raise HttpError(404, "Unknown stage.")
    if d["kind"] == "human":
        raise HttpError(400, f"{d['label']} is done by a person, not run.")
    if is_paused(brand_id):
        raise HttpError(423, "Automation is paused for this brand. Resume it to run stages.", "paused")
    gap = _setup_gap(stage, brand_id)
    if gap:
        raise HttpError(412, gap, "pending_setup")
    if get("SELECT id FROM workflow_runs WHERE brand_id = ? AND stage = ? AND status = 'running'", brand_id, stage):
        raise HttpError(409, "This stage is already running.")
    if user:
        audit(user, "workflow.retry" if trigger == "retry" else "workflow.run", "stage", stage, brand_id, d["label"])
    runners = {
        "topic_research": lambda: _topic_research(brand_id, user),
        "keyword_validation": lambda: _keyword_validation(brand_id),
        "content_generation": lambda: _content_generation(brand_id, user, topic_id),
        "image_selection": lambda: _image_selection(brand_id),
        "shopify_draft": lambda: _shopify_drafts(brand_id, user),
        "performance_tracking": lambda: _performance_tracking(brand_id),
    }
    return record_run(brand_id, stage, trigger, user, runners[stage], retry_of)


def retry_run(user: dict, run_id: int) -> dict:
    r = get("SELECT * FROM workflow_runs WHERE id = ?", run_id)
    if not r:
        raise HttpError(404, "Run not found.")
    if r["status"] != "failed":
        raise HttpError(409, "Only failed runs can be retried.")
    return run_stage(r["stage"], r["brand_id"], user, "retry", retry_of=run_id)


def list_runs(brand_id: str | None, stage: str, status: str, limit: int = 100) -> list[dict]:
    where, args = [], []
    if brand_id:
        where.append("r.brand_id = ?"); args.append(brand_id)
    if stage:
        where.append("r.stage = ?"); args.append(stage)
    if status:
        where.append("r.status = ?"); args.append(status)
    return all_rows(f"""SELECT r.*, u.name AS user_name FROM workflow_runs r LEFT JOIN users u ON u.id = r.user_id
                        {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY r.id DESC LIMIT ?""", *args, min(limit, 500))


def ingest_webhook(body: dict) -> dict:
    """External agents (for example a scheduled Claude routine) report stage progress here."""
    b, stage = body.get("brand"), body.get("stage")
    if b not in ("ridhi", "cpc"):
        raise HttpError(400, "brand must be ridhi or cpc")
    if not any(x["key"] == stage for x in STAGES):
        raise HttpError(400, "unknown stage")
    status = body.get("status") if body.get("status") in ("running", "succeeded", "failed", "waiting", "skipped") else "succeeded"
    t = body.get("finished_at") or now()
    rid = run("""INSERT INTO workflow_runs (brand_id, stage, status, trigger_kind, message, error, details_json, started_at, finished_at)
                 VALUES (?,?,?,?,?,?,?,?,?)""",
              b, stage, status, "webhook", s(body.get("message"), 1000), s(body.get("error"), 2000) or None,
              json.dumps({"agent": s(body.get("agent"), 120), "externalId": s(body.get("external_id"), 200)}),
              body.get("started_at") or t, None if status == "running" else t).last_id
    audit(None, "workflow.webhook", "stage", stage, b, f"{status}: {s(body.get('message'), 200)}")
    return {"id": rid}


def automation_configured() -> dict:
    return {"claude": claude.configured(), "webhook": bool(config.workflow_webhook_secret)}
