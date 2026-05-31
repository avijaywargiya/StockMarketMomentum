# Momentum Command Center

A local Streamlit dashboard for tracking a curated momentum stock watchlist. Ranks which stocks are accelerating, maintaining momentum, weakening, or at risk of breakdown.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

**Windows (double-click):**
```
run.bat
```

**Or from terminal:**
```bash
python -m streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Editing the Watchlist

### From inside the app (recommended)
- Use the **sidebar** → **Edit Watchlist** section
- **Add / Update Ticker**: Enter ticker, company, theme → click Add / Update
- **Remove Tickers**: Select one or more tickers → click Remove Selected
- Changes auto-save to `data/watchlist.csv` and clear cached data

### Manually editing the CSV
Edit `data/watchlist.csv` directly. Format:
```
ticker,company,theme
NVDA,NVIDIA Corporation,AI Infrastructure
AAPL,Apple Inc,Technology
```
Then click **Refresh Market Data** in the sidebar.

---

## How Scoring Works

### Momentum Score (0–100, higher = stronger)
Factors contributing positively:
- Price above 21/50/200 EMA (aligned EMAs)
- Strong 1M, 3M, 6M returns relative to peers
- Positive relative strength vs SPY and QQQ
- Expanding volume on up days
- High trend consistency (fraction of up-days)

Factors causing penalties:
- Extreme overextension above 50 EMA (>25–40% above)
- Failed recent high (>7% below 20-day high)
- Climactic or expanding-down volume

### Deterioration Score (0–100, higher = more warning signs)
Factors that raise deterioration score:
- Price below 21 EMA, 50 EMA, 200 EMA
- 21 EMA below 50 EMA (trend breakdown)
- 50 EMA below 200 EMA (major breakdown)
- Negative RS vs QQQ over 1M and 3M
- Negative 1W or 1M returns
- 2+ heavy-volume down days in recent 10 days
- Failed recent high
- Overextension followed by weakness

### Classification Logic
| Status | Criteria |
|---|---|
| Accelerating | Mom ≥68, Det ≤25, above 50 EMA |
| Maintaining | Mom ≥55, Det ≤40, above 50 EMA |
| Weakening | Between Maintaining and Distribution Risk |
| Distribution Risk | Det ≥60, or below 50 EMA with Det ≥45 |
| Broken Momentum | Below 50 & 200 EMA, Mom <40 |

### Ranking
**6M Rank** (swing-trade focused): weighted toward 1M/3M/6M returns, RS vs QQQ, volume signal, EMA alignment, penalizes overextension.

**1Y Rank** (durable leadership): weighted toward 6M/1Y trend, above 200 EMA, trend consistency, lower deterioration.

### Suggested Action
| Status | Action |
|---|---|
| Accelerating + Low/Moderate Risk | Add on Pullback |
| Maintaining + Low/Moderate Risk | Hold |
| Weakening | Watch / Trim |
| Distribution Risk | Trim |
| Broken Momentum | Avoid / Exit Candidate |

---

## Data Source & Limitations

- **Data**: [yfinance](https://github.com/ranaroussi/yfinance) pulling adjusted close from Yahoo Finance
- **Not real-time**: Data is end-of-day (EOD). Intraday prices are not available in the free tier
- **Cache**: Data is cached for 1 hour to avoid repeated API calls. Click "Refresh Market Data" to force reload
- **Missing tickers**: If a ticker can't be fetched (delisted, bad symbol, API error), it's skipped with a warning
- **Survivorship bias**: Watchlist is manually curated — no automatic universe expansion
- **Extended-hours prices**: yfinance does not provide pre/post-market prices in default mode

---

## File Structure

```
StockMarketMomentum/
├── app.py                  # Main Streamlit application
├── requirements.txt
├── run.bat                 # Windows one-click launcher
├── README.md
├── data/
│   └── watchlist.csv       # Editable watchlist (ticker, company, theme)
└── src/
    ├── config.py           # Constants, paths, EMA periods
    ├── data_fetcher.py     # yfinance download + caching
    ├── indicators.py       # EMA, RS, volume, trend calculations
    ├── scoring.py          # Momentum/deterioration scores, ranking, classification
    └── ui_components.py    # Chart builder, styled tables, alert cards
```

---

## Windows Desktop Shortcut

1. Right-click `run.bat` → Send to → Desktop (create shortcut)
2. Or create a `.vbs` wrapper for a silent launch (no terminal window)

---

## Future Upgrade Ideas

### AI Commentary
- Connect to Claude/OpenAI/Gemini API to generate natural-language summaries for each ticker
- Add to each row: "Why is this stock weakening? What are the key risks?"

### News & Sentiment
- Integrate Benzinga, Finviz, or Alpha Vantage news feeds
- Sentiment scoring from headlines

### Sector ETF Benchmarks
- Compare each theme against its sector ETF (e.g., SMH for semiconductors, ARKK for disruptive tech)
- Add relative strength vs sector, not just vs QQQ

### Persistent History
- Store daily snapshots of scores and ranks to a local SQLite database
- Plot score trend over time in the ticker deep-dive chart
- Track rank changes day-over-day

### Alert System
- Email or desktop notification when a stock crosses from Maintaining → Distribution Risk
- Volume spike alerts (climactic selling)

### Scheduled Daily Run
- Set up Windows Task Scheduler or a simple cron (WSL) to run a data fetch script each evening
- Push results to a summary email or Slack webhook

### Real-Time / Intraday (Paid APIs)
- Upgrade to Polygon.io, Alpaca, or Interactive Brokers API for live quotes
- Show intraday chart for same-day momentum confirmation

---

## Troubleshooting

**App crashes on startup:**
- Make sure all packages are installed: `pip install -r requirements.txt`
- Check Python version ≥ 3.9

**"No data loaded" error:**
- Check internet connection
- yfinance rate-limits occasionally; wait a minute and refresh

**Stale data after editing watchlist:**
- Click "Refresh Market Data" in the sidebar — this clears the cache and re-downloads

**Port already in use:**
- Run with a different port: `python -m streamlit run app.py --server.port 8502`
