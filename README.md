# 📊 Options Trading System — Nifty 50

A backtesting and live execution engine for Nifty 50 options trading, powered by the **DhanHQ API** and deployed on **Streamlit Cloud**.

> **Non-tech friendly**: No coding required to use. All configuration is done through the web interface.

---

## 🚀 Quick Start (Streamlit Cloud)

### 1. Deploy to Streamlit Cloud

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

1. Go to **https://share.streamlit.io**
2. Sign in with your GitHub account
3. Click **"New app"** → select this repository (`Hari-sh-S/Opencode-options`)
4. Set:
   - **Repository**: `Hari-sh-S/Opencode-options`
   - **Branch**: `main`
   - **Main file**: `streamlit_app.py`
5. Click **"Deploy"**

### 2. Add Your Secrets

After deploy, go to **Settings → Secrets** and add:

```toml
DHAN_CLIENT_ID = "your_dhan_client_id"
DHAN_PIN = "your_dhan_pin"
HF_TOKEN = "your_huggingface_token"        # optional — for saving strategies
HF_DATASET_REPO = "your_dataset_repo"      # optional
```

> **Where to get these?**
> - **DHAN_CLIENT_ID & DHAN_PIN**: Login to [Dhan Console](https://console.dhan.co) → API → Generate API credentials
> - **HF_TOKEN**: Sign up at [huggingface.co](https://huggingface.co) → Settings → Access Tokens

### 3. Use the App

| Tab | What it does |
|-----|-------------|
| 🔐 **Dhan Auth** | Enter your 6-digit TOTP code to authenticate with Dhan API. Token lasts 24 hours. Also shows India VIX and available expiry dates. |
| 📈 **Backtest** | Test your trading strategy on historical expired options data. Enter a formula, configure options, and see results (win rate, P&L, equity curve). |
| ⚡ **Execution** | Run your strategy live during market hours. Check entry signals, view Greeks, monitor positions. |
| 📖 **Formula Ref** | Full reference for the formula language with examples. |

---

## 📝 Formula Language

Entry and exit conditions are written in a simple formula language:

```
TIMEFRAME/ENTITY: INDICATOR(FIELD, PERIOD) OPERATOR VALUE
```

**Examples:**

| Formula | Meaning |
|---------|---------|
| `60m/Index: SMA(Close,20) > SMA(Close,50)` | 20-period SMA crosses above 50-period SMA on the 60-min chart |
| `15m/Index: RSI(Close,14) < 30` | RSI is below 30 (oversold) on the 15-min chart |
| `60m/Index: SMA(Close,20) > 15000 AND 15m/Index: RSI(Close,14) < 30` | Both conditions must be true |

**Timeframes:** `1m`, `5m`, `15m`, `30m`, `60m`
**Entities:** `Index` (Nifty 50), `Opt` (option price)
**Indicators:** SMA, EMA, RSI, MACD, Bollinger Bands, Supertrend, ADX, ATR, ROC, Williams %R, Stochastic, Candlestick Patterns (Doji, Engulfing, Hammer, Shooting Star)

*See the **Formula Reference** tab in the app for the complete list.*

---

## 🔧 Local Development

If you want to run the app on your own computer:

```bash
# Clone the repo
git clone https://github.com/Hari-sh-S/Opencode-options.git
cd Opencode-options

# Install dependencies
pip install -r requirements.txt

# Create secrets file
# Edit .streamlit/secrets.toml with your Dhan credentials

# Run the app
streamlit run streamlit_app.py
```

---

## 🧠 How It Works

### Backtesting
- Uses **expired options data** from Dhan API — gives you actual option premiums (open, high, low, close) along with underlying spot price
- Bar-by-bar simulation: for each candle, checks if your entry formula is true, then tracks P&L until exit conditions are met
- Results include: win rate, profit factor, Sharpe ratio, max drawdown, equity curve

### Live Execution
- Connects to Dhan's live API during market hours
- Checks your entry formula on the latest candle data
- Shows real-time Greeks (Delta, Gamma, Theta, Vega), IV, OI
- Places orders through Dhan when conditions are met

### Data Sources
| Data | Source |
|------|--------|
| Nifty 50 prices | Dhan expired options API (`spot` field) |
| Option premiums | Dhan expired options API (backtest) |
| Live option chain | Dhan API |
| Live Greeks | Dhan option chain API |
| India VIX | Yahoo Finance (`^INDIAVIX`) |

---

## 📁 Project Structure

```
opencode-options/
├── streamlit_app.py          ← Main Streamlit app (entry point)
├── requirements.txt          ← Python dependencies
├── .streamlit/
│   └── secrets.toml          ← API credentials (NOT committed to Git)
├── modules/
│   ├── auth.py               ← Dhan TOTP authentication
│   ├── data_manager.py       ← All Dhan data fetching
│   ├── formula_parser.py     ← Formula DSL parser & evaluator
│   ├── formula_reference.py  ← Formula parameter reference
│   ├── indicators.py         ← 20+ technical indicators
│   ├── instrument_selector.py ← ATM/ITM/OTM selection
│   ├── position_sizing.py    ← Position sizing methods
│   ├── exit_conditions.py    ← Exit logic (TGT/SL/time/candle)
│   ├── strategy_template.py  ← Save/load strategies
│   ├── vix.py                ← India VIX fetcher
│   ├── backtest/
│   │   ├── engine.py         ← Backtest simulation engine
│   │   └── metrics.py        ← Performance metrics
│   └── execution/
│       ├── engine.py         ← Live execution engine
│       └── order_manager.py  ← Dhan order management
└── utils/
    └── __init__.py
```

---

## ⚖️ Disclaimer

**Trading in options involves substantial risk of loss.** This software is provided for educational and research purposes only. Past performance in backtests does not guarantee future results. Always trade with capital you can afford to lose.

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **Streamlit** — Web UI
- **DhanHQ API** — Brokerage & data
- **yfinance** — India VIX
- **Pandas / Plotly** — Data analysis & charts
- **Hugging Face Datasets** — Strategy storage
