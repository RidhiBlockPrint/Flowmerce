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


def load_config() -> ShippingConfig:
    """Read at call time so tests and a restarted server see current values."""
    return ShippingConfig(
        shop_domain=env("SHIPPING_SHOPIFY_SHOP", seo_config.brands["ridhi"].shop_domain),
        client_id=env("SHIPPING_SHOPIFY_CLIENT_ID"),
        client_secret=env("SHIPPING_SHOPIFY_CLIENT_SECRET"),
        token=env("SHIPPING_SHOPIFY_ACCESS_TOKEN"),
        api_version=env("SHIPPING_SHOPIFY_API_VERSION", "2026-01"),
        orders_since=env("SHIPPING_ORDERS_SINCE", "2026-07-01"),
        timezone=env("SHIPPING_TIMEZONE", "Asia/Kolkata"),
        grey_days=int(env("SHIPPING_GREY_DAYS", "2")),
        yellow_days=int(env("SHIPPING_YELLOW_DAYS", "4")),
        orange_days=int(env("SHIPPING_ORANGE_DAYS", "6")),
        red_days=int(env("SHIPPING_RED_DAYS", "9")),
    )
