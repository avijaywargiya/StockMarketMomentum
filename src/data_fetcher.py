import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

from src.config import LOOKBACK_DAYS, BENCHMARK_SPY, BENCHMARK_QQQ


def _date_range():
    end = datetime.today()
    start = end - timedelta(days=LOOKBACK_DAYS)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def fetch_ticker_data(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    try:
        df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None
        # yfinance 1.x returns MultiIndex columns even for single tickers — flatten first
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        df.dropna(subset=["Close"], inplace=True)
        return df
    except Exception as e:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_all_data(tickers: tuple, _cache_key: str = "") -> dict:
    """
    Download price data for all tickers plus benchmarks.
    Returns dict of {ticker: DataFrame}.
    """
    start, end = _date_range()
    all_tickers = list(tickers) + [BENCHMARK_SPY, BENCHMARK_QQQ]
    results = {}
    failed = []

    progress = st.progress(0, text="Fetching market data...")
    total = len(all_tickers)

    for i, ticker in enumerate(all_tickers):
        df = fetch_ticker_data(ticker, start, end)
        if df is not None and not df.empty:
            results[ticker] = df
        else:
            failed.append(ticker)
        progress.progress((i + 1) / total, text=f"Fetching {ticker}... ({i+1}/{total})")

    progress.empty()

    if failed:
        watchlist_failed = [t for t in failed if t not in (BENCHMARK_SPY, BENCHMARK_QQQ)]
        if watchlist_failed:
            st.warning(f"Could not fetch data for: {', '.join(watchlist_failed)}")

    return results


def get_last_price(df: pd.DataFrame) -> float:
    return float(df["Close"].iloc[-1])


def get_last_volume(df: pd.DataFrame) -> float:
    return float(df["Volume"].iloc[-1])


def get_returns(df: pd.DataFrame) -> dict:
    close = df["Close"]
    last = float(close.iloc[-1])

    def pct(days):
        if len(close) < days + 1:
            return np.nan
        past = float(close.iloc[-days - 1])
        return (last - past) / past * 100 if past != 0 else np.nan

    trading_days = {
        "1D": 1,
        "1W": 5,
        "1M": 21,
        "3M": 63,
        "6M": 126,
        "1Y": 252,
    }
    return {k: pct(v) for k, v in trading_days.items()}


def get_data_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
