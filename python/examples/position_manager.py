#!/usr/bin/env python3
"""Minimal risk / position management for the auto-trader demo.

Separated from the strategy and the orchestrator so it can be swapped or reused.
Responsibilities:
  * size_by_risk(): simple position sizing from a risk budget + stop distance.
  * PositionManager: place the entry, wait for the fill, then close the whole
    filled quantity when price touches take-profit or stop-loss (or a time limit).

This is a demo — one position at a time, whole-position exit, no scaling/partials,
no trailing. Prices for TP/SL comparison are in the same unit the stream/strategy
use; only order placement is converted to the API unit via market_utils.
"""
import asyncio
import functools
import json
from dataclasses import dataclass
from typing import Optional

from market_utils import to_order_price
from position_store import clear_position, save_position
from strategy_base import Signal
from log_util import log


async def _run_blocking(func, *args, **kwargs):
    """Run a blocking DNSEClient (urllib3) call without stalling the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


def size_by_risk(entry, stop_loss, risk_points, min_qty=1):
    """Position sizing: quantity so that a stop-out loses ~`risk_points` in total.

    quantity = risk_points / |entry - stop_loss|. Returns min_qty when risk_points
    is 0/unset (fixed sizing) or the stop distance is degenerate.
    """
    distance = abs(entry - stop_loss)
    if risk_points and distance > 0:
        return max(min_qty, int(risk_points // distance))
    return min_qty


@dataclass
class TradeResult:
    """Outcome of a managed trade."""

    filled: bool
    reason: str                    # tp | sl | timeout | entry_failed | entry_not_filled
    side: Optional[str] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0

    @property
    def pnl_points(self) -> float:
        if not self.filled or self.side is None:
            return 0.0
        move = self.exit_price - self.entry_price
        return move if self.side == "NB" else -move


class PositionManager:
    """Places an entry, waits for the fill, then exits on TP/SL/timeout."""

    def __init__(self, rest, ws, *, account_no, symbol, market_type, quantity,
                 loan_package_id=None, trading_token=None,
                 entry_fill_timeout=30.0, manage_timeout=0.0, encoding="msgpack"):
        self.rest = rest
        self.ws = ws
        self.account_no = account_no
        self.symbol = symbol
        self.market_type = market_type
        self.quantity = quantity
        self.loan_package_id = loan_package_id
        self.trading_token = trading_token
        self.entry_fill_timeout = entry_fill_timeout
        self.manage_timeout = manage_timeout  # 0 = wait indefinitely for TP/SL
        self.encoding = encoding

        self._signal = None
        self._entry_id = None
        self._filled_qty = 0
        self._avg_price = 0.0
        self._entry_filled = asyncio.Event()
        self._last_price = None
        self._exit = asyncio.Event()
        self._exit_reason = None

    # ── order placement (off the event loop) ─────────────────────────────────
    async def _post(self, side, price, qty):
        payload = {
            "symbol": self.symbol, "side": side,
            "orderType": "LO", "quantity": qty,
            "price": to_order_price(self.market_type, price),
        }
        if self.loan_package_id is not None:
            payload["loanPackageId"] = self.loan_package_id
        return await _run_blocking(
            self.rest.post_order, account_no=self.account_no,
            market_type=self.market_type, payload=payload,
            trading_token=self.trading_token, order_category="NORMAL",
        )

    # ── realtime event handlers ──────────────────────────────────────────────
    def _on_order(self, o):
        # Log every order event for visibility.
        mine = self._entry_id is not None and str(o.id) == str(self._entry_id)
        log(f"  [sự kiện lệnh | {'CỦA TÔI' if mine else 'khác'}] id={o.id} mã={o.symbol} "
            f"chiều={o.side} trạng thái={o.orderStatus} khớp={o.fillQuantity}/{o.quantity} giá={o.price}")
        if mine and o.fillQuantity and o.fillQuantity > 0:
            self._filled_qty = o.fillQuantity
            self._avg_price = o.averagePrice or self._signal.entry
            self._entry_filled.set()

    def _on_position(self, p):
        # Log every position event for visibility.
        tag = "CỦA TÔI" if p.symbol == self.symbol else "khác"
        log(f"  [sự kiện vị thế | {tag}] mã={p.symbol} chiều={p.side} "
            f"kl_mở={p.openQuantity} giá_vốn={p.costPrice} trạng thái={p.status}")

    def feed_price(self, price):
        """Feed the current price (from the live OHLC stream) to drive TP/SL."""
        if price is None:
            return
        self._last_price = price
        self._check_exit(price)

    def _check_exit(self, price):
        if self._exit.is_set() or not self._entry_filled.is_set():
            return
        s = self._signal
        if s.side == "NB":                       # long: TP above, SL below
            if price >= s.take_profit:
                self._trigger("tp", price)
            elif price <= s.stop_loss:
                self._trigger("sl", price)
        else:                                    # short: TP below, SL above
            if price <= s.take_profit:
                self._trigger("tp", price)
            elif price >= s.stop_loss:
                self._trigger("sl", price)

    def _trigger(self, reason, price):
        self._exit_reason = reason
        log(f"  [chạm {reason.upper()}] giá={price} → đóng vị thế")
        self._exit.set()

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def _subscribe(self):
        await self.ws.subscribe_order_event(
            market_type=self.market_type, on_order_event=self._on_order, encoding=self.encoding
        )
        await self.ws.subscribe_position_event(
            market_type=self.market_type, on_position_event=self._on_position, encoding=self.encoding
        )
        # TP/SL prices are fed in via feed_price() from the app's live OHLC stream
        # (subscribed once at startup), so no per-manager price subscription here.
        await asyncio.sleep(0.3)  # let subscriptions register

    def _persist(self):
        """Save the open position so it survives an app restart."""
        save_position({
            "account_no": self.account_no,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "side": self._signal.side,
            "quantity": self._filled_qty,
            "entry_price": self._signal.entry,
            "avg_price": self._avg_price,
            "stop_loss": self._signal.stop_loss,
            "take_profit": self._signal.take_profit,
            "entry_order_id": self._entry_id,
        })

    async def run(self, signal) -> TradeResult:
        """Open a new position from a signal, then manage TP/SL to exit."""
        self._signal = signal
        await self._subscribe()

        # 1) place the entry order
        status, body = await self._post(signal.side, signal.entry, self.quantity)
        if not status or status >= 300:
            return TradeResult(False, f"entry_failed[{status}]: {body}", side=signal.side)
        self._entry_id = str(json.loads(body)["id"])
        log(f"Đã đặt lệnh vào {signal.side} id={self._entry_id} "
              f"@ {to_order_price(self.market_type, signal.entry)} sl={self.quantity}")

        # 2) wait for the fill
        try:
            await asyncio.wait_for(self._entry_filled.wait(), timeout=self.entry_fill_timeout)
        except asyncio.TimeoutError:
            await self._post_cancel()
            return TradeResult(False, "entry_not_filled", side=signal.side)

        self._persist()  # position is open → survive restarts
        return await self._manage_and_close()

    async def resume(self, saved) -> TradeResult:
        """Resume managing a persisted open position (skip entry/fill)."""
        self._signal = Signal(
            side=saved["side"], entry=saved["entry_price"],
            stop_loss=saved["stop_loss"], take_profit=saved["take_profit"],
        )
        self._filled_qty = int(saved["quantity"])
        self._avg_price = saved.get("avg_price", saved["entry_price"])
        self._entry_id = saved.get("entry_order_id")
        self._entry_filled.set()
        await self._subscribe()
        log(f"Khôi phục {self._signal.side} sl={self._filled_qty} giá_vào={self._avg_price} "
              f"TP={self._signal.take_profit} SL={self._signal.stop_loss}")
        return await self._manage_and_close()

    async def _manage_and_close(self) -> TradeResult:
        """Wait for TP/SL (or timeout), then close the whole position and forget it."""
        signal = self._signal
        if self._last_price is not None:
            self._check_exit(self._last_price)  # maybe already beyond a level
        log(f"Đang quản lý vị thế: TP={signal.take_profit} SL={signal.stop_loss} "
              f"(hết giờ={self.manage_timeout or '∞'}s)")
        try:
            if self.manage_timeout and self.manage_timeout > 0:
                await asyncio.wait_for(self._exit.wait(), timeout=self.manage_timeout)
            else:
                await self._exit.wait()
            reason = self._exit_reason
        except asyncio.TimeoutError:
            reason = "timeout"

        # close the whole filled quantity at the current price (marketable LO)
        close_side = "NS" if signal.side == "NB" else "NB"
        exit_price = self._last_price if self._last_price is not None else signal.entry
        status, body = await self._post(close_side, exit_price, self._filled_qty)
        log(f"Đóng ({reason}) {close_side} sl={self._filled_qty} "
              f"@ {to_order_price(self.market_type, exit_price)} → [{status}]")
        clear_position()  # position closed → forget it
        return TradeResult(True, reason, side=signal.side, entry_price=self._avg_price,
                           exit_price=exit_price, quantity=self._filled_qty)

    async def _post_cancel(self):
        await _run_blocking(
            self.rest.cancel_order, self.account_no, self._entry_id,
            market_type=self.market_type, trading_token=self.trading_token,
            order_category="NORMAL",
        )
        log(f"Lệnh vào không khớp trong {self.entry_fill_timeout:.0f}s → đã huỷ {self._entry_id}")
