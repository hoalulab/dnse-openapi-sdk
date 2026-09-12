#!/usr/bin/env python3
"""Ichimoku Cloud strategy (demo — reference port, not trading advice).

Ported from the Go reference (internal/strategy/ichimoku_cloud.go) to this SDK's
pluggable Strategy interface. It scores long/short setups from:

  * Price vs the Kumo (cloud): above cloud = bullish, below = bearish   [35 pts]
  * Tenkan vs Kijun: a fresh cross scores more than a plain stack       [35/15]
  * Chikou (lagging span) vs price 26 bars ago                          [15 pts]
  * RSI confirmation (not overbought/oversold)                          [15 pts]
  * ADX filter: skip when the market is too flat (no trend)

When the score clears `min_score`, it emits a Signal with a structure-based stop
(the far side of the cloud) and an R:R-multiple take-profit.

This shows a second, more involved strategy alongside strategy_price_action.py —
customers can copy this shape for their own indicators.
"""
from typing import List

from indicators import adx, ichimoku, rsi
from strategy_base import Candle, Signal, Strategy, register


@register
class IchimokuCloudStrategy(Strategy):
    """Ichimoku trend/momentum strategy with cloud stop and R:R target."""

    name = "ichimoku_cloud"

    def __init__(self, min_score=60.0, reward_risk=2.0, adx_floor=18.0,
                 rsi_period=14, rsi_overbought=70.0, rsi_oversold=30.0):
        self.min_score = min_score
        self.reward_risk = reward_risk
        self.adx_floor = adx_floor
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    def analyze(self, candles: List[Candle]) -> Signal:
        # Need 52 (Senkou B) + 26 (forward displacement) + 1 prior bar for the cross.
        if len(candles) < 80:
            return Signal(reason=f"need 80 bars, have {len(candles)}")

        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]

        adx_val = adx(highs, lows, closes, 14)
        if adx_val is None:
            return Signal(reason="not enough data for ADX")
        if adx_val < self.adx_floor:
            return Signal(reason=f"ADX={adx_val:.1f} < {self.adx_floor} (sideway) → skip")

        now = ichimoku(highs, lows)
        prev = ichimoku(highs[:-1], lows[:-1])
        if now is None or prev is None:
            return Signal(reason="not enough data for Ichimoku")
        tenkan, kijun, senkou_a, senkou_b = now
        prev_tenkan, prev_kijun, _, _ = prev
        cloud_top, cloud_bot = max(senkou_a, senkou_b), min(senkou_a, senkou_b)

        last_close = closes[-1]
        rsi_val = rsi(closes, self.rsi_period) or 50.0
        chikou_above = closes[-1] > closes[-27]
        chikou_below = closes[-1] < closes[-27]

        # ─── LONG ────────────────────────────────────────────────────────────
        score, reasons = 0.0, []
        if last_close > cloud_top:
            score += 35
            reasons.append(f"price {last_close} above Kumo {cloud_top:.2f}")
        if prev_tenkan <= prev_kijun and tenkan > kijun:
            score += 35
            reasons.append(f"Tenkan {tenkan:.2f} crossed up Kijun {kijun:.2f}")
        elif tenkan > kijun:
            score += 15
            reasons.append(f"Tenkan {tenkan:.2f} > Kijun {kijun:.2f}")
        if chikou_above:
            score += 15
            reasons.append("Chikou above price 26 bars ago")
        if self.rsi_oversold < rsi_val < self.rsi_overbought and rsi_val > 45:
            score += 15
            reasons.append(f"RSI={rsi_val:.1f} bullish-valid")

        if score >= self.min_score:
            risk = last_close - cloud_bot
            if risk > 0:
                return Signal(
                    side="NB", entry=last_close, stop_loss=cloud_bot,
                    take_profit=last_close + self.reward_risk * risk,
                    reason=f"LONG {score:.0f}pts: " + "; ".join(reasons),
                )

        # ─── SHORT ───────────────────────────────────────────────────────────
        score, reasons = 0.0, []
        if last_close < cloud_bot:
            score += 35
            reasons.append(f"price {last_close} below Kumo {cloud_bot:.2f}")
        if prev_tenkan >= prev_kijun and tenkan < kijun:
            score += 35
            reasons.append(f"Tenkan {tenkan:.2f} crossed down Kijun {kijun:.2f}")
        elif tenkan < kijun:
            score += 15
            reasons.append(f"Tenkan {tenkan:.2f} < Kijun {kijun:.2f}")
        if chikou_below:
            score += 15
            reasons.append("Chikou below price 26 bars ago")
        if self.rsi_oversold < rsi_val < self.rsi_overbought and rsi_val < 55:
            score += 15
            reasons.append(f"RSI={rsi_val:.1f} bearish-valid")

        if score >= self.min_score:
            risk = cloud_top - last_close
            if risk > 0:
                return Signal(
                    side="NS", entry=last_close, stop_loss=cloud_top,
                    take_profit=last_close - self.reward_risk * risk,
                    reason=f"SHORT {score:.0f}pts: " + "; ".join(reasons),
                )

        return Signal(reason=f"score below {self.min_score} (ADX={adx_val:.1f})")
