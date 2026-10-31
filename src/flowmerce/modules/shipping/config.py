"""Shipping settings from the environment / .env (the same file the rest of Flowmerce reads)."""

from __future__ import annotations

from dataclasses import dataclass

from ..seo.config import config as seo_config
from ..seo.config import env


@dataclass(frozen=True)
class ShippingConfig:
    shop_domain: str
    client_id: str
    client_secret: str
    token: str  # optional legacy static Admin API token
    api_version: str
    orders_since: str
    timezone: str
    grey_days: int
    yellow_days: int
    orange_days: int
    red_days: int
    critical_days: int = 13

    @property
    def thresholds(self) -> dict:
        return {
            "grey": self.grey_days,
            "yellow": self.yellow_days,
            "orange": self.orange_days,
            "red": self.red_days,
        }

    @property
    def has_shopify_credentials(self) -> bool:
        return bool(self.shop_domain and (self.token or (self.client_id and self.client_secret)))


def _pick(*keys: str, default: str = "") -> str:
    """First non-empty environment value. Shipping names (SHIPPING_*) win; the delayed-order-tracker's original
    names (SHOPIFY_CLIENT_ID, ORDERS_SINCE, ...) are accepted too, so an existing .env keeps working."""
    for k in keys:
        v = env(k)
        if v:
            return v
    return default


def load_config() -> ShippingConfig:
    """Read at call time so tests and a restarted server see current values."""
    return ShippingConfig(
        shop_domain=_pick(
            "SHIPPING_SHOPIFY_SHOP",
            "SHOPIFY_STORE_DOMAIN",
            default=seo_config.brands["ridhi"].shop_domain,
        ),
        client_id=_pick("SHIPPING_SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_ID"),
        client_secret=_pick("SHIPPING_SHOPIFY_CLIENT_SECRET", "SHOPIFY_CLIENT_SECRET"),
        token=_pick("SHIPPING_SHOPIFY_ACCESS_TOKEN", "SHOPIFY_ACCESS_TOKEN"),
        # SHOPIFY_API_VERSION is the SEO module's setting, so Shipping does not borrow it.
        api_version=_pick("SHIPPING_SHOPIFY_API_VERSION", default="2026-01"),
        orders_since=_pick("SHIPPING_ORDERS_SINCE", "ORDERS_SINCE", default="2026-07-01"),
        timezone=_pick("SHIPPING_TIMEZONE", "TIMEZONE", default="Asia/Kolkata"),
        grey_days=int(_pick("SHIPPING_GREY_DAYS", "GREY_THRESHOLD_DAYS", default="2")),
        yellow_days=int(_pick("SHIPPING_YELLOW_DAYS", "YELLOW_THRESHOLD_DAYS", default="4")),
        orange_days=int(_pick("SHIPPING_ORANGE_DAYS", "ORANGE_THRESHOLD_DAYS", default="6")),
        red_days=int(_pick("SHIPPING_RED_DAYS", "RED_THRESHOLD_DAYS", default="9")),
        critical_days=int(_pick("SHIPPING_CRITICAL_DAYS", default="13")),
    )
