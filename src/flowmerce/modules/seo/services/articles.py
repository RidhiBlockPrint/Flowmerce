"""The article lifecycle on the dashboard side.

  idea → draft → in_review → approved → publish_requested → scheduled / published
                   ↘ changes_requested ↗                ↘ failed (retry from Publishing)

Rules enforced here, not in the browser:
 - Every save that changes content bumps the version and stores a full revision snapshot.
 - Approval is tied to a content hash. Editing approved content drops it back to draft and cancels
   pending publish requests, so changed text can never ride on an old approval.
 - A reviewer approves a specific version; if the text changed while they read, the approval is refused.
 - Whether an article is live is tracked separately (shopify_published, live_hash)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..audit import audit
from ..db import Row, all_rows, get, now, run, tx
from ..util import HttpError, s, sanitize_html, sha256, slugify

ARTICLE_STATUSES = ["idea", "draft", "in_review", "changes_requested", "approved", "publish_requested", "scheduled", "published", "failed"]
CONTENT_FIELDS = ["title", "handle", "primary_keyword", "meta_title", "meta_description", "summary_html", "body_html", "tags", "author", "image_url", "image_alt"]
APPROVAL_BOUND = {"approved", "publish_requested", "scheduled", "published"}


def content_of(a: Row) -> dict[str, str]:
    return {f: str(a.get(f) or "") for f in CONTENT_FIELDS}


def hash_content(c: dict[str, str]) -> str:
    return sha256(json.dumps([c.get(f, "") or "" for f in CONTENT_FIELDS], separators=(",", ":"), ensure_ascii=False))


def next_action(a: Row) -> dict:
    st = a["status"]
    live = bool(a.get("shopify_published"))
    if st == "idea":
        return {"role": "seo_manager", "label": "Write the first draft"}
    if st == "draft":
        return {"role": "seo_manager", "label": "Finish edits, then send for review" if live else "Finish and send for review"}
    if st == "changes_requested":
        return {"role": "seo_manager", "label": "Address reviewer feedback"}
    if st == "in_review":
        return {"role": "reviewer", "label": "Review content"}
    if st == "approved":
        return {"role": "seo_manager", "label": "Request update of the live article" if live else "Save Shopify draft or request publishing"}
    if st == "publish_requested":
        return {"role": "reviewer", "label": "Authorize publishing"}
    if st == "scheduled":
        when = ""
        if a.get("publish_at"):
            when = datetime.fromisoformat(a["publish_at"].replace("Z", "+00:00")).strftime("%d %b %H:%M UTC")
        return {"role": "", "label": f"Goes live {when}" if when else "Goes live at the scheduled time"}
    if st == "failed":
        return {"role": "seo_manager", "label": "Check the error and retry"}
    if st == "published":
        return {"role": "seo_manager", "label": "Track performance"}
    return {"role": "", "label": ""}


def decorate(a: Row) -> Row:
    return {
        **a,
        "shopify_published": bool(a.get("shopify_published")),
        "has_shopify_draft": bool(a.get("shopify_article_id")) and not a.get("shopify_published"),
        "live_differs": bool(a.get("shopify_published")) and bool(a.get("live_hash")) and a.get("live_hash") != a.get("content_hash"),
        "approval_current": bool(a.get("approved_hash")) and a.get("approved_hash") == a.get("content_hash"),
        "next_action": next_action(a),
    }


def _unique_handle(brand_id: str, wanted: str, except_id: int | None = None) -> str:
    base = slugify(wanted) or "article"
    h = base
    for i in range(2, 200):
        if not get("SELECT id FROM articles WHERE brand_id = ? AND handle = ? AND id IS NOT ?", brand_id, h, except_id):
            return h
        h = f"{base}-{i}"
    raise HttpError(409, "Could not find a free URL handle.")


def _clean(inp: dict, base: dict[str, str]) -> dict[str, str]:
    c = dict(base)
    if "title" in inp:
        c["title"] = s(inp["title"], 255).strip()
    if "handle" in inp:
        c["handle"] = slugify(s(inp["handle"], 255))
    if "primary_keyword" in inp:
        c["primary_keyword"] = s(inp["primary_keyword"], 200).strip()
    if "meta_title" in inp:
        c["meta_title"] = s(inp["meta_title"], 120).strip()
    if "meta_description" in inp:
        c["meta_description"] = s(inp["meta_description"], 400).strip()
    if "summary_html" in inp:
        c["summary_html"] = sanitize_html(s(inp["summary_html"], 5000))
    if "body_html" in inp:
        c["body_html"] = sanitize_html(s(inp["body_html"], 400000))
    if "tags" in inp:
        lst = inp["tags"] if isinstance(inp["tags"], list) else s(inp["tags"], 2000).split(",")
        seen: list[str] = []
        for t in (str(x).strip() for x in lst):
            if t and t not in seen:
                seen.append(t)
        c["tags"] = ", ".join(seen[:30])
    if "author" in inp:
        c["author"] = s(inp["author"], 120).strip()
    if "image_url" in inp:
        u = s(inp["image_url"], 2000).strip()
        if u and not u.lower().startswith("https://"):
            raise HttpError(400, "Image URL must start with https://")
        c["image_url"] = u
    if "image_alt" in inp:
        c["image_alt"] = s(inp["image_alt"], 300).strip()
    return c


def snapshot(article_id: int, version: int, c: dict, user_id: int | None, note: str) -> None:
    run("INSERT INTO article_revisions (article_id, version, data_json, content_hash, user_id, note, created_at) VALUES (?,?,?,?,?,?,?)",
        article_id, version, json.dumps(c, ensure_ascii=False), hash_content(c), user_id, note, now())


def get_article(aid: int) -> Row:
    a = get("SELECT * FROM articles WHERE id = ?", aid)
    if not a:
        raise HttpError(404, "Article not found.")
    return a


def create_article(user: dict | None, brand_id: str, inp: dict, origin: str = "app", status: str = "draft") -> Row:
    c = _clean(inp, {f: "" for f in CONTENT_FIELDS})
    if not c["title"]:
        raise HttpError(400, "A title is required.")
    c["handle"] = _unique_handle(brand_id, c["handle"] or c["title"])
    h = hash_content(c)
    t = now()
    with tx():
        r = run(
            f"""INSERT INTO articles (brand_id, topic_id, {', '.join(CONTENT_FIELDS)}, status, version, content_hash, origin, assignee_id, created_by, created_at, updated_at)
                VALUES (?, ?, {', '.join('?' for _ in CONTENT_FIELDS)}, ?, 1, ?, ?, ?, ?, ?, ?)""",
            brand_id, int(inp["topic_id"]) if inp.get("topic_id") else None, *[c[f] for f in CONTENT_FIELDS],
            status, h, origin, int(inp["assignee_id"]) if inp.get("assignee_id") else None, user["id"] if user else None, t, t,
        )
        snapshot(r.last_id, 1, c, user["id"] if user else None, "Created" if origin == "app" else f"Imported ({origin})")
        audit(user, "article.create", "article", r.last_id, brand_id, c["title"], {"origin": origin})
        return get_article(r.last_id)


def save_article(user: dict, aid: int, inp: dict, note: str = "") -> Row:
    with tx():
        a = get_article(aid)
        if inp.get("expected_version") is not None and int(inp["expected_version"]) != a["version"]:
            raise HttpError(409, f"Someone saved version {a['version']} while you were editing. Reload to see their changes before saving.", "version_conflict")
        if a["status"] == "scheduled":
            raise HttpError(409, "This article is scheduled on Shopify. Cancel the schedule from Publishing before editing.", "scheduled")
        before = content_of(a)
        c = _clean(inp, before)
        if not c["title"]:
            raise HttpError(400, "A title is required.")
        if c["handle"] != before["handle"]:
            if a["shopify_published"]:
                raise HttpError(409, "The URL handle of a live article cannot change here; it would break the published link.")
            c["handle"] = _unique_handle(a["brand_id"], c["handle"] or c["title"], a["id"])
        meta: list[str] = []
        if "assignee_id" in inp:
            run("UPDATE articles SET assignee_id = ? WHERE id = ?", int(inp["assignee_id"]) if inp["assignee_id"] else None, aid)
            meta.append("assignee")
        if "topic_id" in inp:
            run("UPDATE articles SET topic_id = ? WHERE id = ?", int(inp["topic_id"]) if inp["topic_id"] else None, aid)
            meta.append("topic")
        h = hash_content(c)
        if h == a["content_hash"]:
            if meta:
                audit(user, "article.update_meta", "article", aid, a["brand_id"], ", ".join(meta))
            return get_article(aid)

        status = a["status"]
        cancelled = 0
        if status in APPROVAL_BOUND or status in ("in_review", "failed"):
            # Changed text never keeps an earlier approval or an open review.
            status = "draft"
            cancelled = run("""UPDATE publish_requests SET status='cancelled', decision_note='Content changed after the request', decided_at=?
                               WHERE article_id = ? AND status IN ('pending','failed')""", now(), aid).changes
        if a["status"] == "idea" and c["body_html"]:
            status = "draft"
        version = a["version"] + 1
        changed = [f for f in CONTENT_FIELDS if c[f] != before[f]]
        run(f"UPDATE articles SET {', '.join(f + ' = ?' for f in CONTENT_FIELDS)}, content_hash = ?, version = ?, status = ?, updated_at = ? WHERE id = ?",
            *[c[f] for f in CONTENT_FIELDS], h, version, status, now(), aid)
        snapshot(aid, version, c, user["id"], note or f"Edited {', '.join(changed)}")
        audit(user, "article.edit", "article", aid, a["brand_id"], f"v{version}: {', '.join(changed)}",
              {"fields": changed, "statusBefore": a["status"], "statusAfter": status, "cancelledRequests": cancelled})
        return get_article(aid)


def submit_for_review(user: dict, aid: int) -> Row:
    a = get_article(aid)
    if a["status"] not in ("draft", "changes_requested", "idea", "failed"):
        raise HttpError(409, f'An article that is "{a["status"].replace("_", " ")}" cannot be sent for review.')
    missing = [n for n, f in (("body", "body_html"), ("meta description", "meta_description"), ("primary keyword", "primary_keyword")) if not a[f].strip()]
    if missing:
        raise HttpError(400, f"Add the {', '.join(missing)} before sending for review.")
    run("UPDATE articles SET status = 'in_review', updated_at = ? WHERE id = ?", now(), aid)
    run("INSERT INTO review_notes (article_id, user_id, reviewer_name, kind, note, version, created_at) VALUES (?,?,?,?,?,?,?)",
        aid, user["id"], user["name"], "submitted", "", a["version"], now())
    audit(user, "article.submit", "article", aid, a["brand_id"], f"v{a['version']} sent for review")
    return get_article(aid)


def review_article(user: dict, aid: int, decision: str, version: Any, note: str) -> Row:
    with tx():
        a = get_article(aid)
        if a["status"] != "in_review":
            raise HttpError(409, "This article is not waiting for review.")
        try:
            v = int(version)
        except (TypeError, ValueError):
            v = -1
        if v != a["version"]:
            raise HttpError(409, f"The content changed to version {a['version']} after you opened it. Reload and review the current text.", "version_conflict")
        if decision == "approve":
            run("UPDATE articles SET status='approved', approved_hash=?, approved_by=?, approved_at=?, review_note=?, updated_at=? WHERE id=?",
                a["content_hash"], user["id"], now(), s(note, 2000), now(), aid)
        elif decision == "request_changes":
            if not str(note or "").strip():
                raise HttpError(400, "Say what needs to change.")
            run("UPDATE articles SET status='changes_requested', approved_hash=NULL, review_note=?, updated_at=? WHERE id=?", s(note, 2000), now(), aid)
        else:
            raise HttpError(400, "Decision must be approve or request_changes.")
        run("INSERT INTO review_notes (article_id, user_id, reviewer_name, kind, note, version, created_at) VALUES (?,?,?,?,?,?,?)",
            aid, user["id"], user["name"], "approved" if decision == "approve" else "changes_requested", s(note, 2000), a["version"], now())
        audit(user, "article.approve" if decision == "approve" else "article.request_changes", "article", aid, a["brand_id"],
              f"v{a['version']}" + (f": {s(note, 140)}" if note else ""))
        return get_article(aid)


def restore_revision(user: dict, aid: int, rev_id: int) -> Row:
    rev = get("SELECT * FROM article_revisions WHERE id = ? AND article_id = ?", rev_id, aid)
    if not rev:
        raise HttpError(404, "Revision not found.")
    return save_article(user, aid, json.loads(rev["data_json"]), f"Restored version {rev['version']}")


def list_revisions(aid: int) -> list[Row]:
    return all_rows("""SELECT r.id, r.version, r.content_hash, r.note, r.created_at, u.name AS user_name
                       FROM article_revisions r LEFT JOIN users u ON u.id = r.user_id WHERE r.article_id = ? ORDER BY r.version DESC""", aid)


SORT_COLS = {"updated": "a.updated_at", "title": "a.title COLLATE NOCASE", "status": "a.status", "published": "a.published_at", "created": "a.created_at"}


def list_articles(brand: str | None, status: str, q: str, sort: str, direction: str, live: str, assignee: str, limit: int, offset: int) -> dict:
    where: list[str] = []
    params: list[Any] = []
    if brand:
        where.append("a.brand_id = ?"); params.append(brand)
    if status:
        lst = [x for x in status.split(",") if x in ARTICLE_STATUSES]
        if lst:
            where.append(f"a.status IN ({','.join('?' for _ in lst)})"); params += lst
    if live == "1":
        where.append("a.shopify_published = 1")
    if live == "0":
        where.append("a.shopify_published = 0")
    if assignee:
        where.append("a.assignee_id = ?"); params.append(int(assignee))
    if q:
        like = "%" + q.replace("%", "").replace("_", "") + "%"
        where.append("(a.title LIKE ? OR a.primary_keyword LIKE ? OR a.handle LIKE ? OR a.tags LIKE ?)"); params += [like] * 4
    order = f"{SORT_COLS.get(sort or 'updated', 'a.updated_at')} {'ASC' if direction == 'asc' else 'DESC'}"
    frm = f"FROM articles a LEFT JOIN users u ON u.id = a.assignee_id {'WHERE ' + ' AND '.join(where) if where else ''}"
    total = get(f"SELECT COUNT(*) AS n {frm}", *params)["n"]
    rows = all_rows(f"""SELECT a.id, a.brand_id, a.title, a.handle, a.primary_keyword, a.status, a.version, a.shopify_published, a.shopify_article_id,
                               a.live_hash, a.content_hash, a.approved_hash, a.published_at, a.publish_at, a.updated_at, a.created_at, a.origin, a.live_url,
                               a.meta_description, a.assignee_id, u.name AS assignee_name, a.last_error
                        {frm} ORDER BY {order} LIMIT ? OFFSET ?""", *params, min(limit or 50, 500), offset or 0)
    return {"total": total, "rows": [decorate(r) for r in rows]}


def status_counts(brand: str | None) -> list[Row]:
    if brand:
        return all_rows("SELECT brand_id, status, COUNT(*) AS n, SUM(shopify_published) AS live FROM articles WHERE brand_id = ? GROUP BY brand_id, status", brand)
    return all_rows("SELECT brand_id, status, COUNT(*) AS n, SUM(shopify_published) AS live FROM articles GROUP BY brand_id, status")
