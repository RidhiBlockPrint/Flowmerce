"""Shopify Admin GraphQL client: read-only, paginated, with timeouts and retries."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

ORDERS_QUERY = """
query Orders($cursor: String, $q: String!) {
  orders(first: 50, after: $cursor, query: $q, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      id name createdAt cancelledAt closedAt displayFulfillmentStatus displayFinancialStatus
      totalPriceSet { shopMoney { amount currencyCode } }
      note
      fulfillments(first: 20) {
        id status createdAt displayStatus estimatedDeliveryAt deliveredAt
        trackingInfo(first: 10) { number company url }
        events(first: 50) { edges { node { status happenedAt message } } }
      }
    } }
  }
}
"""

# Open or in-transit orders only. Delivered orders are picked up as delivered
# shipments from their fulfillment status, so they still show in the KPI.
ORDER_FILTER = (
    "created_at:>='{since}' AND -status:cancelled AND "
    "(fulfillment_status:unfulfilled OR fulfillment_status:partial OR fulfillment_status:shipped)"
)


class ShopifyError(RuntimeError):
    pass


TOKEN_REFRESH_MARGIN = 300  # refresh 5 minutes before expiry


class TokenProvider:
    """Gets an Admin API token with the app's Client ID + Client secret
    (client_credentials grant, used by Dev Dashboard apps). The token lasts about
    24 hours, so it is cached and refreshed before it expires."""

    def __init__(
        self,
        domain: str,
        client_id: str,
        client_secret: str,
        timeout: int = 30,
        opener=None,
        clock=time.time,
    ):
        if not (domain and client_id and client_secret):
            raise ShopifyError(
                "SHOPIFY_STORE_DOMAIN, SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET are required"
            )
        self.url = f"https://{domain}/admin/oauth/access_token"
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen
        self._clock = clock
        self._token = None
        self._expires_at = 0.0

    def get(self) -> str:
        if self._token and self._clock() < self._expires_at - TOKEN_REFRESH_MARGIN:
            return self._token
        return self._fetch()

    def invalidate(self):
        self._token = None

    def _fetch(self) -> str:
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with self._open(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ShopifyError(
                f"Token request failed: HTTP {exc.code}. Check Client ID, secret and store domain."
            ) from exc
        except urllib.error.URLError as exc:
            raise ShopifyError(f"Token request network error: {exc.reason}") from exc
        token = data.get("access_token")
        if not token:
            raise ShopifyError("Token response had no access_token")
        self._token = token
        self._expires_at = self._clock() + int(data.get("expires_in") or 86399)
        return token


class ShopifyClient:
    def __init__(
        self,
        domain: str,
        token: str = "",
        api_version: str = "2026-01",
        timeout: int = 30,
        max_retries: int = 4,
        opener=None,
        sleep=time.sleep,
        token_provider: "TokenProvider" = None,
    ):
        if not domain:
            raise ShopifyError("SHOPIFY_STORE_DOMAIN is required")
        if not token and token_provider is None:
            raise ShopifyError("Provide a token or a TokenProvider (Client ID + secret)")
        self.url = f"https://{domain}/admin/api/{api_version}/graphql.json"
        self.token = token
        self.token_provider = token_provider
        self.timeout = timeout
        self.max_retries = max_retries
        self._open = opener or urllib.request.urlopen
        self._sleep = sleep

    def _current_token(self) -> str:
        return self.token_provider.get() if self.token_provider else self.token

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        refreshed_once = False
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                self.url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": self._current_token(),
                },
            )
            try:
                with self._open(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 401 and self.token_provider and not refreshed_once:
                    self.token_provider.invalidate()  # token expired: fetch a new one, retry once
                    refreshed_once = True
                    continue
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    self._sleep(min(2**attempt, 30))
                    continue
                raise ShopifyError(f"Shopify HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    self._sleep(min(2**attempt, 30))
                    continue
                raise ShopifyError(f"Shopify network error: {exc.reason}") from exc
            if data.get("errors"):
                raise ShopifyError(f"Shopify GraphQL error: {data['errors'][0].get('message')}")
            return data["data"]
        raise ShopifyError("Shopify retries exhausted")

    def fetch_orders(self, since: str):
        """Yield order nodes created on/after `since` (YYYY-MM-DD), page by page."""
        cursor = None
        while True:
            data = self._post(
                {
                    "query": ORDERS_QUERY,
                    "variables": {"cursor": cursor, "q": ORDER_FILTER.format(since=since)},
                }
            )
            conn = data["orders"]
            for edge in conn["edges"]:
                yield edge["node"]
            if not conn["pageInfo"]["hasNextPage"]:
                return
            cursor = conn["pageInfo"]["endCursor"]
