import ccxt
import pandas as pd
from config import OHLCV_LIMIT


_exchange = ccxt.binance()


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = OHLCV_LIMIT) -> pd.DataFrame:
    """Fetch OHLCV candles from Binance."""
    raw = _exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df.astype(float)


def fetch_ticker(symbol: str) -> dict:
    """Fetch the latest ticker snapshot from Binance."""
    ticker = _exchange.fetch_ticker(symbol)
    return {
        "last": ticker.get("last"),
        "bid": ticker.get("bid"),
        "ask": ticker.get("ask"),
        "change_pct": ticker.get("percentage"),
        "timestamp": ticker.get("timestamp"),
    }
