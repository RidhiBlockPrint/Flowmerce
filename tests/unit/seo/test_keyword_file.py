"""The Ridhi keyword workbook reader: read-only, numbers taken only from the sheet, nothing invented."""
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from flowmerce.modules.seo.services import keyword_file  # noqa: E402


def make_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Ridhi keyword data collection - test"])
    db = wb.create_sheet("Keyword DB")
    db.append(["id", "keyword", "topic", "cluster", "intent", "gsc_clicks", "gsc_impressions", "gsc_avg_position",
               "search_volume", "keyword_difficulty", "recommended_action", "confidence", "notes"])
    db.append(["K01", "block print quilt", "T1", "Quilts", "Commercial", "40", "2369", "8.12",
               "1,300 (Semrush US 2026-10-19)", "4 (Semrush US 2026-10-19)", "New blog", "Medium", "note"])
    db.append(["K02", "quilt king", None, "Quilts", None, None, None, None, None, None, None, None, None])
    db.append([None, None])
    opp = wb.create_sheet("Opportunities")
    opp.append(["id", "keyword"])
    opp.append(["K01", "block print quilt"])
    new = wb.create_sheet("New keywords")
    new.append(["id", "keyword"])
    new.append(["K02", "quilt king"])
    wb.save(path)


def test_reads_rows_and_flags_without_inventing_values(tmp_path, monkeypatch):
    f = tmp_path / "ridhi-keyword-db-2026-10-30.xlsx"
    make_workbook(f)
    monkeypatch.setattr(keyword_file, "find_file", lambda: f)
    data = keyword_file.load()
    assert data["found"] and data["brand"] == "ridhi" and data["error"] is None
    first, second = data["rows"]
    assert (first["search_volume"], first["keyword_difficulty"], first["gsc_clicks"]) == (1300, 4, 40)
    assert first["gsc_avg_position"] == 8.12 and first["opportunity"] and not first["new"]
    assert second["search_volume"] is None and second["gsc_clicks"] is None and second["new"]
    assert data["clusters"] == ["Quilts"]


def test_missing_file_is_reported_not_faked(monkeypatch):
    monkeypatch.setattr(keyword_file, "find_file", lambda: None)
    data = keyword_file.load()
    assert data["found"] is False and data["rows"] == []


def test_source_file_is_not_modified(tmp_path, monkeypatch):
    f = tmp_path / "ridhi-keyword-db-2026-10-30.xlsx"
    make_workbook(f)
    before = (f.stat().st_mtime_ns, f.read_bytes())
    monkeypatch.setattr(keyword_file, "find_file", lambda: f)
    keyword_file.load()
    assert (f.stat().st_mtime_ns, f.read_bytes()) == before
