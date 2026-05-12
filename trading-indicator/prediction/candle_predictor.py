import numpy as np
import pandas as pd
from config import PREDICTED_CANDLES


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range for candle-size estimation."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]


def _body_ratio(df: pd.DataFrame, period: int = 14) -> float:
    """Average body-to-range ratio over recent candles."""
    body  = (df["close"] - df["open"]).abs()
    rng   = (df["high"]  - df["low"]).replace(0, np.nan)
    ratio = (body / rng).dropna()
    return float(ratio.tail(period).mean())


def predict_candles(
    df: pd.DataFrame,
    signal: dict,
    n: int = PREDICTED_CANDLES,
) -> list[dict]:
    """
    Generate n predicted future candles based on TV signal + ATR.

    Each candle dict contains:
        open, high, low, close  – predicted OHLC
        direction               – "BUY" | "SELL" | "NEUTRAL"
        color                   – hex color string
        candle_index            – 1-based position (1 = next candle)
    """
    direction  = signal["recommendation"]
    strength   = signal["strength"]          # 0-1 confidence
    last_close = float(df["close"].iloc[-1])
    atr        = _atr(df)
    body_ratio = _body_ratio(df)

    candles = []
    price   = last_close

    for i in range(1, n + 1):
        # Scale movement: stronger signal → bigger move, tapers off over time
        decay     = 1 / (1 + 0.3 * (i - 1))
        move_size = atr * strength * decay

        if direction == "BUY":
            open_  = price
            close_ = price + move_size * body_ratio
            high_  = close_ + atr * (1 - body_ratio) * 0.5
            low_   = open_  - atr * (1 - body_ratio) * 0.3
            color  = "#00C853"   # green
        elif direction == "SELL":
            open_  = price
            close_ = price - move_size * body_ratio
            high_  = open_  + atr * (1 - body_ratio) * 0.3
            low_   = close_ - atr * (1 - body_ratio) * 0.5
            color  = "#D50000"   # red
        else:
            half   = move_size * 0.3
            open_  = price
            close_ = price + np.random.choice([-1, 1]) * half
            high_  = max(open_, close_) + atr * 0.2
            low_   = min(open_, close_) - atr * 0.2
            color  = "#FF6F00"   # amber

        candles.append({
            "candle_index": i,
            "open":         round(open_,  8),
            "high":         round(high_,  8),
            "low":          round(low_,   8),
            "close":        round(close_, 8),
            "direction":    direction,
            "color":        color,
        })
        price = close_

    return candles
