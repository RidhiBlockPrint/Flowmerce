"""Read-only data for the Home / Morning Brief page (GET /api/home).

Every value comes from records this app already holds. Nothing is invented: when a source has no data
the value is None or the list is empty, and the source says so. Figures from synthetic demo fixtures that
may sit in the analytics tables are never reported as metrics: they are withheld and flagged, so real and
synthetic data cannot be mixed on Home. Only the SEO & Blog project is built, so it is the only project
that contributes records here.

Alerts and approvals are computed by the API layer from the same functions the Overview and Tasks
endpoints use (so role filtering is identical) and passed in; this module never imports the API
router, which keeps the dependency one-way.
"""
from __future__ import annotations

from typing import Any

from ..db import all_rows, now
from ..integrations.status import all_statuses
from ..util import add_days, today
from . import analytics, workflow
from .demo import demo_loaded

WINDOW_DAYS = 28
LATENCY_DAYS = 3  # Search Console data settles about 3 days after the fact
MAX_JOBS = 8
MAX_APPROVALS = 10

STAGE_LABEL = {s["key"]: s["label"] for s in workflow.STAGES}
APPROVAL_KINDS = {"review": "Content approval", "authorize": "Publish approval", "topic": "Topic approval"}
SYNC_LABEL = {"shopify": "Shopify Admin API", "gsc": "Search Console", "ga4": "GA4"}

REPORTS_NOTE = (
    "Dated reports are not produced yet. The SEO & Blog pipeline records its runs, shown under job and sync "
    "activity, but it does not write a daily report."
)


def metric_window() -> tuple[str, str]:
    """The fixed 28-day window ending three days ago."""
    to = add_days(today(), -LATENCY_DAYS)
    return add_days(to, -(WINDOW_DAYS - 1)), to


def _metric(brand_id: str, key: str, label: str, report: dict, field: str, origin: str) -> dict:
    source = report["source"]
    kind = source["kind"]
    base = {"brand": brand_id, "module": "seo", "key": key, "label": label, "source": source}
    if kind is None:
        return {**base, "value": None, "withheld": False, "note": f"No {origin} data for this window"}
    if kind == "demo":
        return {**base, "value": None, "withheld": True, "note": f"{origin} demo fixtures are loaded; their synthetic figures are not shown on Home"}
    return {**base, "value": (report["totals"] or {}).get(field), "withheld": False, "note": origin}


def _metrics(brand_ids: list[str], frm: str, to: str) -> list[dict]:
    out: list[dict] = []
    for b in brand_ids:
        gsc, ga4 = analytics.gsc_report(b, frm, to), analytics.ga4_report(b, frm, to)
        out.append(_metric(b, "gsc_clicks", "Search clicks", gsc, "clicks", "Search Console"))
        out.append(_metric(b, "gsc_impressions", "Search impressions", gsc, "impressions", "Search Console"))
        out.append(_metric(b, "ga4_sessions", "Sessions", ga4, "sessions", "GA4"))
    return out


def _approvals(tasks: list[dict], brand_ids: list[str]) -> list[dict]:
    """Tasks that are decisions for the signed-in role (review, publish authorization, topic approval).
    The tasks arrive already filtered by role; other task kinds are personal to-dos, not approvals."""
    rows = [t for t in tasks if t["kind"] in APPROVAL_KINDS and t["brand"] in brand_ids]
    rows.sort(key=lambda t: t["since"] or "")
    return [{"id": f"{t['kind']}-{i}", "brand": t["brand"], "module": "seo", "kind": t["kind"], "label": APPROVAL_KINDS[t["kind"]],
             "title": t["title"], "action": t["action"], "to": t["link"], "since": t["since"]} for i, t in enumerate(rows)]


def _alerts(alerts: list[dict]) -> list[dict]:
    order = {"critical": 0, "warning": 1, "info": 2}
    rows = sorted(alerts, key=lambda a: order.get(a["level"], 3))
    return [{"id": f"alert-{i}", "module": "seo", "severity": a["level"], "title": a["title"],
             "detail": (a.get("detail") or "")[:300], "to": a.get("link")} for i, a in enumerate(rows)]


def _jobs(brand_ids: list[str]) -> list[dict]:
    if not brand_ids:
        return []
    ph = ",".join("?" for _ in brand_ids)
    rows = all_rows(f"""SELECT id, brand_id, stage, status, trigger_kind, started_at, finished_at FROM workflow_runs
                        WHERE brand_id IN ({ph}) ORDER BY id DESC LIMIT ?""", *brand_ids, MAX_JOBS)
    last_ok = {(r["brand_id"], r["stage"]): r["t"] for r in all_rows(
        f"SELECT brand_id, stage, MAX(finished_at) t FROM workflow_runs WHERE status = 'succeeded' AND brand_id IN ({ph}) GROUP BY brand_id, stage", *brand_ids)}
    return [{"id": r["id"], "brand": r["brand_id"], "module": "seo", "name": STAGE_LABEL.get(r["stage"], r["stage"]), "status": r["status"],
             "trigger": r["trigger_kind"], "startedAt": r["started_at"], "finishedAt": r["finished_at"],
             "lastSuccessAt": last_ok.get((r["brand_id"], r["stage"]))} for r in rows]


def _syncs(brand_ids: list[str]) -> list[dict]:
    """Integrations that have actually been attempted. Error text is left out here: it already appears
    in the alerts, and nothing about an unconfigured integration is invented."""
    return [{"key": s["key"], "label": SYNC_LABEL[s["key"]], "brand": s["brand_id"], "status": s["status"],
             "lastSuccessAt": s["last_success_at"], "lastAttemptAt": s["last_attempt_at"]}
            for s in all_statuses()
            if s["key"] in SYNC_LABEL and s["brand_id"] in brand_ids and (s["last_attempt_at"] or s["last_success_at"])]


def _brief(approvals: list[dict], alerts: list[dict]) -> list[dict]:
    """Plain statements computed from the counts above; never free-written findings."""
    points: list[dict] = []
    for b in sorted({a["brand"] for a in approvals}):
        n = sum(1 for a in approvals if a["brand"] == b)
        points.append({"module": "seo", "brand": b, "text": f"{n} item{'s' if n != 1 else ''} waiting for a decision in SEO & Blog Content."})
    critical = sum(1 for a in alerts if a["severity"] == "critical")
    if critical:
        points.append({"module": "seo", "brand": None, "text": f"{critical} critical alert{'s' if critical != 1 else ''} need attention."})
    return points


def build_home(brand_ids: list[str], alerts: list[dict], tasks: list[dict]) -> dict[str, Any]:
    """Assemble the Home payload for the given brands. Read-only: it only queries."""
    frm, to = metric_window()
    approvals = _approvals(tasks, brand_ids)
    shaped_alerts = _alerts(alerts)
    return {
        "generatedAt": now(),
        "window": {"from": frm, "to": to, "days": WINDOW_DAYS},
        "brands": list(brand_ids),
        "demoFixturesLoaded": demo_loaded(),
        "brief": _brief(approvals, shaped_alerts),
        "metrics": _metrics(brand_ids, frm, to),
        "approvals": approvals[:MAX_APPROVALS],
        "approvalsTotal": len(approvals),
        "alerts": shaped_alerts,
        "reports": [],
        "reportsNote": REPORTS_NOTE,
        "jobs": _jobs(brand_ids),
        "syncs": _syncs(brand_ids),
    }
