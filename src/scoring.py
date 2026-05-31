import numpy as np
import pandas as pd
from src.indicators import (
    compute_all_emas,
    compute_ema_alignment,
    compute_relative_strength,
    compute_distance_from_50dma,
    compute_failed_recent_high,
    compute_heavy_volume_down_days,
    compute_trend_consistency,
    compute_volume_signal,
)
from src.config import BENCHMARK_SPY, BENCHMARK_QQQ


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    if np.isnan(val):
        return 50.0
    return max(lo, min(hi, val))


def compute_momentum_score(
    ticker_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    qqq_df: pd.DataFrame,
    returns: dict,
) -> float:
    """
    Momentum Score 0-100.
    Higher = stronger momentum.
    """
    score = 50.0
    df = compute_all_emas(ticker_df)
    ema = compute_ema_alignment(df)

    # --- EMA position (max 18 pts) ---
    if ema["above_200ema"]:
        score += 6
    if ema["above_50ema"]:
        score += 6
    if ema["above_21ema"]:
        score += 6

    # --- EMA alignment (max 6 pts) ---
    if ema["ema21_above_50"]:
        score += 3
    if ema["ema50_above_200"]:
        score += 3

    # --- Return contributions (max 20 pts) ---
    r1m = returns.get("1M", np.nan)
    r3m = returns.get("3M", np.nan)
    r6m = returns.get("6M", np.nan)

    def ret_pts(r, strong, moderate):
        if np.isnan(r):
            return 0
        if r > strong:
            return 7
        elif r > moderate:
            return 4
        elif r > 0:
            return 2
        return -3

    score += ret_pts(r1m, 10, 5)
    score += ret_pts(r3m, 20, 10)
    score += ret_pts(r6m, 30, 15)

    # --- Relative strength vs benchmarks (max 16 pts) ---
    rs_spy = compute_relative_strength(ticker_df, spy_df, lookback=63)
    rs_qqq = compute_relative_strength(ticker_df, qqq_df, lookback=63)

    def rs_pts(rs, hi, lo):
        if np.isnan(rs):
            return 0
        if rs > hi:
            return 8
        elif rs > 0:
            return 4
        elif rs > lo:
            return -2
        return -6

    score += rs_pts(rs_spy, 10, -10)
    score += rs_pts(rs_qqq, 10, -10)

    # --- Trend consistency (max 8 pts) ---
    tc = compute_trend_consistency(ticker_df, lookback=63)
    if not np.isnan(tc):
        score += (tc - 0.5) * 16  # 0.5 baseline → 0pts; 0.65 → ~2.4; 0.4 → -1.6

    # --- Volume (max 5 pts) ---
    vol_sig = compute_volume_signal(ticker_df)
    vol_bonus = {
        "Expanding Up": 5,
        "Normal": 1,
        "Contracting": -1,
        "Expanding Down": -5,
        "Climactic": -3,
    }
    score += vol_bonus.get(vol_sig, 0)

    # --- Overextension penalty ---
    dist50 = compute_distance_from_50dma(df)
    if not np.isnan(dist50):
        if dist50 > 40:
            score -= 8
        elif dist50 > 25:
            score -= 4
        elif dist50 > 15:
            score -= 1

    # --- Failed high penalty ---
    if compute_failed_recent_high(ticker_df):
        score -= 5

    return round(_clamp(score), 1)


def compute_deterioration_score(
    ticker_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    qqq_df: pd.DataFrame,
    returns: dict,
) -> float:
    """
    Deterioration Score 0-100.
    Higher = more warning signs.
    """
    score = 0.0
    df = compute_all_emas(ticker_df)
    ema = compute_ema_alignment(df)

    # --- EMA violations (max 30 pts) ---
    if not ema["above_21ema"]:
        score += 10
    if not ema["above_50ema"]:
        score += 12
    if not ema["above_200ema"]:
        score += 15

    # --- EMA alignment breakdown ---
    if not ema["ema21_above_50"]:
        score += 8
    if not ema["ema50_above_200"]:
        score += 8

    # --- RS deterioration vs QQQ ---
    rs_qqq_3m = compute_relative_strength(ticker_df, qqq_df, lookback=63)
    rs_qqq_1m = compute_relative_strength(ticker_df, qqq_df, lookback=21)
    if not np.isnan(rs_qqq_3m):
        if rs_qqq_3m < -15:
            score += 12
        elif rs_qqq_3m < -5:
            score += 6
    if not np.isnan(rs_qqq_1m):
        if rs_qqq_1m < -10:
            score += 8
        elif rs_qqq_1m < -3:
            score += 3

    # --- Negative returns ---
    r1w = returns.get("1W", np.nan)
    r1m = returns.get("1M", np.nan)
    r3m = returns.get("3M", np.nan)
    if not np.isnan(r1w) and r1w < -3:
        score += 5
    if not np.isnan(r1m) and r1m < -5:
        score += 8
    elif not np.isnan(r1m) and r1m < 0:
        score += 3
    if not np.isnan(r3m) and r3m < -10:
        score += 8

    # --- Heavy-volume down days ---
    hvd = compute_heavy_volume_down_days(ticker_df, lookback=10)
    if hvd >= 4:
        score += 12
    elif hvd >= 2:
        score += 6
    elif hvd == 1:
        score += 2

    # --- Failed recent high ---
    if compute_failed_recent_high(ticker_df):
        score += 8

    # --- Overextension followed by weakness ---
    dist50 = compute_distance_from_50dma(df)
    if not np.isnan(dist50) and not np.isnan(r1w):
        if dist50 > 25 and r1w < -3:
            score += 8

    return round(_clamp(score), 1)


def classify_status(mom_score: float, det_score: float, ema: dict, returns: dict) -> str:
    r1m = returns.get("1M", 0) or 0
    above_50 = ema.get("above_50ema", False)
    above_200 = ema.get("above_200ema", False)

    if mom_score >= 68 and det_score <= 25 and above_50:
        return "Accelerating"
    elif mom_score >= 55 and det_score <= 40 and above_50:
        return "Maintaining"
    elif not above_50 and not above_200 and mom_score < 40:
        return "Broken Momentum"
    elif det_score >= 60 or (not above_50 and det_score >= 45):
        return "Distribution Risk"
    else:
        return "Weakening"


def compute_risk_level(det_score: float, mom_score: float, ema: dict) -> str:
    above_200 = ema.get("above_200ema", True)
    if det_score >= 65 or (not above_200 and mom_score < 35):
        return "Very High"
    elif det_score >= 45 or mom_score < 45:
        return "High"
    elif det_score >= 25 or mom_score < 60:
        return "Moderate"
    return "Low"


def compute_suggested_action(status: str, risk: str) -> str:
    if status == "Accelerating" and risk in ("Low", "Moderate"):
        return "Add on Pullback"
    elif status == "Maintaining" and risk in ("Low", "Moderate"):
        return "Hold"
    elif status == "Weakening":
        return "Watch / Trim"
    elif status == "Distribution Risk":
        return "Trim"
    elif status == "Broken Momentum":
        return "Avoid / Exit Candidate"
    return "Hold"


def compute_6m_rank_score(
    mom_score: float,
    det_score: float,
    returns: dict,
    rs_qqq: float,
    dist50: float,
) -> float:
    """
    Composite score for 6M swing-trade ranking.
    Uses raw return percentages as the primary driver so scores spread
    naturally across the watchlist (no artificial clamping that ties scores).
    Higher score = better rank.
    """
    r1m = returns.get("1M", 0) or 0
    r3m = returns.get("3M", 0) or 0
    r6m = returns.get("6M", 0) or 0

    # Primary: weighted raw returns — these vary widely and create separation
    s = (r1m * 0.40) + (r3m * 0.30) + (r6m * 0.15)

    # RS vs QQQ: relative strength adds another differentiating dimension
    if not np.isnan(rs_qqq):
        s += rs_qqq * 0.20

    # Quality modifier: momentum health shifts the score up/down
    s += (mom_score - 50) * 0.25
    s -= det_score * 0.15

    # Overextension penalty (high dist from 50DMA = mean-reversion risk)
    if not np.isnan(dist50):
        if dist50 > 50:
            s -= 20
        elif dist50 > 35:
            s -= 12
        elif dist50 > 20:
            s -= 5

    return round(s, 3)  # Keep full precision — no clamping, preserves spread


def compute_1y_rank_score(
    mom_score: float,
    det_score: float,
    returns: dict,
    rs_qqq: float,
    dist50: float,
    above_200ema: bool,
    trend_consistency: float,
) -> float:
    """
    Composite score for 1Y leadership ranking.
    Emphasises 6M/1Y trend and durability over short-term momentum.
    Higher score = better rank.
    """
    r3m = returns.get("3M", 0) or 0
    r6m = returns.get("6M", 0) or 0
    r1y = returns.get("1Y", 0) or 0

    # Primary: longer-horizon raw returns
    s = (r6m * 0.35) + (r1y * 0.25) + (r3m * 0.15)

    # RS vs QQQ
    if not np.isnan(rs_qqq):
        s += rs_qqq * 0.20

    # Durability adjusters
    s += (mom_score - 50) * 0.20
    s -= det_score * 0.18
    if above_200ema:
        s += 8
    if not np.isnan(trend_consistency):
        s += (trend_consistency - 0.5) * 30  # ~±15 pts for consistency spread

    # Moderate overextension penalty (less punishing than 6M rank)
    if not np.isnan(dist50) and dist50 > 40:
        s -= 8

    return round(s, 3)  # No clamping — raw spread for clean ranking


def score_ticker(
    ticker: str,
    ticker_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    qqq_df: pd.DataFrame,
    returns: dict,
) -> dict:
    df = compute_all_emas(ticker_df)
    ema = compute_ema_alignment(df)

    mom_score = compute_momentum_score(ticker_df, spy_df, qqq_df, returns)
    det_score = compute_deterioration_score(ticker_df, spy_df, qqq_df, returns)
    status = classify_status(mom_score, det_score, ema, returns)
    risk = compute_risk_level(det_score, mom_score, ema)
    action = compute_suggested_action(status, risk)
    vol_sig = compute_volume_signal(ticker_df)
    dist50 = compute_distance_from_50dma(df)
    rs_spy = compute_relative_strength(ticker_df, spy_df, lookback=63)
    rs_qqq = compute_relative_strength(ticker_df, qqq_df, lookback=63)
    trend_c = compute_trend_consistency(ticker_df, lookback=63)

    rank6m = compute_6m_rank_score(mom_score, det_score, returns, rs_qqq, dist50)
    rank1y = compute_1y_rank_score(
        mom_score, det_score, returns, rs_qqq, dist50,
        ema.get("above_200ema", False), trend_c
    )

    return {
        "momentum_score": mom_score,
        "deterioration_score": det_score,
        "status": status,
        "risk_level": risk,
        "suggested_action": action,
        "volume_signal": vol_sig,
        "rs_vs_spy": rs_spy,
        "rs_vs_qqq": rs_qqq,
        "dist_from_50dma": dist50,
        "price_vs_21ema": ema.get("price_vs_21ema_pct"),
        "price_vs_50ema": ema.get("price_vs_50ema_pct"),
        "price_vs_200ema": ema.get("price_vs_200ema_pct"),
        "above_21ema": ema.get("above_21ema"),
        "above_50ema": ema.get("above_50ema"),
        "above_200ema": ema.get("above_200ema"),
        "rank_6m_score": rank6m,
        "rank_1y_score": rank1y,
        "trend_consistency": trend_c,
    }
