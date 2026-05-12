import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


_DISPLAY_CANDLES = 80   # how many real candles to show


def build_chart(
    df: pd.DataFrame,
    predicted: list[dict],
    backtest: dict,
    symbol: str,
    timeframe: str,
    signal: dict,
) -> go.Figure:
    """
    Build an interactive Plotly candlestick chart with:
      - Last _DISPLAY_CANDLES real candles
      - 5 predicted candles in a distinct colour
      - Probability annotation
    """
    real = df.tail(_DISPLAY_CANDLES).copy()

    # ── Build future timestamps ──────────────────────────────────────────────
    last_ts   = real.index[-1]
    tf_delta  = _infer_timedelta(real)
    future_ts = [last_ts + tf_delta * i for i in range(1, len(predicted) + 1)]

    # ── Subplots: candles (top) + volume (bottom) ────────────────────────────
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.02,
    )

    # Real candles
    fig.add_trace(
        go.Candlestick(
            x=real.index,
            open=real["open"], high=real["high"],
            low=real["low"],   close=real["close"],
            name="السعر الفعلي",
            increasing_line_color="#26A69A",
            decreasing_line_color="#EF5350",
        ),
        row=1, col=1,
    )

    # Volume bars
    colors_vol = ["#26A69A" if c >= o else "#EF5350"
                  for c, o in zip(real["close"], real["open"])]
    fig.add_trace(
        go.Bar(x=real.index, y=real["volume"], name="الحجم",
               marker_color=colors_vol, opacity=0.6),
        row=2, col=1,
    )

    # Predicted candles (one trace per candle for individual colours)
    for c, ts in zip(predicted, future_ts):
        fig.add_trace(
            go.Candlestick(
                x=[ts],
                open=[c["open"]], high=[c["high"]],
                low=[c["low"]],   close=[c["close"]],
                name=f"متوقعة #{c['candle_index']}",
                increasing_line_color=c["color"],
                decreasing_line_color=c["color"],
                increasing_fillcolor=c["color"],
                decreasing_fillcolor=c["color"],
                opacity=0.75,
                showlegend=(c["candle_index"] == 1),
            ),
            row=1, col=1,
        )

    # Separator line between real and predicted
    fig.add_vline(
        x=last_ts, line_dash="dash", line_color="gray", line_width=1,
        row=1, col=1,
    )

    # ── Probability annotation ───────────────────────────────────────────────
    direction_ar = {"BUY": "📈 شراء", "SELL": "📉 بيع", "NEUTRAL": "↔ محايد"}
    acc          = backtest.get("accuracy_pct", 0)
    buy_acc      = backtest.get("buy_accuracy",  0)
    sell_acc     = backtest.get("sell_accuracy", 0)
    direction    = signal["recommendation"]
    strength_pct = round(signal["strength"] * 100, 1)

    annotation_text = (
        f"<b>{symbol} | {timeframe}</b><br>"
        f"إشارة: {direction_ar.get(direction, direction)}<br>"
        f"قوة الإشارة: {strength_pct}%<br>"
        f"دقة الإشارة (backtest): {acc}%<br>"
        f"دقة الشراء: {buy_acc}% | دقة البيع: {sell_acc}%"
    )

    fig.add_annotation(
        text=annotation_text,
        xref="paper", yref="paper",
        x=0.01, y=0.97,
        align="right",
        showarrow=False,
        bgcolor="rgba(0,0,0,0.6)",
        bordercolor="gray",
        font=dict(color="white", size=12),
    )

    # ── Layout ───────────────────────────────────────────────────────────────
    fig.update_layout(
        title=f"مؤشر التداول المخصص – {symbol} ({timeframe})",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=700,
        legend=dict(orientation="h", y=-0.05),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)")

    return fig


def _infer_timedelta(df: pd.DataFrame) -> pd.Timedelta:
    if len(df) >= 2:
        return df.index[-1] - df.index[-2]
    return pd.Timedelta(hours=1)
