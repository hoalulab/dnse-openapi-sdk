#!/usr/bin/env python3
"""A minimal price-action breakout strategy (demo only — not trading advice).

Idea (deliberately simple):
  * Look at the last `lookback` candles (the "range"), excluding the newest bar.
  * If the newest bar CLOSES ABOVE the range high  -> break up   -> go long (NB).
  * If the newest bar CLOSES BELOW the range low   -> break down -> go short (NS).
  * Stop-loss = the opposite side of the range (structure-based).
  * Take-profit = entry +/- reward_risk * risk.

Swap this out for any other Strategy subclass — the auto-trader only depends on
the strategy_base.Strategy interface.
"""
from typing import List

from strategy_base import Candle, Signal, Strategy, register


@register
class PriceActionStrategy(Strategy):
    """Range-breakout price action with structure stop and R:R target."""

    name = "price_action"

    def __init__(self, lookback=10, reward_risk=2.0):
        self.lookback = lookback
        self.reward_risk = reward_risk

    def analyze(self, candles: List[Candle]) -> Signal:
        need = self.lookback + 1
        if len(candles) < need:
            return Signal(reason=f"need {need} bars, have {len(candles)}")

        window = candles[-need:-1]          # the range (exclude the newest bar)
        last = candles[-1]                  # the potential breakout bar
        range_high = max(c.high for c in window)
        range_low = min(c.low for c in window)
        entry = last.close

        # Break up -> long
        if last.close > range_high:
            risk = entry - range_low
            if risk <= 0:
                return Signal(reason="invalid risk (long)")
            return Signal(
                side="NB",
                entry=entry,
                stop_loss=range_low,
                take_profit=entry + self.reward_risk * risk,
                reason=f"close {entry} broke range high {range_high} (R:R={self.reward_risk})",
            )

        # Break down -> short
        if last.close < range_low:
            risk = range_high - entry
            if risk <= 0:
                return Signal(reason="invalid risk (short)")
            return Signal(
                side="NS",
                entry=entry,
                stop_loss=range_high,
                take_profit=entry - self.reward_risk * risk,
                reason=f"close {entry} broke range low {range_low} (R:R={self.reward_risk})",
            )

        return Signal(reason=f"inside range [{range_low}, {range_high}]")
