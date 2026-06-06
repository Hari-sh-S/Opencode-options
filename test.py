#!/usr/bin/env python3
"""
Standalone test to verify Dhan expired options API with your credentials.
Run: python test.py
"""
import os
import json
from datetime import datetime, timedelta
from dhanhq import dhanhq, DhanLogin, DhanContext

# ===== SET YOUR CREDENTIALS HERE =====
DHAN_CLIENT_ID = "YOUR_CLIENT_ID"
DHAN_PIN = "YOUR_PIN"
TOTP = "YOUR_6_DIGIT_TOTP"
# ======================================

NIFTY_SECURITY_ID = "13"

def get_token(client_id, pin, totp):
    dhan_login = DhanLogin(client_id)
    resp = dhan_login.generate_token(pin, totp)
    if resp and "accessToken" in resp:
        return resp["accessToken"]
    print(f"Auth failed: {resp}")
    return None

def test_expired_options(dhan, expiry_flag, expiry_code, strike, option_type, from_date, to_date, interval=1):
    print(f"\nTesting: {expiry_flag} code {expiry_code} {strike} {option_type}")
    print(f"  Date range: {from_date} to {to_date}")
    print(f"  Interval: {interval}min")
    
    resp = dhan.expired_options_data(
        security_id=int(NIFTY_SECURITY_ID),
        exchange_segment="NSE_FNO",
        instrument_type="OPTIDX",
        expiry_flag=expiry_flag,
        expiry_code=expiry_code,
        strike=strike,
        drv_option_type=option_type,
        required_data=["open", "high", "low", "close", "volume", "oi", "iv", "spot"],
        from_date=from_date,
        to_date=to_date,
        interval=interval,
    )
    
    print(f"  Status: {resp.get('status')}")
    if resp.get("status") == "success" and resp.get("data"):
        data = resp["data"]
        print(f"  Data keys: {list(data.keys())}")
        opt_key = "CE" if option_type == "CALL" else "PE"
        opt_data = data.get(opt_key) or data.get(opt_key.lower())
        if opt_data and opt_data.get("timestamp"):
            n = len(opt_data["timestamp"])
            print(f"  ✅ Got {n} bars for {opt_key}")
            # Show first few
            for i in range(min(3, n)):
                ts = datetime.fromtimestamp(opt_data["timestamp"][i]).strftime("%Y-%m-%d %H:%M")
                o = opt_data["open"][i]
                h = opt_data["high"][i]
                l = opt_data["low"][i]
                c = opt_data["close"][i]
                print(f"    {ts}  O:{o} H:{h} L:{l} C:{c}")
            return True
        else:
            print(f"  ⚠️ No {opt_key} data in response")
            return False
    else:
        err = resp.get("remarks", "unknown")
        if isinstance(err, dict):
            err = err.get("error_message", str(err))
        print(f"  ❌ Failed: {err}")
        return False

def main():
    # Authenticate
    token = get_token(DHAN_CLIENT_ID, DHAN_PIN, TOTP)
    if not token:
        return
    
    dhan_context = DhanContext(DHAN_CLIENT_ID, token)
    dhan = dhanhq(dhan_context)
    print("✅ Authenticated")
    
    # Test recent date (last week)
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    print("\n" + "="*60)
    print("TEST 1: Recent week (ATM CALL, WEEK code 1)")
    test_expired_options(dhan, "WEEK", 1, "ATM", "CALL", from_date, to_date, 1)
    
    print("\n" + "="*60)
    print("TEST 2: Same, 1-day range (exact working example)")
    to_date2 = datetime.now().strftime("%Y-%m-%d")
    from_date2 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    test_expired_options(dhan, "WEEK", 1, "ATM", "CALL", from_date2, to_date2, 1)
    
    print("\n" + "="*60)
    print("TEST 3: MONTH expiry (ATM CALL, MONTH code 1)")
    test_expired_options(dhan, "MONTH", 1, "ATM", "CALL", from_date, to_date, 1)
    
    print("\n" + "="*60)
    print("TEST 4: 3-month range with WEEK code 1")
    from_date3 = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    test_expired_options(dhan, "WEEK", 1, "ATM", "CALL", from_date3, to_date, 1)

if __name__ == "__main__":
    main()