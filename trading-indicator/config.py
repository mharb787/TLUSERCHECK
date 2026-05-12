TOP_10_COINS = [
    {"symbol": "BTC",  "name": "Bitcoin",       "binance": "BTCUSDT",  "tv": "BTCUSDT"},
    {"symbol": "ETH",  "name": "Ethereum",      "binance": "ETHUSDT",  "tv": "ETHUSDT"},
    {"symbol": "BNB",  "name": "Binance Coin",  "binance": "BNBUSDT",  "tv": "BNBUSDT"},
    {"symbol": "XRP",  "name": "Ripple",        "binance": "XRPUSDT",  "tv": "XRPUSDT"},
    {"symbol": "SOL",  "name": "Solana",        "binance": "SOLUSDT",  "tv": "SOLUSDT"},
    {"symbol": "ADA",  "name": "Cardano",       "binance": "ADAUSDT",  "tv": "ADAUSDT"},
    {"symbol": "DOGE", "name": "Dogecoin",      "binance": "DOGEUSDT", "tv": "DOGEUSDT"},
    {"symbol": "TRX",  "name": "TRON",          "binance": "TRXUSDT",  "tv": "TRXUSDT"},
    {"symbol": "AVAX", "name": "Avalanche",     "binance": "AVAXUSDT", "tv": "AVAXUSDT"},
    {"symbol": "LINK", "name": "Chainlink",     "binance": "LINKUSDT", "tv": "LINKUSDT"},
]

TIMEFRAMES = {
    "1m":  {"ccxt": "1m",  "tv": "1",    "label": "1 دقيقة"},
    "5m":  {"ccxt": "5m",  "tv": "5",    "label": "5 دقائق"},
    "15m": {"ccxt": "15m", "tv": "15",   "label": "15 دقيقة"},
    "1h":  {"ccxt": "1h",  "tv": "60",   "label": "1 ساعة"},
    "4h":  {"ccxt": "4h",  "tv": "240",  "label": "4 ساعات"},
    "1d":  {"ccxt": "1d",  "tv": "1D",   "label": "يومي"},
    "1w":  {"ccxt": "1w",  "tv": "1W",   "label": "أسبوعي"},
}

PREDICTED_CANDLES = 5
OHLCV_LIMIT      = 500
BACKTEST_WINDOW  = 200

TV_EXCHANGE = "BINANCE"
