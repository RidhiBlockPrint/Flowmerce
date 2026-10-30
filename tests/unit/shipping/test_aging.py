import unittest
from datetime import UTC, datetime, timedelta, timezone
from datetime import timedelta as td

from flowmerce.modules.shipping.aging import categorize, complete_days

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def days_ago(d, extra_hours=0):
    return NOW - timedelta(days=d, hours=extra_hours)


class AgingBoundaryTests(unittest.TestCase):
    def test_each_boundary_day(self):
        cases = {
            0: "on_track",
            1: "on_track",
            2: "grey",
            3: "grey",
            4: "yellow",
            5: "yellow",
            6: "orange",
            8: "orange",
            9: "red",
            15: "red",
        }
        for days, expected in cases.items():
            with self.subTest(days=days):
                self.assertEqual(categorize(days_ago(days), NOW), expected)

    def test_exact_days_six_eight(self):
        self.assertEqual(categorize(days_ago(6), NOW), "orange")
        self.assertEqual(categorize(days_ago(7), NOW), "orange")
        self.assertEqual(categorize(days_ago(8), NOW), "orange")

    def test_only_complete_24h_periods_count(self):
        # 47h59m is still 1 complete day, not 2
        self.assertEqual(complete_days(days_ago(1, extra_hours=23), NOW), 1)
        self.assertEqual(categorize(days_ago(1, extra_hours=23), NOW), "on_track")
        self.assertEqual(complete_days(days_ago(2), NOW), 2)

    def test_custom_thresholds_are_respected(self):
        t = {"grey": 1, "yellow": 2, "orange": 3, "red": 4}
        self.assertEqual(categorize(days_ago(1), NOW, t), "grey")
        self.assertEqual(categorize(days_ago(4), NOW, t), "red")

    def test_missing_scan_is_never_on_track(self):
        self.assertEqual(categorize(None, NOW), "no_scan")
        self.assertIsNone(complete_days(None, NOW))

    def test_delivered_wins_over_age(self):
        self.assertEqual(categorize(days_ago(20), NOW, delivered=True), "delivered")

    def test_timezone_conversion_same_instant(self):
        # 08:30 IST on 15 Oct == 03:00 UTC on 15 Oct
        ist = timezone(td(hours=5, minutes=30))
        scan_ist = datetime(2026, 10, 15, 8, 30, tzinfo=ist)
        scan_utc = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)
        self.assertEqual(complete_days(scan_ist, NOW), complete_days(scan_utc, NOW))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            complete_days(datetime(2026, 10, 1), NOW)


if __name__ == "__main__":
    unittest.main()
