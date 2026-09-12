#!/usr/bin/env python3
"""Full flow demo: stream prices -> strategy -> entry -> manage TP/SL exit.

End-to-end auto-trader with pluggable strategy AND risk/position management:
  1. Seed the candle buffer from the historical OHLC REST endpoint (so the
     strategy has enough bars immediately), then keep it updated from the
     closed-OHLC WebSocket stream.
  2. Feed the rolling candle history (seeded history + new bars) to a pluggable
     Strategy (strategy_base).
  3. On the first actionable Signal, print the trade plan (side/entry/SL/TP)
     and size the position from a risk budget (position_manager.size_by_risk).
  4. DRY RUN by default. With PLACE_ORDER=1 the PositionManager places the entry,
     waits for the fill, then closes the position when price hits TP or SL
     (or an optional time limit) and reports the result.

Both the strategy and the risk manager are decoupled modules — swap either one
without touching the rest. This is a demo, not a production trading system.

The OHLC candles are subscribed under a data symbol (default VN30F1M, the generic
front-month alias) while orders and order/trade/position events use the actual
contract symbol (default 41I1G7000) — they refer to the same instrument/price.

Config via env (or examples/.env):
    DNSE_API_KEY, DNSE_API_SECRET, DNSE_ACCOUNT_NO, DNSE_BASE_URL, DNSE_WS_URL,
    SYMBOL, OHLC_SYMBOL, MARKET_TYPE, RESOLUTION, STRATEGY, QUANTITY, PLACE_ORDER,
    RISK_POINTS, ENTRY_FILL_TIMEOUT, MANAGE_TIMEOUT
Run: python examples/use-cases/auto-trader.py
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

_EXAMPLES_DIR = os.path.dirname(os.path.dirname(__file__))  # examples/
sys.path.insert(0, os.path.dirname(_EXAMPLES_DIR))          # python/  (for `dnse`)
sys.path.insert(0, _EXAMPLES_DIR)                           # examples/ (helpers)

from dnse import DNSEClient, TradingClient
from dnse.websocket.models import Ohlc
from market_utils import to_order_price
from position_manager import PositionManager, size_by_risk
from position_store import clear_position, load_position
from strategy_base import Candle, get_strategy
from token_store import ensure_trading_token
from log_util import log
import strategy_price_action  # noqa: F401  (registers the "price_action" strategy)
import strategy_ichimoku      # noqa: F401  (registers the "ichimoku_cloud" strategy)
import strategy_scalping      # noqa: F401  (registers the "scalping" strategy)

SYMBOL = os.environ.get("SYMBOL", "41I1G7000")           # trading symbol (orders + order/trade/position events)
OHLC_SYMBOL = os.environ.get("OHLC_SYMBOL", "VN30F1M")   # OHLC candles use the generic front-month alias
MARKET_TYPE = os.environ.get("MARKET_TYPE", "DERIVATIVE")
RESOLUTION = os.environ.get("RESOLUTION", "1")          # OHLC bar size (minutes)
STRATEGY = os.environ.get("STRATEGY", "scalping")
QUANTITY = int(os.environ.get("QUANTITY", "1"))         # fixed size (fallback)
RISK_POINTS = float(os.environ.get("RISK_POINTS", "0"))  # >0 -> size by risk
ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO", "0001000115")
PLACE_ORDER = os.environ.get("PLACE_ORDER", "1") == "1"
ENTRY_FILL_TIMEOUT = float(os.environ.get("ENTRY_FILL_TIMEOUT", "30"))
MANAGE_TIMEOUT = float(os.environ.get("MANAGE_TIMEOUT", "0"))  # 0 = wait until TP/SL
ENCODING = os.environ.get("WS_ENCODING", "msgpack")  # price/trading stream encoding
MAX_BARS = 200


def _fmt_time(t):
    """Format the OHLC epoch time as Vietnam local time (UTC+7)."""
    try:
        t = int(t)
        if t > 1_000_000_000_000:  # milliseconds
            t //= 1000
        return datetime.fromtimestamp(t, timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return str(t)


def _res_minutes(resolution):
    """Minutes per bar for a DNSE resolution string ('1','5','1H','1D','1W')."""
    return {"1H": 60, "1D": 1440, "1W": 10080}.get(resolution, int(resolution) if resolution.isdigit() else 1)


def fetch_history(rest, symbol, resolution, market_type, bars=MAX_BARS):
    """Seed the candle buffer from the historical OHLC REST endpoint.

    Returns up to `bars` most recent Candles (oldest -> newest), or [] on failure.
    """
    now = int(time.time())
    lookback = max(bars * _res_minutes(resolution) * 60 * 12, 5 * 86400)  # generous window
    status, body = rest.get_ohlc(
        bar_type=market_type,
        query={"symbol": symbol, "resolution": resolution, "from": now - lookback, "to": now},
    )
    if not status or status >= 300:
        log(f"  (lấy nến lịch sử lỗi [{status}]: {body}) — chỉ dùng nến trực tiếp")
        return []
    d = json.loads(body)
    t, o, h, low, c, v = (d.get(k, []) for k in ("t", "o", "h", "l", "c", "v"))
    out = [Candle(str(t[i]), o[i], h[i], low[i], c[i], v[i]) for i in range(len(t))]
    return out[-bars:]


def _append_bar(candles, bar):
    """Append a streamed bar; if it repeats the last bar's time, update in place."""
    c = Candle(str(bar.time), bar.open, bar.high, bar.low, bar.close, bar.volume)
    if candles and candles[-1].time == c.time:
        candles[-1] = c
    else:
        candles.append(c)
    del candles[:-MAX_BARS]


def _client():
    return DNSEClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_BASE_URL", "https://openapi.dnse.com.vn"),
        api_version=os.environ.get("DNSE_API_VERSION", "2026-07-23"),
    )


def _print_plan(strat, signal, quantity):
    log("\n=== KẾ HOẠCH VÀO LỆNH ===")
    log(f"  chiến lược : {strat.name}")
    log(f"  mã        : {SYMBOL}  (tín hiệu từ {OHLC_SYMBOL})")
    log(f"  chiều     : {signal.side}")
    log(f"  giá vào   : {to_order_price(MARKET_TYPE, signal.entry)}")
    log(f"  cắt lỗ    : {to_order_price(MARKET_TYPE, signal.stop_loss)}")
    log(f"  chốt lời  : {to_order_price(MARKET_TYPE, signal.take_profit)}")
    log(f"  khối lượng: {quantity}" + (f"  (rủi ro {RISK_POINTS} điểm)" if RISK_POINTS else ""))
    log(f"  lý do     : {signal.reason}")


async def trade_loop(rest, ws, strat, price):
    """Seed history, subscribe once, then loop forever: signal -> trade -> repeat.

    A failed/unfilled order is only logged — the loop keeps watching for the next
    signal. New signals are ignored while a trade is being managed.
    """
    candles = fetch_history(rest, OHLC_SYMBOL, RESOLUTION, MARKET_TYPE)
    log(f"Đã nạp {len(candles)} nến lịch sử {RESOLUTION}m của {OHLC_SYMBOL}")
    box = {"signal": None}
    fired = asyncio.Event()
    busy = {"v": False}  # True while a trade is being placed/managed

    def on_ohlc(bar: Ohlc):
        # Combine history + the new bar for the decision.
        _append_bar(candles, bar)

        # Log every OHLC bar received.
        log(f"[OHLC {bar.symbol} {RESOLUTION}m {_fmt_time(bar.time)}] "
              f"O={bar.open} H={bar.high} L={bar.low} C={bar.close} V={bar.volume} "
              f"(bars={len(candles)})")

        # Log whether entry conditions are met — and whether we act on them.
        sig = strat.analyze(candles)
        if not sig.actionable:
            log(f"  ❌ chưa đủ điều kiện: {sig.reason}")
        elif busy["v"]:
            log(f"  ⏸ đủ điều kiện ({sig.side}) nhưng ĐANG GIỮ 1 vị thế → bỏ qua (mỗi lần 1 lệnh)")
        elif box["signal"] is not None:
            log(f"  ⏸ đủ điều kiện ({sig.side}) nhưng đã có tín hiệu đang chờ xử lý → bỏ qua")
        else:
            log(f"  ✅ ĐỦ ĐIỀU KIỆN vào lệnh: {sig.side} entry={sig.entry} "
                f"SL={sig.stop_loss} TP={sig.take_profit} | {sig.reason}")
            box["signal"] = sig
            fired.set()

    await ws.subscribe_ohlc_closed(
        [OHLC_SYMBOL], resolution=RESOLUTION, on_ohlc=on_ohlc, encoding=ENCODING
    )
    log(f"Đang nghe nến {RESOLUTION}m {ENCODING} của {OHLC_SYMBOL} "
          f"(giao dịch {SYMBOL}) với chiến lược '{strat.name}'...")

    while True:
        await fired.wait()
        fired.clear()
        signal, box["signal"] = box["signal"], None
        if signal is None:
            continue

        quantity = size_by_risk(signal.entry, signal.stop_loss, RISK_POINTS, QUANTITY)
        _print_plan(strat, signal, quantity)

        if not PLACE_ORDER:
            log("CHẠY THỬ — đặt PLACE_ORDER=1 để vào lệnh; tiếp tục theo dõi tín hiệu.\n")
            continue

        busy["v"] = True
        manager = _new_manager(rest, ws, quantity)
        price["cb"] = manager.feed_price  # route live-OHLC prices into TP/SL
        try:
            log("Đang vào lệnh + quản lý TP/SL...")
            _report(await manager.run(signal))
        except Exception as exc:  # never let a trade error stop the app
            log(f"Lỗi khi đặt/quản lý lệnh: {type(exc).__name__}: {exc} — tiếp tục theo dõi")
        finally:
            price["cb"] = None
            busy["v"] = False
        log("Tiếp tục theo dõi tín hiệu tiếp theo...\n")


def _loan_package_id(rest):
    status, body = rest.get_loan_packages(ACCOUNT_NO, market_type=MARKET_TYPE, symbol=SYMBOL)
    packages = json.loads(body).get("loanPackages", []) if status and status < 300 else []
    return packages[0]["id"] if packages else None


def _open_qty(rest, symbol):
    """Broker's current OPEN quantity for `symbol` (None if the query fails).

    The positions endpoint returns {"positions": [...]}, each with openQuantity
    and a status (OPEN/CLOSED). Sum the open quantity of matching-symbol entries.
    """
    status, body = rest.get_positions(ACCOUNT_NO, market_type=MARKET_TYPE)
    if not status or status >= 300:
        return None
    total = 0
    for pos in json.loads(body).get("positions", []):
        if pos.get("symbol") == symbol:
            total += pos.get("openQuantity", 0) or 0
    return total


def _new_manager(rest, ws, quantity):
    return PositionManager(
        rest, ws,
        account_no=ACCOUNT_NO, symbol=SYMBOL, market_type=MARKET_TYPE,
        quantity=quantity, loan_package_id=_loan_package_id(rest),
        trading_token=ensure_trading_token(rest),
        entry_fill_timeout=ENTRY_FILL_TIMEOUT, manage_timeout=MANAGE_TIMEOUT,
        encoding=ENCODING,
    )


def _report(result):
    log("\n=== KẾT QUẢ ===")
    if result.filled:
        log(f"  thoát={result.reason}  giá_vào={result.entry_price}  "
              f"giá_ra={result.exit_price}  sl={result.quantity}  "
              f"lãi/lỗ={result.pnl_points:+.2f} điểm")
    else:
        log(f"  không vào lệnh: {result.reason}")


async def _resume_if_any(rest, ws, price):
    """If a persisted position exists (and is still open at the broker), manage it.

    Returns True if it handled a resume (caller should stop), else False.
    """
    saved = load_position()
    if not (saved and saved.get("symbol") == SYMBOL and saved.get("account_no") == ACCOUNT_NO):
        return False

    log(f"\nTìm thấy vị thế đã lưu: {saved}")
    if not PLACE_ORDER:
        log("CHẠY THỬ — sẽ khôi phục quản lý vị thế này. Đặt PLACE_ORDER=1 để khôi phục.")
        return True

    open_qty = _open_qty(rest, SYMBOL)
    if not open_qty:  # 0 or None -> closed/settled while the app was down
        log("Sàn báo không còn vị thế MỞ cho mã này (đã đóng) → xoá trạng thái cũ.")
        clear_position()
        return False

    log(f"Sàn xác nhận còn {open_qty} vị thế mở → khôi phục quản lý TP/SL.")
    manager = _new_manager(rest, ws, int(saved["quantity"]))
    price["cb"] = manager.feed_price
    try:
        _report(await manager.resume(saved))
    finally:
        price["cb"] = None
    return True


async def main():
    rest = _client()
    strat = get_strategy(STRATEGY)

    # Prepare the trading token up front so we're ready to place orders (does the
    # OTP flow now if needed). Cached to file — reused on the next run within ~8h.
    if PLACE_ORDER:
        log("Chuẩn bị trading token để sẵn sàng đặt lệnh...")
        ensure_trading_token(rest)

    ws = TradingClient(
        api_key=os.environ.get("DNSE_API_KEY", "replace-with-api-key"),
        api_secret=os.environ.get("DNSE_API_SECRET", "replace-with-api-secret"),
        base_url=os.environ.get("DNSE_WS_URL", "wss://ws-openapi.dnse.com.vn"),
        encoding=ENCODING,
    )
    await ws.connect()

    # Live OHLC price feed for TP/SL risk management — subscribed once at startup,
    # NOT logged per message. Forwards the current price to the active manager.
    price = {"last": None, "cb": None}

    def on_price(bar: Ohlc):
        price["last"] = bar.close
        if price["cb"] is not None:
            price["cb"](bar.close)

    await ws.subscribe_ohlc([OHLC_SYMBOL], resolution=RESOLUTION, on_ohlc=on_price, encoding=ENCODING)
    log(f"Nghe nến {RESOLUTION}m (thường) của {OHLC_SYMBOL} cho TP/SL (không log từng nến)")

    try:
        # Resume a position carried over from a previous run, if any (one-shot).
        await _resume_if_any(rest, ws, price)
        # Then run continuously: watch signals, trade, and keep going.
        await trade_loop(rest, ws, strat, price)
    finally:
        await ws.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
