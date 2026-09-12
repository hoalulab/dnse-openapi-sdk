#!/usr/bin/env python3
"""Use case: fetch historical orders and today's positions/deals. No OTP required.

Ported from dnse-py to drive THIS project's ``DNSEClient`` — signing is handled
inside the client (see ``dnse/api/common.py``). Note: DNSE serves "deals" from the
positions endpoint, i.e. ``DNSEClient.get_positions()``.

Config via env vars: DNSE_API_KEY, DNSE_API_SECRET, DNSE_ACCOUNT_NO, DNSE_BASE_URL
Run: python examples/use-cases/order-history.py
"""
import json
import os
import sys
from datetime import date, timedelta

# Import the local SDK (three levels up: examples/use-cases -> examples -> python/)
_EXAMPLES_DIR = os.path.dirname(os.path.dirname(__file__))  # examples/
sys.path.insert(0, os.path.dirname(_EXAMPLES_DIR))          # python/  (for `dnse`)
sys.path.insert(0, _EXAMPLES_DIR)                           # examples/ (helpers)

from dnse import DNSEClient
from env_util import load_dotenv
from log_util import log

load_dotenv()

ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO", "0001000115")


def main():
    client = DNSEClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
        api_version=os.environ.get("DNSE_API_VERSION", "2026-07-23"),
    )

    # Last 30 days of order history
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=7)).isoformat()

    status, body = client.get_order_history(
        ACCOUNT_NO, market_type="STOCK", from_date=from_date, to_date=to_date
    )
    if not status or status >= 300:
        raise SystemExit(f"get_order_history() lỗi [{status}]: {body}")
    history = json.loads(body).get("data", [])
    log(f"Lịch sử lệnh ({from_date} -> {to_date}): {len(history)} lệnh")
    for o in history:
        log(
            f"  {o.get('id')}  {o.get('symbol')}  {o.get('side')}  "
            f"sl={o.get('quantity')}  trạng thái={o.get('orderStatus')}"
        )

    # Today's positions (the endpoint returns {"positions": [...]})
    status, body = client.get_positions(ACCOUNT_NO, market_type="STOCK")
    if not status or status >= 300:
        raise SystemExit(f"get_positions() lỗi [{status}]: {body}")
    positions = json.loads(body).get("positions", [])
    log(f"\nVị thế hôm nay: {len(positions)}")
    for d in positions:
        log(f"  {d.get('symbol')}  sl={d.get('openQuantity')}  "
            f"trạng thái={d.get('status')}  giá vốn={d.get('costPrice')}")


if __name__ == "__main__":
    main()
