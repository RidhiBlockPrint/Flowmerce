import unittest
from datetime import UTC, datetime, timedelta

from flowmerce.modules.shipping.aging import flow_category, is_no_movement
from flowmerce.modules.shipping.normalize import normalize_orders

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def ago(days, hours=0):
    return NOW - timedelta(days=days, hours=hours)


class PreDispatchTests(unittest.TestCase):
    """Not dispatched: clock starts at order date."""

    def test_grey_2_3(self):
        self.assertEqual(flow_category(ago(2), None, NOW)[0], "grey")
        self.assertEqual(flow_category(ago(3), None, NOW)[0], "grey")

    def test_yellow_4_5_orange_6_8_red_9(self):
        self.assertEqual(flow_category(ago(4), None, NOW)[0], "yellow")
        self.assertEqual(flow_category(ago(5), None, NOW)[0], "yellow")
        self.assertEqual(flow_category(ago(6), None, NOW)[0], "orange")
        self.assertEqual(flow_category(ago(8), None, NOW)[0], "orange")
        self.assertEqual(flow_category(ago(9), None, NOW)[0], "red")

    def test_stage_label(self):
        self.assertEqual(flow_category(ago(3), None, NOW)[2], "pre_dispatch")


class DispatchedTests(unittest.TestCase):
    """Dispatched: clock starts at dispatch date. Green for 0-3 days."""

    def test_on_track_0_to_3(self):
        self.assertEqual(flow_category(ago(10), ago(0), NOW)[0], "on_track")
        self.assertEqual(flow_category(ago(10), ago(3), NOW)[0], "on_track")

    def test_yellow_4_5(self):
        self.assertEqual(flow_category(ago(10), ago(4), NOW)[0], "yellow")
        self.assertEqual(flow_category(ago(10), ago(5), NOW)[0], "yellow")

    def test_orange_6_8_red_9(self):
        self.assertEqual(flow_category(ago(10), ago(6), NOW)[0], "orange")
        self.assertEqual(flow_category(ago(10), ago(8), NOW)[0], "orange")
        self.assertEqual(flow_category(ago(12), ago(9), NOW)[0], "red")

    def test_dispatch_date_is_used_not_order_date(self):
        # ordered 20 days ago but dispatched today: still on track
        self.assertEqual(flow_category(ago(20), ago(0), NOW)[0], "on_track")

    def test_delivered_wins(self):
        self.assertEqual(flow_category(ago(20), ago(15), NOW, delivered=True)[0], "delivered")


class ScanDoesNotResetTests(unittest.TestCase):
    def test_recent_scan_does_not_reset_red(self):
        # dispatched 10 days ago; a scan today must NOT make it green/yellow
        cat, days, _ = flow_category(ago(12), ago(10), NOW)
        self.assertEqual(cat, "red")
        self.assertEqual(days, 10)


class EventsNormalizeTests(unittest.TestCase):
    def _order(self, events):
        return {
            "id": "gid://shopify/Order/9",
            "name": "#9",
            "createdAt": "2026-10-01T04:00:00Z",
            "cancelledAt": None,
            "fulfillments": [
                {
                    "id": "f9",
                    "status": "SUCCESS",
                    "createdAt": "2026-10-02T06:00:00Z",
                    "displayStatus": "IN_TRANSIT",
                    "trackingInfo": [{"number": "D1", "company": "DHL Express"}],
                    "events": {"edges": [{"node": e} for e in events]},
                }
            ],
        }

    def test_latest_event_becomes_last_scan(self):
        row = list(
            normalize_orders(
                [
                    self._order(
                        [
                            {
                                "status": "IN_TRANSIT",
                                "happenedAt": "2026-10-03T09:00:00Z",
                                "message": "Picked up",
                            },
                            {
                                "status": "IN_TRANSIT",
                                "happenedAt": "2026-10-05T10:30:00Z",
                                "message": "Arrived hub",
                            },
                        ]
                    )
                ]
            )
        )[0]
        self.assertEqual(row["last_scan_at"].isoformat(), "2026-10-05T10:30:00+00:00")
        self.assertEqual(row["last_scan_description"], "Arrived hub")
        self.assertEqual(row["tracking_source"], "shopify_events")

    def test_no_events_means_no_scan(self):
        row = list(normalize_orders([self._order([])]))[0]
        self.assertIsNone(row["last_scan_at"])
        self.assertEqual(row["tracking_source"], "shopify")


class NoMovementTests(unittest.TestCase):
    def test_flag_at_5_days_and_above(self):
        self.assertFalse(is_no_movement(ago(4), NOW))
        self.assertTrue(is_no_movement(ago(5), NOW))
        self.assertTrue(is_no_movement(ago(30), NOW))

    def test_delivered_never_flagged(self):
        self.assertFalse(is_no_movement(ago(30), NOW, delivered=True))

    def test_no_scan_not_flagged(self):
        self.assertFalse(is_no_movement(None, NOW))


if __name__ == "__main__":
    unittest.main()
