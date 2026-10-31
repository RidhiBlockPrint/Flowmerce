"""Background refresh. Only reads: it runs the Performance tracking stage (Shopify, Search Console, GA4)
for each brand when the last run is more than 6 hours old. It never generates content, creates Shopify
drafts or publishes — those need a person to start them. Paused brands are skipped."""
from __future__ import annotations

import threading
import time

from ..config import BRAND_IDS
from ...shipping.master_sync import tick as master_tick
from ...shipping.sync import tick as shipping_tick
from ..util import ms_since
from .runs import last_run
from .workflow import is_paused, run_stage

EVERY_SECONDS = 15 * 60
REFRESH_HOURS = 6
_started = False


def tick() -> None:
    try:
        shipping_tick()  # read-only Shopify sync for the Shipping module, when its credentials are set
    except Exception as e:  # noqa: BLE001
        print("shipping sync failed:", e)
    try:
        master_tick()  # copies orders, items, shipments and scans into the master database
    except Exception as e:  # noqa: BLE001
        print("master database sync failed:", e)
    for b in BRAND_IDS:
        if is_paused(b):
            continue
        last = last_run(b, "performance_tracking")
        if last and ms_since(last["started_at"]) < REFRESH_HOURS * 3600_000:
            continue
        try:
            run_stage("performance_tracking", b, None, "scheduler")
        except Exception:  # noqa: BLE001 — recorded on the run and integration status
            pass


def start_scheduler() -> None:
    global _started
    if _started:
        return
    _started = True

    def loop() -> None:
        time.sleep(5)
        while True:
            try:
                tick()
            except Exception as e:  # noqa: BLE001
                print("scheduler tick failed:", e)
            time.sleep(EVERY_SECONDS)

    threading.Thread(target=loop, name="blog-ops-scheduler", daemon=True).start()
