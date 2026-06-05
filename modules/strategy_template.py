import json
import streamlit as st
from datetime import datetime
from datasets import load_dataset, Dataset
from huggingface_hub import HfApi

def _get_hf_repo():
    return st.secrets.get("HF_DATASET_REPO", "")

def _get_hf_token():
    return st.secrets.get("HF_TOKEN", "")

def save_strategy(strategy_config, name=None):
    repo = _get_hf_repo()
    token = _get_hf_token()
    if not repo or not token:
        st.warning("HF_TOKEN and HF_DATASET_REPO must be set in secrets")
        return False
    if name is None:
        name = f"strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    strategy_config["name"] = name
    strategy_config["saved_at"] = datetime.now().isoformat()
    try:
        api = HfApi()
        try:
            api.dataset_info(repo, token=token)
        except Exception:
            api.create_repo(repo_id=repo, repo_type="dataset", private=True, token=token)
        try:
            existing_ds = load_dataset(repo, split="train", token=token)
            existing_data = existing_ds.to_list()
        except Exception:
            existing_data = []
        existing_data.append({"strategy_name": name, "config": json.dumps(strategy_config)})
        new_ds = Dataset.from_list(existing_data)
        new_ds.push_to_hub(repo, token=token)
        return True
    except Exception as e:
        st.error(f"Failed to save strategy: {e}")
        return False

def load_strategies():
    repo = _get_hf_repo()
    token = _get_hf_token()
    if not repo or not token:
        return []
    try:
        ds = load_dataset(repo, split="train", token=token)
        strategies = []
        for row in ds.to_list():
            config = json.loads(row["config"])
            strategies.append(config)
        return strategies
    except Exception:
        return []

def delete_strategy(name):
    repo = _get_hf_repo()
    token = _get_hf_token()
    if not repo or not token:
        return False
    try:
        ds = load_dataset(repo, split="train", token=token)
        data = ds.to_list()
        data = [row for row in data if row.get("strategy_name") != name]
        new_ds = Dataset.from_list(data)
        new_ds.push_to_hub(repo, token=token)
        return True
    except Exception:
        return False
