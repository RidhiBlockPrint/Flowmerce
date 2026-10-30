import json
import unittest
import urllib.error

from flowmerce.modules.shipping.shopify import ShopifyClient, ShopifyError, TokenProvider


class Resp:
    def __init__(self, body):
        self.body = body

    def read(self):
        return json.dumps(self.body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def token_opener(tokens):
    """Returns tokens in order from the token endpoint; records requests."""
    seen = []

    def opener(req, timeout):
        seen.append(req)
        if req.full_url.endswith("/admin/oauth/access_token"):
            return Resp({"access_token": tokens.pop(0), "expires_in": 86399})
        raise AssertionError("unexpected URL " + req.full_url)

    return opener, seen


class TokenProviderTests(unittest.TestCase):
    def test_fetches_with_client_credentials_form(self):
        opener, seen = token_opener(["tok-1"])
        tp = TokenProvider("shop.myshopify.com", "CID", "SEC", opener=opener, clock=Clock())
        self.assertEqual(tp.get(), "tok-1")
        body = seen[0].data.decode()
        self.assertIn("grant_type=client_credentials", body)
        self.assertIn("client_id=CID", body)
        self.assertIn("client_secret=SEC", body)
        self.assertEqual(seen[0].full_url, "https://shop.myshopify.com/admin/oauth/access_token")

    def test_token_is_cached_until_near_expiry(self):
        opener, seen = token_opener(["tok-1", "tok-2"])
        clock = Clock()
        tp = TokenProvider("s.myshopify.com", "C", "S", opener=opener, clock=clock)
        self.assertEqual(tp.get(), "tok-1")
        clock.t += 3600  # one hour later: still valid
        self.assertEqual(tp.get(), "tok-1")
        self.assertEqual(len(seen), 1)

    def test_refreshes_before_expiry(self):
        opener, seen = token_opener(["tok-1", "tok-2"])
        clock = Clock()
        tp = TokenProvider("s.myshopify.com", "C", "S", opener=opener, clock=clock)
        tp.get()
        clock.t += 86399 - 60  # inside the 5-minute refresh margin
        self.assertEqual(tp.get(), "tok-2")
        self.assertEqual(len(seen), 2)

    def test_token_endpoint_error_is_clear(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

        tp = TokenProvider("s.myshopify.com", "C", "bad", opener=opener, clock=Clock())
        with self.assertRaises(ShopifyError) as ctx:
            tp.get()
        self.assertIn("Client ID", str(ctx.exception))

    def test_missing_credentials_rejected(self):
        with self.assertRaises(ShopifyError):
            TokenProvider("s.myshopify.com", "", "")


class ClientWithProviderTests(unittest.TestCase):
    def test_401_triggers_one_refresh_and_retry(self):
        tokens = ["old", "new"]
        used = []

        class Provider:
            def get(self):
                return tokens[0]

            def invalidate(self):
                tokens.pop(0)

        calls = {"n": 0}

        def opener(req, timeout):
            calls["n"] += 1
            used.append(req.get_header("X-shopify-access-token"))
            if calls["n"] == 1:
                raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
            return Resp({"data": {"orders": {"edges": [], "pageInfo": {"hasNextPage": False}}}})

        client = ShopifyClient(
            "s.myshopify.com",
            api_version="2026-01",
            opener=opener,
            sleep=lambda s: None,
            token_provider=Provider(),
        )
        self.assertEqual(list(client.fetch_orders("2026-07-01")), [])
        self.assertEqual(used, ["old", "new"])

    def test_needs_token_or_provider(self):
        with self.assertRaises(ShopifyError):
            ShopifyClient("s.myshopify.com")


if __name__ == "__main__":
    unittest.main()
