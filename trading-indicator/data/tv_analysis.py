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
        "raw_rec":         rec,
        "buy_count":       buy,
        "sell_count":      sell,
        "neutral_count":   neut,
        "strength":        strength,
        "oscillators":     analysis.oscillators,
        "moving_averages": analysis.moving_averages,
    }
