"""Shopify Admin GraphQL API, one store per brand.

Needs a custom-app Admin API access token (shpat_…) with scopes read_content, write_content and
read_products, set as RIDHI_SHOPIFY_ADMIN_TOKEN / CPC_SHOPIFY_ADMIN_TOKEN. It never leaves the server.

Writes are deliberately narrow: create_hidden_draft() always sends isPublished: false, and
update_hidden_draft() first reads the article and refuses if it is live. The only function that can
make an article visible is publish_article(), called by services/publishing.py after its own checks."""
from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import BrandConfig, config
from ..util import HttpError

ARTICLE_FIELDS = """
  id title handle body summary tags isPublished publishedAt updatedAt
  author { name }
  image { url altText }
  seoTitle: metafield(namespace: "global", key: "title_tag") { value }
  seoDescription: metafield(namespace: "global", key: "description_tag") { value }
"""


def configured(b: BrandConfig) -> bool:
    return bool(b.admin_token and b.shop_domain)


def _gql(b: BrandConfig, query: str, variables: dict | None = None) -> dict:
    if not configured(b):
        raise HttpError(412, f"Shopify Admin API is not set up for {b.name}.", "pending_setup")
    url = f"https://{b.shop_domain}/admin/api/{config.shopify_api_version}/graphql.json"
    for attempt in range(4):
        res = httpx.post(url, json={"query": query, "variables": variables or {}},
                         headers={"X-Shopify-Access-Token": b.admin_token}, timeout=30)
        if res.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        if res.status_code in (401, 403):
            raise RuntimeError(f"Shopify {res.status_code}: the access token for {b.name} was refused or lacks a scope "
                               "(needs read_content, write_content, read_products).")
        if res.status_code >= 300:
            raise RuntimeError(f"Shopify {res.status_code}: {res.text[:300]}")
        data = res.json()
        errors = data.get("errors") or []
        if any((e.get("extensions") or {}).get("code") == "THROTTLED" for e in errors):
            time.sleep(2 * (attempt + 1))
            continue
        if errors:
            raise RuntimeError("Shopify: " + "; ".join(e.get("message", "") for e in errors))
        return data["data"]
    raise RuntimeError("Shopify kept rate-limiting the request; try again shortly.")


def shop_info(b: BrandConfig) -> dict:
    return _gql(b, "{ shop { name myshopifyDomain primaryDomain { url } } }")["shop"]


def find_blog(b: BrandConfig) -> dict:
    nodes = _gql(b, "{ blogs(first: 50) { nodes { id handle title } } }")["blogs"]["nodes"]
    blog = next((n for n in nodes if n["handle"] == b.blog_handle), nodes[0] if nodes else None)
    if not blog:
        raise RuntimeError(f"No blog exists on {b.name}'s store. Create one in Shopify → Online Store → Blog posts.")
    return blog


def list_articles(b: BrandConfig, blog_id: str) -> list[dict]:
    out: list[dict] = []
    after = None
    for _ in range(40):
        d = _gql(b, f"""query($id: ID!, $after: String) {{
          blog(id: $id) {{ articles(first: 50, after: $after) {{ nodes {{ {ARTICLE_FIELDS} }} pageInfo {{ hasNextPage endCursor }} }} }}
        }}""", {"id": blog_id, "after": after})
        conn = (d.get("blog") or {}).get("articles")
        if not conn:
            break
        out.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        after = conn["pageInfo"]["endCursor"]
    return out


def get_article(b: BrandConfig, article_id: str) -> dict | None:
    return _gql(b, f"query($id: ID!) {{ article(id: $id) {{ {ARTICLE_FIELDS} }} }}", {"id": article_id})["article"]


def list_products(b: BrandConfig) -> list[dict]:
    out: list[dict] = []
    after = None
    for _ in range(20):
        d = _gql(b, """query($after: String) {
          products(first: 100, after: $after, query: "status:active") {
            nodes { handle title productType onlineStoreUrl featuredMedia { preview { image { url } } } }
            pageInfo { hasNextPage endCursor }
          }
        }""", {"after": after})
        for p in d["products"]["nodes"]:
            img = (((p.get("featuredMedia") or {}).get("preview") or {}).get("image") or {}).get("url", "")
            out.append({"handle": p["handle"], "title": p["title"], "type": p.get("productType") or "", "image": img,
                        "url": p.get("onlineStoreUrl") or f"https://{b.storefront_domain}/products/{p['handle']}"})
        if not d["products"]["pageInfo"]["hasNextPage"]:
            break
        after = d["products"]["pageInfo"]["endCursor"]
    return out


def _article_input(a: dict) -> dict:
    metafields = []
    if a.get("meta_title"):
        metafields.append({"namespace": "global", "key": "title_tag", "type": "single_line_text_field", "value": a["meta_title"]})
    if a.get("meta_description"):
        metafields.append({"namespace": "global", "key": "description_tag", "type": "multi_line_text_field", "value": a["meta_description"]})
    out: dict[str, Any] = {
        "title": a["title"], "handle": a["handle"], "body": a["body"], "summary": a.get("summary") or None,
        "tags": a.get("tags", []), "author": {"name": a.get("author") or "Editorial Team"},
    }
    if a.get("image_url"):
        out["image"] = {"url": a["image_url"], "altText": a.get("image_alt") or a["title"]}
    if metafields:
        out["metafields"] = metafields
    return out


def _check(m: dict, what: str) -> dict:
    if m.get("userErrors"):
        raise RuntimeError(f"Shopify rejected the {what}: " + "; ".join(
            f"{'.'.join(e.get('field') or [])} {e['message']}".strip() for e in m["userErrors"]))
    if not m.get("article"):
        raise RuntimeError(f"Shopify returned no article for the {what}.")
    return m["article"]


_CREATE = """mutation($article: ArticleCreateInput!) {
  articleCreate(article: $article) { article { id handle isPublished publishedAt } userErrors { field message } } }"""
_UPDATE = """mutation($id: ID!, $article: ArticleUpdateInput!) {
  articleUpdate(id: $id, article: $article) { article { id handle isPublished publishedAt } userErrors { field message } } }"""


def create_hidden_draft(b: BrandConfig, blog_id: str, a: dict) -> dict:
    """Create the article hidden. isPublished is hard-coded False."""
    d = _gql(b, _CREATE, {"article": {**_article_input(a), "blogId": blog_id, "isPublished": False}})
    return _check(d["articleCreate"], "draft")


def update_hidden_draft(b: BrandConfig, article_id: str, a: dict) -> dict:
    """Update an article that is still hidden. Refuses when it is live, so a draft save can never
    change what customers see."""
    current = get_article(b, article_id)
    if not current:
        raise RuntimeError("The Shopify article no longer exists. It may have been deleted in Shopify admin.")
    if current["isPublished"]:
        raise HttpError(409, "This article is live on the storefront. Changes to live content go through a publish request.", "live_article")
    d = _gql(b, _UPDATE, {"id": article_id, "article": {**_article_input(a), "isPublished": False}})
    return _check(d["articleUpdate"], "draft update")


def publish_article(b: BrandConfig, blog_id: str, article_id: str | None, a: dict, publish_date: str | None) -> dict:
    """Make an article visible now, at a future time, or replace a live article's content.
    Called only by services/publishing.py."""
    visibility: dict[str, Any] = {"isPublished": True}
    if publish_date:
        visibility["publishDate"] = publish_date
    if article_id:
        d = _gql(b, _UPDATE, {"id": article_id, "article": {**_article_input(a), **visibility}})
        return _check(d["articleUpdate"], "publish")
    d = _gql(b, _CREATE, {"article": {**_article_input(a), "blogId": blog_id, **visibility}})
    return _check(d["articleCreate"], "publish")
