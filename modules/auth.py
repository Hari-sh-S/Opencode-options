import streamlit as st
import time
import pickle
import os
import json
from datetime import datetime, timedelta
from dhanhq import DhanLogin, dhanhq, DhanContext

TOKEN_CACHE_FILE = "dhan_token_cache.pkl"
HF_TOKEN_FILE = "dhan_token.json"

def _hf_enabled():
    return bool(st.secrets.get("HF_TOKEN") and st.secrets.get("HF_DATASET_REPO"))

def _save_token_to_hf(token, expiry):
    if not _hf_enabled():
        return
    try:
        from huggingface_hub import HfApi
        repo = st.secrets["HF_DATASET_REPO"]
        data = json.dumps({
            "access_token": token,
            "expiry": expiry.isoformat() if hasattr(expiry, "isoformat") else expiry,
            "client_id": st.secrets.get("DHAN_CLIENT_ID", ""),
        })
        api = HfApi(token=st.secrets["HF_TOKEN"])
        api.upload_file(
            path_or_fileobj=data.encode(),
            path_in_repo=HF_TOKEN_FILE,
            repo_id=repo,
            repo_type="dataset",
        )
    except Exception:
        pass

def _load_token_from_hf():
    if not _hf_enabled():
        return None
    try:
        from huggingface_hub import hf_hub_download
        repo = st.secrets["HF_DATASET_REPO"]
        path = hf_hub_download(
            repo_id=repo,
            filename=HF_TOKEN_FILE,
            token=st.secrets["HF_TOKEN"],
            repo_type="dataset",
        )
        with open(path) as f:
            data = json.load(f)
        expiry = data.get("expiry")
        if expiry:
            if isinstance(expiry, str):
                expiry = datetime.fromisoformat(expiry)
            if datetime.now() < expiry:
                return data.get("access_token")
    except Exception:
        pass
    return None

def _delete_token_from_hf():
    if not _hf_enabled():
        return
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=st.secrets["HF_TOKEN"])
        api.delete_file(
            path_in_repo=HF_TOKEN_FILE,
            repo_id=st.secrets["HF_DATASET_REPO"],
            repo_type="dataset",
        )
    except Exception:
        pass

def get_cached_token():
    token = None
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "rb") as f:
            cache = pickle.load(f)
        if "access_token" in cache and "expiry" in cache:
            expiry = cache["expiry"]
            if isinstance(expiry, str):
                expiry = datetime.fromisoformat(expiry)
            if datetime.now() < expiry:
                token = cache["access_token"]
    if not token:
        token = _load_token_from_hf()
        if token:
            cache_token(token, persist_only=True)
    return token

def cache_token(access_token, persist_only=False):
    expiry = datetime.now() + timedelta(hours=23, minutes=30)
    if not persist_only:
        with open(TOKEN_CACHE_FILE, "wb") as f:
            pickle.dump({"access_token": access_token, "expiry": expiry}, f)
    _save_token_to_hf(access_token, expiry)

def clear_token_cache():
    if os.path.exists(TOKEN_CACHE_FILE):
        os.remove(TOKEN_CACHE_FILE)
    _delete_token_from_hf()

def verify_token(token):
    client_id = st.secrets.get("DHAN_CLIENT_ID", "")
    try:
        dhan_login = DhanLogin(client_id)
        profile = dhan_login.user_profile(token)
        return profile and profile.get("status") == "success"
    except Exception:
        return False

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
        err = access_token_data or {}
        msg = err.get("message", str(err))
        if "2 minutes" in msg:
            cached = get_cached_token()
            if cached and verify_token(cached):
                st.info("⏳ Using cached token (Dhan rate limit — 2 min wait). It's still valid.")
                dhan_context = DhanContext(client_id, cached)
                dhan = dhanhq(dhan_context)
                return dhan, cached
            st.warning("⏳ Dhan allows only one token per 2 minutes. Wait 2 min, then try again.")
        else:
            st.error(f"Auth failed: {msg}")
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
                if os.path.exists(TOKEN_CACHE_FILE):
                    with open(TOKEN_CACHE_FILE, "rb") as f:
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
