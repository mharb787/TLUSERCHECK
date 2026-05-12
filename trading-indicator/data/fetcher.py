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
