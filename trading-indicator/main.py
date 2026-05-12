"""
مؤشر التداول المخصص – أكبر 10 عملات رقمية
============================================
الاستخدام:
    python main.py                          # BTC / 1h (افتراضي)
    python main.py --symbol ETH --tf 4h
    python main.py --symbol SOL --tf 15m --output sol_15m.html
    python main.py --all --tf 1d           # يولّد تقرير لجميع العملات
"""

import argparse
import os
import sys

# ── يضيف مجلد المشروع إلى مسار البحث ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from config import TOP_10_COINS, TIMEFRAMES
from data.fetcher      import fetch_ohlcv
from data.tv_analysis  import get_tv_signal
from prediction.candle_predictor import predict_candles
from prediction.backtester       import run_backtest
from visualization.chart         import build_chart


def run(symbol: str, timeframe: str, output: str | None = None) -> None:
    coin = next((c for c in TOP_10_COINS if c["symbol"] == symbol.upper()), None)
    if coin is None:
        print(f"[!] العملة '{symbol}' غير مدعومة. الخيارات: "
              + ", ".join(c["symbol"] for c in TOP_10_COINS))
        return

    tf_cfg = TIMEFRAMES.get(timeframe)
    if tf_cfg is None:
        print(f"[!] الفريم '{timeframe}' غير مدعوم. الخيارات: "
              + ", ".join(TIMEFRAMES.keys()))
        return

    print(f"\n{'='*55}")
    print(f"  {coin['name']} ({coin['symbol']}) | فريم: {tf_cfg['label']}")
    print(f"{'='*55}")

    # 1. جلب بيانات الأسعار
    print("► جلب بيانات OHLCV من Binance…")
    df = fetch_ohlcv(coin["binance"], tf_cfg["ccxt"])
    print(f"  ✓ {len(df)} شمعة")

    # 2. إشارة TradingView
    print("► قراءة إشارة TradingView…")
    signal = get_tv_signal(coin["tv"], timeframe)
    direction_ar = {"BUY": "شراء 📈", "SELL": "بيع 📉", "NEUTRAL": "محايد ↔"}
    print(f"  ✓ الإشارة: {direction_ar.get(signal['recommendation'])} "
          f"| قوة: {round(signal['strength']*100,1)}% "
          f"| Buy:{signal['buy_count']} Sell:{signal['sell_count']} Neutral:{signal['neutral_count']}")

    # 3. توقع 5 شمعات
    print("► توليد الشمعات المتوقعة…")
    predicted = predict_candles(df, signal)
    for c in predicted:
        print(f"  شمعة #{c['candle_index']}: "
              f"O={c['open']:.4f}  H={c['high']:.4f}  "
              f"L={c['low']:.4f}   C={c['close']:.4f}  [{c['color']}]")

    # 4. Backtest
    print("► تشغيل الـ Backtest…")
    backtest = run_backtest(df)
    print(f"  ✓ الدقة الإجمالية: {backtest['accuracy_pct']}%  "
          f"| شراء: {backtest['buy_accuracy']}%  "
          f"| بيع: {backtest['sell_accuracy']}%  "
          f"| إشارات: {backtest['total_signals']}")

    # 5. رسم المخطط
    print("► بناء المخطط التفاعلي…")
    fig = build_chart(df, predicted, backtest, coin["symbol"], timeframe, signal)

    out_path = output or f"{coin['symbol']}_{timeframe}.html"
    fig.write_html(out_path)
    print(f"  ✓ تم الحفظ: {out_path}")


def run_all(timeframe: str) -> None:
    for coin in TOP_10_COINS:
        try:
            run(coin["symbol"], timeframe,
                output=f"reports/{coin['symbol']}_{timeframe}.html")
        except Exception as e:
            print(f"[!] خطأ في {coin['symbol']}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="مؤشر التداول المخصص – أكبر 10 عملات رقمية"
    )
    parser.add_argument("--symbol",  default="BTC",
                        help="رمز العملة مثل BTC أو ETH")
    parser.add_argument("--tf",      default="1h",
                        help="الفريم: 1m 5m 15m 1h 4h 1d 1w")
    parser.add_argument("--output",  default=None,
                        help="مسار ملف HTML للمخطط")
    parser.add_argument("--all",     action="store_true",
                        help="تشغيل جميع العملات العشر")
    args = parser.parse_args()

    if args.all:
        os.makedirs("reports", exist_ok=True)
        run_all(args.tf)
    else:
        run(args.symbol, args.tf, args.output)


if __name__ == "__main__":
    main()
