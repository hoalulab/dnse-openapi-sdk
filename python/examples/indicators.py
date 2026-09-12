#!/usr/bin/env python3
"""Tiny pure-Python technical indicators for the demo strategies.

Standard-library only (no numpy/talib). Good enough for examples; for production
use a vetted TA library. Each function returns None when there isn't enough data.
"""
from typing import List, Optional, Tuple


def rsi_series(closes: List[float], period: int = 14) -> List[float]:
    """Wilder's RSI as a series (one value per bar from index `period` onward)."""
    if len(closes) <= period:
        return []
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_gain, avg_loss = gains / period, losses / period

    def _rsi(g, loss):
        return 100.0 if loss == 0 else 100.0 - 100.0 / (1.0 + g / loss)

    out = [_rsi(avg_gain, avg_loss)]
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(d, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0.0)) / period
        out.append(_rsi(avg_gain, avg_loss))
    return out


def rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Wilder's RSI of the latest bar."""
    series = rsi_series(closes, period)
    return series[-1] if series else None


def ema_series(values: List[float], period: int) -> List[float]:
    """EMA as a series (seeded with the SMA of the first `period` values)."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    out = [ema]
    for v in values[period:]:
        ema += k * (v - ema)
        out.append(ema)
    return out  # out[-1] aligns with the latest bar


def macd_hist(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9
              ) -> List[float]:
    """MACD histogram (macd line - signal line) as a series aligned to the latest bar."""
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    if not fast_ema or not slow_ema:
        return []
    m = min(len(fast_ema), len(slow_ema))
    macd_line = [fast_ema[-m + i] - slow_ema[-m + i] for i in range(m)]
    sig = ema_series(macd_line, signal)
    if not sig:
        return []
    k = min(len(macd_line), len(sig))
    return [macd_line[-k + i] - sig[-k + i] for i in range(k)]


def atr(highs, lows, closes, period: int = 14) -> Optional[float]:
    """Wilder's ATR of the latest bar."""
    n = len(closes)
    if n <= period:
        return None
    trs = [max(highs[i] - lows[i],
               abs(highs[i] - closes[i - 1]),
               abs(lows[i] - closes[i - 1])) for i in range(1, n)]
    val = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        val = (val * (period - 1) + trs[i]) / period
    return val


def _wilder_smooth(values: List[float], period: int) -> List[float]:
    """Wilder running sum smoothing (seed = sum of first `period`)."""
    if len(values) < period:
        return []
    smoothed = [sum(values[:period])]
    for i in range(period, len(values)):
        smoothed.append(smoothed[-1] - smoothed[-1] / period + values[i])
    return smoothed


def adx(highs, lows, closes, period: int = 14) -> Optional[float]:
    """Wilder's ADX (trend strength) of the latest bar."""
    n = len(closes)
    if n <= 2 * period:
        return None
    trs, plus_dm, minus_dm = [], [], []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    atr = _wilder_smooth(trs, period)
    pdm = _wilder_smooth(plus_dm, period)
    mdm = _wilder_smooth(minus_dm, period)
    dxs = []
    for a, p, m in zip(atr, pdm, mdm):
        if a == 0:
            dxs.append(0.0)
            continue
        pdi, mdi = 100 * p / a, 100 * m / a
        s = pdi + mdi
        dxs.append(100 * abs(pdi - mdi) / s if s else 0.0)
    if len(dxs) < period:
        return sum(dxs) / len(dxs) if dxs else None
    val = sum(dxs[:period]) / period
    for i in range(period, len(dxs)):
        val = (val * (period - 1) + dxs[i]) / period
    return val


def _midpoint_at(highs, lows, end: int, period: int) -> float:
    """(highest high + lowest low) / 2 over the `period` bars ending at index `end`."""
    lo = end - period + 1
    return (max(highs[lo:end + 1]) + min(lows[lo:end + 1])) / 2.0


def ichimoku(highs, lows, tenkan_p=9, kijun_p=26, senkou_b_p=52, displacement=26
             ) -> Optional[Tuple[float, float, float, float]]:
    """Return (tenkan, kijun, senkou_a, senkou_b) at the latest bar — full Ichimoku.

    Tenkan and Kijun are the current conversion/base lines. Senkou A/B are the
    *cloud under the current price*: the leading spans are plotted `displacement`
    bars into the future, so the cloud aligned with "now" is the one computed
    `displacement` bars ago. We therefore evaluate the spans at index
    (n - 1 - displacement), i.e. with the standard 26-period forward shift.

    Returns None until there is enough history (senkou_b_p + displacement bars).
    """
    n = len(highs)
    past = n - 1 - displacement          # bar whose leading spans display at "now"
    if past < senkou_b_p - 1:
        return None
    tenkan = _midpoint_at(highs, lows, n - 1, tenkan_p)
    kijun = _midpoint_at(highs, lows, n - 1, kijun_p)
    senkou_a = (_midpoint_at(highs, lows, past, tenkan_p)
                + _midpoint_at(highs, lows, past, kijun_p)) / 2.0
    senkou_b = _midpoint_at(highs, lows, past, senkou_b_p)
    return tenkan, kijun, senkou_a, senkou_b
