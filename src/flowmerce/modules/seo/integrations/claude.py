"""Claude (Anthropic Messages API) for topic research and first drafts.

It runs the requests this dashboard makes, and each one is logged as a workflow run. It has no view of
Claude agents running elsewhere; those can report progress to POST /api/hooks/workflow.

Output is constrained to JSON with structured outputs (output_config.format). Server-side refusal
fallbacks are on by default (CLAUDE_FALLBACKS=false turns them off)."""
from __future__ import annotations

import json

from ..config import BrandConfig, config
from ..util import HttpError

_client = None


def configured() -> bool:
    return bool(config.anthropic_api_key)


def _get_client():
    global _client
    if not configured():
        raise HttpError(412, "ANTHROPIC_API_KEY is not set on the server.", "pending_setup")
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    return _client


def _structured(system: str, prompt: str, schema: dict, effort: str) -> tuple[dict, str]:
    import anthropic
    client = _get_client()
    extra: dict = {"output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}}}
    params = dict(model=config.claude_model, max_tokens=32000, thinking={"type": "adaptive"}, system=system,
                  messages=[{"role": "user", "content": prompt}])
    try:
        if config.claude_fallbacks:
            extra["fallbacks"] = "default"
            with client.beta.messages.stream(**params, betas=["server-side-fallback-2026-07-01"], extra_body=extra) as stream:
                message = stream.get_final_message()
        else:
            with client.messages.stream(**params, extra_body=extra) as stream:
                message = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise RuntimeError("Claude rejected the API key (401). Check ANTHROPIC_API_KEY.") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("Claude rate limit reached (429). Retry in a minute.") from e
    except anthropic.BadRequestError as e:
        raise RuntimeError(f"Claude rejected the request (400): {e.message}") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError("Could not reach the Claude API.") from e
    if message.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request (refusal). Rephrase the topic and retry.")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("Claude ran out of output tokens before finishing. Retry or narrow the request.")
    text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    try:
        return json.loads(text), message.model
    except ValueError as e:
        raise RuntimeError("Claude returned output that is not valid JSON.") from e


def _brand_system(b: BrandConfig, v: dict) -> str:
    lines = [
        f"You are the SEO content strategist for {b.name} ({b.storefront_domain}), an online store selling hand block-printed cotton home textiles made by artisans in India.",
        f"Brand voice: {v['voice']}" if v.get("voice") else "",
        f"Audience: {v['audience']}" if v.get("audience") else "",
        f"Never: {v['avoid']}" if v.get("avoid") else "",
        "Write for people first and search engines second. Do not invent statistics, awards, certifications, prices, shipping promises or customer quotes. If a fact about the store is not given to you, leave it out.",
    ]
    return "\n".join(x for x in lines if x)


def research_topics(b: BrandConfig, v: dict, existing_titles: list[str], products: list[str], queries: list[str], count: int, focus: str = "") -> tuple[dict, str]:
    schema = {
        "type": "object", "additionalProperties": False, "required": ["topics"],
        "properties": {"topics": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["title", "primary_keyword", "secondary_keywords", "intent", "rationale"],
            "properties": {
                "title": {"type": "string"}, "primary_keyword": {"type": "string"},
                "secondary_keywords": {"type": "array", "items": {"type": "string"}},
                "intent": {"type": "string", "enum": ["informational", "commercial", "transactional", "navigational"]},
                "rationale": {"type": "string"},
            }}}},
    }
    parts = [
        f"Propose {count} new blog topics for {b.name}.",
        f"Focus: {focus}" if focus else "",
        "Each topic needs one primary keyword a shopper would actually type, 2–5 secondary keywords, the search intent, and one or two sentences on why it fits this store.",
        "Do not repeat or closely overlap these existing articles:",
        *[f"- {t}" for t in existing_titles[:80]],
        ("\nProducts the store sells (link-worthy):\n" + "\n".join(f"- {p}" for p in products[:60])) if products else "",
        ("\nSearch queries that already bring visitors to the blog (from Search Console):\n" + "\n".join(f"- {q}" for q in queries[:40])) if queries else "",
        "You have no keyword-volume data: do not state or guess search volumes.",
    ]
    return _structured(_brand_system(b, v), "\n".join(p for p in parts if p), schema, "medium")


def generate_draft(b: BrandConfig, v: dict, topic: dict, links: list[dict]) -> tuple[dict, str]:
    fields = ["title", "handle", "meta_title", "meta_description", "summary_html", "body_html", "tags", "image_alt"]
    schema = {
        "type": "object", "additionalProperties": False, "required": fields,
        "properties": {**{f: {"type": "string"} for f in fields if f != "tags"}, "tags": {"type": "array", "items": {"type": "string"}}},
    }
    parts = [
        f"Write a complete blog article for {b.name}.",
        f"Working title: {topic['title']}",
        f"Primary keyword: {topic['primary_keyword']}",
        f"Secondary keywords: {topic['secondary_keywords']}" if topic.get("secondary_keywords") else "",
        f"Search intent: {topic['intent']}",
        f"Editor notes: {topic['notes']}" if topic.get("notes") else "",
        "",
        "Requirements:",
        "- body_html: 1,200–1,800 words of clean HTML using only <h2>, <h3>, <p>, <ul>, <ol>, <li>, <strong>, <em>, <a>, <blockquote>. No <h1> (the theme renders the title), no inline styles, no scripts, no images.",
        "- Use the primary keyword in the first paragraph and in at least one <h2>, naturally.",
        "- Add 2–4 internal links, chosen only from the list below, with descriptive anchor text. Use the URLs exactly as given.",
        "- End with a short FAQ section (<h2>Frequently asked questions</h2> with 3–4 <h3> questions).",
        "- meta_title at most 60 characters; meta_description 140–155 characters; handle is a short lowercase-hyphenated URL slug.",
        "- summary_html: one or two sentences in a <p> for the blog listing.",
        "- tags: 3–6 short tags. image_alt: alt text for a featured image of the main product type.",
        "",
        "Internal link targets:",
        *[f"- {l['title']}: {l['url']}" for l in links[:40]],
    ]
    return _structured(_brand_system(b, v), "\n".join(parts), schema, "high")


def ping() -> dict:
    m = _get_client().models.retrieve(config.claude_model)
    return {"model": m.id}
