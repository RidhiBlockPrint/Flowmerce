"""Excel workbooks for data that cannot be fetched live (keyword-tool volumes, offline review notes,
Search Console / GA4 exports when the API is not connected) and for reports.

Every workbook has the same shape so exports can be edited and imported back:
  Data   — one header row, then records; dropdown and number validation on each column
  Fields — the schema: column, required, type, allowed values, description
  About  — what the file is, when it was generated, filters applied
  _meta  — hidden; the record kind and schema version, checked on import
Imports are two-step: a preview that validates every row and flags duplicates (within the file and
against the database), then a commit of the rows that passed."""
from __future__ import annotations

import io
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ..audit import audit
from ..db import all_rows, get, now, run, tx
from ..util import HttpError, norm_keyword, page_path, s, slugify, utcnow
from .articles import create_article, save_article

SCHEMA_VERSION = 1

BRAND = {"key": "brand", "header": "brand", "type": "enum", "required": True, "values": ["ridhi", "cpc"], "width": 10, "description": "ridhi = Ridhi Block Print, cpc = Cotton Print Club"}
SOURCE_TS = {"key": "source_timestamp", "header": "source_timestamp", "type": "datetime", "required": True, "width": 20, "description": "When this data was taken from its source (export time). Used to flag stale data."}
INTENTS = ["informational", "commercial", "transactional", "navigational"]


def F(key: str, typ: str, desc: str = "", required: bool = False, width: int = 16, values: list[str] | None = None, mn: float | None = None, mx: float | None = None) -> dict:
    return {"key": key, "header": key, "type": typ, "required": required, "width": width, "values": values, "min": mn, "max": mx, "description": desc}


KINDS: dict[str, dict] = {
    "topics": {"title": "Blog topics", "importable": True,
               "description": "Topic ideas with their target keywords. Duplicate = same brand and primary keyword.",
               "fields": [BRAND, F("title", "text", "Working title", True, 48), F("primary_keyword", "text", "The main search phrase this article targets", True, 32),
                          F("secondary_keywords", "text", "Comma-separated", width=40), F("intent", "enum", "Search intent", width=16, values=INTENTS),
                          F("search_volume", "int", "Monthly searches from your keyword tool", width=14, mn=0),
                          F("keyword_difficulty", "int", "0–100 from your keyword tool", width=14, mn=0, mx=100),
                          F("volume_source", "text", "Tool the volume came from, e.g. Semrush", width=18),
                          F("status", "enum", "Defaults to proposed", width=12, values=["proposed", "validated", "approved", "rejected"]),
                          F("notes", "longtext", "Brief for the writer", width=40), SOURCE_TS]},
    "keywords": {"title": "Keyword research", "importable": True,
                 "description": "Keyword volumes and difficulty from an external tool. Used by Keyword validation. Duplicate = same brand and keyword.",
                 "fields": [BRAND, F("keyword", "text", "Search phrase", True, 36), F("search_volume", "int", "Monthly searches", True, 14, mn=0),
                            F("keyword_difficulty", "int", "0–100", width=14, mn=0, mx=100), F("intent", "enum", "Search intent", width=16, values=INTENTS),
                            F("source_tool", "text", "Semrush, Ahrefs, Google Keyword Planner…", True, 18),
                            F("source_date", "date", "Date the numbers were pulled", True, 14), F("notes", "longtext", "", width=30)]},
    "articles": {"title": "Blog records", "importable": True,
                 "description": "Article records. Import creates or updates working copies only (idea or draft); it never touches Shopify, and rows for articles under review, approved or live are refused. Duplicate = same brand and handle.",
                 "fields": [BRAND, F("title", "text", "Article title", True, 48), F("handle", "text", "URL slug; made from the title when empty", width=32),
                            F("primary_keyword", "text", width=28), F("meta_title", "text", "≤ 60 characters", width=40),
                            F("meta_description", "longtext", "140–155 characters", width=50), F("tags", "text", "Comma-separated", width=24),
                            F("author", "text", width=18),
                            F("status", "enum", "Export only. On import, new rows become idea (no body) or draft.", width=16,
                              values=["idea", "draft", "in_review", "changes_requested", "approved", "publish_requested", "scheduled", "published", "failed"]),
                            F("live", "enum", "Export only: visible on the storefront", width=8, values=["yes", "no"]),
                            F("url", "url", "Export only: live URL", width=40), F("updated_at", "datetime", "Export only", width=20),
                            F("body_html", "longtext", "Optional article HTML", width=50)]},
    "approvals": {"title": "Review notes", "importable": True,
                  "description": "Review decisions made outside the dashboard. Imported rows are attached to the article as notes only — they do not approve content or authorize publishing; that happens in the dashboard. Duplicate = same article, reviewer and time.",
                  "fields": [BRAND, F("article_handle", "text", "Handle of the article reviewed", True, 32), F("reviewer_name", "text", "", True, 20),
                             F("decision", "enum", "", True, 18, ["recommend_approve", "changes_requested", "comment"]),
                             F("note", "longtext", "", True, 50), F("reviewed_at", "datetime", "", True, 20)]},
    "gsc_pages": {"title": "Search Console — pages by day", "importable": True,
                  "description": "Daily clicks and impressions per blog URL, exported from Search Console (Performance → Pages, with a Date dimension) when the API is not connected. Duplicate = same brand, date and page.",
                  "fields": [BRAND, F("date", "date", "Day the metrics describe", True, 12), F("page", "url", "Full URL or path of the blog article", True, 50),
                             F("clicks", "int", "", True, 10, mn=0), F("impressions", "int", "", True, 12, mn=0),
                             F("position", "number", "Average position", True, 10, mn=1, mx=200), SOURCE_TS]},
    "gsc_queries": {"title": "Search Console — queries for a period", "importable": True,
                    "description": "Queries for a reporting period (Search Console does not split queries by day in exports). Duplicate = same brand, period, page and query.",
                    "fields": [BRAND, F("period_start", "date", "", True, 12), F("period_end", "date", "", True, 12),
                               F("page", "url", "Optional: the page the query led to", width=44), F("query", "text", "", True, 36),
                               F("clicks", "int", "", True, 10, mn=0), F("impressions", "int", "", True, 12, mn=0),
                               F("position", "number", "", True, 10, mn=1, mx=200), SOURCE_TS]},
    "ga4_pages": {"title": "GA4 — landing pages by day", "importable": True,
                  "description": "GA4 landing-page sessions exported from Explore when the Data API is not connected. Duplicate = same brand, date and landing page.",
                  "fields": [BRAND, F("date", "date", "", True, 12), F("landing_page", "url", "Path or URL", True, 50),
                             F("sessions", "int", "", True, 10, mn=0), F("engaged_sessions", "int", "", True, 16, mn=0),
                             F("avg_engagement_seconds", "number", "Average engagement time per session", width=20, mn=0),
                             F("key_events", "number", "Conversions (GA4 key events)", width=12, mn=0), SOURCE_TS]},
    "audit": {"title": "Audit log", "importable": False, "description": "Who did what and when. Export only.",
              "fields": [{**F("ts", "datetime", width=20), "header": "time"}, {**F("user_email", "text", width=26), "header": "user"},
                         F("action", "text", width=24), {**F("brand_id", "text", width=8), "header": "brand"},
                         F("entity", "text", width=22), F("summary", "longtext", width=60)]},
}


def kinds_public() -> list[dict]:
    return [{"key": k, "title": v["title"], "description": v["description"], "importable": v["importable"],
             "fields": [{x: f[x] for x in ("key", "header", "type", "required", "values", "description") if f.get(x) is not None} for f in v["fields"]]}
            for k, v in KINDS.items()]


# ---------------- writing ----------------

def _validation(f: dict) -> DataValidation | None:
    blank = not f.get("required")
    t = f["type"]
    if t == "enum" and f.get("values"):
        dv = DataValidation(type="list", formula1='"' + ",".join(f["values"]) + '"', allow_blank=blank)
    elif t in ("int", "number"):
        kind = "whole" if t == "int" else "decimal"
        if f.get("max") is not None:
            dv = DataValidation(type=kind, operator="between", formula1=str(f.get("min") or 0), formula2=str(f["max"]), allow_blank=blank)
        else:
            dv = DataValidation(type=kind, operator="greaterThanOrEqual", formula1=str(f.get("min") or 0), allow_blank=blank)
    elif t in ("date", "datetime"):
        dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(2015,1,1)", allow_blank=blank)
    else:
        return None
    dv.showErrorMessage = True
    dv.errorTitle = f["header"]
    dv.error = f"Choose one of: {', '.join(f['values'])}" if f.get("values") else f"Enter a valid {t}"
    return dv


def build_workbook(kind_key: str, rows: list[dict], about: dict[str, str]) -> bytes:
    kind = KINDS.get(kind_key)
    if not kind:
        raise HttpError(404, "Unknown workbook type.")
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    fields = kind["fields"]
    ws.append([f["header"] + (" *" if f.get("required") else "") for f in fields])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2A2420")
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    for r in rows:
        ws.append([r.get(f["key"]) for f in fields])
    last = max(len(rows) + 500, 1000)
    for i, f in enumerate(fields, start=1):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = f.get("width") or 16
        fmt = "yyyy-mm-dd" if f["type"] == "date" else "yyyy-mm-dd hh:mm" if f["type"] == "datetime" else None
        for row in ws.iter_rows(min_row=2, max_row=len(rows) + 1, min_col=i, max_col=i):
            for cell in row:
                if fmt:
                    cell.number_format = fmt
                if f["type"] == "longtext":
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
        if kind["importable"]:
            dv = _validation(f)
            if dv:
                ws.add_data_validation(dv)
                dv.add(f"{letter}2:{letter}{last + 1}")
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(fields))}1"

    fs = wb.create_sheet("Fields")
    fs.append(["column", "required", "type", "allowed values / range", "description"])
    for c in fs[1]:
        c.font = Font(bold=True)
    for f in fields:
        rng = ", ".join(f["values"]) if f.get("values") else (f"{f.get('min') if f.get('min') is not None else ''} – {f.get('max') if f.get('max') is not None else ''}"
                                                                if f.get("min") is not None or f.get("max") is not None else "")
        fs.append([f["header"], "yes" if f.get("required") else "", f["type"], rng, f.get("description", "")])
    for col, w in zip("ABCDE", (24, 10, 12, 40, 80)):
        fs.column_dimensions[col].width = w

    ab = wb.create_sheet("About")
    lines = [
        ("Workbook", kind["title"]), ("What it holds", kind["description"]),
        ("Generated", datetime.now(timezone.utc).isoformat(timespec="seconds")), ("Schema version", str(SCHEMA_VERSION)),
        ("Import", "Edit the Data sheet, keep the header row, then import it from Data & Reports. Columns marked * are required."
         if kind["importable"] else "This workbook is a report and cannot be imported."),
        *about.items(),
    ]
    for k, v in lines:
        ab.append([k, v])
        ab.cell(row=ab.max_row, column=1).font = Font(bold=True)
    ab.column_dimensions["A"].width = 22
    ab.column_dimensions["B"].width = 100

    meta = wb.create_sheet("_meta")
    meta.append(["kind", kind_key])
    meta.append(["schema_version", SCHEMA_VERSION])
    meta.sheet_state = "veryHidden"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- reading & validation ----------------

def _parse_date(v: Any, with_time: bool) -> str | None:
    d: datetime | None = None
    if isinstance(v, datetime):
        d = v
    elif isinstance(v, date):
        d = datetime(v.year, v.month, v.day)
    elif isinstance(v, (int, float)) and 20000 < v < 80000:
        d = datetime(1899, 12, 30) + timedelta(days=float(v))  # Excel serial date
    else:
        txt = str(v).strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                d = datetime.strptime(txt, fmt)
                break
            except ValueError:
                continue
        if d is None:
            try:
                d = datetime.fromisoformat(txt.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return None
    if d.tzinfo:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d.isoformat(timespec="milliseconds") + "Z" if with_time else d.strftime("%Y-%m-%d")


def _coerce(f: dict, raw: Any) -> tuple[Any, str | None]:
    if raw is None or str(raw).strip() == "":
        return None, (f"{f['header']} is required" if f.get("required") else None)
    t = f["type"]
    if t in ("int", "number"):
        try:
            n = float(raw) if isinstance(raw, (int, float)) else float(str(raw).replace(",", "").replace(" ", "").replace("%", ""))
        except ValueError:
            return None, f"{f['header']} must be a number"
        if t == "int" and not float(n).is_integer():
            return None, f"{f['header']} must be a whole number"
        if f.get("min") is not None and n < f["min"]:
            return None, f"{f['header']} must be ≥ {f['min']}"
        if f.get("max") is not None and n > f["max"]:
            return None, f"{f['header']} must be ≤ {f['max']}"
        return (int(n) if t == "int" else n), None
    if t in ("date", "datetime"):
        d = _parse_date(raw, t == "datetime")
        if not d:
            return None, f"{f['header']} is not a date"
        if d[:10] > (utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"):
            return None, f"{f['header']} is in the future"
        return d, None
    if t == "enum":
        v = str(raw).strip().lower()
        if v not in f["values"]:
            return None, f"{f['header']} must be one of {', '.join(f['values'])}"
        return v, None
    return s(raw, 400000 if t == "longtext" else 2000).strip(), None


def _natural_key(kind: str, d: dict) -> str:
    if kind == "topics":
        return f"{d['brand']}|{norm_keyword(d['primary_keyword'])}"
    if kind == "keywords":
        return f"{d['brand']}|{norm_keyword(d['keyword'])}"
    if kind == "articles":
        return f"{d['brand']}|{d.get('handle') or slugify(d['title'])}"
    if kind == "approvals":
        return f"{d['brand']}|{d['article_handle']}|{d['reviewer_name']}|{d['reviewed_at']}"
    if kind == "gsc_pages":
        return f"{d['brand']}|{d['date']}|{page_path(d['page'])}"
    if kind == "gsc_queries":
        return f"{d['brand']}|{d['period_start']}|{d['period_end']}|{page_path(d['page']) if d.get('page') else ''}|{d['query']}"
    if kind == "ga4_pages":
        return f"{d['brand']}|{d['date']}|{page_path(d['landing_page'])}"
    return json.dumps(d, default=str)


def _exists(kind: str, d: dict) -> bool:
    if kind == "topics":
        return bool(get("SELECT 1 FROM topics WHERE brand_id = ? AND keyword_norm = ?", d["brand"], norm_keyword(d["primary_keyword"])))
    if kind == "keywords":
        return bool(get("SELECT 1 FROM keywords WHERE brand_id = ? AND keyword_norm = ?", d["brand"], norm_keyword(d["keyword"])))
    if kind == "articles":
        return bool(get("SELECT 1 FROM articles WHERE brand_id = ? AND handle = ?", d["brand"], d.get("handle") or slugify(d["title"])))
    if kind == "approvals":
        return bool(get("""SELECT 1 FROM review_notes n JOIN articles a ON a.id = n.article_id WHERE a.brand_id = ? AND a.handle = ?
                           AND n.reviewer_name = ? AND n.created_at = ? AND n.source = 'excel'""", d["brand"], d["article_handle"], d["reviewer_name"], d["reviewed_at"]))
    if kind == "gsc_pages":
        return bool(get("SELECT 1 FROM gsc_page_daily WHERE brand_id = ? AND source = 'excel' AND date = ? AND page = ?", d["brand"], d["date"], page_path(d["page"])))
    if kind == "gsc_queries":
        return bool(get("""SELECT 1 FROM gsc_query_period WHERE brand_id = ? AND source = 'excel' AND start_date = ? AND end_date = ? AND page = ? AND query = ?""",
                        d["brand"], d["period_start"], d["period_end"], page_path(d["page"]) if d.get("page") else "", d["query"]))
    if kind == "ga4_pages":
        return bool(get("SELECT 1 FROM ga4_page_daily WHERE brand_id = ? AND source = 'excel' AND date = ? AND page_path = ?", d["brand"], d["date"], page_path(d["landing_page"])))
    return False


def _age_days(iso: str) -> float:
    return (utcnow() - datetime.fromisoformat(iso.replace("Z", "")[:19] if "T" in iso else iso)).total_seconds() / 86400


def _cross_checks(kind: str, d: dict, errors: list[str], warnings: list[str]) -> None:
    if kind in ("gsc_pages", "gsc_queries") and d.get("clicks") is not None and d.get("impressions") is not None and d["clicks"] > d["impressions"]:
        errors.append("clicks cannot exceed impressions")
    if kind == "ga4_pages" and d["engaged_sessions"] > d["sessions"]:
        errors.append("engaged_sessions cannot exceed sessions")
    if kind == "gsc_queries" and d["period_start"] > d["period_end"]:
        errors.append("period_start is after period_end")
    if kind == "keywords" and d.get("source_date") and _age_days(d["source_date"]) > 180:
        warnings.append("source_date is over 6 months old")
    if d.get("source_timestamp") and _age_days(d["source_timestamp"]) > 30:
        warnings.append("source_timestamp is over 30 days old")
    if kind == "articles":
        a = get("SELECT status FROM articles WHERE brand_id = ? AND handle = ?", d["brand"], d.get("handle") or slugify(d["title"]))
        if a and a["status"] not in ("idea", "draft", "changes_requested"):
            errors.append(f'article is "{a["status"]}" — edit it in the dashboard so review rules apply')
        md = d.get("meta_description")
        if md and (len(md) < 70 or len(md) > 170):
            warnings.append(f"meta_description is {len(md)} characters")
    if kind == "approvals" and not get("SELECT 1 FROM articles WHERE brand_id = ? AND handle = ?", d["brand"], d["article_handle"]):
        errors.append(f'no {d["brand"]} article with handle "{d["article_handle"]}"')


def parse_workbook(kind_key: str, buf: bytes) -> dict:
    kind = KINDS.get(kind_key)
    if not kind or not kind["importable"]:
        raise HttpError(400, "This workbook type cannot be imported.")
    try:
        wb = load_workbook(io.BytesIO(buf), data_only=True)
    except Exception:
        raise HttpError(400, "The file could not be read as an .xlsx workbook.")
    warnings: list[str] = []
    if "_meta" in wb.sheetnames:
        meta_kind = str(wb["_meta"]["B1"].value or "")
        if meta_kind and meta_kind != kind_key:
            raise HttpError(400, f'This workbook is a "{meta_kind}" file, not "{kind_key}".')
    else:
        warnings.append("No template marker found; columns were matched by header name.")
    ws = wb["Data"] if "Data" in wb.sheetnames else wb.worksheets[0]
    header = [str(c.value or "").replace("*", "").strip().lower() for c in ws[1]]
    colmap: dict[int, dict] = {}
    for idx, h in enumerate(header):
        f = next((x for x in kind["fields"] if x["header"].lower() == h or x["key"] == h), None)
        if f:
            colmap[idx] = f
    present = list(colmap.values())
    missing = [f["header"] for f in kind["fields"] if f.get("required") and f not in present]
    if missing:
        raise HttpError(400, f"Missing required columns: {', '.join(missing)}")
    rows: list[dict] = []
    seen: set[str] = set()
    for row_no, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        raw = {colmap[i]["key"]: v for i, v in enumerate(values) if i in colmap}
        if all(v is None or str(v).strip() == "" for v in raw.values()):
            continue
        data: dict[str, Any] = {}
        errors: list[str] = []
        row_warn: list[str] = []
        for f in kind["fields"]:
            if f not in present:
                data[f["key"]] = None
                continue
            val, err = _coerce(f, raw.get(f["key"]))
            data[f["key"]] = val
            if err:
                errors.append(err)
        if not errors:
            _cross_checks(kind_key, data, errors, row_warn)
        key = "" if errors else _natural_key(kind_key, data)
        dup = None
        if key and key in seen:
            dup = "file"
        elif key and _exists(kind_key, data):
            dup = "existing"
        if key:
            seen.add(key)
        rows.append({"row": row_no, "data": data, "errors": errors, "warnings": row_warn, "duplicate": dup, "key": key})
        if len(rows) > 50000:
            raise HttpError(413, "More than 50,000 rows; split the file.")
    return {
        "kind": kind_key, "warnings": warnings,
        "summary": {
            "total": len(rows), "valid": sum(1 for r in rows if not r["errors"]), "invalid": sum(1 for r in rows if r["errors"]),
            "duplicatesInFile": sum(1 for r in rows if r["duplicate"] == "file"),
            "duplicatesExisting": sum(1 for r in rows if r["duplicate"] == "existing"),
            "withWarnings": sum(1 for r in rows if r["warnings"]),
        },
        "rows": rows,
    }


# ---------------- committing ----------------

def commit_import(user: dict, kind_key: str, buf: bytes, filename: str, on_duplicate: str) -> dict:
    parsed = parse_workbook(kind_key, buf)
    inserted = updated = duplicates = 0
    rejected = [r for r in parsed["rows"] if r["errors"]]
    t = now()
    with tx():
        for r in parsed["rows"]:
            if r["errors"]:
                continue
            if r["duplicate"] == "file" or (r["duplicate"] == "existing" and on_duplicate != "update"):
                duplicates += 1
                continue
            res = _write_row(user, kind_key, r["data"], r["duplicate"] == "existing", t)
            inserted += res == "inserted"
            updated += res == "updated"
        run("""INSERT INTO imports (kind, filename, user_id, created_at, rows_total, inserted, updated, duplicates, rejected, errors_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            kind_key, s(filename, 200), user["id"], t, len(parsed["rows"]), inserted, updated, duplicates, len(rejected),
            json.dumps([{"row": r["row"], "errors": r["errors"]} for r in rejected[:200]]))
    audit(user, "data.import", "import", kind_key, "", f"{filename}: {inserted} new, {updated} updated, {duplicates} duplicates skipped, {len(rejected)} rejected")
    return {"inserted": inserted, "updated": updated, "duplicates": duplicates, "rejected": len(rejected), "total": len(parsed["rows"])}


def _write_row(user: dict, kind: str, d: dict, exists: bool, t: str) -> str:
    if kind == "topics":
        norm = norm_keyword(d["primary_keyword"])
        if exists:
            run("""UPDATE topics SET title=?, secondary_keywords=COALESCE(?, secondary_keywords), intent=COALESCE(?, intent), search_volume=COALESCE(?, search_volume),
                     keyword_difficulty=COALESCE(?, keyword_difficulty), volume_source=COALESCE(?, volume_source), notes=COALESCE(?, notes),
                     status=COALESCE(?, status), source_updated_at=?, updated_at=? WHERE brand_id=? AND keyword_norm=?""",
                d["title"], d["secondary_keywords"], d["intent"], d["search_volume"], d["keyword_difficulty"], d["volume_source"], d["notes"],
                d["status"], d["source_timestamp"], t, d["brand"], norm)
            return "updated"
        run("""INSERT INTO topics (brand_id, title, primary_keyword, keyword_norm, secondary_keywords, intent, search_volume, keyword_difficulty, volume_source, notes, status, source, created_by, created_at, updated_at, source_updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?, 'excel', ?,?,?,?)""",
            d["brand"], d["title"], d["primary_keyword"], norm, d["secondary_keywords"] or "", d["intent"] or "informational", d["search_volume"],
            d["keyword_difficulty"], d["volume_source"], d["notes"] or "", d["status"] or "proposed", user["id"], t, t, d["source_timestamp"])
        return "inserted"
    if kind == "keywords":
        run("""INSERT INTO keywords (brand_id, keyword, keyword_norm, search_volume, keyword_difficulty, intent, source_tool, source_date, notes, source, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?, 'excel', ?, ?)
               ON CONFLICT(brand_id, keyword_norm) DO UPDATE SET search_volume=excluded.search_volume, keyword_difficulty=excluded.keyword_difficulty,
                 intent=COALESCE(excluded.intent, intent), source_tool=excluded.source_tool, source_date=excluded.source_date, notes=excluded.notes, updated_at=excluded.updated_at""",
            d["brand"], d["keyword"], norm_keyword(d["keyword"]), d["search_volume"], d["keyword_difficulty"], d["intent"], d["source_tool"], d["source_date"], d["notes"] or "", t, t)
        return "updated" if exists else "inserted"
    if kind == "articles":
        handle = d.get("handle") or slugify(d["title"])
        patch = {"title": d["title"], "handle": handle, **{k: d[k] for k in ("primary_keyword", "meta_title", "meta_description", "tags", "author", "body_html") if d.get(k) is not None}}
        if exists:
            a = get("SELECT id FROM articles WHERE brand_id = ? AND handle = ?", d["brand"], handle)
            save_article(user, a["id"], patch, "Updated from Excel import")
            return "updated"
        create_article(user, d["brand"], patch, "excel", "draft" if d.get("body_html") else "idea")
        return "inserted"
    if kind == "approvals":
        a = get("SELECT id, version FROM articles WHERE brand_id = ? AND handle = ?", d["brand"], d["article_handle"])
        run("INSERT INTO review_notes (article_id, user_id, reviewer_name, kind, note, version, source, created_at) VALUES (?,?,?,?,?,?,?,?)",
            a["id"], user["id"], d["reviewer_name"], f"offline_{d['decision']}", d["note"], a["version"], "excel", d["reviewed_at"])
        return "inserted"
    if kind == "gsc_pages":
        run("""INSERT OR REPLACE INTO gsc_page_daily (brand_id, date, page, clicks, impressions, ctr, position, source, source_timestamp, imported_at) VALUES (?,?,?,?,?,?,?, 'excel', ?, ?)""",
            d["brand"], d["date"], page_path(d["page"]), d["clicks"], d["impressions"], d["clicks"] / d["impressions"] if d["impressions"] else 0, d["position"], d["source_timestamp"], t)
        return "updated" if exists else "inserted"
    if kind == "gsc_queries":
        run("""INSERT OR REPLACE INTO gsc_query_period (brand_id, start_date, end_date, page, query, clicks, impressions, ctr, position, source, source_timestamp, imported_at)
               VALUES (?,?,?,?,?,?,?,?,?, 'excel', ?, ?)""",
            d["brand"], d["period_start"], d["period_end"], page_path(d["page"]) if d.get("page") else "", d["query"], d["clicks"], d["impressions"],
            d["clicks"] / d["impressions"] if d["impressions"] else 0, d["position"], d["source_timestamp"], t)
        return "updated" if exists else "inserted"
    if kind == "ga4_pages":
        run("""INSERT OR REPLACE INTO ga4_page_daily (brand_id, date, page_path, sessions, engaged_sessions, engagement_rate, avg_engagement_seconds, key_events, source, source_timestamp, imported_at)
               VALUES (?,?,?,?,?,?,?,?, 'excel', ?, ?)""",
            d["brand"], d["date"], page_path(d["landing_page"]), d["sessions"], d["engaged_sessions"], d["engaged_sessions"] / d["sessions"] if d["sessions"] else 0,
            d["avg_engagement_seconds"] or 0, d["key_events"] or 0, d["source_timestamp"], t)
        return "updated" if exists else "inserted"
    return "skipped"


# ---------------- exports ----------------

def _dt(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None) if "T" in v else datetime.strptime(v[:10], "%Y-%m-%d")
    except ValueError:
        return None


def export_rows(kind: str, brand: str | None, status: str, frm: str, to: str, q: str) -> list[dict]:
    bw = " AND brand_id = ?" if brand else ""
    ba = [brand] if brand else []
    rng = frm and to
    ra = [frm, to] if rng else []
    if kind == "topics":
        rows = all_rows(f"""SELECT brand_id brand, title, primary_keyword, secondary_keywords, intent, search_volume, keyword_difficulty, volume_source, status, notes,
                            COALESCE(source_updated_at, updated_at) source_timestamp FROM topics WHERE 1=1{bw}{' AND status = ?' if status else ''} ORDER BY brand_id, title""",
                        *ba, *([status] if status else []))
        return [{**r, "source_timestamp": _dt(r["source_timestamp"])} for r in rows]
    if kind == "keywords":
        return [{**r, "source_date": _dt(r["source_date"])} for r in all_rows(
            f"SELECT brand_id brand, keyword, search_volume, keyword_difficulty, intent, source_tool, source_date, notes FROM keywords WHERE 1=1{bw} ORDER BY brand_id, search_volume DESC", *ba)]
    if kind == "articles":
        st = [x for x in status.split(",") if x] if status else []
        rows = all_rows(f"""SELECT brand_id brand, title, handle, primary_keyword, meta_title, meta_description, tags, author, status, shopify_published, live_url url, updated_at
                            FROM articles WHERE 1=1{bw}{f" AND status IN ({','.join('?' for _ in st)})" if st else ''}{' AND title LIKE ?' if q else ''} ORDER BY brand_id, updated_at DESC""",
                        *ba, *st, *([f"%{q}%"] if q else []))
        return [{**r, "live": "yes" if r["shopify_published"] else "no", "updated_at": _dt(r["updated_at"])} for r in rows]
    if kind == "approvals":
        rows = all_rows(f"""SELECT a.brand_id brand, a.handle article_handle, n.reviewer_name, n.kind decision, n.note, n.created_at reviewed_at
                            FROM review_notes n JOIN articles a ON a.id = n.article_id WHERE n.kind != 'submitted'{' AND a.brand_id = ?' if brand else ''} ORDER BY n.created_at DESC""", *ba)
        return [{**r, "decision": "recommend_approve" if r["decision"] == "approved" else r["decision"].replace("offline_", ""), "reviewed_at": _dt(r["reviewed_at"])} for r in rows]
    if kind == "gsc_pages":
        return [{**r, "date": _dt(r["date"]), "source_timestamp": _dt(r["source_timestamp"])} for r in all_rows(
            f"""SELECT brand_id brand, date, page, clicks, impressions, position, source_timestamp FROM gsc_page_daily WHERE source != 'demo'{bw}{' AND date BETWEEN ? AND ?' if rng else ''}
                ORDER BY brand_id, date, page LIMIT 200000""", *ba, *ra)]
    if kind == "gsc_queries":
        return [{**r, "period_start": _dt(r["period_start"]), "period_end": _dt(r["period_end"]), "source_timestamp": _dt(r["source_timestamp"])} for r in all_rows(
            f"""SELECT brand_id brand, start_date period_start, end_date period_end, page, query, clicks, impressions, position, source_timestamp
                FROM gsc_query_period WHERE source != 'demo'{bw} ORDER BY brand_id, clicks DESC LIMIT 200000""", *ba)]
    if kind == "ga4_pages":
        return [{**r, "date": _dt(r["date"]), "source_timestamp": _dt(r["source_timestamp"])} for r in all_rows(
            f"""SELECT brand_id brand, date, page_path landing_page, sessions, engaged_sessions, avg_engagement_seconds, key_events, source_timestamp
                FROM ga4_page_daily WHERE source != 'demo'{bw}{' AND date BETWEEN ? AND ?' if rng else ''} ORDER BY brand_id, date LIMIT 200000""", *ba, *ra)]
    if kind == "audit":
        return [{**r, "ts": _dt(r["ts"])} for r in all_rows(
            f"""SELECT ts, user_email, action, brand_id, entity_type || ' ' || entity_id entity, summary FROM audit_log WHERE 1=1{bw}{' AND substr(ts,1,10) BETWEEN ? AND ?' if rng else ''}
                ORDER BY id DESC LIMIT 100000""", *ba, *ra)]
    raise HttpError(404, "Unknown export.")


# ---------------- data health ----------------

def data_health() -> dict:
    flags: list[dict] = []

    def n(sql: str) -> int:
        return int((get(sql) or {}).get("n") or 0)

    def push(sev: str, area: str, count: int, message: str, link: str | None = None) -> None:
        if count:
            flags.append({"severity": sev, "area": area, "count": count, "message": message, "link": link})

    push("warning", "Topics", n("SELECT COUNT(*) n FROM topics WHERE status IN ('proposed','validated') AND search_volume IS NULL"), "topics have no search-volume data", "/topics?missing=volume")
    push("warning", "Keywords", n("SELECT COUNT(*) n FROM keywords WHERE source_date < date('now','-180 days')"), "keyword rows are more than 6 months old", "/topics?tab=keywords")
    push("warning", "Articles", n("SELECT COUNT(*) n FROM articles WHERE status IN ('draft','idea','changes_requested') AND updated_at < strftime('%Y-%m-%dT%H:%M:%fZ','now','-21 days')"),
         "drafts untouched for 3+ weeks", "/blogs?status=draft,idea,changes_requested&sort=updated&dir=asc")
    push("warning", "Reviews", n("SELECT COUNT(*) n FROM articles WHERE status = 'in_review' AND updated_at < strftime('%Y-%m-%dT%H:%M:%fZ','now','-5 days')"),
         "articles waiting for review for 5+ days", "/blogs?status=in_review")
    push("warning", "Articles", n("SELECT COUNT(*) n FROM articles WHERE shopify_published = 1 AND meta_description = ''"), "live articles have no meta description in the dashboard", "/blogs?live=1")
    push("info", "Articles", n("SELECT COUNT(*) n FROM articles WHERE status IN ('approved','in_review') AND image_url = ''"), "articles in review or approved have no featured image", "/blogs?status=in_review,approved")
    for table, label, link in (("gsc_page_daily", "Search Console", "/analytics"), ("ga4_page_daily", "GA4", "/analytics?tab=ga4")):
        for b in ("ridhi", "cpc"):
            api = get(f"SELECT 1 FROM {table} WHERE brand_id = ? AND source = 'api' LIMIT 1", b)
            ex = get(f"SELECT MAX(date) mx FROM {table} WHERE brand_id = ? AND source = 'excel'", b)
            if not api and ex and ex["mx"] and _age_days(ex["mx"]) > 14:
                flags.append({"severity": "warning", "area": label, "count": 1, "link": link,
                              "message": f"{'Ridhi' if b == 'ridhi' else 'CPC'} imported {label} data ends {ex['mx']}; import a newer export"})
    imports = all_rows("SELECT i.*, u.name user_name FROM imports i LEFT JOIN users u ON u.id = i.user_id ORDER BY i.id DESC LIMIT 25")
    return {"flags": flags, "imports": imports}
