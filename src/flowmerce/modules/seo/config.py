"""Server configuration. Every secret is read from the environment (or a local, git-ignored .env file)
and stays on the server: nothing here is sent to the browser except what brand_public() picks out."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("FLOWMERCE_ROOT") or Path(__file__).resolve().parents[4])


def _load_env_file(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines, # comments, optional quotes. Real environment wins."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


_load_env_file(ROOT / ".env")


def env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()


def flag(key: str, default: bool = False) -> bool:
    v = env(key)
    return default if not v else v.lower() in ("1", "true", "yes", "on")


BRAND_IDS = ("ridhi", "cpc")


@dataclass(frozen=True)
class BrandConfig:
    id: str
    name: str
    short: str
    storefront_domain: str
    shop_domain: str
    admin_token: str
    blog_handle: str
    gsc_property: str
    ga4_property_id: str


def _brand(bid: str, prefix: str, name: str, short: str, storefront: str, shop: str, blog: str, gsc: str) -> BrandConfig:
    return BrandConfig(
        id=bid,
        name=env(f"{prefix}_NAME", name),
        short=short,
        storefront_domain=env(f"{prefix}_STOREFRONT_DOMAIN", storefront),
        shop_domain=env(f"{prefix}_SHOPIFY_SHOP", shop),
        admin_token=env(f"{prefix}_SHOPIFY_ADMIN_TOKEN"),
        blog_handle=env(f"{prefix}_SHOPIFY_BLOG_HANDLE", blog),
        gsc_property=env(f"{prefix}_GSC_PROPERTY", gsc),
        ga4_property_id=env(f"{prefix}_GA4_PROPERTY_ID"),
    )


class Config:
    root = ROOT
    port = int(env("PORT", "8787"))
    host = env("HOST", "127.0.0.1")
    data_dir = (ROOT / env("DATA_DIR", "data")).resolve()
    production = env("APP_ENV", env("NODE_ENV")) == "production"
    cookie_secure = flag("COOKIE_SECURE", env("APP_ENV", env("NODE_ENV")) == "production")
    session_hours = int(env("SESSION_HOURS", "12"))

    # Safety switch. Until an admin sets this, the server refuses every request that would make an
    # article visible on a storefront, whoever asks. Hidden Shopify drafts are still allowed.
    allow_live_publish = flag("ALLOW_LIVE_PUBLISH", False)

    shopify_api_version = env("SHOPIFY_API_VERSION", "2025-10")
    public_feed_sync = flag("PUBLIC_FEED_SYNC", True)
    # Relative paths (e.g. secrets/key.json) are taken from the project folder.
    google_service_account_file = str(ROOT / env("GOOGLE_SERVICE_ACCOUNT_FILE")) if env("GOOGLE_SERVICE_ACCOUNT_FILE") else ""
    anthropic_api_key = env("ANTHROPIC_API_KEY")
    claude_model = env("CLAUDE_MODEL", "claude-opus-5-5")
    claude_fallbacks = flag("CLAUDE_FALLBACKS", True)
    workflow_webhook_secret = env("WORKFLOW_WEBHOOK_SECRET")
    scheduler = flag("SCHEDULER", True)
    admin_email = env("ADMIN_EMAIL")
    admin_password = env("ADMIN_PASSWORD")

    brands: dict[str, BrandConfig] = {
        "ridhi": _brand("ridhi", "RIDHI", "Ridhi Block Print", "Ridhi", "ridhiblockprint.com",
                        "guz0he-21.myshopify.com", "news", "sc-domain:ridhiblockprint.com"),
        "cpc": _brand("cpc", "CPC", "Cotton Print Club", "CPC", "cottonprintclub.com",
                      "liquidationfashion.myshopify.com", "blogs", "sc-domain:cottonprintclub.com"),
    }


config = Config()


def is_brand(v: object) -> bool:
    return v in BRAND_IDS


def has_google_credentials() -> bool:
    f = config.google_service_account_file
    return bool(f) and Path(f).exists()
