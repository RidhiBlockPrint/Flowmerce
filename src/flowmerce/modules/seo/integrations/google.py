"""Google Search Console and GA4 Data API through one service account.

Setup: create a service account, download its JSON key outside the web root (or into secrets/, which
is git-ignored), set GOOGLE_SERVICE_ACCOUNT_FILE, then add the service-account email as a user on each
Search Console property and as a Viewer on each GA4 property. Tokens are cached in memory only."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.parse import quote

import httpx

from ..config import BrandConfig, config, has_google_credentials
from ..util import HttpError, page_path

SCOPE_GSC = "https://www.googleapis.com/auth/webmasters.readonly"
SCOPE_GA4 = "https://www.googleapis.com/auth/analytics.readonly"

_creds: dict[str, object] = {}
_lock = threading.Lock()


def service_account_email() -> str | None:
    try:
        return json.loads(Path(config.google_service_account_file).read_text())["client_email"]
    except Exception:
        return None


def _token(scope: str) -> str:
    if not has_google_credentials():
        raise HttpError(412, "Google service account is not configured.", "pending_setup")
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    with _lock:
        cred = _creds.get(scope)
        if cred is None:
            cred = service_account.Credentials.from_service_account_file(config.google_service_account_file, scopes=[scope])
            _creds[scope] = cred
        if not cred.valid:  # type: ignore[attr-defined]
            try:
                cred.refresh(Request())  # type: ignore[attr-defined]
            except Exception as e:
                raise RuntimeError(f"Google token exchange failed: {e}") from e
        return cred.token  # type: ignore[attr-defined]


def _post(url: str, scope: str, body: dict) -> dict:
    res = httpx.post(url, json=body, headers={"Authorization": f"Bearer {_token(scope)}"}, timeout=60)
    data = res.json() if res.content else {}
    if res.status_code >= 300:
        msg = (data.get("error") or {}).get("message") or res.reason_phrase
        if res.status_code == 403:
            raise RuntimeError(f"Google refused access (403): {msg}. Add the service account to this property.")
        raise RuntimeError(f"Google API {res.status_code}: {msg}")
    return data


def gsc_configured(b: BrandConfig) -> bool:
    return has_google_credentials() and bool(b.gsc_property)


def ga4_configured(b: BrandConfig) -> bool:
    return has_google_credentials() and bool(b.ga4_property_id)


def gsc_query(b: BrandConfig, start: str, end: str, dimensions: list[str], row_limit: int = 25000) -> list[dict]:
    """Search Analytics for blog URLs only (page contains /blogs/). Paginates with startRow."""
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(b.gsc_property, safe='')}/searchAnalytics/query"
    rows: list[dict] = []
    start_row = 0
    while start_row < 200000:
        data = _post(url, SCOPE_GSC, {
            "startDate": start, "endDate": end, "dimensions": dimensions, "rowLimit": row_limit, "startRow": start_row,
            "dataState": "final",
            "dimensionFilterGroups": [{"filters": [{"dimension": "page", "operator": "contains", "expression": "/blogs/"}]}],
        })
        batch = data.get("rows") or []
        rows.extend(batch)
        if len(batch) < row_limit:
            break
        start_row += row_limit
    return rows


def ga4_report(b: BrandConfig, start: str, end: str) -> list[dict]:
    """GA4 landing-page report for blog URLs. keyEvents is GA4's current name for conversions."""
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{quote(b.ga4_property_id, safe='')}:runReport"
    out: list[dict] = []
    limit, offset = 50000, 0
    while offset < 500000:
        data = _post(url, SCOPE_GA4, {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "date"}, {"name": "landingPage"}],
            "metrics": [{"name": n} for n in ("sessions", "engagedSessions", "engagementRate", "userEngagementDuration", "keyEvents")],
            "dimensionFilter": {"filter": {"fieldName": "landingPage", "stringFilter": {"matchType": "CONTAINS", "value": "/blogs/"}}},
            "limit": limit, "offset": offset,
        })
        rows = data.get("rows") or []
        for r in rows:
            d = r["dimensionValues"][0]["value"]
            m = [float(v["value"]) for v in r["metricValues"]]
            out.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:8]}", "path": page_path(r["dimensionValues"][1]["value"]),
                        "sessions": m[0], "engaged": m[1], "duration": m[3], "key_events": m[4]})
        if len(rows) < limit:
            break
        offset += limit
    return out
