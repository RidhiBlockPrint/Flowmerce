from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse


class HttpError(Exception):
    def __init__(self, status: int, message: str, code: str = "error", details: Any = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code
        self.details = details


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:120]


def norm_keyword(s: str) -> str:
    """Lower-case, drop punctuation, collapse spaces: "Block-print  Tablecloth" == "block print tablecloth"."""
    s = re.sub(r"[^\w]+", " ", str(s or "").lower(), flags=re.UNICODE).replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def strip_html(html: str) -> str:
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", str(html or ""), flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


_STOP = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "how", "your", "what", "is", "are", "guide"}


def similarity(a: str, b: str) -> float:
    """Word-set overlap, used to warn when a new topic would compete with an existing article."""
    def words(s: str) -> set[str]:
        return {w for w in norm_keyword(s).split(" ") if len(w) > 2 and w not in _STOP}
    A, B = words(a), words(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    return inter / (len(A) + len(B) - inter)


_ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i", "u", "s", "a", "ul", "ol", "li",
    "blockquote", "img", "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td", "span", "div",
    "code", "pre", "sup", "sub",
}
_ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "th": ["colspan", "rowspan", "scope"],
    "td": ["colspan", "rowspan"],
    "*": ["class"],
}
_DROP_WITH_CONTENT = re.compile(r"<(script|style|iframe|object|embed|noscript|template|form|svg|math)\b[\s\S]*?</\1\s*>", re.I)
_TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>")
_ATTR = re.compile(r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")


def _safe_url(u: str, for_img: bool) -> str | None:
    v = u.strip()
    if re.match(r"^(https?:)?//", v, re.I) or v.startswith("/") or v.startswith("#"):
        return v
    if re.match(r"^mailto:", v, re.I) and not for_img:
        return v
    if not re.match(r"^[a-z][a-z0-9+.-]*:", v, re.I):
        return v
    return None


def sanitize_html(html: str) -> str:
    """Allow-list sanitizer for article HTML. Content ends up on a public storefront, so anything that
    can run script is removed before saving."""
    s = re.sub(r"<!--[\s\S]*?-->", "", str(html or ""))
    s = _DROP_WITH_CONTENT.sub("", s)

    def repl(m: re.Match[str]) -> str:
        tag = m.group(1).lower()
        if tag not in _ALLOWED_TAGS:
            return ""
        if m.group(0).startswith("</"):
            return f"</{tag}>"
        allowed = _ALLOWED_ATTRS.get(tag, []) + _ALLOWED_ATTRS["*"]
        out: list[str] = []
        for a in _ATTR.finditer(m.group(2)):
            name = a.group(1).lower()
            if name not in allowed:
                continue
            val = next((g for g in (a.group(2), a.group(3), a.group(4)) if g is not None), "")
            if name in ("href", "src"):
                ok = _safe_url(val, name == "src")
                if ok is None:
                    continue
                val = ok
            if name == "target" and val != "_blank":
                continue
            out.append(f'{name}="{val.replace(chr(34), "&quot;")}"')
        if tag == "a" and 'target="_blank"' in out and not any(x.startswith("rel=") for x in out):
            out.append('rel="noopener"')
        self_close = tag in ("br", "hr", "img")
        return f"<{tag}{(' ' + ' '.join(out)) if out else ''}{' /' if self_close else ''}>"

    return _TAG.sub(repl, s).strip()


def iso_date(d: date | datetime) -> str:
    return d.strftime("%Y-%m-%d")


def add_days(day: str, n: int) -> str:
    return iso_date(datetime.strptime(day, "%Y-%m-%d") + timedelta(days=n))


def days_between(a: str, b: str) -> int:
    return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (the database stores UTC throughout)."""
    from datetime import timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today() -> str:
    return iso_date(utcnow())


def safe_json(s: str | None, fallback: Any) -> Any:
    try:
        return json.loads(s) if s else fallback
    except (TypeError, ValueError):
        return fallback


def s(v: Any, max_len: int = 100000) -> str:
    if v is None:
        return ""
    return str(v)[:max_len]


def page_path(u: str) -> str:
    """Strip a URL down to the path Search Console and GA4 can be joined on."""
    try:
        p = urlparse(u if "://" in u else "https://x.invalid" + (u if u.startswith("/") else "/" + u)).path
        return p.rstrip("/") or "/"
    except ValueError:
        return u


def parse_iso(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def ms_since(iso: str) -> float:
    from datetime import timezone
    return (datetime.now(timezone.utc) - parse_iso(iso)).total_seconds() * 1000
