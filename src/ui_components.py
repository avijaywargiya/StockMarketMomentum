import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from src.config import STATUS_COLORS, EMA_SHORT, EMA_MID, EMA_LONG
from src.indicators import compute_all_emas, compute_rs_line


STATUS_BADGE_CSS = """
<style>
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.78em;
    font-weight: 600;
    color: white;
}
.metric-card {
    background: #1a1a2e;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 4px 0;
}
</style>
"""


def status_badge_html(status: str) -> str:
    color = STATUS_COLORS.get(status, "#888")
    return f'<span class="badge" style="background:{color}">{status}</span>'


def color_status(val: str) -> str:
    color = STATUS_COLORS.get(val, "#888888")
    return f"color: {color}; font-weight: bold"


def style_dataframe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def _color_status(val):
        return color_status(val) if val in STATUS_COLORS else ""

    def _color_rs(val):
        try:
            v = float(val)
            if v > 10:
                return "color: #00C853"
            elif v > 0:
                return "color: #80E27E"
            elif v > -10:
                return "color: #FF6D00"
            else:
                return "color: #DD2C00"
        except Exception:
            return ""

    def _color_ret(val):
        try:
            v = float(str(val).replace("%", ""))
            if v > 5:
                return "color: #00C853"
            elif v > 0:
                return "color: #80E27E"
            elif v > -5:
                return "color: #FF6D00"
            else:
                return "color: #DD2C00"
        except Exception:
            return ""

    def _color_risk(val):
        m = {"Low": "#00C853", "Moderate": "#FFD600", "High": "#FF6D00", "Very High": "#DD2C00"}
        return f"color: {m.get(val, '#888')}"

    def _color_score(val):
        try:
            v = float(val)
            if v >= 70:
                return "color: #00C853"
            elif v >= 50:
                return "color: #80E27E"
            elif v >= 35:
                return "color: #FF6D00"
            else:
                return "color: #DD2C00"
        except Exception:
            return ""

    def _color_det(val):
        try:
            v = float(val)
            if v <= 20:
                return "color: #00C853"
            elif v <= 40:
                return "color: #80E27E"
            elif v <= 60:
                return "color: #FF6D00"
            else:
                return "color: #DD2C00"
        except Exception:
            return ""

    styler = df.style
    if "Momentum Status" in df.columns:
        styler = styler.map(_color_status, subset=["Momentum Status"])
    if "Risk Level" in df.columns:
        styler = styler.map(_color_risk, subset=["Risk Level"])
    for col in ["RS vs SPY", "RS vs QQQ"]:
        if col in df.columns:
            styler = styler.map(_color_rs, subset=[col])
    for col in ["1D %", "1W %", "1M %", "3M %", "6M %"]:
        if col in df.columns:
            styler = styler.map(_color_ret, subset=[col])
    if "Momentum Score" in df.columns:
        styler = styler.map(_color_score, subset=["Momentum Score"])
    if "Deterioration Score" in df.columns:
        styler = styler.map(_color_det, subset=["Deterioration Score"])
    return styler


def build_price_chart(df: pd.DataFrame, ticker: str, qqq_df: pd.DataFrame = None) -> go.Figure:
    df = compute_all_emas(df)
    rs_line = compute_rs_line(df, qqq_df) if qqq_df is not None else None

    rows = 3 if rs_line is not None else 2
    row_heights = [0.55, 0.25, 0.20] if rows == 3 else [0.65, 0.35]
    subplot_titles = [f"{ticker} Price + EMAs", "Volume", "RS vs QQQ"] if rows == 3 else [f"{ticker} Price + EMAs", "Volume"]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # Price
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="Price",
        increasing_line_color="#00C853",
        decreasing_line_color="#DD2C00",
    ), row=1, col=1)

    ema_colors = {f"EMA{EMA_SHORT}": "#FDD835", f"EMA{EMA_MID}": "#29B6F6", f"EMA{EMA_LONG}": "#EF5350"}
    for col, color in ema_colors.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                mode="lines", name=col,
                line=dict(color=color, width=1.3),
            ), row=1, col=1)

    # Volume
    colors = ["#00C853" if c >= o else "#DD2C00"
              for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        name="Volume", marker_color=colors, showlegend=False,
    ), row=2, col=1)

    # RS line
    if rs_line is not None and not rs_line.empty and rows == 3:
        fig.add_trace(go.Scatter(
            x=rs_line.index, y=rs_line.values,
            mode="lines", name="RS vs QQQ",
            line=dict(color="#CE93D8", width=1.5),
            showlegend=False,
        ), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=620,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02),
    )
    return fig


def render_alert_card(title: str, items: list, color: str = "#DD2C00"):
    if not items:
        return
    items_html = "".join(f"<li>{i}</li>" for i in items)
    st.markdown(
        f"""
        <div style="background:{color}22; border-left:4px solid {color}; border-radius:6px; padding:10px 14px; margin:6px 0">
        <b style="color:{color}">{title}</b>
        <ul style="margin:6px 0 0 0; padding-left:18px; font-size:0.9em">{items_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value, color: str = "#2979FF"):
    st.markdown(
        f"""
        <div style="background:#1E1E2E; border-radius:8px; padding:12px 16px; text-align:center; border: 1px solid {color}44">
        <div style="font-size:0.75em; color:#aaa; text-transform:uppercase; letter-spacing:0.05em">{label}</div>
        <div style="font-size:1.6em; font-weight:700; color:{color}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mini_table(df: pd.DataFrame, cols: list, title: str, color: str = "#2979FF"):
    if df.empty:
        st.caption(f"No data for {title}")
        return
    st.markdown(f"**{title}**")
    show = df[cols].copy() if all(c in df.columns for c in cols) else df.copy()
    st.dataframe(style_dataframe(show), use_container_width=True, hide_index=True)
