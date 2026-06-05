import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dhanhq import dhanhq

NIFTY_SECURITY_ID = "13"

OPTIONS_INTERVAL_MAP = {"1m": 1, "5m": 5, "15m": 15, "30m": 25, "60m": 60}

def _valid_interval(interval):
    interval_map = {1: 1, 5: 5, 15: 15, 30: 25, 60: 60}
    return interval_map.get(interval, 15)

def fetch_expired_options_data(dhan, expiry_flag, expiry_code, strike, option_type,
                                from_date, to_date, interval=15):
    interval = _valid_interval(interval)
    try:
        resp = dhan.expired_options_data(
            security_id=NIFTY_SECURITY_ID,
            exchange_segment=dhanhq.NSE_FNO,
            instrument_type="OPTIDX",
            expiry_flag=expiry_flag,
            expiry_code=expiry_code,
            strike=strike,
            drv_option_type=option_type,
            required_data=["open", "high", "low", "close", "volume", "oi", "iv", "spot"],
            from_date=from_date[:10],
            to_date=to_date[:10],
            interval=interval,
        )
        st.caption(f"API resp keys: {list(resp.keys()) if resp else 'None'}, status: {resp.get('status')}")
        if resp.get("status") == "success" and resp.get("data"):
            data = resp["data"]
            st.caption(f"Data keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
            opt_key = "CE" if option_type.upper() == "CALL" else "PE"
            opt_data = data.get(opt_key) or data.get(opt_key.lower())
            if opt_data:
                st.caption(f"Opt data keys: {list(opt_data.keys())[:5] if isinstance(opt_data, dict) else type(opt_data).__name__}, has timestamp: {bool(opt_data.get('timestamp'))}")
            else:
                st.caption(f"opt_data is None for key '{opt_key}'")
            if opt_data and opt_data.get("timestamp"):
                return _parse_candle_response(opt_data)
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"Expired options data error: {e}")
        return pd.DataFrame()

def fetch_both_ce_pe(dhan, expiry_flag, expiry_code, strike, from_date, to_date, interval=15):
    calls = fetch_expired_options_data(dhan, expiry_flag, expiry_code, strike, "CALL", from_date, to_date, interval)
    puts = fetch_expired_options_data(dhan, expiry_flag, expiry_code, strike, "PUT", from_date, to_date, interval)
    return calls, puts

def _parse_candle_response(data):
    try:
        timestamps = data.get("timestamp", [])
        if not timestamps:
            return pd.DataFrame()
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("Asia/Kolkata"),
            "open": [float(x) if x else 0 for x in data.get("open", [])],
            "high": [float(x) if x else 0 for x in data.get("high", [])],
            "low": [float(x) if x else 0 for x in data.get("low", [])],
            "close": [float(x) if x else 0 for x in data.get("close", [])],
            "volume": [int(x) if x else 0 for x in data.get("volume", [])],
        })
        if data.get("oi"):
            df["oi"] = [int(x) if x else 0 for x in data["oi"]]
        if data.get("iv"):
            df["iv"] = [float(x) if x else 0 for x in data["iv"]]
        if data.get("spot"):
            df["spot"] = [float(x) if x else 0 for x in data["spot"]]
        if data.get("strike"):
            df["strike"] = [float(x) if x else 0 for x in data["strike"]]
        df = df.dropna(subset=["open", "high", "low", "close"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
    except Exception as e:
        st.warning(f"Parse error: {e}")
        return pd.DataFrame()

def build_backtest_data_bundle(opt_df):
    bundle = {}
    if opt_df.empty:
        return bundle
    opt_df = opt_df.reset_index(drop=True)
    index_df = pd.DataFrame({
        "timestamp": opt_df["timestamp"],
        "open": opt_df.get("spot", opt_df["close"]),
        "high": opt_df.get("spot", opt_df["close"]),
        "low": opt_df.get("spot", opt_df["close"]),
        "close": opt_df.get("spot", opt_df["close"]),
        "volume": 0,
    })
    bundle["opt"] = opt_df
    bundle["index"] = index_df
    return bundle

def fetch_expiry_list(dhan):
    try:
        resp = dhan.expiry_list(
            under_security_id=int(NIFTY_SECURITY_ID),
            under_exchange_segment=dhanhq.INDEX,
        )
        if resp.get("status") == "success":
            return resp.get("data", [])
        return []
    except Exception as e:
        st.warning(f"Expiry list error: {e}")
        return []

def get_option_chain_data(dhan, expiry):
    try:
        resp = dhan.option_chain(
            under_security_id=int(NIFTY_SECURITY_ID),
            under_exchange_segment=dhanhq.INDEX,
            expiry=expiry,
        )
        if resp.get("status") == "success":
            return resp["data"]
        return None
    except Exception as e:
        st.warning(f"Option chain error: {e}")
        return None

def extract_greeks_from_chain(chain_data, strike, option_type="CE"):
    try:
        oc = chain_data.get("oc", {})
        strike_str = str(int(strike)) if not isinstance(strike, str) else strike
        contract = oc.get(strike_str, {}).get(option_type.lower(), {})
        return {
            "delta": contract.get("delta"),
            "gamma": contract.get("gamma"),
            "theta": contract.get("theta"),
            "vega": contract.get("vega"),
            "iv": contract.get("iv"),
            "oi": contract.get("oi"),
            "ltp": contract.get("lastPrice"),
            "bid": contract.get("bid"),
            "ask": contract.get("ask"),
            "security_id": contract.get("securityId"),
        }
    except Exception:
        return {
            "delta": None, "gamma": None, "theta": None, "vega": None,
            "iv": None, "oi": None, "ltp": None, "bid": None, "ask": None,
            "security_id": None,
        }

def calculate_pcr(chain_data):
    try:
        oc = chain_data.get("oc", {})
        total_ce_oi = 0
        total_pe_oi = 0
        for strike_str, contracts in oc.items():
            ce_oi = contracts.get("ce", {}).get("oi", 0) or 0
            pe_oi = contracts.get("pe", {}).get("oi", 0) or 0
            total_ce_oi += int(ce_oi)
            total_pe_oi += int(pe_oi)
        if total_ce_oi > 0:
            return total_pe_oi / total_ce_oi
        return None
    except Exception:
        return None

def calculate_max_pain(chain_data):
    try:
        oc = chain_data.get("oc", {})
        strikes_data = []
        for strike_str, contracts in oc.items():
            strike = float(strike_str)
            ce_oi = int(contracts.get("ce", {}).get("oi", 0) or 0)
            pe_oi = int(contracts.get("pe", {}).get("oi", 0) or 0)
            strikes_data.append((strike, ce_oi, pe_oi))
        pain_values = {}
        for strike, _, _ in strikes_data:
            total_pain = 0
            for s, ce_oi, pe_oi in strikes_data:
                total_pain += max(0, strike - s) * ce_oi
                total_pain += max(0, s - strike) * pe_oi
            pain_values[strike] = total_pain
        if pain_values:
            return min(pain_values, key=pain_values.get)
        return None
    except Exception:
        return None

def get_live_quote(dhan, security_id, segment=None):
    if segment is None:
        segment = dhanhq.NSE_FNO
    try:
        resp = dhan.quote_data({segment: [security_id]})
        if resp.get("status") == "success":
            return resp["data"].get(segment, {}).get(str(security_id), {})
        return {}
    except Exception:
        return {}

def get_live_index_value(dhan):
    try:
        resp = dhan.quote_data({dhanhq.INDEX: [int(NIFTY_SECURITY_ID)]})
        if resp.get("status") == "success":
            return resp["data"].get(dhanhq.INDEX, {}).get(NIFTY_SECURITY_ID, {}).get("last_price")
        return None
    except Exception:
        return None

def resample_to_timeframe(df, target_tf):
    if df.empty:
        return df
    df = df.set_index("timestamp")
    agg_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    if "oi" in df.columns:
        agg_dict["oi"] = "last"
    if "iv" in df.columns:
        agg_dict["iv"] = "mean"
    if "spot" in df.columns:
        agg_dict["spot"] = "last"
    resampled = df.resample(target_tf).agg(agg_dict)
    resampled = resampled.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return resampled

def fetch_index_data(dhan, timeframe="15m", from_date=None, to_date=None, interval=15):
    try:
        interval_map_inv = {1: 1, 5: 5, 15: 15, 30: 25, 60: 60}
        api_interval = interval_map_inv.get(interval, 15)
        if not from_date:
            from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        resp = dhan.intraday_minute_data(
            security_id=NIFTY_SECURITY_ID,
            exchange_segment=dhanhq.INDEX,
            instrument_type="INDEX",
            from_date=from_date[:10],
            to_date=to_date[:10],
            interval=api_interval,
            oi=False,
        )
        if resp.get("status") == "success" and resp.get("data"):
            rows = resp["data"]
            records = []
            for row in rows:
                ts = row.get("start_time") or row.get("timestamp", "")
                records.append({
                    "timestamp": pd.to_datetime(ts),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume", 0),
                })
            if not records:
                return pd.DataFrame()
            df = pd.DataFrame(records)
            df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("timestamp")
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()
