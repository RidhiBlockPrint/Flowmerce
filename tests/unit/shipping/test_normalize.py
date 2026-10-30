import unittest

from flowmerce.modules.shipping.normalize import normalize_orders


def order(**kw):
    base = {
        "id": "gid://shopify/Order/1",
        "name": "#1",
        "createdAt": "2026-10-01T04:00:00Z",
        "cancelledAt": None,
        "fulfillments": [],
    }
    base.update(kw)
    return base


class NormalizeTests(unittest.TestCase):
    def test_order_without_fulfillment_yields_nothing(self):
        self.assertEqual(list(normalize_orders([order()])), [])

    def test_cancelled_order_skipped(self):
        o = order(
            cancelledAt="2026-10-02T00:00:00Z",
            fulfillments=[
                {"id": "f1", "status": "SUCCESS", "displayStatus": "FULFILLED", "trackingInfo": []}
            ],
        )
        self.assertEqual(list(normalize_orders([o])), [])

    def test_multiple_fulfillments_and_tracking_numbers_kept_apart(self):
        o = order(
            fulfillments=[
                {
                    "id": "f1",
                    "status": "SUCCESS",
                    "createdAt": "2026-10-02T06:00:00Z",
                    "displayStatus": "IN_TRANSIT",
                    "trackingInfo": [{"number": "A1", "company": "DHL Express", "url": "u1"}],
                },
                {
                    "id": "f2",
                    "status": "SUCCESS",
                    "createdAt": "2026-10-03T06:00:00Z",
                    "displayStatus": "FULFILLED",
                    "trackingInfo": [
                        {"number": "B1", "company": "Amazon Logistics", "url": "u2"},
                        {"number": "B2", "company": "Amazon Logistics", "url": "u3"},
                    ],
                },
            ]
        )
        rows = list(normalize_orders([o]))
        self.assertEqual(
            [(r["fulfillment_id"], r["tracking_number"]) for r in rows],
            [("f1", "A1"), ("f2", "B1"), ("f2", "B2")],
        )

    def test_status_mapping_and_exceptions(self):
        def one(display):
            o = order(
                fulfillments=[
                    {
                        "id": "f",
                        "status": "SUCCESS",
                        "displayStatus": display,
                        "trackingInfo": [{"number": "N", "company": "USPS"}],
                    }
                ]
            )
            return list(normalize_orders([o]))[0]

        self.assertEqual(one("DELIVERED")["normalized_tracking_status"], "delivered")
        self.assertEqual(one("IN_TRANSIT")["normalized_tracking_status"], "in_transit")
        self.assertEqual(one("FAILURE")["exception"], "failed_delivery")
        self.assertEqual(one("RETURNED")["exception"], "returned")
        self.assertEqual(one("IN_TRANSIT")["exception"], "")

    def test_missing_tracking_number_still_represented(self):
        o = order(
            fulfillments=[
                {"id": "f", "status": "SUCCESS", "displayStatus": "FULFILLED", "trackingInfo": []}
            ]
        )
        row = list(normalize_orders([o]))[0]
        self.assertEqual(row["tracking_number"], "")
        self.assertIsNone(row["last_scan_at"])  # never invent a scan

    def test_timestamps_are_utc_aware(self):
        o = order(
            fulfillments=[
                {
                    "id": "f",
                    "status": "SUCCESS",
                    "createdAt": "2026-10-02T06:00:00Z",
                    "displayStatus": "FULFILLED",
                    "estimatedDeliveryAt": "2026-10-09T03:59:59Z",
                    "trackingInfo": [{"number": "N"}],
                }
            ]
        )
        row = list(normalize_orders([o]))[0]
        self.assertEqual(row["fulfilled_at"].utcoffset().total_seconds(), 0)
        self.assertEqual(row["expected_delivery_at"].day, 9)


if __name__ == "__main__":
    unittest.main()


class LiveShapeTests(unittest.TestCase):
    """Uses a response with the exact field shape returned by the live Shopify Admin API."""

    def test_live_shape_maps_correctly(self):
        import json
        import os

        path = os.path.join(os.path.dirname(__file__), "fixtures", "shopify_live_shape.json")
        with open(path, encoding="utf-8") as fh:
            nodes = [e["node"] for e in json.load(fh)["data"]["orders"]["edges"]]
        rows = list(normalize_orders(nodes))
        # order A has a fulfillment without tracking; order B has two packages; order C is in transit with an ETA
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["tracking_number"], "")
        self.assertEqual(
            {r["tracking_number"] for r in rows if r["order_number"] == "#SAMPLE-B"},
            {"TBA000000000001", "TBA000000000002"},
        )
        c = [r for r in rows if r["order_number"] == "#SAMPLE-C"][0]
        self.assertEqual(c["normalized_tracking_status"], "in_transit")
        self.assertEqual(c["expected_delivery_at"].isoformat(), "2026-10-22T03:59:59+00:00")
        self.assertTrue(all(r["last_scan_at"] is None for r in rows))  # Shopify gives no scan time
