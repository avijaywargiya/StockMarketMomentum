from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"

LOOKBACK_DAYS = 400  # ~18 months of trading days

MOMENTUM_STATUSES = [
    "Accelerating",
    "Maintaining",
    "Weakening",
    "Distribution Risk",
    "Broken Momentum",
]

THEMES = [
    "AI Infrastructure",
    "Semiconductors",
    "AI Software",
    "Cybersecurity",
    "Cloud/Software",
    "Quantum Computing",
    "Space",
    "Nuclear Energy",
    "Crypto Infrastructure",
    "Photonics",
    "Robotics/EV",
    "Fintech",
    "Ad Tech",
    "Biotech AI",
    "Robotics",
    "Other",
]

STATUS_COLORS = {
    "Accelerating": "#00C853",
    "Maintaining": "#2979FF",
    "Weakening": "#FF6D00",
    "Distribution Risk": "#DD2C00",
    "Broken Momentum": "#B71C1C",
}

RISK_LEVELS = ["Low", "Moderate", "High", "Very High"]

SUGGESTED_ACTIONS = [
    "Add on Pullback",
    "Hold",
    "Watch / Trim",
    "Trim",
    "Avoid / Exit Candidate",
]

VOLUME_SIGNALS = [
    "Expanding Up",
    "Normal",
    "Contracting",
    "Expanding Down",
    "Climactic",
]

# Benchmark tickers used for relative strength
BENCHMARK_SPY = "SPY"
BENCHMARK_QQQ = "QQQ"

# EMA periods
EMA_SHORT = 21
EMA_MID = 50
EMA_LONG = 200
