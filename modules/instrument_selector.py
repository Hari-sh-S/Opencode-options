import streamlit as st
import json
from modules.data_manager import fetch_expiry_list, get_option_chain_data

EXPIRY_FLAGS = {"Weekly": "WEEK", "Monthly": "MONTH"}
EXPIRY_CODES = {"Near": 1, "Next": 2, "Far": 3}

def get_available_expiries(dhan):
    return fetch_expiry_list(dhan)

def select_instrument_atm_offset(chain_data, spot, offset=0, option_type="CE"):
    try:
        oc = chain_data.get("oc", {})
        strikes = sorted([float(k) for k in oc.keys()])
        if not strikes:
            return None
        atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
        target_idx = min(max(atm_idx + offset, 0), len(strikes) - 1)
        target_strike = strikes[target_idx]
        sym_str = str(int(target_strike))
        contracts = oc.get(sym_str, {})
        opt = contracts.get(option_type.lower(), {})
        return {
            "strike": target_strike,
            "security_id": str(opt.get("securityId", "")),
            "ltp": opt.get("lastPrice", 0),
            "option_type": option_type,
            "delta": opt.get("delta"),
            "gamma": opt.get("gamma"),
            "theta": opt.get("theta"),
            "vega": opt.get("vega"),
            "iv": opt.get("iv"),
            "oi": opt.get("oi", 0),
        }
    except Exception as e:
        st.warning(f"Instrument selection error: {e}")
        return None

def select_instrument_by_premium(chain_data, target_premium, option_type="CE"):
    try:
        oc = chain_data.get("oc", {})
        best = None
        best_diff = float("inf")
        for strike_str, contracts in oc.items():
            opt = contracts.get(option_type.lower(), {})
            ltp = opt.get("lastPrice")
            if ltp:
                ltp = float(ltp)
                diff = abs(ltp - target_premium)
                if diff < best_diff:
                    best_diff = diff
                    best = {
                        "strike": float(strike_str),
                        "security_id": str(opt.get("securityId", "")),
                        "ltp": ltp,
                        "option_type": option_type,
                        "delta": opt.get("delta"),
                        "gamma": opt.get("gamma"),
                        "theta": opt.get("theta"),
                        "vega": opt.get("vega"),
                        "iv": opt.get("iv"),
                        "oi": opt.get("oi", 0),
                    }
        return best
    except Exception:
        return None
