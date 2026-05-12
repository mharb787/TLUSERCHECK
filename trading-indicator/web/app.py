import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from flask import Flask, render_template, jsonify, request
from config import TOP_10_COINS, TIMEFRAMES
from data.fetcher import fetch_ohlcv, fetch_ticker
from data.tv_analysis import get_local_signal, get_tv_signal
from prediction.candle_predictor import predict_candles
from prediction.backtester import run_backtest
from visualization.chart import build_chart

app = Flask(__name__)


@app.route("/")
def index():
    coins = [{"symbol": c["symbol"], "name": c["name"]} for c in TOP_10_COINS]
    timeframes = [{"key": k, "label": v["label"]} for k, v in TIMEFRAMES.items()]
    return render_template("index.html", coins=coins, timeframes=timeframes)


@app.route("/api/analyze")
def analyze():
    symbol = request.args.get("symbol", "BTC").upper()
    tf     = request.args.get("tf", "1h")

    coin = next((c for c in TOP_10_COINS if c["symbol"] == symbol), None)
    if not coin or tf not in TIMEFRAMES:
        return jsonify({"error": "رمز أو فريم غير صحيح"}), 400

    tf_cfg = TIMEFRAMES[tf]

    try:
        df        = fetch_ohlcv(coin["binance"], tf_cfg["ccxt"])
        try:
            signal = get_tv_signal(coin["tv"], tf)
        except Exception as tv_error:
            signal = get_local_signal(df)
            signal["warning"] = f"TradingView unavailable: {tv_error}"

        predicted = predict_candles(df, signal)
        backtest  = run_backtest(df)
        fig       = build_chart(df, predicted, backtest, coin["symbol"], tf, signal)

        direction_map = {"BUY": "شراء", "SELL": "بيع", "NEUTRAL": "محايد"}
        direction_color = {"BUY": "#00C853", "SELL": "#D50000", "NEUTRAL": "#FF6F00"}
        rec = signal["recommendation"]

        return jsonify({
            "chart":     fig.to_json(),
            "signal": {
                "recommendation": rec,
                "label":   direction_map.get(rec, rec),
                "color":   direction_color.get(rec, "#888"),
                "strength": round(signal["strength"] * 100, 1),
                "buy":     signal["buy_count"],
                "sell":    signal["sell_count"],
                "neutral": signal["neutral_count"],
                "source":  signal.get("source", "tradingview"),
                "warning": signal.get("warning"),
            },
            "backtest": {
                "accuracy":  backtest["accuracy_pct"],
                "buy_acc":   backtest["buy_accuracy"],
                "sell_acc":  backtest["sell_accuracy"],
                "signals":   backtest["total_signals"],
            },
            "predicted": predicted,
            "coin":  coin["name"],
            "tf":    tf_cfg["label"],
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/live")
def live():
    symbol = request.args.get("symbol", "BTC").upper()
    tf = request.args.get("tf", "1h")

    coin = next((c for c in TOP_10_COINS if c["symbol"] == symbol), None)
    if not coin or tf not in TIMEFRAMES:
        return jsonify({"error": "رمز أو فريم غير صحيح"}), 400

    try:
        ticker = fetch_ticker(coin["binance"])
        df = fetch_ohlcv(coin["binance"], TIMEFRAMES[tf]["ccxt"], limit=120)
        signal = get_local_signal(df)
        rec = signal["recommendation"]

        direction_map = {"BUY": "شراء", "SELL": "بيع", "NEUTRAL": "محايد"}
        direction_color = {"BUY": "#00C853", "SELL": "#D50000", "NEUTRAL": "#FF6F00"}

        return jsonify({
            "coin": coin["name"],
            "symbol": coin["symbol"],
            "price": ticker["last"],
            "bid": ticker["bid"],
            "ask": ticker["ask"],
            "change_pct": ticker["change_pct"],
            "timestamp": ticker["timestamp"],
            "signal": {
                "recommendation": rec,
                "label": direction_map.get(rec, rec),
                "color": direction_color.get(rec, "#888"),
                "strength": round(signal["strength"] * 100, 1),
                "source": "live-binance",
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/coins")
def coins_status():
    """Quick signal summary for all 10 coins (for dashboard cards)."""
    tf = request.args.get("tf", "1h")
    if tf not in TIMEFRAMES:
        tf = "1h"
    tf_cfg = TIMEFRAMES[tf]
    results = []
    for coin in TOP_10_COINS:
        try:
            try:
                signal = get_tv_signal(coin["tv"], tf)
            except Exception:
                df = fetch_ohlcv(coin["binance"], tf_cfg["ccxt"], limit=120)
                signal = get_local_signal(df)
            rec = signal["recommendation"]
            results.append({
                "symbol":  coin["symbol"],
                "name":    coin["name"],
                "rec":     rec,
                "strength": round(signal["strength"] * 100, 1),
                "source":   signal.get("source", "tradingview"),
            })
        except Exception:
            results.append({"symbol": coin["symbol"], "name": coin["name"],
                            "rec": "N/A", "strength": 0})
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
