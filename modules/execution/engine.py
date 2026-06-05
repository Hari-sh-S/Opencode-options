import streamlit as st
import pandas as pd
import time
from datetime import datetime, time as dtime
from modules.formula_parser import parse_formula, evaluate_formula_node
from modules.data_manager import (
    fetch_index_data, get_live_quote, get_live_index_value, get_option_chain_data,
)
from modules.position_sizing import calculate_position_size
from modules.execution.order_manager import OrderManager
from modules.instrument_selector import (
    select_instrument_atm_offset, select_instrument_by_premium,
)

MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)

class ExecutionEngine:
    def __init__(self, dhan):
        self.dhan = dhan
        self.order_manager = OrderManager(dhan)
        self.active_positions = []
        self.pending_entries = []
        self.execution_log = []

    def is_market_open(self):
        now = datetime.now().time()
        return MARKET_OPEN <= now <= MARKET_CLOSE

    def check_entry(self, config):
        if not self.is_market_open():
            return {"status": "market_closed", "message": "Market is closed"}
        entry_formula = config.get("entry_formula", "")
        timeframe = config.get("timeframe", "15m")
        expiry_date = config.get("expiry")
        entry_logic = config.get("entry_logic", "atm")
        atm_offset = config.get("atm_offset", 0)
        target_premium = config.get("target_premium", 200)
        option_type = "CE" if config.get("option_type", "CALL") == "CALL" else "PE"
        index_value = get_live_index_value(self.dhan)
        if not index_value:
            return {"status": "error", "message": "Could not fetch index value"}
        from_date = datetime.now().strftime("%Y-%m-%d") + " 09:15:00"
        to_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        index_df = fetch_index_data(self.dhan, timeframe, from_date, to_date)
        if index_df.empty:
            return {"status": "error", "message": "No intraday data available"}
        data_bundle = {timeframe: {"index": index_df}}
        parsed, error = parse_formula(entry_formula)
        if error:
            return {"status": "error", "message": f"Formula error: {error}"}
        should_enter, eval_error = evaluate_formula_node(parsed, data_bundle, len(index_df) - 1)
        if eval_error:
            return {"status": "error", "message": f"Evaluation error: {eval_error}"}
        if should_enter:
            chain_data = get_option_chain_data(self.dhan, expiry_date)
            if not chain_data:
                return {"status": "error", "message": "Could not fetch option chain"}
            instrument = None
            if entry_logic == "atm":
                instrument = select_instrument_atm_offset(
                    chain_data, index_value, 0, option_type
                )
            elif entry_logic == "atm_plus":
                instrument = select_instrument_atm_offset(
                    chain_data, index_value, atm_offset, option_type
                )
            elif entry_logic == "atm_minus":
                instrument = select_instrument_atm_offset(
                    chain_data, index_value, -atm_offset, option_type
                )
            elif entry_logic == "premium":
                instrument = select_instrument_by_premium(
                    chain_data, target_premium, option_type
                )
            if not instrument or not instrument.get("security_id"):
                return {"status": "error", "message": "Could not select instrument"}
            return {
                "status": "entry_signal",
                "instrument": instrument,
                "index_value": index_value,
                "expiry": expiry_date,
                "message": f"Entry signal at {instrument.get('strike')} {option_type}",
            }
        return {"status": "no_signal", "message": "No entry condition met"}

    def execute_entry(self, config, instrument):
        capital = config.get("initial_capital", 100000)
        option_price = instrument.get("ltp", 0)
        position_method = config.get("position_method", "Fixed Lot")
        fixed_lots = config.get("fixed_lots", 1)
        risk_per_trade = config.get("risk_per_trade_pct", 2)
        quantity = calculate_position_size(
            position_method, capital, option_price,
            lots=fixed_lots,
            risk_per_trade_pct=risk_per_trade,
        )
        if quantity <= 0:
            return {"status": "error", "message": "Position size is zero"}
        order_result = self.order_manager.place_order(
            security_id=instrument["security_id"],
            transaction_type="BUY",
            quantity=quantity,
            order_type="MARKET",
            tag=f"ENTRY_{instrument['strike']}_{instrument['option_type']}",
        )
        log_entry = {
            "time": datetime.now().isoformat(),
            "action": "ENTRY",
            "instrument": instrument,
            "quantity": quantity,
            "order_result": order_result,
        }
        self.execution_log.append(log_entry)
        return {"status": "order_placed", "order_result": order_result, "quantity": quantity}

    def check_exit(self, position, config):
        exit_config = config.get("exit_config", {})
        if not position:
            return False
        current_price = self.order_manager.get_positions()
        if exit_config.get("time_based_exit"):
            exit_time_str = exit_config.get("exit_time", "15:15")
            exit_time = datetime.strptime(exit_time_str, "%H:%M").time()
            if datetime.now().time() >= exit_time:
                return True
        pnl_pct = exit_config.get("target_pct", 0)
        sl_pct = exit_config.get("stop_loss_pct", 0)
        if pnl_pct > 0 or sl_pct > 0:
            position_pnl = position.get("pnl_pct", 0)
            if pnl_pct > 0 and position_pnl >= pnl_pct:
                return True
            if sl_pct > 0 and position_pnl <= -sl_pct:
                return True
        return False

    def execute_exit(self, position):
        result = self.order_manager.exit_position(
            security_id=position["security_id"],
            quantity=position["quantity"],
            transaction_type="SELL",
        )
        log_entry = {
            "time": datetime.now().isoformat(),
            "action": "EXIT",
            "position": position,
            "order_result": result,
        }
        self.execution_log.append(log_entry)
        return result

    def run_cycle(self, config):
        if not self.is_market_open():
            return {"status": "market_closed", "message": "Market closed. Next cycle at market open."}
        for pos in self.active_positions:
            if self.check_exit(pos, config):
                self.execute_exit(pos)
        if len(self.active_positions) < config.get("max_positions", 1):
            entry_result = self.check_entry(config)
            if entry_result["status"] == "entry_signal":
                instrument = entry_result["instrument"]
                exec_result = self.execute_entry(config, instrument)
                return exec_result
            return entry_result
        return {"status": "max_positions", "message": f"Max positions ({len(self.active_positions)}) reached"}

    def run_live(self, config, interval_seconds=60):
        placeholder = st.empty()
        status_placeholder = st.empty()
        while True:
            if not self.is_market_open():
                next_open = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
                if next_open < datetime.now():
                    next_open = next_open + timedelta(days=1)
                wait_seconds = (next_open - datetime.now()).total_seconds()
                status_placeholder.info(f"Market closed. Next check at {next_open.strftime('%H:%M:%S')}")
                time.sleep(min(wait_seconds, 300))
                continue
            result = self.run_cycle(config)
            with placeholder.container():
                st.write(f"Cycle at {datetime.now().strftime('%H:%M:%S')}")
                st.json(result)
            time.sleep(interval_seconds)


