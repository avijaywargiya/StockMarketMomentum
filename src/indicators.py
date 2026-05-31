import pandas as pd
import numpy as np
from src.config import EMA_SHORT, EMA_MID, EMA_LONG


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_all_emas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[f"EMA{EMA_SHORT}"] = compute_ema(df["Close"], EMA_SHORT)
    df[f"EMA{EMA_MID}"] = compute_ema(df["Close"], EMA_MID)
    df[f"EMA{EMA_LONG}"] = compute_ema(df["Close"], EMA_LONG)
    return df


def compute_volume_signal(df: pd.DataFrame, lookback: int = 20) -> str:
    if len(df) < lookback + 1:
        return "Normal"
    vol = df["Volume"].iloc[-lookback:]
    avg_vol = vol.iloc[:-1].mean()
    last_vol = float(df["Volume"].iloc[-1])
    last_close = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2])
    price_up = last_close >= prev_close
    ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

    if ratio > 2.5:
        return "Climactic"
    elif ratio > 1.4 and price_up:
        return "Expanding Up"
    elif ratio > 1.4 and not price_up:
        return "Expanding Down"
    elif ratio < 0.6:
        return "Contracting"
    return "Normal"


def compute_relative_strength(
    ticker_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    lookback: int = 63,
) -> float:
    """RS ratio: ticker performance / benchmark performance over lookback days."""
    if ticker_df is None or benchmark_df is None:
        return np.nan
    t_close = ticker_df["Close"].iloc[-lookback:] if len(ticker_df) >= lookback else ticker_df["Close"]
    b_close = benchmark_df["Close"].iloc[-lookback:] if len(benchmark_df) >= lookback else benchmark_df["Close"]
    if len(t_close) < 2 or len(b_close) < 2:
        return np.nan
    t_ret = (float(t_close.iloc[-1]) - float(t_close.iloc[0])) / float(t_close.iloc[0]) * 100
    b_ret = (float(b_close.iloc[-1]) - float(b_close.iloc[0])) / float(b_close.iloc[0]) * 100
    return round(t_ret - b_ret, 2)


def compute_rs_line(ticker_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> pd.Series:
    """Daily RS line for charting: ticker close / benchmark close."""
    aligned = ticker_df[["Close"]].join(
        benchmark_df[["Close"]], how="inner", lsuffix="_ticker", rsuffix="_bench"
    )
    if aligned.empty:
        return pd.Series(dtype=float)
    rs = aligned["Close_ticker"] / aligned["Close_bench"]
    rs.name = "RS_Line"
    return rs


def compute_distance_from_50dma(df: pd.DataFrame) -> float:
    if f"EMA{EMA_MID}" not in df.columns:
        df = compute_all_emas(df)
    last_close = float(df["Close"].iloc[-1])
    ema50 = float(df[f"EMA{EMA_MID}"].iloc[-1])
    if ema50 == 0:
        return np.nan
    return round((last_close - ema50) / ema50 * 100, 2)


def compute_failed_recent_high(df: pd.DataFrame, lookback: int = 20) -> bool:
    """True if close is more than 7% below the recent 20-day high."""
    if len(df) < lookback:
        return False
    recent_high = float(df["Close"].iloc[-lookback:].max())
    last_close = float(df["Close"].iloc[-1])
    return (recent_high - last_close) / recent_high > 0.07


def compute_heavy_volume_down_days(df: pd.DataFrame, lookback: int = 10) -> int:
    """Count of down days with volume > 1.3x average in last N days."""
    if len(df) < lookback + 20:
        return 0
    window = df.iloc[-lookback:].copy()
    avg_vol = float(df["Volume"].iloc[-30:-lookback].mean()) if len(df) > lookback + 30 else float(df["Volume"].mean())
    if avg_vol == 0:
        return 0
    down_days = window[window["Close"] < window["Close"].shift(1)]
    heavy = down_days[down_days["Volume"] > avg_vol * 1.3]
    return len(heavy)


def compute_trend_consistency(df: pd.DataFrame, lookback: int = 63) -> float:
    """Fraction of days close > previous close over lookback period. Range 0-1."""
    if len(df) < lookback + 1:
        return np.nan
    window = df["Close"].iloc[-lookback:]
    up_days = (window.diff() > 0).sum()
    return round(up_days / lookback, 4)


def compute_ema_alignment(df: pd.DataFrame) -> dict:
    if f"EMA{EMA_LONG}" not in df.columns:
        df = compute_all_emas(df)
    last = df.iloc[-1]
    close = float(last["Close"])
    e21 = float(last[f"EMA{EMA_SHORT}"])
    e50 = float(last[f"EMA{EMA_MID}"])
    e200 = float(last[f"EMA{EMA_LONG}"])
    return {
        "above_21ema": close > e21,
        "above_50ema": close > e50,
        "above_200ema": close > e200,
        "ema21_above_50": e21 > e50,
        "ema50_above_200": e50 > e200,
        "price_vs_21ema_pct": round((close - e21) / e21 * 100, 2) if e21 else np.nan,
        "price_vs_50ema_pct": round((close - e50) / e50 * 100, 2) if e50 else np.nan,
        "price_vs_200ema_pct": round((close - e200) / e200 * 100, 2) if e200 else np.nan,
    }
