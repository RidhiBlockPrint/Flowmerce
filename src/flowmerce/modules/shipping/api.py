"""HTTP endpoints for the Shipping module, mounted at /api/shipping by the SEO app so they sit behind the same
loopback guard, CSRF check and local-operator identity as everything else. Reads need "view"; marking shipments and
notes need "shipping:update"; running a sync needs "analytics:sync"."""

from __future__ import annotations

from fastapi import APIRouter, Body, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ..seo import auth
from ..seo.audit import audit
from ..seo.util import HttpError, s
from . import repo, service
from .alerts import run_alerts
from .config import load_config
from .schema import schema_version, table_counts
from .sync import sync_now

shipping = APIRouter(prefix="/api/shipping")
JSONBody = Body(default_factory=dict)

VIEWS = {
    "",
    "red",
    "orange",
    "yellow",
    "grey",
    "on_track",
    "no_scan",
    "unconfirmed",
    "nomove",
    "noscan",
    "exception",
    "lost",
    "failed",
    "delivered",
    "covered",
}
SORTS = {"priority", "oldest", "stuck", "order"}


def _int(request: Request, key: str, default: int, lo: int = 0, hi: int = 100000) -> int:
    try:
        return max(lo, min(hi, int(request.query_params.get(key, default))))
    except ValueError:
        return default


def _filters(request: Request) -> dict:
    view = request.query_params.get("view", "")
    sort = request.query_params.get("sort", "priority")
    if view not in VIEWS:
        raise HttpError(400, "Unknown view.", "bad_request")
    if sort not in SORTS:
        raise HttpError(400, "Unknown sort order.", "bad_request")
    return {
        "view": view,
        "carrier": request.query_params.get("carrier", "")[:80],
        "status": request.query_params.get("status", "")[:40],
        "q": request.query_params.get("q", "")[:80],
        "days": _int(request, "days", 0, 0, 3650),
        "sort": sort,
    }


@shipping.get("/status")
def status(request: Request):
    auth.require_perm(request, "view")
    repo.ready()
    cfg = load_config()
    return {
        "shopifyConfigured": cfg.has_shopify_credentials,
        "shop": cfg.shop_domain,
        "ordersSince": cfg.orders_since,
        "schemaVersion": schema_version(),
        "counts": table_counts(),
        "thresholds": cfg.thresholds,
        "readOnlyShopify": True,
    }


@shipping.get("/summary")
def summary(request: Request):
    auth.require_perm(request, "view")
    return service.summary(week_days=_int(request, "week_days", 0, 0, 3650))


@shipping.get("/shipments")
def shipments(request: Request):
    auth.require_perm(request, "view")
    return service.list_shipments(
        **_filters(request), page=_int(request, "page", 0), size=_int(request, "size", 10, 1, 200)
    )


@shipping.get("/shipments/detail")
def shipment_detail(request: Request):
    auth.require_perm(request, "view")
    order = request.query_params.get("order", "")
    d = service.detail(order, request.query_params.get("key", ""))
    if not d:
        raise HttpError(404, "Shipment not found.", "not_found")
    return d


@shipping.post("/shipments/manual")
def mark_manual(request: Request, body: dict = JSONBody):
    """Team check for Amazon/unknown carriers (they send no delivery event to Shopify)."""
    u = auth.require_perm(request, "shipping:update")
    order, tracking, st = (
        s(body.get("order_number"), 60),
        s(body.get("tracking_number"), 120),
        body.get("status"),
    )
    if not order or st not in service.MANUAL_STATUSES:
        raise HttpError(400, "order_number and a valid status are required.", "bad_request")
    if not any(
        r["order_number"] == order and r["tracking_number"] == tracking
        for r in repo.all_shipments()
    ):
        raise HttpError(404, "Shipment not found.", "not_found")
    repo.set_manual_status(order, tracking, st, u["email"])
    audit(u, "shipping.mark", "shipment", f"{order}|{tracking}", summary=f"{order} marked {st}")
    return {"ok": True}


@shipping.post("/notes")
def save_note(request: Request, body: dict = JSONBody):
    u = auth.require_perm(request, "shipping:update")
    order = s(body.get("order_number"), 60)
    if not order:
        raise HttpError(400, "order_number is required.", "bad_request")
    repo.set_note(order, str(body.get("note") or ""), u["email"])
    audit(u, "shipping.note", "shipment", order, summary=f"Note saved on {order}")
    return {"ok": True}


@shipping.get("/analytics")
def analytics(request: Request):
    auth.require_perm(request, "view")
    return service.analytics()


@shipping.get("/issues")
def issues(request: Request):
    auth.require_perm(request, "view")
    return service.issues()


@shipping.get("/checks")
def checks(request: Request):
    auth.require_perm(request, "view")
    return service.checks_page()


@shipping.get("/runs")
def runs(request: Request):
    auth.require_perm(request, "view")
    return service.last_run_info()


@shipping.post("/sync")
async def sync(request: Request):
    """Read Shopify orders and fulfilments now (read-only) and save them. Runs off the event loop."""
    u = auth.require_perm(request, "analytics:sync")
    result = await run_in_threadpool(sync_now)
    audit(
        u,
        "shipping.sync",
        "sync",
        "",
        summary=f"{result['sync_status']}: {result.get('orders_processed', 0)} orders",
    )
    return result


@shipping.get("/export/{kind}")
def export(kind: str, request: Request):
    auth.require_perm(request, "view")
    if kind not in ("filtered", "escalation", "verify"):
        raise HttpError(404, "Unknown export.", "not_found")
    name, text = service.export_csv(kind, **_filters(request))
    return Response(
        text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@shipping.post("/alerts/send")
async def send_alerts(request: Request):
    """Email the critical / stuck / notes-mismatch digest now. Needs SMTP_HOST, SMTP_USER, SMTP_PASS, ALERT_TO in .env."""
    u = auth.require_perm(request, "analytics:sync")
    from . import repo as _repo

    msg = await run_in_threadpool(
        lambda: run_alerts(
            _repo.all_shipments(), thresholds=load_config().thresholds, checks=_repo.order_checks()
        )
    )
    audit(u, "shipping.alert", "alert", "", summary=msg[:200])
    return {"result": msg}
