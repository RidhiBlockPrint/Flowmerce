from __future__ import annotations

import json

from ..config import BRAND_IDS, BrandConfig, config
from ..db import get, now, run
from ..integrations import shopify
from ..integrations.google import ga4_configured, gsc_configured
from ..util import s, safe_json

# Editable, non-secret brand settings. Credentials are environment-only and not part of this.
DEFAULTS = {
    "ridhi": {
        "voice": "Warm, knowledgeable and craft-proud; explains hand block printing plainly; practical styling and care advice.",
        "audience": "Home decor shoppers in the US and UK looking for handmade cotton table linen, bedding and cushions.",
        "avoid": "Hype, invented statistics, competitor names, medical or eco claims that are not verified.",
        "defaultAuthor": "Ridhi Block Print",
        "topicsPerRun": 5, "draftsPerRun": 1,
        "researchFocus": "Table linen, bedding and seasonal hosting with block-print textiles.",
    },
    "cpc": {
        "voice": "Elegant, inviting and seasonal; focuses on tablescapes, gatherings and gifting with block-printed cotton.",
        "audience": "Hosts and home decor shoppers in the US who buy tablecloths, napkins, placemats and cushions.",
        "avoid": "Hype, invented statistics, competitor names, discount claims not given by the team.",
        "defaultAuthor": "Cotton Print Club",
        "topicsPerRun": 5, "draftsPerRun": 1,
        "researchFocus": "Holiday and seasonal tablescapes, formal table settings, bundles and gifting.",
    },
}


def brand(bid: str) -> BrandConfig:
    return config.brands[bid]


def brand_settings(bid: str) -> dict:
    row = get("SELECT settings_json FROM brand_settings WHERE brand_id = ?", bid)
    return {**DEFAULTS[bid], **safe_json(row["settings_json"] if row else None, {})}


def _clamp(v: object, d: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, round(float(v))))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return d


def update_brand_settings(bid: str, patch: dict, user_id: int) -> dict:
    cur = brand_settings(bid)
    nxt = {
        "voice": s(patch["voice"], 1000) if "voice" in patch else cur["voice"],
        "audience": s(patch["audience"], 1000) if "audience" in patch else cur["audience"],
        "avoid": s(patch["avoid"], 1000) if "avoid" in patch else cur["avoid"],
        "defaultAuthor": s(patch["defaultAuthor"], 120) if "defaultAuthor" in patch else cur["defaultAuthor"],
        "researchFocus": s(patch["researchFocus"], 500) if "researchFocus" in patch else cur["researchFocus"],
        "topicsPerRun": _clamp(patch.get("topicsPerRun"), cur["topicsPerRun"], 1, 15) if "topicsPerRun" in patch else cur["topicsPerRun"],
        "draftsPerRun": _clamp(patch.get("draftsPerRun"), cur["draftsPerRun"], 1, 5) if "draftsPerRun" in patch else cur["draftsPerRun"],
    }
    run("""INSERT INTO brand_settings (brand_id, settings_json, updated_at, updated_by) VALUES (?,?,?,?)
           ON CONFLICT(brand_id) DO UPDATE SET settings_json=excluded.settings_json, updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
        bid, json.dumps(nxt), now(), user_id)
    return nxt


def brand_public(bid: str) -> dict:
    """What the browser may know about a brand: no tokens, only whether each piece is set up."""
    b = config.brands[bid]
    return {
        "id": b.id, "name": b.name, "short": b.short,
        "storefrontUrl": f"https://{b.storefront_domain}",
        "blogUrl": f"https://{b.storefront_domain}/blogs/{b.blog_handle}",
        "shopDomain": b.shop_domain, "blogHandle": b.blog_handle, "gscProperty": b.gsc_property,
        "ga4PropertyId": f"…{b.ga4_property_id[-4:]}" if b.ga4_property_id else "",
        "configured": {"shopifyAdmin": shopify.configured(b), "gsc": gsc_configured(b), "ga4": ga4_configured(b)},
        "settings": brand_settings(bid),
    }


def all_brands() -> list[dict]:
    return [brand_public(b) for b in BRAND_IDS]
