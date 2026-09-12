#!/usr/bin/env python3
"""Scalping strategy (demo — reference port, not trading advice).

Ported from the Go reference (internal/strategy/scalping.go). Short-term momentum
scalping for a fast timeframe (1m–3m) using:

  * EMA 8/21: a fresh cross scores most; price above/below the pair scores less.
  * RSI 7: rising momentum in a valid band (or a bounce from oversold).
  * MACD 8/17/9 histogram: positive & rising (long) / negative & falling (short).
  * ATR 7 filter: skip when volatility is too low (flat market).

Accumulates a score across those conditions (not a hard AND-gate) and fires when
it clears `min_score`. Stop-loss / take-profit are ATR-based (natural for scalps).
"""
from typing import List

from indicators import atr, ema_series, macd_hist, rsi_series
from strategy_base import Candle, Signal, Strategy, register


@register
class ScalpingStrategy(Strategy):
    """EMA 8/21 + RSI 7 + MACD 8/17/9 momentum scalper with ATR stops."""

    name = "scalping"

    def __init__(self, min_score=55.0, atr_floor=0.5, sl_atr_mult=1.5, reward_risk=1.5):
        # atr_floor tuned for VN30F1M 1m: ATR7 median ~0.97, p25 ~0.79. 0.7 skips
        # the quietest ~15% of bars (dead chop) while keeping most active bars.
        # (The Go reference used 2.0 — far too high for this timeframe.)
        # Lower (0.5) = more signals; higher (0.8–0.9) = fewer, higher-quality.
        self.min_score = min_score
        self.atr_floor = atr_floor        # skip when ATR below this (sideway)
        self.sl_atr_mult = sl_atr_mult    # stop distance = sl_atr_mult * ATR
        self.reward_risk = reward_risk

    def analyze(self, candles: List[Candle]) -> Signal:
        if len(candles) < 30:
            return Signal(reason=f"need 30 bars, have {len(candles)}")

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        ema_fast = ema_series(closes, 8)
        ema_slow = ema_series(closes, 21)
        rsi = rsi_series(closes, 7)
        hist = macd_hist(closes, 8, 17, 9)
        atr_val = atr(highs, lows, closes, 7)
        if (len(ema_fast) < 2 or len(ema_slow) < 2 or len(rsi) < 2
                or len(hist) < 2 or atr_val is None):
            return Signal(reason="not enough data for indicators")

        # ATR filter: too flat → skip
        if atr_val < self.atr_floor:
            return Signal(reason=f"ATR={atr_val:.2f} < {self.atr_floor} (flat) → skip")

        f, pf = ema_fast[-1], ema_fast[-2]
        s, ps = ema_slow[-1], ema_slow[-2]
        r, pr = rsi[-1], rsi[-2]
        h, ph = hist[-1], hist[-2]
        last = closes[-1]

        # ─── LONG ────────────────────────────────────────────────────────────
        score, reasons = 0.0, []
        if pf <= ps and f > s:
            score += 45
            reasons.append("EMA8 crossed up EMA21")
        elif f > s:
            score += 20
            reasons.append(f"price {last} above EMA8>EMA21")
        if r > pr and 40 <= r <= 65:
            score += 30
            reasons.append(f"RSI={r:.1f} rising")
        elif r < 35 and r > pr:
            score += 20
            reasons.append(f"RSI={r:.1f} bouncing from oversold")
        if h > 0 and h > ph:
            score += 25
            reasons.append("MACD hist positive & rising")
        elif h > ph and h > -1.0:
            score += 10
            reasons.append("MACD hist turning up")

        if score >= self.min_score:
            sl = last - self.sl_atr_mult * atr_val
            risk = last - sl
            return Signal("NB", last, sl, last + self.reward_risk * risk,
                          f"LONG {score:.0f}pts: " + "; ".join(reasons))

        # ─── SHORT ───────────────────────────────────────────────────────────
        score, reasons = 0.0, []
        if pf >= ps and f < s:
            score += 45
            reasons.append("EMA8 crossed down EMA21")
        elif f < s:
            score += 20
            reasons.append(f"price {last} below EMA8<EMA21")
        if r < pr and 35 <= r <= 60:
            score += 30
            reasons.append(f"RSI={r:.1f} falling")
        elif r > 65 and r < pr:
            score += 20
            reasons.append(f"RSI={r:.1f} pulling back from overbought")
        if h < 0 and h < ph:
            score += 25
            reasons.append("MACD hist negative & falling")
        elif h < ph and h < 1.0:
            score += 10
            reasons.append("MACD hist turning down")

        if score >= self.min_score:
            sl = last + self.sl_atr_mult * atr_val
            risk = sl - last
            return Signal("NS", last, sl, last - self.reward_risk * risk,
                          f"SHORT {score:.0f}pts: " + "; ".join(reasons))

        return Signal(reason=f"score below {self.min_score} (ATR={atr_val:.2f})")
