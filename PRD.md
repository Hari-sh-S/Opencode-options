# PRD — Options Trading System (Nifty 50)

## Status: Initial Build Complete (v0.1)

### Architecture
- **Frontend**: Streamlit Cloud (4 tabs: Auth, Backtest, Execution, Formula Ref)
- **Data Source**: DhanHQ API — Expired Options Data (backtesting), Option Chain (live)
- **VIX**: Yahoo Finance (`^INDIAVIX`)
- **Auth**: Dhan TOTP → access token (24h), cached locally
- **State**: Streamlit session state + Hugging Face datasets (strategy templates)

### Key Design Decisions
| Decision | Choice | Reason |
|----------|--------|--------|
| Backtest data | Expired Options API | Has real option OHLC + spot for index |
| Index data | `spot` field from expired options | No separate API needed |
| Greeks in backtest | ❌ Not available | Expired options API doesn't return Greeks |
| Greeks live | ✅ Option Chain API | Has delta/gamma/theta/vega |
| PCR/MaxPain | ✅ Only live | Needs all strikes' OI from option chain |
| 30m timeframe | ✅ Available | Expired options supports 1,5,15,30,60 min |
| Expiry dates | `dhan.expiry_list()` API | Dynamic, no hardcoding |
| Execution hosting | Streamlit (tab open) → later Oracle VPS | Streamlit can't run background processes |

### File Map
```
streamlit_app.py          ← Main app (4 tabs)
modules/
├── auth.py               ← Dhan TOTP auth + 24h token cache
├── data_manager.py       ← Expired options fetch, option chain, PCR, MaxPain, Greeks
├── formula_parser.py     ← DSL parser, validator, evaluator (20+ indicators)
├── formula_reference.py  ← Full parameter reference data
├── indicators.py         ← SMA, EMA, RSI, MACD, BB, Supertrend, ADX, patterns, etc.
├── instrument_selector.py ← ATM/ATM±N/premium, expiry list
├── position_sizing.py    ← Fixed/Volatility/Full Capital/Kelly
├── exit_conditions.py    ← Time/candle/TGT/SL/indicator exits
├── strategy_template.py  ← HF datasets save/load
├── vix.py                ← Yahoo Finance India VIX
├── backtest/
│   ├── engine.py         ← Bar-by-bar on expired options OHLC
│   └── metrics.py        ← Win rate, Sharpe, DD, profit factor, expectancy
└── execution/
    ├── engine.py         ← Live entry/exit checks, order orchestration
    └── order_manager.py  ← Dhan order wrapper
```

### Formula DSL
```
TIMEFRAME/ENTITY: INDICATOR(FIELD, PERIOD) OPERATOR VALUE [AND/OR ...]
```
- Timeframes: 1m, 5m, 15m, 30m, 60m
- Entities: Index (uses spot), Opt (uses option OHLC)
- Indicators: SMA, EMA, RSI, MACD, BB, Supertrend, ADX, ATR, ROC, WilliamsR, StochK
- Patterns: Doji, Engulfing, Hammer, ShootingStar
- Special: VIX, PCR, MaxPain, Delta, Gamma, Theta, Vega, IVPercentile, OIChange, BidAskSpread, HourFilter, DayFilter
- Fields: Open, High, Low, Close, Volume, OI, IV, Spot

### Pending / Known Gaps
1. Execution engine needs manual tab-open mode (no background process on Streamlit Cloud)
2. Greeks/PCR/MaxPain only available in live execution, not backtest
3. Index data from expired options has only `spot` (no index OHLC) — sufficient for most indicators
4. Multi-timeframe data bundle not fully wired (currently single TF per backtest)
5. No slippage/commission modeling in backtest yet
