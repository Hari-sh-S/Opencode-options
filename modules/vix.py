import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

VIX_SYMBOL = "^INDIAVIX"

@st.cache_data(ttl=300)
def get_vix_quote():
    try:
        ticker = yf.Ticker(VIX_SYMBOL)
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        latest = hist.iloc[-1]
        return {
            "current": latest["Close"],
            "high": latest["High"],
            "low": latest["Low"],
            "change": latest["Close"] - hist.iloc[-2]["Close"] if len(hist) > 1 else 0,
            "timestamp": latest.name,
        }
    except Exception:
        return None

def get_vix_history(period="1mo"):
    try:
        ticker = yf.Ticker(VIX_SYMBOL)
        hist = ticker.history(period=period)
        if hist.empty:
            return pd.DataFrame()
        return hist
    except Exception:
        return pd.DataFrame()

def get_vix_percentile(days=252):
    hist = get_vix_history(f"{days}d")
    if hist.empty:
        return None, None
    current = hist["Close"].iloc[-1]
    rank = (hist["Close"] < current).sum() / len(hist) * 100
    return current, rank
