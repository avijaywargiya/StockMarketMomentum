"""
Momentum Command Center
A local Streamlit dashboard for tracking stock momentum leadership.
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import io

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from src.config import (
    WATCHLIST_PATH, MOMENTUM_STATUSES, THEMES, STATUS_COLORS,
    RISK_LEVELS, SUGGESTED_ACTIONS, VOLUME_SIGNALS,
    BENCHMARK_SPY, BENCHMARK_QQQ, EMA_SHORT, EMA_MID, EMA_LONG,
)
from src.data_fetcher import load_all_data, get_last_price, get_returns, get_data_timestamp
from src.scoring import score_ticker
from src.indicators import compute_all_emas
from src.ui_components import (
    STATUS_BADGE_CSS, style_dataframe, build_price_chart,
    render_alert_card, render_metric_card, render_mini_table, status_badge_html,
)

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Momentum Command Center",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(STATUS_BADGE_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
.stTabs [data-baseweb="tab"] { font-size: 1em; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_watchlist() -> pd.DataFrame:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if WATCHLIST_PATH.exists():
        df = pd.read_csv(WATCHLIST_PATH)
        for col in ["ticker", "company", "theme"]:
            if col not in df.columns:
                df[col] = ""
        df["ticker"] = df["ticker"].str.upper().str.strip()
        return df.dropna(subset=["ticker"])
    # Bootstrap minimal watchlist
    default = pd.DataFrame([
        {"ticker": "NVDA", "company": "NVIDIA Corporation", "theme": "AI Infrastructure"},
        {"ticker": "SPY", "company": "SPDR S&P 500 ETF", "theme": "Benchmark"},
    ])
    default.to_csv(WATCHLIST_PATH, index=False)
    return default


def save_watchlist(df: pd.DataFrame):
    df.to_csv(WATCHLIST_PATH, index=False)


def fmt_pct(val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:+.1f}%"


def fmt_num(val, decimals=1) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:.{decimals}f}"


# ─── Session state ─────────────────────────────────────────────────────────────
if "cache_key" not in st.session_state:
    st.session_state["cache_key"] = "init"
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = None


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 Momentum Command Center")
    st.caption("Data: yfinance adjusted close (EOD). Not real-time.")

    # Detect Streamlit Community Cloud (no persistent filesystem)
    _is_cloud = not Path("data/watchlist.csv").is_absolute() and \
                "streamlit" in str(Path.home()).lower() or \
                Path("/mount/src").exists()
    if _is_cloud:
        st.info(
            "**Cloud mode:** Watchlist edits are session-only and reset on restart. "
            "To persist changes, edit `data/watchlist.csv` in the GitHub repo.",
            icon="☁️",
        )

    # Refresh
    if st.button("🔄 Refresh Market Data", use_container_width=True):
        import time
        st.session_state["cache_key"] = str(time.time())
        st.cache_data.clear()
        st.rerun()

    if st.session_state.get("last_refresh"):
        st.caption(f"Data as of: {st.session_state['last_refresh']}")

    st.divider()

    # Sidebar filters (used by Tab 1 overview)
    st.subheader("Quick Filters")
    watchlist_df_sidebar = load_watchlist()
    all_themes = sorted(watchlist_df_sidebar["theme"].dropna().unique().tolist())
    sb_themes = st.multiselect("Theme", all_themes, key="sb_themes")
    sb_status = st.multiselect("Momentum Status", MOMENTUM_STATUSES, key="sb_status")
    sb_risk = st.multiselect("Risk Level", RISK_LEVELS, key="sb_risk")

    st.divider()

    # ── Edit Watchlist ────────────────────────────────────────────────────────
    st.subheader("Edit Watchlist")
    with st.expander("➕ Add / Update Ticker"):
        new_ticker = st.text_input("Ticker Symbol", key="new_ticker").upper().strip()
        new_company = st.text_input("Company Name", key="new_company")
        theme_opts = sorted(set(THEMES + all_themes))
        new_theme = st.selectbox("Theme", theme_opts, key="new_theme")
        if st.button("Add / Update", use_container_width=True):
            if new_ticker:
                wl = load_watchlist()
                mask = wl["ticker"] == new_ticker
                if mask.any():
                    wl.loc[mask, "company"] = new_company
                    wl.loc[mask, "theme"] = new_theme
                    st.success(f"Updated {new_ticker}")
                else:
                    wl = pd.concat([
                        wl,
                        pd.DataFrame([{"ticker": new_ticker, "company": new_company, "theme": new_theme}])
                    ], ignore_index=True)
                    st.success(f"Added {new_ticker}")
                save_watchlist(wl)
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Enter a ticker symbol.")

    with st.expander("🗑 Remove Tickers"):
        wl_remove = load_watchlist()
        remove_choices = st.multiselect(
            "Select tickers to remove",
            wl_remove["ticker"].tolist(),
            key="remove_tickers",
        )
        if st.button("Remove Selected", use_container_width=True):
            if remove_choices:
                wl_remove = wl_remove[~wl_remove["ticker"].isin(remove_choices)]
                save_watchlist(wl_remove)
                st.success(f"Removed: {', '.join(remove_choices)}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Select at least one ticker.")

    st.divider()
    watchlist_df = load_watchlist()
    st.caption(f"Watchlist: {len(watchlist_df)} stocks")


# ─── Load data ────────────────────────────────────────────────────────────────
watchlist_df = load_watchlist()
tickers_tuple = tuple(watchlist_df["ticker"].tolist())

with st.spinner("Loading market data (cached for 1 hour)..."):
    raw_data = load_all_data(tickers_tuple, _cache_key=st.session_state["cache_key"])

st.session_state["last_refresh"] = raw_data.get("_fetched_at", get_data_timestamp())

spy_df = raw_data.get(BENCHMARK_SPY)
qqq_df = raw_data.get(BENCHMARK_QQQ)


# ─── Build master results table ───────────────────────────────────────────────
# Not cached here — raw_data is already cached by load_all_data; this is fast CPU work.
def build_results(tickers_tuple, _cache_key=""):
    results = []
    watchlist = load_watchlist()
    ticker_info = {r["ticker"]: r for _, r in watchlist.iterrows()}

    for ticker in tickers_tuple:
        if ticker in (BENCHMARK_SPY, BENCHMARK_QQQ):
            continue
        df = raw_data.get(ticker)
        if df is None or df.empty:
            continue
        info = ticker_info.get(ticker, {})
        returns = get_returns(df)
        try:
            scores = score_ticker(ticker, df, spy_df, qqq_df, returns)
        except Exception as e:
            continue

        last_close = get_last_price(df)
        row = {
            "Ticker": ticker,
            "Company": info.get("company", ""),
            "Theme": info.get("theme", ""),
            "Last Close": round(last_close, 2),
            "1D %": fmt_pct(returns.get("1D")),
            "1W %": fmt_pct(returns.get("1W")),
            "1M %": fmt_pct(returns.get("1M")),
            "3M %": fmt_pct(returns.get("3M")),
            "6M %": fmt_pct(returns.get("6M")),
            "Momentum Status": scores["status"],
            "Momentum Score": scores["momentum_score"],
            "Deterioration Score": scores["deterioration_score"],
            "6M Rank Score": scores["rank_6m_score"],
            "1Y Rank Score": scores["rank_1y_score"],
            "RS vs SPY": fmt_num(scores.get("rs_vs_spy")),
            "RS vs QQQ": fmt_num(scores.get("rs_vs_qqq")),
            "Dist from 50DMA": fmt_num(scores.get("dist_from_50dma")),
            "Price vs 21EMA %": fmt_num(scores.get("price_vs_21ema")),
            "Price vs 50EMA %": fmt_num(scores.get("price_vs_50ema")),
            "Price vs 200EMA %": fmt_num(scores.get("price_vs_200ema")),
            "Above 21EMA": "✅" if scores.get("above_21ema") else "❌",
            "Above 50EMA": "✅" if scores.get("above_50ema") else "❌",
            "Above 200EMA": "✅" if scores.get("above_200ema") else "❌",
            "Volume Signal": scores["volume_signal"],
            "Risk Level": scores["risk_level"],
            "Suggested Action": scores["suggested_action"],
            "Notes": "",
            # raw numeric for sorting
            "_ret_1d": returns.get("1D") or np.nan,
            "_ret_1w": returns.get("1W") or np.nan,
            "_ret_1m": returns.get("1M") or np.nan,
            "_ret_3m": returns.get("3M") or np.nan,
            "_ret_6m": returns.get("6M") or np.nan,
            "_rs_qqq_raw": scores.get("rs_vs_qqq") or np.nan,
        }
        results.append(row)
    return pd.DataFrame(results)


results_df = build_results(tickers_tuple, _cache_key=st.session_state["cache_key"])

if results_df.empty:
    st.error("No data loaded. Check your internet connection and try refreshing.")
    st.stop()

# Rank columns: sanitize missing/infinite scores before casting ranks to int.
# A ticker with incomplete market data should stay visible, but rank below valid rows.
for score_col, rank_col in [("6M Rank Score", "6M Rank"), ("1Y Rank Score", "1Y Rank")]:
    clean_scores = pd.to_numeric(results_df[score_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid_scores = clean_scores.dropna()
    fill_value = valid_scores.min() - 1 if not valid_scores.empty else 0
    results_df[score_col] = clean_scores.fillna(fill_value)
    results_df[rank_col] = results_df[score_col].rank(ascending=False, method="min").astype(int)


# ─── Apply sidebar filters ────────────────────────────────────────────────────
def apply_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    if sb_themes:
        df = df[df["Theme"].isin(sb_themes)]
    if sb_status:
        df = df[df["Momentum Status"].isin(sb_status)]
    if sb_risk:
        df = df[df["Risk Level"].isin(sb_risk)]
    return df


filtered_df = apply_sidebar_filters(results_df.copy())


# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 Momentum Command Center", "📋 Full Watchlist"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: Momentum Command Center
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Momentum Command Center")
    _spy_last = spy_df.index[-1].strftime("%Y-%m-%d") if spy_df is not None and not spy_df.empty else "unknown"
    st.caption(f"Data fetched: {st.session_state['last_refresh']} · Prices through: {_spy_last} (cached 1 hr)")
    if sb_themes or sb_status or sb_risk:
        active = []
        if sb_themes:
            active.append(f"Theme: {', '.join(sb_themes)}")
        if sb_status:
            active.append(f"Status: {', '.join(sb_status)}")
        if sb_risk:
            active.append(f"Risk: {', '.join(sb_risk)}")
        st.caption("Active filters: " + " | ".join(active))

    view = filtered_df if not filtered_df.empty else results_df

    # ── Summary metrics ──────────────────────────────────────────────────────
    total = len(view)
    n_accel = (view["Momentum Status"] == "Accelerating").sum()
    n_broken = (view["Momentum Status"] == "Broken Momentum").sum()
    n_dist = (view["Momentum Status"] == "Distribution Risk").sum()
    n_maint = (view["Momentum Status"] == "Maintaining").sum()
    n_weak = (view["Momentum Status"] == "Weakening").sum()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_metric_card("Total Stocks", total, "#2979FF")
    with c2:
        render_metric_card("Accelerating", n_accel, "#00C853")
    with c3:
        render_metric_card("Maintaining", n_maint, "#2979FF")
    with c4:
        render_metric_card("Weakening", n_weak, "#FF6D00")
    with c5:
        render_metric_card("Dist Risk", n_dist, "#DD2C00")
    with c6:
        render_metric_card("Broken", n_broken, "#B71C1C")

    st.divider()

    # ── Top 10 Accelerating / Weakening ──────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("🟢 Top 10 Accelerating")
        accel = view[view["Momentum Status"] == "Accelerating"].nsmallest(10, "6M Rank")
        mini_cols = ["Ticker", "Company", "Momentum Score", "6M Rank", "1M %", "Volume Signal"]
        render_mini_table(accel, mini_cols, "", "#00C853")

    with col_b:
        st.subheader("🔴 Top 10 Weakening / At Risk")
        weak = view[view["Momentum Status"].isin(["Weakening", "Distribution Risk", "Broken Momentum"])]
        weak_sorted = weak.nsmallest(10, "Deterioration Score") if weak.empty else weak.nlargest(10, "Deterioration Score")
        mini_cols_w = ["Ticker", "Company", "Momentum Status", "Deterioration Score", "1M %", "Risk Level"]
        render_mini_table(weak_sorted, mini_cols_w, "", "#DD2C00")

    st.divider()

    # ── Rank Movers ───────────────────────────────────────────────────────────
    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("⬆️ Biggest Positive Rank Movers (6M)")
        top_movers = view.nsmallest(10, "6M Rank")[["Ticker", "Company", "6M Rank", "Momentum Score", "Momentum Status"]]
        render_mini_table(top_movers, top_movers.columns.tolist(), "", "#00C853")

    with col_d:
        st.subheader("⬇️ Biggest Negative Rank Movers (6M)")
        bot_movers = view.nlargest(10, "6M Rank")[["Ticker", "Company", "6M Rank", "Deterioration Score", "Momentum Status"]]
        render_mini_table(bot_movers, bot_movers.columns.tolist(), "", "#DD2C00")

    st.divider()

    # ── Sector/Theme Leadership ───────────────────────────────────────────────
    st.subheader("🏆 Sector / Theme Leadership")
    if "Theme" in view.columns:
        theme_summary = (
            view.groupby("Theme")
            .agg(
                Count=("Ticker", "count"),
                Avg_Mom_Score=("Momentum Score", "mean"),
                Avg_Det_Score=("Deterioration Score", "mean"),
                Accelerating=("Momentum Status", lambda x: (x == "Accelerating").sum()),
                Broken=("Momentum Status", lambda x: (x == "Broken Momentum").sum()),
            )
            .round(1)
            .reset_index()
            .sort_values("Avg_Mom_Score", ascending=False)
        )
        theme_summary.columns = ["Theme", "Count", "Avg Mom Score", "Avg Det Score", "Accelerating", "Broken"]
        st.dataframe(theme_summary, use_container_width=True, hide_index=True)

    st.divider()

    # ── Alerts ────────────────────────────────────────────────────────────────
    st.subheader("⚠️ Key Warning Alerts")

    broken = view[view["Momentum Status"] == "Broken Momentum"]["Ticker"].tolist()
    dist_risk = view[view["Momentum Status"] == "Distribution Risk"]["Ticker"].tolist()
    high_det = view[view["Deterioration Score"] >= 65]["Ticker"].tolist()
    below_200 = view[view["Above 200EMA"] == "❌"]["Ticker"].tolist()

    render_alert_card("Broken Momentum", broken[:10], "#B71C1C")
    render_alert_card("Distribution Risk", dist_risk[:10], "#DD2C00")
    render_alert_card("High Deterioration Score (≥65)", high_det[:10], "#FF6D00")
    render_alert_card("Below 200 EMA", below_200[:10], "#FF6D00")

    if not any([broken, dist_risk, high_det, below_200]):
        st.success("No major warnings in current filtered view.")

    st.divider()

    # ── Action Needed Today ───────────────────────────────────────────────────
    st.subheader("🎯 Action Needed Today")
    action_cols = ["Ticker", "Company", "Momentum Status", "Suggested Action", "Risk Level", "1D %", "Volume Signal"]

    exit_candidates = view[view["Suggested Action"] == "Avoid / Exit Candidate"]
    trim_now = view[view["Suggested Action"] == "Trim"]
    add_candidates = view[
        (view["Suggested Action"] == "Add on Pullback") &
        (view["_ret_1d"].notna()) &
        (view["_ret_1d"] < -1.5)
    ]

    if not exit_candidates.empty:
        st.markdown("**Exit / Avoid:**")
        st.dataframe(
            style_dataframe(exit_candidates[action_cols]),
            use_container_width=True, hide_index=True,
        )

    if not trim_now.empty:
        st.markdown("**Trim:**")
        st.dataframe(
            style_dataframe(trim_now[action_cols]),
            use_container_width=True, hide_index=True,
        )

    if not add_candidates.empty:
        st.markdown("**Add on Pullback (down today ≥ 1.5%):**")
        st.dataframe(
            style_dataframe(add_candidates[action_cols]),
            use_container_width=True, hide_index=True,
        )

    if exit_candidates.empty and trim_now.empty and add_candidates.empty:
        st.info("No immediate actions flagged for current filter.")

    st.divider()

    # ── Chart section ─────────────────────────────────────────────────────────
    st.subheader("📈 Ticker Deep Dive")
    valid_tickers = [t for t in tickers_tuple if t in raw_data and t not in (BENCHMARK_SPY, BENCHMARK_QQQ)]
    selected = st.selectbox("Select Ticker", valid_tickers, key="chart_ticker_tab1")

    if selected and selected in raw_data:
        t_df = raw_data[selected]
        info_row = results_df[results_df["Ticker"] == selected]
        if not info_row.empty:
            r = info_row.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Last Close", f"${r['Last Close']:.2f}")
            c2.metric("Momentum Score", r["Momentum Score"])
            c3.metric("Deterioration Score", r["Deterioration Score"])
            with c4:
                st.markdown(f"**Status:** {status_badge_html(r['Momentum Status'])}", unsafe_allow_html=True)
        fig = build_price_chart(t_df, selected, qqq_df)
        st.plotly_chart(fig, use_container_width=True, key="chart_tab1")
        st.caption("Chart shows adjusted close data via yfinance. EMAs: 21 (yellow), 50 (blue), 200 (red).")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: Full Watchlist
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Full Watchlist")

    # ── Tab-level filters ─────────────────────────────────────────────────────
    st.subheader("Filters")
    fc1, fc2, fc3 = st.columns(3)
    fc4, fc5, fc6, fc7 = st.columns(4)

    with fc1:
        search_q = st.text_input("Search Ticker / Company", key="wl_search")
    with fc2:
        f_themes = st.multiselect("Theme", sorted(results_df["Theme"].dropna().unique()), key="wl_themes")
    with fc3:
        f_status = st.multiselect("Momentum Status", MOMENTUM_STATUSES, key="wl_status")
    with fc4:
        f_risk = st.multiselect("Risk Level", RISK_LEVELS, key="wl_risk")
    with fc5:
        f_action = st.multiselect("Suggested Action", SUGGESTED_ACTIONS, key="wl_action")
    with fc6:
        f_vol = st.multiselect("Volume Signal", VOLUME_SIGNALS, key="wl_vol")
    with fc7:
        sort_by = st.selectbox(
            "Sort By",
            ["6M Rank", "1Y Rank", "Momentum Score", "Deterioration Score", "1M %", "3M %"],
            key="wl_sort",
        )

    # Apply tab filters
    wl_view = results_df.copy()

    if search_q:
        q = search_q.upper().strip()
        wl_view = wl_view[
            wl_view["Ticker"].str.upper().str.contains(q) |
            wl_view["Company"].str.upper().str.contains(q, na=False)
        ]
    if f_themes:
        wl_view = wl_view[wl_view["Theme"].isin(f_themes)]
    if f_status:
        wl_view = wl_view[wl_view["Momentum Status"].isin(f_status)]
    if f_risk:
        wl_view = wl_view[wl_view["Risk Level"].isin(f_risk)]
    if f_action:
        wl_view = wl_view[wl_view["Suggested Action"].isin(f_action)]
    if f_vol:
        wl_view = wl_view[wl_view["Volume Signal"].isin(f_vol)]

    # Sort
    sort_map = {
        "6M Rank": ("6M Rank", True),
        "1Y Rank": ("1Y Rank", True),
        "Momentum Score": ("Momentum Score", False),
        "Deterioration Score": ("Deterioration Score", False),
        "1M %": ("_ret_1m", False),
        "3M %": ("_ret_3m", False),
    }
    sort_col, sort_asc = sort_map.get(sort_by, ("6M Rank", True))
    if sort_col in wl_view.columns:
        wl_view = wl_view.sort_values(sort_col, ascending=sort_asc)

    # ── Counts ────────────────────────────────────────────────────────────────
    st.caption(
        f"**Showing {len(wl_view)} of {len(results_df)} stocks** in watchlist"
    )

    # ── Display columns (hide internal raw cols) ──────────────────────────────
    display_cols = [
        "Ticker", "Company", "Theme", "Last Close",
        "1D %", "1W %", "1M %", "3M %", "6M %",
        "Momentum Status", "6M Rank", "1Y Rank",
        "Momentum Score", "Deterioration Score",
        "RS vs SPY", "RS vs QQQ",
        "Price vs 21EMA %", "Price vs 50EMA %", "Price vs 200EMA %",
        "Above 21EMA", "Above 50EMA", "Above 200EMA",
        "Volume Signal", "Dist from 50DMA",
        "Risk Level", "Suggested Action", "Notes",
    ]
    display_cols = [c for c in display_cols if c in wl_view.columns]
    wl_display = wl_view[display_cols]

    st.dataframe(
        style_dataframe(wl_display),
        use_container_width=True,
        hide_index=True,
        height=520,
    )

    # ── CSV Export ────────────────────────────────────────────────────────────
    csv_buffer = io.BytesIO()
    wl_display.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    st.download_button(
        label="⬇️ Download Filtered Table as CSV",
        data=csv_buffer.getvalue(),
        file_name="momentum_watchlist_filtered.csv",
        mime="text/csv",
    )

    st.divider()

    # ── Ticker Chart in Tab 2 ─────────────────────────────────────────────────
    st.subheader("📈 Ticker Deep Dive")
    valid_tickers2 = [t for t in wl_view["Ticker"].tolist() if t in raw_data]
    if valid_tickers2:
        selected2 = st.selectbox("Select Ticker", valid_tickers2, key="chart_ticker_tab2")
        if selected2 and selected2 in raw_data:
            t_df2 = raw_data[selected2]
            info_row2 = results_df[results_df["Ticker"] == selected2]
            if not info_row2.empty:
                r2 = info_row2.iloc[0]
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Last Close", f"${r2['Last Close']:.2f}")
                m2.metric("Mom Score", r2["Momentum Score"])
                m3.metric("Det Score", r2["Deterioration Score"])
                m4.metric("6M Rank", r2["6M Rank"])
                m5.metric("1Y Rank", r2["1Y Rank"])
            fig2 = build_price_chart(t_df2, selected2, qqq_df)
            st.plotly_chart(fig2, use_container_width=True, key="chart_tab2")
            st.caption(
                "Chart: adjusted close via yfinance (EOD data, not real-time). "
                "EMAs: 21 yellow, 50 blue, 200 red. RS line vs QQQ shown below volume."
            )
    else:
        st.info("No tickers match current filters.")
