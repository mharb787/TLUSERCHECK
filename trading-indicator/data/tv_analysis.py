from tradingview_ta import TA_Handler, Interval
from config import TV_EXCHANGE

_INTERVAL_MAP = {
    "1m":  Interval.INTERVAL_1_MINUTE,
    "5m":  Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES,
    "1h":  Interval.INTERVAL_1_HOUR,
    "4h":  Interval.INTERVAL_4_HOURS,
    "1d":  Interval.INTERVAL_1_DAY,
    "1w":  Interval.INTERVAL_1_WEEK,
}


def get_tv_signal(tv_symbol: str, timeframe: str) -> dict:
    """
    Returns TradingView analysis for a symbol/timeframe.

    Result keys:
        recommendation  : "BUY" | "SELL" | "NEUTRAL"
        buy_count       : number of buy indicators
        sell_count      : number of sell indicators
        neutral_count   : number of neutral indicators
        strength        : float 0-1 (confidence level)
        oscillators     : dict of oscillator values
        moving_averages : dict of MA values
    """
    interval = _INTERVAL_MAP.get(timeframe, Interval.INTERVAL_1_HOUR)

    handler = TA_Handler(
        symbol=tv_symbol,
        screener="crypto",
        exchange=TV_EXCHANGE,
        interval=interval,
    )

    analysis = handler.get_analysis()
    summary  = analysis.summary

    rec   = summary["RECOMMENDATION"]          # "BUY", "STRONG_BUY", etc.
    buy   = summary["BUY"]
    sell  = summary["SELL"]
    neut  = summary["NEUTRAL"]
    total = buy + sell + neut or 1

    # Normalise to simple direction
    direction = "NEUTRAL"
    if "BUY" in rec:
        direction = "BUY"
    elif "SELL" in rec:
        direction = "SELL"

    # Confidence: how dominant is the winning side
    dominant = max(buy, sell)
    strength = round(dominant / total, 4)

    return {
        "recommendation": direction,
        "source":         "tradingview",
        "raw_rec":         rec,
        "buy_count":       buy,
        "sell_count":      sell,
        "neutral_count":   neut,
        "strength":        strength,
        "oscillators":     analysis.oscillators,
        "moving_averages": analysis.moving_averages,
    }


def get_local_signal(df) -> dict:
    """Fallback signal from Binance candles when TradingView rate-limits requests."""
    close = df["close"]
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    last_ema9 = float(ema9.iloc[-1])
    last_ema21 = float(ema21.iloc[-1])
    last_rsi = float(rsi.iloc[-1]) if not rsi.empty else 50

    buy_score = 0
    sell_score = 0

    if last_ema9 > last_ema21:
        buy_score += 1
    elif last_ema9 < last_ema21:
        sell_score += 1

    if last_rsi < 35:
        buy_score += 1
    elif last_rsi > 65:
        sell_score += 1

    recent_change = float(close.iloc[-1] - close.iloc[-5]) if len(close) >= 5 else 0
    if recent_change > 0:
        buy_score += 1
    elif recent_change < 0:
        sell_score += 1

    neutral_count = max(0, 3 - buy_score - sell_score)
    direction = "NEUTRAL"
    if buy_score > sell_score:
        direction = "BUY"
    elif sell_score > buy_score:
        direction = "SELL"

    total = buy_score + sell_score + neutral_count or 1
    strength = round(max(buy_score, sell_score, neutral_count) / total, 4)

    return {
        "recommendation": direction,
        "source":         "local",
        "raw_rec":        f"LOCAL_{direction}",
        "buy_count":      buy_score,
        "sell_count":     sell_score,
        "neutral_count":  neutral_count,
        "strength":       strength,
        "oscillators":    {"RSI": last_rsi},
        "moving_averages": {"EMA9": last_ema9, "EMA21": last_ema21},
    }
