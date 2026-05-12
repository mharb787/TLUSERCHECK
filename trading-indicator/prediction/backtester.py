import pandas as pd
import numpy as np
from config import BACKTEST_WINDOW, PREDICTED_CANDLES


def _simulate_signal(df: pd.DataFrame, idx: int) -> str:
    """
    Simulate a TV-like signal at position idx using EMA cross + RSI.
    Returns "BUY", "SELL", or "NEUTRAL".
    """
    window = df.iloc[max(0, idx - 50): idx + 1]
    if len(window) < 30:
        return "NEUTRAL"

    close  = window["close"]
    ema9   = close.ewm(span=9,  adjust=False).mean()
    ema21  = close.ewm(span=21, adjust=False).mean()

    delta  = close.diff()
    gain   = delta.clip(lower=0).rolling(14).mean()
    loss   = (-delta.clip(upper=0)).rolling(14).mean()
    rs     = gain / loss.replace(0, np.nan)
    rsi    = 100 - (100 / (1 + rs))

    last_ema9  = ema9.iloc[-1]
    last_ema21 = ema21.iloc[-1]
    last_rsi   = rsi.iloc[-1]

    if last_ema9 > last_ema21 and last_rsi < 70:
        return "BUY"
    elif last_ema9 < last_ema21 and last_rsi > 30:
        return "SELL"
    return "NEUTRAL"


def _check_outcome(df: pd.DataFrame, start: int, direction: str, n: int) -> bool:
    """Check if the actual next n candles confirmed the direction."""
    if start + n >= len(df):
        return False
    future = df.iloc[start: start + n]
    net    = float(future["close"].iloc[-1]) - float(df["close"].iloc[start - 1])
    if direction == "BUY":
        return net > 0
    elif direction == "SELL":
        return net < 0
    return True


def run_backtest(df: pd.DataFrame, n: int = PREDICTED_CANDLES) -> dict:
    """
    Backtest the indicator signal over the last BACKTEST_WINDOW candles.

    Returns:
        accuracy_pct   : overall hit-rate %
        buy_accuracy   : hit-rate for BUY signals %
        sell_accuracy  : hit-rate for SELL signals %
        total_signals  : total non-neutral signals evaluated
        details        : list of per-signal dicts
    """
    if len(df) < BACKTEST_WINDOW + n + 50:
        return {"accuracy_pct": 0, "buy_accuracy": 0, "sell_accuracy": 0,
                "total_signals": 0, "details": []}

    start_idx = len(df) - BACKTEST_WINDOW - n
    end_idx   = len(df) - n

    results = []
    for i in range(start_idx, end_idx):
        signal = _simulate_signal(df, i)
        if signal == "NEUTRAL":
            continue
        correct = _check_outcome(df, i + 1, signal, n)
        results.append({"index": i, "signal": signal, "correct": correct})

    if not results:
        return {"accuracy_pct": 0, "buy_accuracy": 0, "sell_accuracy": 0,
                "total_signals": 0, "details": []}

    total   = len(results)
    correct = sum(r["correct"] for r in results)

    buys        = [r for r in results if r["signal"] == "BUY"]
    sells       = [r for r in results if r["signal"] == "SELL"]
    buy_acc     = round(sum(r["correct"] for r in buys)  / len(buys)  * 100, 2) if buys  else 0
    sell_acc    = round(sum(r["correct"] for r in sells) / len(sells) * 100, 2) if sells else 0
    overall_acc = round(correct / total * 100, 2)

    return {
        "accuracy_pct":  overall_acc,
        "buy_accuracy":  buy_acc,
        "sell_accuracy": sell_acc,
        "total_signals": total,
        "details":       results,
    }
