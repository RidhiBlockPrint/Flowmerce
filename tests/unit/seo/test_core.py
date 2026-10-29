from datetime import datetime, timedelta, timezone

import pytest

from flowmerce.modules.seo.auth import hash_password, verify_password
from flowmerce.modules.seo.db import get
from flowmerce.modules.seo.integrations.shopify_public import parse_atom
from flowmerce.modules.seo.permissions import can
from flowmerce.modules.seo.services import articles, publishing
from flowmerce.modules.seo.services.analytics import gsc_report
from flowmerce.modules.seo.services.demo import clear_demo, load_demo
from flowmerce.modules.seo.services.excel import build_workbook, commit_import, parse_workbook
from flowmerce.modules.seo.util import HttpError, norm_keyword, sanitize_html, similarity


def test_sanitizer_strips_script_and_keeps_markup():
    out = sanitize_html('<h2 onclick="x()">Hi</h2><script>alert(1)</script><p>Text <a href="javascript:alert(1)">bad</a> '
                        '<a href="/products/a" target="_blank">ok</a></p><iframe src="x"></iframe><img src="https://cdn/x.jpg" onerror="y()" alt="A">')
    for bad in ("script", "onclick", "onerror", "javascript:", "iframe"):
        assert bad not in out
    assert "<h2>Hi</h2>" in out
    assert '<a href="/products/a" target="_blank" rel="noopener">ok</a>' in out
    assert '<img src="https://cdn/x.jpg" alt="A" />' in out


def test_keyword_normalisation_and_overlap():
    assert norm_keyword("  Block-Print   Tablecloth!") == "block print tablecloth"
    assert similarity("How to wash block print tablecloths", "Washing block print tablecloths guide") > 0.3
    assert similarity("Christmas tablescape ideas", "Bedding care") == 0


def test_role_permissions():
    assert can("admin", "publish:authorize") and can("reviewer", "publish:authorize")
    assert not can("reviewer", "article:write")
    assert not can("seo_manager", "publish:authorize")
    assert can("seo_manager", "publish:request") and not can("seo_manager", "users:manage")


def test_password_hashing():
    h = hash_password("a very long password")
    assert verify_password("a very long password", h)
    assert not verify_password("wrong password here", h)


def test_article_lifecycle(users):
    m, r = users["seo_manager"], users["reviewer"]
    a = articles.create_article(m, "ridhi", {"title": "Caring for block print linen", "primary_keyword": "block print care"}, "app", "idea")
    assert a["status"] == "idea" and a["version"] == 1
    with pytest.raises(HttpError, match="body"):
        articles.submit_for_review(m, a["id"])
    v2 = articles.save_article(m, a["id"], {"body_html": "<p>Wash cold.</p><script>x</script>", "meta_description": "How to care for block print linen."})
    assert v2["version"] == 2 and v2["status"] == "draft" and "script" not in v2["body_html"]
    assert len(articles.list_revisions(a["id"])) == 2
    with pytest.raises(HttpError, match="version 2"):
        articles.save_article(m, a["id"], {"title": "x", "expected_version": 1})
    articles.submit_for_review(m, a["id"])
    with pytest.raises(HttpError, match="changed"):
        articles.review_article(r, a["id"], "approve", 1, "")
    with pytest.raises(HttpError, match="Say what"):
        articles.review_article(r, a["id"], "request_changes", 2, "")
    ok = articles.review_article(r, a["id"], "approve", 2, "Looks good")
    assert ok["status"] == "approved" and ok["approved_hash"] == ok["content_hash"]
    req = publishing.request_publish(m, a["id"], "publish_now", None, "")
    assert req["status"] == "pending"
    edited = articles.save_article(m, a["id"], {"title": "Caring for hand block print linen"})
    assert edited["status"] == "draft" and edited["approved_hash"] != edited["content_hash"]
    assert get("SELECT status FROM publish_requests WHERE id = ?", req["id"])["status"] == "cancelled"
    with pytest.raises(HttpError, match="reviewer-approved"):
        publishing.request_publish(m, a["id"], "publish_now", None, "")


def test_publishing_guardrails(users):
    m, r = users["seo_manager"], users["reviewer"]
    a = articles.create_article(m, "cpc", {"title": "Formal table settings", "primary_keyword": "formal table setting", "body_html": "<p>Body</p>", "meta_description": "Meta"})
    articles.submit_for_review(m, a["id"])
    articles.review_article(r, a["id"], "approve", a["version"], "")
    req = publishing.request_publish(m, a["id"], "publish_now", None, "please")
    with pytest.raises(HttpError, match="Type PUBLISH"):
        publishing.authorize_request(r, req["id"], "publish", "")
    with pytest.raises(HttpError, match="Someone other than the requester"):
        publishing.authorize_request(m, req["id"], "PUBLISH", "")
    with pytest.raises(HttpError) as e:  # ALLOW_LIVE_PUBLISH is not set: refused before any Shopify call
        publishing.authorize_request(r, req["id"], "PUBLISH", "")
    assert e.value.status == 423
    assert get("SELECT status FROM publish_requests WHERE id = ?", req["id"])["status"] == "pending"
    assert get("SELECT shopify_published FROM articles WHERE id = ?", a["id"])["shopify_published"] == 0
    publishing.reject_request(r, req["id"], "Not this week")
    assert get("SELECT status FROM articles WHERE id = ?", a["id"])["status"] == "approved"
    soon = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    with pytest.raises(HttpError, match="10 minutes"):
        publishing.request_publish(m, a["id"], "schedule", soon, "")


def test_public_atom_feed_parsing():
    xml = """<feed><entry><id>x</id><published>2026-06-10T05:26:34-07:00</published><updated>2026-06-10T05:55:58-07:00</updated>
      <link rel="alternate" type="text/html" href="https://cottonprintclub.com/blogs/blogs/formal-table"/><title>Can I &amp; should I?</title>
      <author><name>Cotton Print Club</name></author><category term="Tablecloths"/>
      <summary type="html"><![CDATA[<p>Yes.</p><p><a class="read-more" href="x">More</a></p>]]></summary><content type="html">&lt;p&gt;Body&lt;/p&gt;</content></entry></feed>"""
    [e] = parse_atom(xml)
    assert e["handle"] == "formal-table" and e["title"] == "Can I & should I?" and e["author"] == "Cotton Print Club"
    assert e["body_html"] == "<p>Body</p>" and e["summary_html"] == "<p>Yes.</p>" and e["tags"] == ["Tablecloths"]


def test_excel_round_trip_validation_and_duplicates(users):
    today = datetime.now()
    buf = build_workbook("keywords", [
        {"brand": "ridhi", "keyword": "block print tablecloth", "search_volume": 1900, "keyword_difficulty": 22, "source_tool": "Semrush", "source_date": today},
        {"brand": "ridhi", "keyword": "Block-Print Tablecloth", "search_volume": 1900, "source_tool": "Semrush", "source_date": today},
        {"brand": "nope", "keyword": "x", "search_volume": -5, "source_tool": "Semrush", "source_date": today},
    ], {})
    p = parse_workbook("keywords", buf)
    assert (p["summary"]["total"], p["summary"]["valid"], p["summary"]["duplicatesInFile"]) == (3, 2, 1)
    bad = next(r for r in p["rows"] if r["errors"])
    assert any("brand" in e for e in bad["errors"]) and any("search_volume" in e for e in bad["errors"])
    res = commit_import(users["seo_manager"], "keywords", buf, "kw.xlsx", "skip")
    assert (res["inserted"], res["duplicates"], res["rejected"]) == (1, 1, 1)
    assert parse_workbook("keywords", buf)["summary"]["duplicatesExisting"] == 1
    with pytest.raises(HttpError, match="keywords"):
        parse_workbook("gsc_pages", buf)


def test_excel_gsc_import_feeds_analytics(users):
    d = datetime.now() - timedelta(days=5)
    buf = build_workbook("gsc_pages", [
        {"brand": "cpc", "date": d, "page": "https://cottonprintclub.com/blogs/blogs/formal-table", "clicks": 12, "impressions": 300, "position": 7.2, "source_timestamp": datetime.now()},
        {"brand": "cpc", "date": d, "page": "/blogs/blogs/other", "clicks": 50, "impressions": 10, "position": 3, "source_timestamp": datetime.now()},
    ], {})
    r = commit_import(users["seo_manager"], "gsc_pages", buf, "gsc.xlsx", "skip")
    assert (r["inserted"], r["rejected"]) == (1, 1)
    day = d.strftime("%Y-%m-%d")
    rep = gsc_report("cpc", day, day)
    assert rep["source"]["kind"] == "excel" and rep["totals"]["clicks"] == 12


def test_demo_never_overrides_real_data(users):
    load_demo(users["admin"])
    day = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    assert gsc_report("cpc", day, day)["source"]["kind"] == "excel"
    assert gsc_report("ridhi", day, day)["source"]["kind"] == "demo"
    clear_demo(users["admin"])
    assert gsc_report("ridhi", day, day)["source"]["kind"] is None
