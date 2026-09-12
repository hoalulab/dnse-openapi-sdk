#!/usr/bin/env python3
"""Use case: place a buy order, then CONFIRM it via realtime events.

Flow: security info -> OTP -> place order (REST) -> subscribe order/position
events (WebSocket) -> wait for confirmation -> cancel if not confirmed.

⚠️  THIS PLACES A REAL ORDER on your account. It uses the floor price from
    security info (a limit order that normally will NOT fill), confirms the
    placement over the WebSocket order/position streams, and cancels at the end.

Confirmation logic:
  * order event for our order id with a live/filled status  -> confirmed
  * position event for our symbol                           -> confirmed (filled)
  * order event with a rejected/expired/cancelled status    -> failed
  * nothing within CONFIRM_TIMEOUT seconds                   -> not confirmed
If the order is NOT confirmed, it is cancelled.

Both signing layers are reused from THIS project: REST via ``DNSEClient``
(``dnse/api/common.py``), WebSocket via ``TradingClient`` (``dnse/websocket``).

Config via env vars:
    DNSE_API_KEY, DNSE_API_SECRET, DNSE_ACCOUNT_NO,
    DNSE_BASE_URL (REST), DNSE_WS_URL (WebSocket), CONFIRM_TIMEOUT (seconds)
Run: python examples/use-cases/place-a-trade.py
"""
import asyncio
import functools
import json
import os
import sys

_EXAMPLES_DIR = os.path.dirname(os.path.dirname(__file__))  # examples/
sys.path.insert(0, os.path.dirname(_EXAMPLES_DIR))          # python/  (for `dnse`)
sys.path.insert(0, _EXAMPLES_DIR)                           # examples/ (helpers)

from dnse import DNSEClient, TradingClient
from dnse.websocket.models import Order, Position
from market_utils import to_order_price
from token_store import clear_token, ensure_trading_token
from log_util import log

ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO", "0001000115")
SYMBOL = "VND"
QUANTITY = 100  # minimum board lot
MARKET_TYPE = "STOCK"
CONFIRM_TIMEOUT = float(os.environ.get("CONFIRM_TIMEOUT", "15"))
HOLD_SECONDS = float(os.environ.get("HOLD_SECONDS", "5"))  # keep order alive after confirm to watch events
ENCODING = os.environ.get("WS_ENCODING", "msgpack")  # price/trading stream encoding

# Order reached the exchange or executed -> placement confirmed.
LIVE_STATUSES = (
    "PENDINGNEW", "NEW", "ACCEPTED", "ACTIVE", "PARTIALLYFILLED", "FILLED",
)
# Order failed / removed -> not a successful placement.
FAIL_STATUSES = ("REJECT", "EXPIRE", "CANCEL", "FAIL", "ERROR")


async def _run_blocking(func, *args, **kwargs):
    """Run a blocking DNSEClient (urllib3) call off the event loop.

    Keeps the WebSocket background tasks (receive loop, heartbeat) running while
    the synchronous REST request is in flight. Compatible with Python 3.8+.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


async def main():
    rest = DNSEClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
        api_version=os.environ.get("DNSE_API_VERSION", "2026-07-23"),
    )

    # --- Step 1: security info -> valid price range (board G1 = round lot) ---
    status, body = rest.get_security_definition(SYMBOL, board_id="G1")
    if not status or status >= 300:
        raise SystemExit(f"get_security_definition() lỗi [{status}]: {body}")
    data = json.loads(body)
    sec = (data if isinstance(data, list) else [data])[0]
    raw_price = sec["basicPrice"]  # secdef price (STOCK: quoted in thousands of VND)
    price = to_order_price(MARKET_TYPE, raw_price)  # STOCK x1000, DERIVATIVE unchanged
    log(
        f"Chứng khoán @ {sec.get('time')} [{os.environ.get('DNSE_BASE_URL', 'prod')}]: "
        f"trần={sec['ceilingPrice']} sàn={sec['floorPrice']} tc={raw_price} "
        f"-> giá đặt lệnh={price}"
    )

    # --- Step 1b: loan package -> loanPackageId (required by the order API) ---
    status, body = rest.get_loan_packages(ACCOUNT_NO, market_type=MARKET_TYPE, symbol=SYMBOL)
    if not status or status >= 300:
        raise SystemExit(f"get_loan_packages() lỗi [{status}]: {body}")
    packages = json.loads(body).get("loanPackages", [])
    if not packages:
        raise SystemExit(
            f"Không có gói vay cho tài khoản {ACCOUNT_NO} / {SYMBOL} — "
            f"đặt DNSE_ACCOUNT_NO thành tiểu khoản thật của bạn."
        )
    loan_package_id = packages[0]["id"]
    log(f"Gói vay: dùng loanPackageId={loan_package_id}")

    # --- Step 2: trading token (reuse cached one <8h, else OTP flow) ---
    trading_token = ensure_trading_token(rest)

    # --- Step 3: safety prompt (also blocking, still before WS connect) ---
    log("\n⚠️  Sắp đặt lệnh MUA THẬT:")
    log(f"   Mã={SYMBOL}  KL={QUANTITY}  Giá={price}  Tài khoản={ACCOUNT_NO}")
    input("Nhấn Enter để tiếp tục hoặc Ctrl+C để huỷ: ")

    # --- Step 4: connect WS and subscribe BEFORE placing (don't miss events) ---
    confirmed = asyncio.Event()
    rejected = asyncio.Event()
    state: dict = {"order": None, "position": None, "reason": None}
    placed_id = {"value": None}  # filled in after post_order returns

    def on_order(o: Order):
        # Log every order event that arrives, whether it's ours or not.
        mine = placed_id["value"] is not None and str(o.id) == str(placed_id["value"])
        log(f"  [sự kiện lệnh | {'MINE' if mine else 'other'}] id={o.id} mã={o.symbol} "
              f"trạng thái={o.orderStatus} khớp={o.fillQuantity}/{o.quantity} giá={o.price}")
        if not mine:
            return
        state["order"] = o
        st = (o.orderStatus or "").upper()
        if any(k in st for k in FAIL_STATUSES):
            state["reason"] = f"trạng thái lệnh {o.orderStatus}"
            rejected.set()
        elif any(k in st for k in LIVE_STATUSES):
            confirmed.set()

    def on_position(p: Position):
        # Log every position event; positions carry no order id, so "mine" = same symbol.
        mine = p.symbol == SYMBOL
        log(f"  [sự kiện vị thế | {'MINE' if mine else 'other'}] mã={p.symbol} chiều={p.side} "
              f"kl_mở={p.openQuantity} giá_vốn={p.costPrice} trạng thái={p.status}")
        if not mine:
            return
        state["position"] = p
        confirmed.set()

    ws = TradingClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_WS_URL", "wss://ws-openapi.dnse.com.vn"),
        encoding=ENCODING,
    )
    log("\nĐang kết nối WebSocket gateway...")
    await ws.connect()
    await ws.subscribe_order_event(market_type=MARKET_TYPE, on_order_event=on_order, encoding=ENCODING)
    await ws.subscribe_position_event(
        market_type=MARKET_TYPE, on_position_event=on_position, encoding=ENCODING
    )
    await asyncio.sleep(0.5)  # let the subscriptions register

    try:
        # --- Step 5: place the order (off-loop so WS keeps receiving) ---
        payload = {
            "symbol": SYMBOL,
            "side": "NB",        # NB = buy
            "orderType": "LO",   # limit order
            "quantity": QUANTITY,
            "price": price,
            "loanPackageId": loan_package_id,
        }
        status, body = await _run_blocking(
            rest.post_order, account_no=ACCOUNT_NO, market_type=MARKET_TYPE, payload=payload,
            trading_token=trading_token, order_category="NORMAL",
        )
        if status in (401, 403):
            clear_token()  # token rejected by server -> force fresh OTP next run
            raise SystemExit(
                f"post_order() bị từ chối trading token [{status}]: {body}\n"
                "Đã xoá token cache — chạy lại để xác thực lại bằng OTP mới."
            )
        if not status or status >= 300:
            raise SystemExit(f"post_order() lỗi [{status}]: {body}")
        order = json.loads(body)
        placed_id["value"] = str(order["id"])
        log(f"\npost_order() được chấp nhận [{status}]: id={placed_id['value']} "
              f"trạng thái={order.get('orderStatus')}")

        # --- Step 6: wait for realtime confirmation ---
        log(f"Chờ tối đa {CONFIRM_TIMEOUT:.0f}s để xác nhận lệnh/vị thế...")
        c_task = asyncio.create_task(confirmed.wait())
        r_task = asyncio.create_task(rejected.wait())
        _, pending = await asyncio.wait(
            {c_task, r_task}, timeout=CONFIRM_TIMEOUT, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()

        # --- Step 7: decide + cancel when not confirmed ---
        if confirmed.is_set():
            source = "sự kiện vị thế (đã khớp)" if state["position"] else "sự kiện lệnh (đang sống)"
            log(f"\n✅ Đã XÁC NHẬN lệnh qua {source}.")
            last_order = state["order"]
            if not state["position"] and last_order is not None:
                log(
                    f"   Lệnh đang sống (trạng thái={last_order.orderStatus}, "
                    f"khớp={last_order.fillQuantity}/{last_order.quantity}); "
                    "chưa có sự kiện vị thế — vị thế chỉ xuất hiện khi lệnh khớp."
                )
            # Keep the order alive briefly so any follow-up events (fills, position)
            # get logged before we cancel.
            if HOLD_SECONDS > 0:
                log(f"Giữ {HOLD_SECONDS:.0f}s để theo dõi thêm sự kiện trước khi huỷ...")
                await asyncio.sleep(HOLD_SECONDS)
            # Demo cleanup: this is a real order — cancel so nothing is left live.
            log("Dọn dẹp lệnh demo...")
            await _cancel(rest, placed_id["value"], trading_token)
        else:
            reason = state["reason"] or f"không có sự kiện xác nhận trong {CONFIRM_TIMEOUT:.0f}s"
            log(f"\n❌ Lệnh CHƯA được xác nhận ({reason}) — đang huỷ.")
            await _cancel(rest, placed_id["value"], trading_token)
    finally:
        log("\nĐang ngắt kết nối WebSocket...")
        await ws.disconnect()


async def _cancel(rest, order_id, trading_token):
    status, body = await _run_blocking(
        rest.cancel_order, ACCOUNT_NO, order_id, market_type=MARKET_TYPE,
        trading_token=trading_token, order_category="NORMAL",
    )
    log(f"cancel_order() [{status}]: lệnh {order_id} -> {body or 'đã huỷ'}")


if __name__ == "__main__":
    asyncio.run(main())
