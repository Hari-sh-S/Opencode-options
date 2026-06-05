import streamlit as st
import time
import pickle
import os
from datetime import datetime, timedelta
from dhanhq import DhanLogin, dhanhq, DhanContext

TOKEN_CACHE_FILE = "dhan_token_cache.pkl"

def get_cached_token():
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "rb") as f:
            cache = pickle.load(f)
        if "access_token" in cache and "expiry" in cache:
            expiry = cache["expiry"]
            if isinstance(expiry, str):
                expiry = datetime.fromisoformat(expiry)
            if datetime.now() < expiry:
                return cache["access_token"]
    return None

def cache_token(access_token):
    expiry = datetime.now() + timedelta(hours=23, minutes=30)
    with open(TOKEN_CACHE_FILE, "wb") as f:
        pickle.dump({"access_token": access_token, "expiry": expiry}, f)

def clear_token_cache():
    if os.path.exists(TOKEN_CACHE_FILE):
        os.remove(TOKEN_CACHE_FILE)

def authenticate(totp):
    client_id = st.secrets.get("DHAN_CLIENT_ID", "")
    pin = st.secrets.get("DHAN_PIN", "")
    if not client_id or not pin:
        st.error("DHAN_CLIENT_ID and DHAN_PIN must be set in Streamlit secrets")
        return None, None
    try:
        dhan_login = DhanLogin(client_id)
        access_token_data = dhan_login.generate_token(pin, totp)
        if access_token_data and "accessToken" in access_token_data:
            token = access_token_data["accessToken"]
            cache_token(token)
            dhan_context = DhanContext(client_id, token)
            dhan = dhanhq(dhan_context)
            return dhan, token
        st.error(f"Auth failed: {access_token_data}")
        return None, None
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None, None

def get_dhan_client():
    client_id = st.secrets.get("DHAN_CLIENT_ID", "")
    token = get_cached_token()
    if token:
        dhan_context = DhanContext(client_id, token)
        dhan = dhanhq(dhan_context)
        return dhan, token
    return None, None

def check_auth_status():
    token = get_cached_token()
    if token:
        client_id = st.secrets.get("DHAN_CLIENT_ID", "")
        try:
            dhan_login = DhanLogin(client_id)
            profile = dhan_login.user_profile(token)
            if profile and profile.get("status") == "success":
                expiry = None
                cache_path = TOKEN_CACHE_FILE
                if os.path.exists(cache_path):
                    with open(cache_path, "rb") as f:
                        cache = pickle.load(f)
                    expiry = cache.get("expiry")
                    if isinstance(expiry, str):
                        expiry = datetime.fromisoformat(expiry)
                return {
                    "status": "active",
                    "token": token,
                    "expires_at": expiry,
                    "client_id": client_id,
                }
        except Exception:
            clear_token_cache()
    return {"status": "inactive", "token": None, "expires_at": None, "client_id": None}
