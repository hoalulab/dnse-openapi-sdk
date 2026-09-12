#!/usr/bin/env python3
"""Reference: full OrdersResource flow (Email OTP mode).

Ported from dnse-py to drive THIS project's ``DNSEClient``. All HMAC signing is
handled inside ``DNSEClient`` (see ``dnse/api/common.py``) — this script only
calls client methods and reads fields from the returned ``(status, body)`` JSON.

Email OTP: call send_email_otp() to trigger an OTP to your registered email,
then enter it to obtain a trading token.

Config via env vars (fallback to placeholders):
    DNSE_API_KEY, DNSE_API_SECRET, DNSE_ACCOUNT_NO, DNSE_BASE_URL

Run: python examples/reference/orders-email-otp.py
"""
import json
import os
import sys
import time

_EXAMPLES_DIR = os.path.dirname(os.path.dirname(__file__))  # examples/
sys.path.insert(0, os.path.dirname(_EXAMPLES_DIR))          # python/  (for `dnse`)
sys.path.insert(0, _EXAMPLES_DIR)                           # examples/ (for `otp_email`)

from dnse import DNSEClient
from market_utils import to_order_price
from otp_email import resolve_otp

ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO", "0001000115")
SYMBOL = "HPG"
MARKET_TYPE = "STOCK"


def main():
    client = DNSEClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
        api_version=os.environ.get("DNSE_API_VERSION", "2026-07-23"),
    )

    # get_orders() — active order book
    status, body = client.get_orders(
        ACCOUNT_NO,
        market_type=MARKET_TYPE,
        order_category="NORMAL",
        page_index=0,
        page_size=20,
    )
    order_book = json.loads(body) if status and status < 300 else {}
    orders = order_book.get("orders", [])
    pagination = {key: value for key, value in order_book.items() if key != "orders"}
    print(f"get_orders() [{status}]: {len(orders)} active orders; pagination={pagination}")

    # get_order_history() — historical orders
    status, body = client.get_order_history(
        ACCOUNT_NO, market_type=MARKET_TYPE, from_date="2026-01-01", to_date="2026-03-01"
    )
    history = json.loads(body).get("data", []) if status and status < 300 else []
    print(f"get_order_history() [{status}]: {len(history)} orders")

    # get_security_definition() — valid price range (board G1 = round lot)
    status, body = client.get_security_definition(SYMBOL, board_id="G1")
    if not status or status >= 300:
        raise SystemExit(f"get_security_definition() failed [{status}]: {body}")
    data = json.loads(body)
    sec = (data if isinstance(data, list) else [data])[0]
    floor_price = sec["floorPrice"]
    order_price = to_order_price(MARKET_TYPE, floor_price)
    print(
        f"get_security_definition('{SYMBOL}'): "
        f"ceiling={sec['ceilingPrice']}  floor={floor_price}  basic={sec['basicPrice']} "
        f"-> order price={order_price}"
    )

    # --- mutations require a trading token (OTP auto-fetched if configured) ---
    otp_requested_at = time.time()
    client.send_email_otp()
    otp = resolve_otp(after_ts=otp_requested_at, prompt="\nEnter OTP from email (or Enter to skip): ")
    if not otp:
        print("Skipping place/update/cancel examples.")
        return

    status, body = client.create_trading_token(otp_type="email_otp", passcode=otp)
    if not status or status >= 300:
        raise SystemExit(f"create_trading_token() failed [{status}]: {body}")
    trading_token = json.loads(body)["tradingToken"]

    # get_loan_packages() — need a real loanPackageId to place an order
    status, body = client.get_loan_packages(ACCOUNT_NO, market_type=MARKET_TYPE, symbol=SYMBOL)
    if not status or status >= 300:
        raise SystemExit(f"get_loan_packages() failed [{status}]: {body}")
    loan_package_id = json.loads(body)["loanPackages"][0]["id"]
    print(f"\nget_loan_packages(): using loanPackageId={loan_package_id}")

    # post_order() — place (floor price stays within valid range)
    payload = {
        "symbol": SYMBOL,
        "side": "NB",        # NB = buy, NS = sell
        "orderType": "LO",   # limit order
        "quantity": 100,
        "price": order_price,
        "loanPackageId": loan_package_id,
    }
    status, body = client.post_order(
        account_no=ACCOUNT_NO,
        market_type=MARKET_TYPE,
        payload=payload,
        trading_token=trading_token,
        order_category="NORMAL",
    )
    if not status or status >= 300:
        raise SystemExit(f"post_order() failed [{status}]: {body}")
    order_id = str(json.loads(body)["id"])
    print(f"\npost_order(): id={order_id}")

    # get_order_detail()
    status, body = client.get_order_detail(
        ACCOUNT_NO, order_id, market_type=MARKET_TYPE, order_category="NORMAL"
    )
    print(f"\nget_order_detail() [{status}]: {body}")

    # put_order() — DNSE modifies as cancel-then-replace: returns a NEW order id
    status, body = client.put_order(
        ACCOUNT_NO,
        order_id,
        market_type=MARKET_TYPE,
        payload={"quantity": 200, "price": order_price},
        trading_token=trading_token,
        order_category="NORMAL",
    )
    if not status or status >= 300:
        raise SystemExit(f"put_order() failed [{status}]: {body}")
    new_order_id = str(json.loads(body)["id"])
    print(f"\nput_order(): replaced by new id={new_order_id}")

    # cancel_order() — cancel the replacement order (new id)
    status, body = client.cancel_order(
        ACCOUNT_NO, new_order_id, market_type=MARKET_TYPE, trading_token=trading_token,
        order_category="NORMAL",
    )
    print(f"\ncancel_order() [{status}]: order {new_order_id} cancelled")


if __name__ == "__main__":
    main()
