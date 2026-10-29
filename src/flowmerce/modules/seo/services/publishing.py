"""Shopify drafts and live publishing — the only code path that can change a storefront.

Making an article visible requires, all checked here on the server:
  1. content approved by a reviewer, and unchanged since (content hash);
  2. a pending publish request for that same hash;
  3. a different person with publish:authorize approving it (admins may approve their own);
  4. the typed confirmation phrase PUBLISH;
  5. ALLOW_LIVE_PUBLISH=true in the server environment — off by default.
Hidden drafts (isPublished: false) skip 2–5 but never touch a live article."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..audit import audit
from ..config import config
from ..db import Row, all_rows, get, now, run, tx
from ..integrations import shopify
from ..util import HttpError, parse_iso, s
from .articles import get_article
from .brands import brand

CONFIRM_PHRASE = "PUBLISH"


def _to_write(a: Row) -> dict:
    return {
        "title": a["title"], "handle": a["handle"], "body": a["body_html"], "summary": a["summary_html"],
        "tags": [t.strip() for t in (a["tags"] or "").split(",") if t.strip()], "author": a["author"],
        "image_url": a["image_url"] or None, "image_alt": a["image_alt"] or None,
        "meta_title": a["meta_title"] or None, "meta_description": a["meta_description"] or None,
    }


def _blog_id_for(a: Row) -> str:
    if a.get("shopify_blog_id"):
        return a["shopify_blog_id"]
    blog = shopify.find_blog(brand(a["brand_id"]))
    run("UPDATE articles SET shopify_blog_id = ? WHERE brand_id = ? AND shopify_blog_id IS NULL", blog["id"], a["brand_id"])
    return blog["id"]


def _adopt_existing(a: Row, blog_id: str) -> str | None:
    """Find an article with this handle already on Shopify, so a retry after a lost response updates it
    instead of creating a duplicate."""
    if a.get("shopify_article_id"):
        return a["shopify_article_id"]
    hit = next((x for x in shopify.list_articles(brand(a["brand_id"]), blog_id) if x["handle"] == a["handle"]), None)
    if hit:
        run("UPDATE articles SET shopify_article_id = ? WHERE id = ?", hit["id"], a["id"])
    return hit["id"] if hit else None


def save_shopify_draft(user: dict, aid: int) -> Row:
    a = get_article(aid)
    b = brand(a["brand_id"])
    if not shopify.configured(b):
        raise HttpError(412, f"Shopify Admin API is not set up for {b.name}. See Integrations.", "pending_setup")
    if a["shopify_published"]:
        raise HttpError(409, "This article is live. Changes to a live article go through a publish request.", "live_article")
    if not a["body_html"].strip():
        raise HttpError(400, "Write the article body before saving it to Shopify.")
    try:
        blog_id = _blog_id_for(a)
        existing = _adopt_existing(a, blog_id)
        res = shopify.update_hidden_draft(b, existing, _to_write(a)) if existing else shopify.create_hidden_draft(b, blog_id, _to_write(a))
        if res["isPublished"]:
            raise RuntimeError("Shopify reports the article as published after a draft save. Check it in Shopify admin.")
        run("UPDATE articles SET shopify_article_id=?, shopify_blog_id=?, shopify_synced_at=?, last_error=NULL WHERE id=?", res["id"], blog_id, now(), aid)
        audit(user, "shopify.draft_update" if existing else "shopify.draft_create", "article", aid, a["brand_id"],
              f"{a['title']} (hidden, v{a['version']})", {"shopifyId": res["id"]})
        return get_article(aid)
    except Exception as e:
        msg = getattr(e, "message", None) or str(e)
        run("UPDATE articles SET last_error=? WHERE id=?", msg[:1000], aid)
        audit(user, "shopify.draft_failed", "article", aid, a["brand_id"], msg[:300])
        raise


def request_publish(user: dict, aid: int, mode: str, publish_at: str | None, note: str) -> Row:
    with tx():
        a = get_article(aid)
        if mode not in ("publish_now", "schedule", "update_live"):
            raise HttpError(400, "Unknown publishing mode.")
        if a["status"] != "approved" or a["approved_hash"] != a["content_hash"]:
            raise HttpError(409, "Only reviewer-approved content can be put forward for publishing. Send it for review first.")
        if a["shopify_published"] and mode != "update_live":
            raise HttpError(409, 'This article is already live; choose "Update live article".')
        if not a["shopify_published"] and mode == "update_live":
            raise HttpError(409, "This article is not live yet; choose publish now or schedule.")
        when = None
        if mode == "schedule":
            try:
                t = parse_iso(str(publish_at or ""))
            except ValueError:
                raise HttpError(400, "Pick a date and time to schedule.")
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if t < datetime.now(timezone.utc) + timedelta(minutes=10):
                raise HttpError(400, "Schedule at least 10 minutes ahead.")
            when = t.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        run("UPDATE publish_requests SET status='cancelled', decision_note='Replaced by a newer request', decided_at=? WHERE article_id=? AND status='pending'", now(), aid)
        r = run("""INSERT INTO publish_requests (article_id, brand_id, mode, publish_at, content_hash, version, status, requested_by, requested_at, note)
                   VALUES (?,?,?,?,?,?, 'pending', ?,?,?)""", aid, a["brand_id"], mode, when, a["content_hash"], a["version"], user["id"], now(), s(note, 2000))
        run("UPDATE articles SET status='publish_requested', publish_at=?, updated_at=? WHERE id=?", when, now(), aid)
        audit(user, "publish.request", "publish_request", r.last_id, a["brand_id"],
              f"{a['title']} — {mode.replace('_', ' ')}" + (f" at {when}" if when else ""), {"articleId": aid, "version": a["version"]})
        return get("SELECT * FROM publish_requests WHERE id = ?", r.last_id)  # type: ignore[return-value]


def _load_request(rid: int) -> Row:
    r = get("SELECT * FROM publish_requests WHERE id = ?", rid)
    if not r:
        raise HttpError(404, "Publish request not found.")
    return r


def _preflight(user: dict, req: Row, confirm: object) -> Row:
    if str(confirm or "").strip() != CONFIRM_PHRASE:
        raise HttpError(400, f"Type {CONFIRM_PHRASE} to confirm.", "confirmation_required")
    if req["requested_by"] == user["id"] and user["role"] != "admin":
        raise HttpError(403, "Someone other than the requester must authorize publishing.", "separation_of_duties")
    a = get_article(req["article_id"])
    if a["content_hash"] != req["content_hash"] or a["approved_hash"] != req["content_hash"]:
        run("UPDATE publish_requests SET status='cancelled', decision_note='Content changed after the request', decided_at=? WHERE id=?", now(), req["id"])
        raise HttpError(409, "The article changed after this request was made. It needs a new review and request.", "stale_request")
    if not config.allow_live_publish:
        raise HttpError(423, "Live publishing is switched off on this server (ALLOW_LIVE_PUBLISH is not set). Nothing was sent to Shopify.", "publishing_disabled")
    if not shopify.configured(brand(a["brand_id"])):
        raise HttpError(412, "Shopify Admin API is not set up for this brand.", "pending_setup")
    if req["mode"] == "schedule" and parse_iso(req["publish_at"]) < datetime.now(timezone.utc) + timedelta(minutes=1):
        raise HttpError(409, "The scheduled time has passed. Ask for a new schedule.", "schedule_passed")
    return a


def _execute(user: dict, req: Row, a: Row) -> dict:
    b = brand(a["brand_id"])
    run("UPDATE publish_requests SET attempts = attempts + 1 WHERE id = ?", req["id"])
    try:
        blog_id = _blog_id_for(a)
        existing = _adopt_existing(a, blog_id)
        scheduled = req["mode"] == "schedule"
        res = shopify.publish_article(b, blog_id, existing, _to_write(a), req["publish_at"] if scheduled else None)
        t = now()
        run("""UPDATE articles SET status=?, shopify_article_id=?, shopify_blog_id=?, shopify_published=1, live_hash=?, live_url=?,
                 published_at=?, publish_at=?, shopify_synced_at=?, last_error=NULL, updated_at=? WHERE id=?""",
            "scheduled" if scheduled else "published", res["id"], blog_id, a["content_hash"],
            f"https://{b.storefront_domain}/blogs/{b.blog_handle}/{res['handle']}",
            res.get("publishedAt") or (req["publish_at"] if scheduled else t), req["publish_at"] if scheduled else None, t, t, a["id"])
        run("UPDATE publish_requests SET status='executed', executed_at=?, error=NULL WHERE id=?", t, req["id"])
        action = "publish.scheduled" if scheduled else "publish.update_live" if req["mode"] == "update_live" else "publish.live"
        audit(user, action, "article", a["id"], a["brand_id"], f"{a['title']} (v{a['version']})", {"requestId": req["id"], "shopifyId": res["id"]})
        return {"ok": True, "article": get_article(a["id"])}
    except Exception as e:
        msg = getattr(e, "message", None) or str(e)
        run("UPDATE publish_requests SET status='failed', error=? WHERE id=?", msg[:2000], req["id"])
        run("UPDATE articles SET status='failed', last_error=?, updated_at=? WHERE id=?", msg[:1000], now(), a["id"])
        audit(user, "publish.failed", "article", a["id"], a["brand_id"], msg[:300], {"requestId": req["id"]})
        raise HttpError(502, f"Shopify did not accept the publish: {msg}", "publish_failed")


def authorize_request(user: dict, rid: int, confirm: object, note: str) -> dict:
    req = _load_request(rid)
    if req["status"] != "pending":
        raise HttpError(409, f"This request is already {req['status']}.")
    a = _preflight(user, req, confirm)
    run("UPDATE publish_requests SET status='approved', decided_by=?, decided_at=?, decision_note=? WHERE id=?", user["id"], now(), s(note, 2000), rid)
    audit(user, "publish.authorize", "publish_request", rid, a["brand_id"], a["title"])
    return _execute(user, {**req, "status": "approved"}, a)


def retry_request(user: dict, rid: int, confirm: object) -> dict:
    req = _load_request(rid)
    if req["status"] != "failed":
        raise HttpError(409, "Only failed publishes can be retried.")
    a = _preflight(user, req, confirm)
    audit(user, "publish.retry", "publish_request", rid, a["brand_id"], a["title"])
    return _execute(user, req, a)


def reject_request(user: dict, rid: int, note: str) -> None:
    req = _load_request(rid)
    if req["status"] not in ("pending", "failed"):
        raise HttpError(409, f"This request is already {req['status']}.")
    if not str(note or "").strip():
        raise HttpError(400, "Give a reason for rejecting.")
    with tx():
        run("UPDATE publish_requests SET status='rejected', decided_by=?, decided_at=?, decision_note=? WHERE id=?", user["id"], now(), s(note, 2000), rid)
        run("UPDATE articles SET status='approved', publish_at=NULL, updated_at=? WHERE id=? AND status IN ('publish_requested','failed')", now(), req["article_id"])
    audit(user, "publish.reject", "publish_request", rid, req["brand_id"], s(note, 200))


def cancel_request(user: dict, rid: int) -> None:
    req = _load_request(rid)
    if req["status"] not in ("pending", "failed"):
        raise HttpError(409, f"This request is already {req['status']}.")
    if req["requested_by"] != user["id"] and user["role"] != "admin":
        raise HttpError(403, "Only the requester or an admin can withdraw a request.")
    with tx():
        run("UPDATE publish_requests SET status='cancelled', decided_by=?, decided_at=?, decision_note='Withdrawn' WHERE id=?", user["id"], now(), rid)
        run("UPDATE articles SET status='approved', publish_at=NULL, updated_at=? WHERE id=? AND status IN ('publish_requested','failed')", now(), req["article_id"])
    audit(user, "publish.cancel", "publish_request", rid, req["brand_id"])


def publishing_queue(brand_id: str | None) -> dict:
    bw = "AND r.brand_id = ?" if brand_id else ""
    aw = "AND brand_id = ?" if brand_id else ""
    args = [brand_id] if brand_id else []
    requests = [{**r, "stale": r["article_hash"] != r["content_hash"]} for r in all_rows(
        f"""SELECT r.*, a.title, a.handle, a.version AS article_version, a.content_hash AS article_hash, a.shopify_published,
                   ru.name AS requested_by_name, du.name AS decided_by_name
            FROM publish_requests r JOIN articles a ON a.id = r.article_id
            LEFT JOIN users ru ON ru.id = r.requested_by LEFT JOIN users du ON du.id = r.decided_by
            WHERE 1=1 {bw} ORDER BY CASE r.status WHEN 'pending' THEN 0 WHEN 'failed' THEN 1 ELSE 2 END, r.requested_at DESC LIMIT 200""", *args)]
    return {
        "requests": requests,
        "scheduled": all_rows(f"SELECT id, brand_id, title, publish_at, live_url FROM articles WHERE status = 'scheduled' {aw} ORDER BY publish_at", *args),
        "drafts": all_rows(f"SELECT id, brand_id, title, status, version, shopify_synced_at, updated_at FROM articles WHERE shopify_article_id IS NOT NULL AND shopify_published = 0 {aw} ORDER BY updated_at DESC", *args),
        "readyForRequest": all_rows(f"SELECT id, brand_id, title, version, approved_at, shopify_published FROM articles WHERE status = 'approved' AND approved_hash = content_hash {aw} ORDER BY approved_at DESC", *args),
        "livePublishingEnabled": config.allow_live_publish,
        "confirmPhrase": CONFIRM_PHRASE,
    }
