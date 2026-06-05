import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="Options Trading System — Nifty 50",
    page_icon="📊",
    layout="wide",
)

from modules.auth import authenticate, get_dhan_client, check_auth_status, clear_token_cache, get_cached_token, get_auth_debug_info
from modules.formula_parser import validate_formula, parse_formula, evaluate_formula_node
from modules.formula_reference import FORMULA_REFERENCE
from modules.data_manager import (
    fetch_expired_options_data, build_backtest_data_bundle,
    get_option_chain_data, get_live_quote, get_live_index_value,
    resample_to_timeframe, fetch_expiry_list,
    calculate_pcr, calculate_max_pain, extract_greeks_from_chain,
)
from modules.backtest.engine import BacktestEngine
from modules.execution.engine import ExecutionEngine
from modules.instrument_selector import (
    select_instrument_atm_offset, select_instrument_by_premium,
    get_available_expiries,
)
from modules.position_sizing import calculate_position_size
from modules.strategy_template import save_strategy, load_strategies
from modules.vix import get_vix_quote

IST = timezone(timedelta(hours=5, minutes=30))

def ist_now():
    return datetime.now(IST).strftime("%d-%b-%Y %I:%M:%S %p")

if "dhan" not in st.session_state:
    st.session_state.dhan = None
if "auth_status" not in st.session_state:
    st.session_state.auth_status = check_auth_status()
if "auth_token" not in st.session_state:
    st.session_state.auth_token = get_cached_token()
if "backtest_results" not in st.session_state:
    st.session_state.backtest_results = None
if "execution_log" not in st.session_state:
    st.session_state.execution_log = []
if "expiry_list" not in st.session_state:
    st.session_state.expiry_list = []

def main():
    st.title("📊 Options Trading System — Nifty 50")
    st.caption(f"🕐 Last updated: {ist_now()}  •  NSE Nifty 50  •  Data: Dhan API")
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🔐 Dhan Auth",
        "📈 Backtest",
        "⚡ Execution",
        "📖 Formula Reference",
    ])

    with tab1:
        render_auth_tab()
    with tab2:
        render_backtest_tab()
    with tab3:
        render_execution_tab()
    with tab4:
        render_formula_reference()

def render_auth_tab():
    st.subheader("Dhan API Authentication")
    col1, col2 = st.columns([1, 1])
    with col1:
        status = st.session_state.auth_status
        if status["status"] == "active":
            st.success(f"✅ Authenticated — Client: {status.get('client_id', '')}")
            expiry = status.get("expires_at")
            if expiry:
                remaining = (expiry - datetime.now()).total_seconds()
                hours = int(remaining // 3600)
                mins = int((remaining % 3600) // 60)
                st.info(f"Token expires in ~{hours}h {mins}m")
            if st.button("🔄 Re-authenticate"):
                clear_token_cache()
                st.session_state.auth_status = check_auth_status()
                st.rerun()
            if st.button("🔌 Disconnect"):
                clear_token_cache()
                st.session_state.auth_status = {"status": "inactive", "token": None, "expires_at": None}
                st.session_state.dhan = None
                st.rerun()
            if st.session_state.dhan:
                if st.button("📋 Load Expiry List"):
                    expiries = fetch_expiry_list(st.session_state.dhan)
                    st.session_state.expiry_list = expiries
                    if expiries:
                        st.success(f"Loaded {len(expiries)} expiry dates")
                    else:
                        st.info("No expiries found")
        else:
            st.warning("⚠️ Not authenticated")
            st.caption("Token lasts 24 hours. You'll be asked for TOTP again when it expires.")
            totp = st.text_input("TOTP Code", type="password", placeholder="Enter 6-digit TOTP")
            if st.button("Authenticate", type="primary"):
                if totp:
                    with st.spinner("Authenticating with Dhan..."):
                        dhan, token = authenticate(totp)
                        if dhan and token:
                            st.session_state.dhan = dhan
                            st.session_state.auth_status = check_auth_status()
                            st.success("✅ Authentication successful!")
                            st.rerun()
                        else:
                            st.error("❌ Auth failed. Check Client ID, PIN, and TOTP.")
                else:
                    st.error("Please enter TOTP code")
        with st.expander("🔍 Debug - Token Status"):
            show = st.checkbox("Show access token (sensitive!)", key="show_token")
            diag = get_auth_debug_info(show_token=show)
            st.json(diag)
            if not diag["hf_enabled"]:
                st.warning("HF_TOKEN or HF_DATASET_REPO not set in secrets — token won't persist across restarts.")
    with col2:
        st.subheader("Data Source")
        st.markdown("""
        - **Backtesting**: Expired Options API (actual option OHLC + spot data)
        - **Live Index**: Dhan quote API
        - **VIX**: Yahoo Finance (`^INDIAVIX`)
        - **Live Greeks**: Option Chain API
        """)
        vix = get_vix_quote()
        if vix:
            st.metric("India VIX", f"{vix['current']:.2f}", f"{vix['change']:.2f}")
        if st.session_state.expiry_list:
            with st.expander("Available Expiry Dates"):
                exp_list = st.session_state.expiry_list
                if isinstance(exp_list, (list, tuple)):
                    for e in exp_list[:15]:
                        st.write(f"- {e}")
                    if len(exp_list) > 15:
                        st.caption(f"... and {len(exp_list)-15} more")
                elif isinstance(exp_list, dict):
                    for i, (k, v) in enumerate(list(exp_list.items())[:15]):
                        st.write(f"- {k}: {v}")
                else:
                    st.write(str(exp_list)[:500])
                    st.caption(f"... and {len(st.session_state.expiry_list)-15} more")

def render_backtest_tab():
    st.subheader("Backtesting Engine — Expired Options Data")
    if st.session_state.auth_status["status"] != "active" or st.session_state.dhan is None:
        st.warning("⚠️ Please authenticate first in the Dhan Auth tab")
        return

    dhan = st.session_state.dhan
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📐 Strategy Config")

        entry_formula = st.text_area(
            "Entry Condition Formula",
            placeholder="e.g. 60m/Index: SMA(Close,20) > 15000 AND 15m/Index: RSI(Close,14) < 30",
            height=80,
            help="See Formula Reference tab for syntax",
        )
        if entry_formula:
            valid, msg = validate_formula(entry_formula)
            if valid:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

        st.subheader("📅 Expired Options Config")
        expiry_flag = st.selectbox("Expiry Flag", ["WEEK", "MONTH"], index=0,
            help="WEEK = weekly expiry, MONTH = monthly expiry")
        expiry_code = st.selectbox("Expiry Code", [1, 2, 3], index=0,
            help="1=Near, 2=Next, 3=Far expiry")
        option_type = st.selectbox("Option Type", ["CALL", "PUT"], index=0)

        strike_options = ["ATM"] + [f"ATM{'+' if i > 0 else ''}{i}" for i in range(1, 11)] + [f"ATM{i}" for i in range(-10, 0)]
        strike = st.selectbox("Strike", strike_options, index=0,
            help="Strike relative to ATM. ATM, ATM+1, ATM-1, etc.")

        interval_map = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}
        timeframe_label = st.selectbox("Timeframe", list(interval_map.keys()), index=2)
        interval = interval_map[timeframe_label]

        col_dates = st.columns(2)
        with col_dates[0]:
            from_date = st.date_input("From Date", datetime.now() - timedelta(days=60),
                help="Max 30 days per API call, but system auto-chunks larger ranges")
        with col_dates[1]:
            to_date = st.date_input("To Date", datetime.now())

        st.subheader("🎯 Exit Conditions")
        use_target = st.checkbox("Target")
        target_pct = st.number_input("Target %", 0.0, 200.0, 10.0, 1.0) if use_target else None
        use_sl = st.checkbox("Stop Loss")
        sl_pct = st.number_input("Stop Loss %", 0.0, 200.0, 5.0, 1.0) if use_sl else None
        use_candle = st.checkbox("Exit after N candles")
        exit_candles = st.number_input("Candles", 1, 999, 5) if use_candle else None

    with col2:
        st.subheader("💰 Capital & Sizing")

        initial_capital = st.number_input("Initial Capital (₹)", 10000, 10000000, 100000, 10000)
        reinvest = st.checkbox("Reinvest profits", value=True)
        max_positions = st.number_input("Max Open Positions", 1, 100, 1)

        pos_method = st.selectbox(
            "Position Sizing",
            ["Fixed Lot", "Volatility Based", "Full Capital", "Kelly Criterion"],
            index=0,
        )
        fixed_lots = st.number_input("Number of Lots", 1, 1000, 1) if pos_method == "Fixed Lot" else None
        risk_pct = st.slider("Risk % per trade", 0.5, 10.0, 2.0, 0.5)

        st.subheader("💾 Strategy")
        strategy_name = st.text_input("Strategy Name", placeholder="MyStrategy")
        if st.button("Save Strategy"):
            if strategy_name:
                config = {k: v for k, v in locals().items() if k != "dhan"}
                if save_strategy(config, strategy_name):
                    st.success(f"✅ '{strategy_name}' saved!")

        st.subheader("📂 Load Strategy")
        strategies = load_strategies()
        if strategies:
            names = [s.get("name", "Unnamed") for s in strategies]
            sel = st.selectbox("Saved strategies", names)
            if st.button("Apply"):
                for s in strategies:
                    if s.get("name") == sel:
                        st.session_state.strategy_config = s
                        st.rerun()

    st.markdown("---")
    st.subheader("▶️ Run Backtest")
    run_btn = st.button("▶️ Run Backtest on Expired Options Data", type="primary")
    progress_bar = st.progress(0, text="Ready")

    if run_btn and entry_formula:
        interval_val = interval_map[timeframe_label]
        config = {
            "initial_capital": initial_capital,
            "reinvest_profits": reinvest,
            "entry_formula": entry_formula,
            "timeframe": timeframe_label,
            "interval": interval_val,
            "option_type": option_type,
            "expiry_flag": expiry_flag,
            "expiry_code": expiry_code,
            "strike": strike,
            "exit_config": {
                "target_pct": target_pct,
                "stop_loss_pct": sl_pct,
                "exit_bar_count": exit_candles,
            },
            "position_method": pos_method,
            "fix_lots": fixed_lots,
            "risk_per_trade_pct": risk_pct,
            "from_date": from_date.strftime("%Y-%m-%d"),
            "to_date": to_date.strftime("%Y-%m-%d"),
            "max_positions": max_positions,
        }
        engine = BacktestEngine(dhan)
        results = engine.run(config, lambda p, m: progress_bar.progress(p, text=m))
        st.session_state.backtest_results = results

    if st.session_state.backtest_results is not None:
        results = st.session_state.backtest_results
        if "error" in results:
            st.error(f"Backtest error: {results['error']}")
        else:
            st.subheader("📊 Results")
            mc = st.columns(4)
            with mc[0]:
                st.metric("Total Trades", results.get("total_trades", 0))
                st.metric("Win Rate", f"{results.get('win_rate', 0)*100:.1f}%")
            with mc[1]:
                st.metric("Total P&L", f"₹{results.get('total_pnl', 0):,.0f}")
                st.metric("Profit Factor", f"{results.get('profit_factor', 0):.2f}")
            with mc[2]:
                st.metric("Max Drawdown", f"₹{results.get('max_drawdown', 0):,.0f}")
                st.metric("Max DD %", f"{results.get('max_drawdown_pct', 0):.1f}%")
            with mc[3]:
                st.metric("Sharpe", f"{results.get('sharpe_ratio', 0):.2f}")
                st.metric("Expectancy", f"₹{results.get('expectancy', 0):.0f}")

            eq = results.get("equity_curve")
            if eq:
                eq_df = pd.DataFrame(eq)
                if not eq_df.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=eq_df["time"], y=eq_df["capital"],
                        mode="lines", name="Equity", line=dict(color="green", width=2)))
                    fig.update_layout(title="Equity Curve", xaxis_title="Date", yaxis_title="Capital (₹)", height=350)
                    st.plotly_chart(fig, use_container_width=True)

def render_execution_tab():
    st.subheader("Execution Engine")
    if st.session_state.auth_status["status"] != "active" or st.session_state.dhan is None:
        st.warning("⚠️ Please authenticate first")
        return

    dhan = st.session_state.dhan
    engine = ExecutionEngine(dhan)

    col1, col2 = st.columns([1, 1])
    with col1:
        timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "30m", "60m"], index=2, key="exec_tf")
        entry_formula = st.text_area("Entry Formula", height=70, key="exec_f",
            placeholder="60m/Index: SMA(Close,20) > SMA(Close,50)")
        if entry_formula:
            valid, msg = validate_formula(entry_formula)
            st.success(f"✅ {msg}") if valid else st.error(f"❌ {msg}")
        option_type = st.selectbox("Option Type", ["CALL", "PUT"], key="exec_opt")
        expiry = st.selectbox("Expiry Date", st.session_state.expiry_list if st.session_state.expiry_list else ["No expiries loaded"], key="exec_exp")
        atm_choice = st.selectbox("Selection", ["ATM", "ATM+1", "ATM-1", "Premium Based"], key="exec_atm")
        target_premium = st.number_input("Target Premium", 0, 10000, 200) if atm_choice == "Premium Based" else None

        st.subheader("Exit")
        ec = {}
        if st.checkbox("Target %", key="ext"):
            ec["target_pct"] = st.number_input("TGT %", 0.0, 100.0, 10.0, key="extv")
        if st.checkbox("Stop Loss %", key="exs"):
            ec["stop_loss_pct"] = st.number_input("SL %", 0.0, 100.0, 5.0, key="exsv")
        if st.checkbox("Time exit", key="extm"):
            ec["exit_time"] = str(st.time_input("Exit at", datetime.strptime("15:15", "%H:%M").time(), key="extmv"))

        capital = st.number_input("Capital (₹)", 10000, 10000000, 100000, key="exec_cap")
        pos_method = st.selectbox("Sizing", ["Fixed Lot", "Volatility Based", "Full Capital"], key="exec_pos")
        fixed_lots = st.number_input("Lots", 1, 100, 1) if pos_method == "Fixed Lot" else None

    with col2:
        st.subheader("Live Controls")
        is_open = engine.is_market_open()
        st.info("🟢 Market Open" if is_open else "🔴 Market Closed")

        if st.button("🔍 Check Entry", type="primary", use_container_width=True):
            if not st.session_state.expiry_list:
                st.warning("Load expiry list from Auth tab first")
            else:
                selected_expiry = expiry if expiry != "No expiries loaded" else (
                    st.session_state.expiry_list[0] if st.session_state.expiry_list else None
                )
                config = {
                    "entry_formula": entry_formula,
                    "timeframe": timeframe,
                    "expiry": selected_expiry,
                    "option_type": option_type,
                    "entry_logic": "atm" if atm_choice == "ATM" else ("atm_plus" if atm_choice == "ATM+1" else "atm_minus" if atm_choice == "ATM-1" else "premium"),
                    "atm_offset": 1 if atm_choice == "ATM+1" else -1 if atm_choice == "ATM-1" else 0,
                    "target_premium": target_premium,
                    "exit_config": ec,
                    "position_method": pos_method,
                    "initial_capital": capital,
                    "fixed_lots": fixed_lots,
                }
                with st.spinner("Checking conditions..."):
                    result = engine.check_entry(config)
                    st.json(result)
                    if result.get("status") == "entry_signal":
                        st.success(f"🎯 {result.get('message')}")
                        inst = result.get("instrument", {})
                        st.write("**Greeks (live):**")
                        st.json({
                            "delta": inst.get("delta"),
                            "gamma": inst.get("gamma"),
                            "theta": inst.get("theta"),
                            "vega": inst.get("vega"),
                            "iv": inst.get("iv"),
                            "oi": inst.get("oi"),
                        })

        if st.button("🔄 Refresh Positions"):
            positions = engine.order_manager.get_positions()
            st.json(positions)

        if st.button("📋 Order Book"):
            orders = engine.order_manager.get_order_list()
            st.json(orders)

        st.subheader("Execution Log")
        if st.session_state.execution_log:
            st.dataframe(pd.DataFrame(st.session_state.execution_log), use_container_width=True)

        if st.session_state.expiry_list and len(st.session_state.expiry_list) > 1:
            st.subheader("Chain Analysis")
            sel_expiry = st.selectbox("Analyse expiry", st.session_state.expiry_list, key="chain_exp")
            if st.button("Get PCR & MaxPain"):
                chain = get_option_chain_data(dhan, sel_expiry)
                if chain:
                    pcr = calculate_pcr(chain)
                    max_pain = calculate_max_pain(chain)
                    colp, colm = st.columns(2)
                    colp.metric("Put-Call Ratio (OI)", f"{pcr:.2f}" if pcr else "N/A")
                    colm.metric("Max Pain Strike", f"₹{max_pain:,.0f}" if max_pain else "N/A")

def render_formula_reference():
    st.subheader("Formula Reference Guide")
    st.markdown("`TIMEFRAME/ENTITY: INDICATOR(FIELD, PERIOD) OPERATOR VALUE`")

    for cat, items in FORMULA_REFERENCE.items():
        with st.expander(f"📋 {cat}", expanded=cat in ["Syntax", "Examples"]):
            if isinstance(items, dict):
                for k, v in items.items():
                    st.markdown(f"**{k}** — {v}" if cat != "Examples" else f"`{k}: {v}`")
            else:
                st.markdown(items)

if __name__ == "__main__":
    main()
