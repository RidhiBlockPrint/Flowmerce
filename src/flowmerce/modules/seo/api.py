"""HTTP API under /api. Every handler starts with require_perm()/require_user(), so permissions hold
no matter what the browser shows or hides. Handlers are plain `def` functions: FastAPI runs them in a
worker thread, so slow calls to Shopify, Google or Claude never block other requests."""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Body, Request, Response
from starlette.concurrency import run_in_threadpool

from . import auth
from .audit import audit
from .config import BRAND_IDS, config, is_brand
from .db import all_rows, get, now, run
from .integrations import claude, shopify
from .integrations.google import ga4_configured, ga4_report, gsc_configured, gsc_query, service_account_email
from .integrations.shopify_public import fetch_public_articles
from .integrations.status import all_statuses, mark_error, mark_success
from .permissions import PERMISSIONS, ROLE_LABELS, is_role, perms_for
from .services import analytics, articles, excel, home, keyword_file, publishing, workflow
from .services.brands import all_brands, brand, brand_public, update_brand_settings
from .services.demo import clear_demo, demo_loaded, load_demo
from .services.sync import products_for, sync_ga4, sync_gsc, sync_shopify
from .util import HttpError, add_days, days_between, norm_keyword, s, safe_json, today

api = APIRouter(prefix="/api")
JSONBody = Body(default_factory=dict)

# ---------------- helpers ----------------

def q(request: Request, k: str) -> str:
    return request.query_params.get(k, "") or ""


def brand_q(request: Request) -> str | None:
    b = q(request, "brand")
    if not b or b == "all":
        return None
    if not is_brand(b):
        raise HttpError(400, "Unknown brand.")
    return b


def brand_param(v: Any) -> str:
    if not is_brand(v):
        raise HttpError(400, "Unknown brand.")
    return v


def brands_for(request: Request) -> list[str]:
    b = brand_q(request)
    return [b] if b else list(BRAND_IDS)


def date_range(request: Request) -> tuple[str, str]:
    """Default window: the 28 days ending 3 days ago, when Search Console data is final."""
    is_day = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    to = q(request, "to") if is_day.match(q(request, "to")) else add_days(today(), -3)
    frm = q(request, "from") if is_day.match(q(request, "from")) else add_days(to, -27)
    if frm > to:
        raise HttpError(400, "The start date is after the end date.")
    if days_between(frm, to) > 500:
        raise HttpError(400, "Choose a range of 16 months or less.")
    return frm, to


def to_int(v: Any) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise HttpError(400, "Bad id.")
    if n <= 0:
        raise HttpError(400, "Bad id.")
    return n


def ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ---------------- auth ----------------

@api.post("/auth/login")
def login(body: dict = JSONBody):
    """Obsolete in local operator mode: nothing is verified, no session is created, no user record is read."""
    raise HttpError(410, "Sign-in is turned off: Flowmerce runs in local operator mode on this computer.", "login_disabled")


@api.post("/auth/logout")
def logout(response: Response):
    """Harmless: there is no session to end. It only clears a leftover cookie from before local operator
    mode; no session record is deleted and nothing is written to the audit log."""
    response.delete_cookie(auth.COOKIE, path="/", httponly=True, samesite="strict", secure=config.cookie_secure)
    return {"ok": True}


@api.get("/auth/me")
def me(request: Request):
    """The local operator: the administrator record every local request acts as, with its permissions."""
    u = auth.require_user(request)
    return {"user": {**u, "roleLabel": ROLE_LABELS[u["role"]]}, "permissions": perms_for(u["role"]), "brands": all_brands(),
            "livePublishing": config.allow_live_publish, "demoLoaded": demo_loaded(), "localOperator": True}


@api.post("/auth/password")
def change_password(body: dict = JSONBody):
    """Obsolete in local operator mode: passwords no longer protect anything, so none is verified or changed."""
    raise HttpError(410, "Password changes are turned off: Flowmerce runs in local operator mode on this computer.", "password_disabled")


# ---------------- brands ----------------

@api.get("/brands")
def brands(request: Request):
    auth.require_perm(request, "view")
    return all_brands()


@api.patch("/brands/{bid}")
def patch_brand(bid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "integrations:manage")
    b = brand_param(bid)
    st = update_brand_settings(b, body, u["id"])
    audit(u, "brand.settings", "brand", b, b, details=body)
    return {**brand_public(b), "settings": st}


@api.get("/brands/{bid}/products")
def brand_products(bid: str, request: Request):
    auth.require_perm(request, "view")
    return products_for(brand_param(bid))


# ---------------- overview & tasks ----------------

STATES = ["idea", "draft", "changes_requested", "in_review", "approved", "publish_requested", "scheduled", "published", "failed"]


def _label_for(key: str) -> str:
    return {"shopify": "Shopify Admin API", "shopify_public": "Shopify public feed", "gsc": "Search Console", "ga4": "GA4",
            "claude": "Claude", "workflow_webhook": "Workflow webhook"}.get(key, key)


def _alerts(brands_: list[str]) -> list[dict]:
    out: list[dict] = []
    for st in all_statuses():
        if st["brand_id"] and st["brand_id"] not in brands_:
            continue
        if st["status"] == "error":
            out.append({"level": "critical", "title": f"{_label_for(st['key'])} sync failing" + (f" · {brand(st['brand_id']).short}" if st["brand_id"] else ""),
                        "detail": st["last_error"] or "Unknown error", "link": "/integrations"})
    for b in brands_:
        for stg in workflow.pipeline(b):
            if stg["state"] == "failed":
                out.append({"level": "critical", "title": f"{stg['label']} failed · {brand(b).short}", "detail": (stg["lastRun"] or {}).get("error") or "", "link": f"/automation?brand={b}"})
        failed = get("SELECT COUNT(*) n FROM publish_requests WHERE brand_id = ? AND status = 'failed'", b)["n"]
        if failed:
            out.append({"level": "critical", "title": f"{failed} publish attempt{'s' if failed > 1 else ''} failed · {brand(b).short}",
                        "detail": "Open Publishing to see the Shopify error and retry.", "link": "/publishing"})
        if workflow.is_paused(b):
            out.append({"level": "info", "title": f"Automation paused · {brand(b).short}",
                        "detail": (get("SELECT reason FROM automation_state WHERE brand_id = ?", b) or {}).get("reason") or "No reason given", "link": f"/automation?brand={b}"})
    pending = get("SELECT COUNT(*) n FROM publish_requests WHERE status = 'pending'")["n"]
    if pending and not config.allow_live_publish:
        out.append({"level": "warning", "title": "Live publishing is switched off on this server",
                    "detail": f"{pending} request{'s' if pending > 1 else ''} waiting. An admin must set ALLOW_LIVE_PUBLISH=true before anything can go live.", "link": "/publishing"})
    if demo_loaded():
        out.append({"level": "warning", "title": "Demo analytics fixtures are loaded",
                    "detail": 'Charts labelled "Demo" are synthetic. Clear them in Data & reports once real data is connected.', "link": "/data"})
    for f in [f for f in excel.data_health()["flags"] if f["severity"] == "warning"][:4]:
        out.append({"level": "warning", "title": f"{f['count']} {f['message']}", "detail": f["area"], "link": f.get("link")})
    return out


@api.get("/overview")
def overview(request: Request):
    auth.require_perm(request, "view")
    frm, to = date_range(request)
    bl = brands_for(request)
    per = []
    for b in bl:
        counts = {st: 0 for st in STATES}
        for r in all_rows("SELECT status, COUNT(*) n FROM articles WHERE brand_id = ? GROUP BY status", b):
            counts[r["status"]] = r["n"]
        live = get("SELECT COUNT(*) n FROM articles WHERE brand_id = ? AND shopify_published = 1", b)["n"]
        pend = get("SELECT COUNT(*) n FROM publish_requests WHERE brand_id = ? AND status = 'pending'", b)["n"]
        stages = workflow.pipeline(b)
        g, a = analytics.gsc_report(b, frm, to), analytics.ga4_report(b, frm, to)
        per.append({
            "brand": b,
            "counts": {**counts, "total": sum(counts.values()), "live": live, "drafts": counts["idea"] + counts["draft"] + counts["changes_requested"]},
            "pendingApprovals": counts["in_review"] + pend,
            "failedWorkflows": sum(1 for x in stages if x["state"] == "failed"),
            "paused": workflow.is_paused(b),
            "stages": [{"key": x["key"], "label": x["label"], "state": x["state"], "pending": x["pending"]} for x in stages],
            "gsc": {"source": g["source"], "totals": g["totals"], "previous": g["previous"], "series": g["series"], "top": g["pages"][:5]},
            "ga4": {"source": a["source"], "totals": a["totals"], "previous": a["previous"], "series": a["series"]},
        })
    if len(bl) == 1:
        activity = all_rows("SELECT id, ts, user_email, action, entity_type, entity_id, brand_id, summary FROM audit_log WHERE brand_id = ? ORDER BY id DESC LIMIT 14", bl[0])
    else:
        activity = all_rows("SELECT id, ts, user_email, action, entity_type, entity_id, brand_id, summary FROM audit_log ORDER BY id DESC LIMIT 14")
    return {"range": {"from": frm, "to": to}, "brands": per, "activity": activity, "integrations": _integration_list(), "alerts": _alerts(bl)}


@api.get("/tasks")
def tasks(request: Request):
    return _tasks_for(auth.require_user(request))


def _tasks_for(u: dict) -> list[dict]:
    """Work waiting on this user, filtered by their role. Shared by /tasks and /home so both agree."""
    p = perms_for(u["role"])
    out: list[dict] = []

    def add(rows: list[dict], kind: str, action: str, link, since: str = "updated_at") -> None:
        out.extend({"kind": kind, "brand": r["brand_id"], "title": r["title"], "action": action, "link": link(r), "since": r[since]} for r in rows)

    if "article:review" in p:
        add(all_rows("SELECT id, brand_id, title, updated_at FROM articles WHERE status = 'in_review' ORDER BY updated_at"), "review", "Review content", lambda r: f"/blogs/{r['id']}?tab=review")
    if "publish:authorize" in p:
        add(all_rows("""SELECT r.id, r.brand_id, a.title, r.requested_at FROM publish_requests r JOIN articles a ON a.id = r.article_id
                        WHERE r.status = 'pending' AND (r.requested_by IS NOT ? OR ? = 'admin') ORDER BY r.requested_at""", u["id"], u["role"]),
            "authorize", "Authorize publishing", lambda r: "/publishing", "requested_at")
    if "article:write" in p:
        add(all_rows("SELECT id, brand_id, title, updated_at FROM articles WHERE status = 'changes_requested' ORDER BY updated_at"), "changes", "Address review notes", lambda r: f"/blogs/{r['id']}")
        add(all_rows("SELECT id, brand_id, title, updated_at FROM articles WHERE status = 'failed' ORDER BY updated_at"), "failed", "Fix failed publish", lambda r: "/publishing")
        add(all_rows("SELECT id, brand_id, title, updated_at FROM articles WHERE status = 'approved' AND approved_hash = content_hash ORDER BY updated_at"), "request", "Request publishing", lambda r: f"/blogs/{r['id']}?tab=publish")
        add(all_rows("SELECT id, brand_id, title, updated_at FROM articles WHERE status IN ('draft','idea') AND assignee_id = ? ORDER BY updated_at", u["id"]), "draft", "Finish your draft", lambda r: f"/blogs/{r['id']}")
    if "topic:decide" in p:
        add(all_rows("SELECT id, brand_id, title, updated_at FROM topics WHERE status = 'validated' ORDER BY updated_at"), "topic", "Approve or reject topic", lambda r: "/topics?status=validated")
    return out


@api.get("/home")
def home_data(request: Request):
    """Read-only summary for the Home page: real SEO & Blog records only, never synthetic figures (see services/home.py)."""
    u = auth.require_perm(request, "view")
    bl = brands_for(request)
    return home.build_home(bl, _alerts(bl), _tasks_for(u))


# ---------------- articles ----------------

@api.get("/articles")
def list_articles(request: Request):
    auth.require_perm(request, "view")
    return articles.list_articles(brand_q(request), q(request, "status"), q(request, "q"), q(request, "sort"), q(request, "dir"), q(request, "live"),
                                  q(request, "assignee"), int(q(request, "limit") or 50), int(q(request, "offset") or 0))


@api.get("/articles/counts")
def article_counts(request: Request):
    auth.require_perm(request, "view")
    return articles.status_counts(brand_q(request))


@api.post("/articles")
def create_article(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "article:write")
    return articles.decorate(articles.create_article(u, brand_param(body.get("brand_id")), body, "app", "draft" if body.get("body_html") else "idea"))


@api.get("/articles/{aid}")
def article_detail(aid: str, request: Request):
    auth.require_perm(request, "view")
    a = articles.get_article(to_int(aid))
    return {
        "article": articles.decorate(a),
        "revisions": articles.list_revisions(a["id"]),
        "notes": all_rows("SELECT * FROM review_notes WHERE article_id = ? ORDER BY created_at DESC", a["id"]),
        "requests": all_rows("""SELECT r.*, ru.name requested_by_name, du.name decided_by_name FROM publish_requests r
                                LEFT JOIN users ru ON ru.id = r.requested_by LEFT JOIN users du ON du.id = r.decided_by WHERE article_id = ? ORDER BY r.id DESC""", a["id"]),
        "topic": get("SELECT * FROM topics WHERE id = ?", a["topic_id"]) if a["topic_id"] else None,
        "queries": analytics.article_queries(a["brand_id"], a["live_url"]) if a["live_url"] else None,
        "assignees": all_rows("SELECT id, name, role FROM users WHERE active = 1 AND role IN ('seo_manager','admin') ORDER BY name"),
    }


@api.patch("/articles/{aid}")
def save_article(aid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "article:write")
    return articles.decorate(articles.save_article(u, to_int(aid), body, s(body.get("note"), 300)))


@api.get("/articles/{aid}/revisions/{rid}")
def revision(aid: str, rid: str, request: Request):
    auth.require_perm(request, "view")
    r = get("SELECT r.*, u.name user_name FROM article_revisions r LEFT JOIN users u ON u.id = r.user_id WHERE r.id = ? AND r.article_id = ?", to_int(rid), to_int(aid))
    if not r:
        raise HttpError(404, "Revision not found.")
    return {**r, "data": safe_json(r["data_json"], {})}


@api.post("/articles/{aid}/restore/{rid}")
def restore(aid: str, rid: str, request: Request):
    u = auth.require_perm(request, "article:write")
    return articles.decorate(articles.restore_revision(u, to_int(aid), to_int(rid)))


@api.post("/articles/{aid}/submit")
def submit(aid: str, request: Request):
    return articles.decorate(articles.submit_for_review(auth.require_perm(request, "article:submit"), to_int(aid)))


@api.post("/articles/{aid}/review")
def review(aid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "article:review")
    return articles.decorate(articles.review_article(u, to_int(aid), s(body.get("decision"), 40), body.get("version"), s(body.get("note"), 2000)))


@api.post("/articles/{aid}/shopify-draft")
def shopify_draft(aid: str, request: Request):
    return articles.decorate(publishing.save_shopify_draft(auth.require_perm(request, "shopify:draft"), to_int(aid)))


@api.post("/articles/{aid}/publish-request")
def publish_request(aid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "publish:request")
    return publishing.request_publish(u, to_int(aid), s(body.get("mode"), 30), body.get("publish_at"), s(body.get("note"), 2000))


# ---------------- publishing ----------------

@api.get("/publishing")
def publishing_queue(request: Request):
    auth.require_perm(request, "view")
    return publishing.publishing_queue(brand_q(request))


@api.post("/publish-requests/{rid}/authorize")
def authorize(rid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "publish:authorize")
    return publishing.authorize_request(u, to_int(rid), body.get("confirm"), s(body.get("note"), 2000))


@api.post("/publish-requests/{rid}/retry")
def retry_publish(rid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "publish:authorize")
    return publishing.retry_request(u, to_int(rid), body.get("confirm"))


@api.post("/publish-requests/{rid}/reject")
def reject_publish(rid: str, request: Request, body: dict = JSONBody):
    publishing.reject_request(auth.require_perm(request, "publish:authorize"), to_int(rid), s(body.get("note"), 2000))
    return {"ok": True}


@api.post("/publish-requests/{rid}/cancel")
def cancel_publish(rid: str, request: Request):
    publishing.cancel_request(auth.require_perm(request, "publish:request"), to_int(rid))
    return {"ok": True}


# ---------------- topics & keywords ----------------

@api.get("/topics")
def topics(request: Request):
    auth.require_perm(request, "view")
    where, args = [], []
    b = brand_q(request)
    if b:
        where.append("t.brand_id = ?"); args.append(b)
    if q(request, "status"):
        lst = q(request, "status").split(",")
        where.append(f"t.status IN ({','.join('?' for _ in lst)})"); args += lst
    if q(request, "missing") == "volume":
        where.append("t.search_volume IS NULL")
    if q(request, "q"):
        where.append("(t.title LIKE ? OR t.primary_keyword LIKE ?)"); args += [f"%{q(request, 'q')}%"] * 2
    return all_rows(f"""SELECT t.*, u.name owner_name, (SELECT a.id FROM articles a WHERE a.topic_id = t.id LIMIT 1) article_id
                        FROM topics t LEFT JOIN users u ON u.id = t.owner_id {'WHERE ' + ' AND '.join(where) if where else ''}
                        ORDER BY CASE t.status WHEN 'validated' THEN 0 WHEN 'proposed' THEN 1 WHEN 'approved' THEN 2 ELSE 3 END, t.updated_at DESC LIMIT 500""", *args)


def _topic_input(body: dict, partial: bool) -> dict:
    out: dict[str, Any] = {}
    if not partial or "title" in body:
        out["title"] = s(body.get("title"), 255).strip()
        if not out["title"]:
            raise HttpError(400, "Title is required.")
    if not partial or "primary_keyword" in body:
        out["primary_keyword"] = s(body.get("primary_keyword"), 200).strip()
        if not out["primary_keyword"]:
            raise HttpError(400, "Primary keyword is required.")
        out["keyword_norm"] = norm_keyword(out["primary_keyword"])
    if "secondary_keywords" in body:
        out["secondary_keywords"] = s(body["secondary_keywords"], 1000)
    if "intent" in body:
        if body["intent"] not in ("informational", "commercial", "transactional", "navigational"):
            raise HttpError(400, "Unknown intent.")
        out["intent"] = body["intent"]
    for k in ("search_volume", "keyword_difficulty"):
        if k in body:
            raw = body[k]
            if raw in ("", None):
                out[k] = None
            else:
                try:
                    v = float(raw)
                except (TypeError, ValueError):
                    raise HttpError(400, f"{k} is out of range.")
                if v < 0 or (k == "keyword_difficulty" and v > 100):
                    raise HttpError(400, f"{k} is out of range.")
                out[k] = int(v)
    if "volume_source" in body:
        out["volume_source"] = s(body["volume_source"], 100)
    if "notes" in body:
        out["notes"] = s(body["notes"], 4000)
    if "owner_id" in body:
        out["owner_id"] = int(body["owner_id"]) if body["owner_id"] else None
    return out


@api.post("/topics")
def create_topic(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "topic:write")
    b = brand_param(body.get("brand_id"))
    t = _topic_input(body, False)
    if get("SELECT 1 FROM topics WHERE brand_id = ? AND keyword_norm = ?", b, t["keyword_norm"]):
        raise HttpError(409, "A topic with this primary keyword already exists for this brand.", "duplicate")
    cols = list(t)
    r = run(f"""INSERT INTO topics (brand_id, {', '.join(cols)}, status, source, created_by, created_at, updated_at, source_updated_at)
                VALUES (?, {', '.join('?' for _ in cols)}, 'proposed', 'manual', ?, ?, ?, ?)""", b, *[t[c] for c in cols], u["id"], now(), now(), now())
    audit(u, "topic.create", "topic", r.last_id, b, t["title"])
    return get("SELECT * FROM topics WHERE id = ?", r.last_id)


@api.patch("/topics/{tid}")
def patch_topic(tid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "topic:write")
    t = get("SELECT * FROM topics WHERE id = ?", to_int(tid))
    if not t:
        raise HttpError(404, "Topic not found.")
    patch = _topic_input(body, True)
    if patch.get("keyword_norm") and patch["keyword_norm"] != t["keyword_norm"] and \
            get("SELECT 1 FROM topics WHERE brand_id = ? AND keyword_norm = ? AND id != ?", t["brand_id"], patch["keyword_norm"], t["id"]):
        raise HttpError(409, "Another topic already targets this keyword.", "duplicate")
    if not patch:
        return t
    # Changing what the topic targets sends it back through validation.
    back = patch.get("keyword_norm") and patch["keyword_norm"] != t["keyword_norm"] and t["status"] in ("validated", "approved")
    reset = "status = 'proposed'," if back else ""
    run(f"UPDATE topics SET {', '.join(c + ' = ?' for c in patch)}, {reset} updated_at = ? WHERE id = ?", *patch.values(), now(), t["id"])
    audit(u, "topic.edit", "topic", t["id"], t["brand_id"], ", ".join(patch))
    return get("SELECT * FROM topics WHERE id = ?", t["id"])


@api.post("/topics/{tid}/decision")
def topic_decision(tid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "topic:decide")
    t = get("SELECT * FROM topics WHERE id = ?", to_int(tid))
    if not t:
        raise HttpError(404, "Topic not found.")
    d = body.get("decision")
    if d not in ("approve", "reject", "reopen"):
        raise HttpError(400, "Decision must be approve, reject or reopen.")
    if d == "approve" and t["status"] not in ("proposed", "validated", "rejected"):
        raise HttpError(409, f"A {t['status']} topic cannot be approved.")
    status = {"approve": "approved", "reject": "rejected", "reopen": "proposed"}[d]
    note = s(body.get("note"), 1000)
    notes = t["notes"] + (f"\n[{u['name']}] {note}" if note else "")
    run("UPDATE topics SET status = ?, notes = ?, updated_at = ? WHERE id = ?", status, notes, now(), t["id"])
    audit(u, f"topic.{d}", "topic", t["id"], t["brand_id"], t["title"])
    return get("SELECT * FROM topics WHERE id = ?", t["id"])


@api.post("/topics/{tid}/article")
def topic_article(tid: str, request: Request, body: dict = JSONBody):
    t = get("SELECT * FROM topics WHERE id = ?", to_int(tid))
    if not t:
        raise HttpError(404, "Topic not found.")
    if t["status"] != "approved":
        raise HttpError(409, "Approve the topic before starting an article.")
    existing = get("SELECT id FROM articles WHERE topic_id = ?", t["id"])
    if existing:
        return {"articleId": existing["id"]}
    if body.get("mode") == "claude":
        u = auth.require_perm(request, "workflow:run")
        r = workflow.run_stage("content_generation", t["brand_id"], u, "manual", topic_id=t["id"])
        if r["status"] == "failed":
            raise HttpError(502, r.get("error") or "Generation failed.")
        return {"articleId": (get("SELECT id FROM articles WHERE topic_id = ?", t["id"]) or {}).get("id"), "run": r}
    u = auth.require_perm(request, "article:write")
    a = articles.create_article(u, t["brand_id"], {"title": t["title"], "primary_keyword": t["primary_keyword"], "topic_id": t["id"],
                                                    "author": brand_public(t["brand_id"])["settings"]["defaultAuthor"]}, "app", "idea")
    run("UPDATE topics SET status = 'in_production', updated_at = ? WHERE id = ?", now(), t["id"])
    return {"articleId": a["id"]}


@api.get("/keywords")
def keywords(request: Request):
    auth.require_perm(request, "view")
    b = brand_q(request)
    if b:
        return all_rows("SELECT * FROM keywords WHERE brand_id = ? ORDER BY COALESCE(search_volume, -1) DESC LIMIT 1000", b)
    return all_rows("SELECT * FROM keywords ORDER BY COALESCE(search_volume, -1) DESC LIMIT 1000")


@api.get("/keyword-file")
def keyword_file_data(request: Request):
    """Read-only view of the Ridhi keyword research workbook in data/ (never written to the database)."""
    auth.require_perm(request, "view")
    return keyword_file.load()


@api.post("/keywords")
def create_keyword(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "topic:write")
    b = brand_param(body.get("brand_id"))
    kw = s(body.get("keyword"), 200).strip()
    if not kw:
        raise HttpError(400, "Keyword is required.")
    raw = body.get("search_volume")
    try:
        vol = None if raw in ("", None) else int(float(raw))
    except (TypeError, ValueError):
        raise HttpError(400, "Search volume must be a positive number.")
    if vol is not None and vol < 0:
        raise HttpError(400, "Search volume must be a positive number.")
    if get("SELECT 1 FROM keywords WHERE brand_id = ? AND keyword_norm = ?", b, norm_keyword(kw)):
        raise HttpError(409, "This keyword is already recorded.", "duplicate")
    r = run("""INSERT INTO keywords (brand_id, keyword, keyword_norm, search_volume, keyword_difficulty, intent, source_tool, source_date, notes, source, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?, 'manual', ?, ?)""",
            b, kw, norm_keyword(kw), vol, int(body["keyword_difficulty"]) if body.get("keyword_difficulty") else None, body.get("intent") or None,
            s(body.get("source_tool"), 60) or "manual", s(body.get("source_date"), 10) or today(), s(body.get("notes"), 1000), now(), now())
    audit(u, "keyword.create", "keyword", r.last_id, b, kw)
    return get("SELECT * FROM keywords WHERE id = ?", r.last_id)


# ---------------- analytics ----------------

@api.get("/analytics/gsc")
def analytics_gsc(request: Request):
    auth.require_perm(request, "view")
    frm, to = date_range(request)
    return {"range": {"from": frm, "to": to}, "brands": [analytics.gsc_report(b, frm, to) for b in brands_for(request)]}


@api.get("/analytics/ga4")
def analytics_ga4(request: Request):
    auth.require_perm(request, "view")
    frm, to = date_range(request)
    return {"range": {"from": frm, "to": to}, "brands": [analytics.ga4_report(b, frm, to) for b in brands_for(request)]}


@api.get("/analytics/articles")
def analytics_articles(request: Request):
    auth.require_perm(request, "view")
    frm, to = date_range(request)
    return {"range": {"from": frm, "to": to}, "brands": [analytics.article_performance(b, frm, to) for b in brands_for(request)]}


@api.post("/analytics/sync")
def analytics_sync(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "analytics:sync")
    b = brand_param(body.get("brand"))
    source = s(body.get("source"), 20)
    audit(u, "sync.manual", "integration", source, b)
    fn = {"shopify": sync_shopify, "gsc": sync_gsc, "ga4": sync_ga4}.get(source)
    if not fn:
        raise HttpError(400, "source must be shopify, gsc or ga4")
    try:
        return fn(b)
    except HttpError:
        raise
    except Exception as e:  # noqa: BLE001 — surface the service's message to the user
        raise HttpError(502, str(e), "sync_failed")


# ---------------- automation ----------------

@api.get("/automation")
def automation(request: Request):
    auth.require_perm(request, "view")
    return {
        "brands": [{"brand": b, "paused": workflow.is_paused(b),
                    "pause": get("SELECT a.*, u.name paused_by_name FROM automation_state a LEFT JOIN users u ON u.id = a.paused_by WHERE brand_id = ?", b),
                    "stages": workflow.pipeline(b)} for b in brands_for(request)],
        "runs": workflow.list_runs(brand_q(request), q(request, "stage"), q(request, "status"), 60),
        "configured": workflow.automation_configured(),
    }


@api.post("/automation/{bid}/stages/{stage}/run")
def run_stage(bid: str, stage: str, request: Request):
    return workflow.run_stage(stage, brand_param(bid), auth.require_perm(request, "workflow:run"), "manual")


@api.post("/automation/runs/{rid}/retry")
def retry_run(rid: str, request: Request):
    return workflow.retry_run(auth.require_perm(request, "workflow:run"), to_int(rid))


@api.post("/automation/{bid}/pause")
def pause(bid: str, request: Request, body: dict = JSONBody):
    workflow.set_paused(auth.require_perm(request, "workflow:run"), brand_param(bid), True, s(body.get("reason"), 500))
    return {"ok": True}


@api.post("/automation/{bid}/resume")
def resume(bid: str, request: Request):
    workflow.set_paused(auth.require_perm(request, "workflow:run"), brand_param(bid), False, "")
    return {"ok": True}


@api.post("/hooks/workflow")
def hook(request: Request, body: dict = JSONBody):
    """External agents report progress here with a shared secret (header X-Workflow-Secret)."""
    secret = config.workflow_webhook_secret
    if not secret:
        raise HttpError(404, "Webhook not enabled.")
    given = request.headers.get("X-Workflow-Secret", "")
    if not hmac.compare_digest(hashlib.sha256(secret.encode()).digest(), hashlib.sha256(given.encode()).digest()):
        raise HttpError(401, "Bad secret.")
    return workflow.ingest_webhook(body)


# ---------------- data & reports ----------------

def _xlsx(name: str, data: bytes) -> Response:
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@api.get("/data/kinds")
def data_kinds(request: Request):
    auth.require_perm(request, "view")
    return excel.kinds_public()


@api.get("/data/templates/{kind}")
def template(kind: str, request: Request):
    auth.require_perm(request, "view")
    return _xlsx(f"blog-ops-{kind}-template.xlsx", excel.build_workbook(kind, [], {"Template": "Empty — fill in the Data sheet."}))


@api.get("/data/export/{kind}")
def export(kind: str, request: Request):
    u = auth.require_perm(request, "view")
    if kind == "audit":
        auth.require_perm(request, "audit:view")
    f = {"brand": brand_q(request), "status": q(request, "status"), "from": q(request, "from"), "to": q(request, "to"), "q": q(request, "q")}
    rows = excel.export_rows(kind, f["brand"], f["status"], f["from"], f["to"], f["q"])
    about = {
        "Rows": str(len(rows)),
        "Filters": ", ".join(f"{k}={v}" for k, v in f.items() if v) or "none",
        "Data sources": "Live API and manually imported rows. Demo fixtures are never exported." if kind.startswith(("gsc", "ga4")) else "Dashboard database.",
        "Exported by": u["email"],
    }
    data = excel.build_workbook(kind, rows, about)
    audit(u, "data.export", "export", kind, summary=f"{len(rows)} rows", details=f)
    return _xlsx(f"blog-ops-{kind}-{today()}.xlsx", data)


@api.post("/data/import/{kind}")
async def import_workbook(kind: str, request: Request):
    u = auth.require_perm(request, "data:import")
    buf = await request.body()
    if not buf:
        raise HttpError(400, "Attach an .xlsx file.")
    if len(buf) > 20 * 1024 * 1024:
        raise HttpError(413, "The upload is too large.")
    filename = unquote(request.headers.get("X-Filename", "upload.xlsx"))
    if q(request, "mode") == "commit":
        return await run_in_threadpool(excel.commit_import, u, kind, buf, filename, "update" if q(request, "duplicates") == "update" else "skip")
    p = await run_in_threadpool(excel.parse_workbook, kind, buf)
    flagged = [r for r in p["rows"] if r["errors"] or r["warnings"] or r["duplicate"]][:300]
    clean = [r for r in p["rows"] if not (r["errors"] or r["warnings"] or r["duplicate"])][:20]
    return {**p, "rows": flagged + clean}


@api.get("/data/health")
def health(request: Request):
    auth.require_perm(request, "view")
    return excel.data_health()


@api.post("/admin/demo")
def demo(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "demo:manage")
    if body.get("action") == "load":
        return load_demo(u)
    if body.get("action") == "clear":
        return clear_demo(u)
    raise HttpError(400, "action must be load or clear")


# ---------------- integrations ----------------

def _integration_list() -> list[dict]:
    statuses = all_statuses()

    def st(key: str, b: str = "") -> dict | None:
        return next((x for x in statuses if x["key"] == key and x["brand_id"] == b), None)

    sa = service_account_email()
    items: list[dict] = []
    for b in BRAND_IDS:
        cfg = brand(b)
        admin = shopify.configured(cfg)
        items.append({"key": "shopify", "brand": b, "label": "Shopify Admin API", "configured": admin,
                      "state": ((st("shopify", b) or {}).get("status") or "not_synced") if admin else "pending_setup", "status": st("shopify", b),
                      "provides": "All articles incl. drafts, SEO fields, products · hidden drafts · authorized publishing",
                      "setup": f"Shopify admin → Settings → Apps and sales channels → Develop apps → create an app with Admin API scopes read_content, write_content, read_products. "
                               f"Put its Admin API access token in {b.upper()}_SHOPIFY_ADMIN_TOKEN (shop: {cfg.shop_domain})."})
        items.append({"key": "shopify_public", "brand": b, "label": "Shopify public feed", "configured": config.public_feed_sync,
                      "state": "standby" if admin else ((st("shopify_public", b) or {}).get("status") or "not_synced"), "status": st("shopify_public", b),
                      "provides": f"Live articles and products read from {cfg.storefront_domain}. Read-only, no drafts or SEO fields.",
                      "setup": "Not used while the Admin API is connected." if admin else "No setup needed."})
        g_ok = gsc_configured(cfg)
        items.append({"key": "gsc", "brand": b, "label": "Google Search Console", "configured": g_ok,
                      "state": ((st("gsc", b) or {}).get("status") or "not_synced") if g_ok else "pending_setup", "status": st("gsc", b),
                      "provides": f"Clicks, impressions, CTR, position and queries for /blogs/ URLs on {cfg.gsc_property}",
                      "setup": f"Set GOOGLE_SERVICE_ACCOUNT_FILE, then add {sa or 'the service-account email'} as a user on the Search Console property {cfg.gsc_property}."})
        a_ok = ga4_configured(cfg)
        items.append({"key": "ga4", "brand": b, "label": "Google Analytics 4", "configured": a_ok,
                      "state": ((st("ga4", b) or {}).get("status") or "not_synced") if a_ok else "pending_setup", "status": st("ga4", b),
                      "provides": "Sessions, engaged sessions, engagement time and key events by blog landing page",
                      "setup": f"Set {b.upper()}_GA4_PROPERTY_ID (numeric) and give {sa or 'the service account'} Viewer access on that property."})
    items.append({"key": "claude", "brand": "", "label": "Claude (Anthropic API)", "configured": claude.configured(),
                  "state": ((st("claude") or {}).get("status") or "not_synced") if claude.configured() else "pending_setup", "status": st("claude"),
                  "provides": f"Topic research and first drafts ({config.claude_model}). Runs started here are logged under Automation.",
                  "setup": "Set ANTHROPIC_API_KEY on the server. Claude agents running elsewhere are not visible through the API; they can report progress to the workflow webhook."})
    items.append({"key": "workflow_webhook", "brand": "", "label": "Workflow webhook", "configured": bool(config.workflow_webhook_secret),
                  "state": "connected" if config.workflow_webhook_secret else "pending_setup", "status": None,
                  "provides": "Lets external agents (e.g. a scheduled Claude routine) report stage status: POST /api/hooks/workflow",
                  "setup": 'Set WORKFLOW_WEBHOOK_SECRET and send it in the X-Workflow-Secret header. Body: {"brand","stage","status","message"}.'})
    return items


@api.get("/integrations")
def integrations(request: Request):
    auth.require_perm(request, "view")
    return {"items": _integration_list(), "livePublishing": config.allow_live_publish, "shopifyApiVersion": config.shopify_api_version}


@api.post("/integrations/test")
def integration_test(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "integrations:manage")
    key = s(body.get("key"), 40)
    b = brand_param(body["brand"]) if body.get("brand") else None
    try:
        if key == "shopify" and b:
            result: Any = shopify.shop_info(brand(b))
        elif key == "shopify_public" and b:
            result = {"liveArticles": len(fetch_public_articles(brand(b)))}
        elif key == "gsc" and b:
            end = add_days(today(), -3)
            result = {"rows": len(gsc_query(brand(b), add_days(end, -6), end, ["date"]))}
        elif key == "ga4" and b:
            end = add_days(today(), -1)
            result = {"rows": len(ga4_report(brand(b), end, end))}
        elif key == "claude":
            result = claude.ping()
            mark_success("claude", "", "api", result)
        else:
            raise HttpError(400, "Unknown integration.")
        audit(u, "integration.test", "integration", key, b or "", "ok")
        return {"ok": True, "result": result}
    except HttpError as e:
        if e.status < 500 and e.code != "pending_setup":
            raise
        err = e.message
    except Exception as e:  # noqa: BLE001
        err = str(e)
    if key == "claude":
        mark_error("claude", "", "api", err)
    audit(u, "integration.test_failed", "integration", key, b or "", err[:300])
    return {"ok": False, "error": err}


# ---------------- audit & users ----------------

@api.get("/audit")
def audit_log(request: Request):
    auth.require_perm(request, "audit:view")
    where, args = [], []
    b = brand_q(request)
    if b:
        where.append("brand_id = ?"); args.append(b)
    if q(request, "action"):
        where.append("action LIKE ?"); args.append(q(request, "action") + "%")
    if q(request, "user"):
        where.append("user_email LIKE ?"); args.append(f"%{q(request, 'user')}%")
    if q(request, "entity_type"):
        where.append("entity_type = ?"); args.append(q(request, "entity_type"))
    if q(request, "entity_id"):
        where.append("entity_id = ?"); args.append(q(request, "entity_id"))
    if q(request, "before").isdigit():
        where.append("id < ?"); args.append(int(q(request, "before")))
    rows = all_rows(f"SELECT * FROM audit_log {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY id DESC LIMIT 100", *args)
    return [{**r, "details": safe_json(r["details_json"], {})} for r in rows]


@api.get("/users")
def users(request: Request):
    u = auth.require_user(request)
    full = "users:manage" in perms_for(u["role"])
    rows = all_rows("SELECT id, email, name, role, active, created_at, last_login_at FROM users ORDER BY active DESC, name")
    return {"users": rows if full else [{k: x[k] for k in ("id", "name", "role", "active")} for x in rows],
            "roles": [{"key": k, "label": v, "permissions": perms_for(k)} for k, v in ROLE_LABELS.items()],
            "permissions": PERMISSIONS}


@api.post("/users")
def create_user(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "users:manage")
    email = s(body.get("email"), 200).strip().lower()
    name = s(body.get("name"), 120).strip()
    role = body.get("role")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HttpError(400, "Enter a valid email.")
    if not name:
        raise HttpError(400, "Enter a name.")
    if not is_role(role):
        raise HttpError(400, "Choose a role.")
    err = auth.validate_password(body.get("password"))
    if err:
        raise HttpError(400, err)
    if get("SELECT 1 FROM users WHERE email = ?", email):
        raise HttpError(409, "A user with this email exists.")
    r = run("INSERT INTO users (email, name, role, password_hash, created_at) VALUES (?,?,?,?,?)", email, name, role, auth.hash_password(body["password"]), now())
    audit(u, "user.create", "user", r.last_id, summary=f"{email} as {role}")
    return {"id": r.last_id}


@api.patch("/users/{uid}")
def patch_user(uid: str, request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "users:manage")
    target = get("SELECT * FROM users WHERE id = ?", to_int(uid))
    if not target:
        raise HttpError(404, "User not found.")
    role = body.get("role", target["role"])
    active = target["active"] if "active" not in body else (1 if body["active"] else 0)
    if not is_role(role):
        raise HttpError(400, "Unknown role.")
    if target["role"] == "admin" and (role != "admin" or not active):
        if get("SELECT COUNT(*) n FROM users WHERE role = 'admin' AND active = 1")["n"] <= 1:
            raise HttpError(409, "Keep at least one active admin.")
    changes = []
    if role != target["role"]:
        changes.append(f"role {target['role']}→{role}")
    if active != target["active"]:
        changes.append("reactivated" if active else "deactivated")
    name = (s(body["name"], 120).strip() or target["name"]) if "name" in body else target["name"]
    if name != target["name"]:
        changes.append("name")
    run("UPDATE users SET role = ?, active = ?, name = ? WHERE id = ?", role, active, name, target["id"])
    if body.get("password"):
        err = auth.validate_password(body["password"])
        if err:
            raise HttpError(400, err)
        run("UPDATE users SET password_hash = ? WHERE id = ?", auth.hash_password(body["password"]), target["id"])
        changes.append("password reset")
    if not active or role != target["role"] or body.get("password"):
        run("DELETE FROM sessions WHERE user_id = ?", target["id"])
    audit(u, "user.update", "user", target["id"], summary=f"{target['email']}: {', '.join(changes) or 'no change'}")
    return {"ok": True}
