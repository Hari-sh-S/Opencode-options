import pandas as pd
import numpy as np
from datetime import datetime, time as dtime
from modules.formula_parser import parse_formula, evaluate_formula_node
from modules.data_manager import (
    fetch_expired_options_data, build_backtest_data_bundle, resample_to_timeframe,
    fetch_expiry_list
)
from modules.position_sizing import calculate_position_size
from modules.backtest.metrics import calculate_metrics

class BacktestEngine:
    def __init__(self, dhan_client):
        self.dhan = dhan_client
        self.trades = []
        self.equity_curve = []
        self.current_position = None
        self.entry_bar_idx = None

    def run(self, config, progress_callback=None):
        self.trades = []
        self.equity_curve = []
        self.current_position = None
        self.entry_bar_idx = None

        capital = config.get("initial_capital", 100000)
        reinvest = config.get("reinvest_profits", False)
        entry_formula = config.get("entry_formula", "")
        timeframe = config.get("timeframe", "15m")
        option_type = config.get("option_type", "CALL")
        exit_config = config.get("exit_config", {})
        position_method = config.get("position_method", "Fixed Lot")
        from_date = config.get("from_date", "")
        to_date = config.get("to_date", "")
        max_positions = config.get("max_positions", 1)

        expiry_flag = config.get("expiry_flag", "WEEK")
        expiry_code = config.get("expiry_code", 1)
        strike = config.get("strike", "ATM")
        interval = config.get("interval", 15)

        if not from_date or not to_date:
            return {"error": "Backtest date range required"}

        parsed_entry, entry_error = parse_formula(entry_formula)
        if entry_error:
            return {"error": f"Entry formula error: {entry_error}"}

        if progress_callback:
            progress_callback(0.05, "Fetching expired options data...")

        opt_df = fetch_expired_options_data(
            self.dhan, expiry_flag, expiry_code, strike,
            option_type, from_date, to_date, interval,
            progress_callback=progress_callback,
        )

        if opt_df.empty:
            return {"error": f"No expired options data for {strike} {option_type} {expiry_flag} expiry code {expiry_code}"}

        if progress_callback:
            progress_callback(0.2, f"Loaded {len(opt_df)} bars of option data")

        expiry_boundaries = []
        if expiry_flag == "WEEK" and not any([exit_config.get("target_pct"), exit_config.get("stop_loss_pct"), exit_config.get("exit_bar_count")]):
            try:
                expiries = fetch_expiry_list(self.dhan)
                if expiries:
                    cutoff = datetime.strptime(from_date[:10], "%Y-%m-%d") if from_date else opt_df["timestamp"].min()
                expiry_times = []
                for e in expiries:
                    ed = datetime.strptime(str(e)[:10], "%Y-%m-%d")
                    ed_close = ed.replace(hour=15, minute=30, second=0)
                    if ed_close > cutoff:
                        expiry_times.append(ed_close)
                expiry_times.sort()
                for et in expiry_times:
                    mask = (opt_df["timestamp"].dt.date == et.date()) & (opt_df["timestamp"].dt.time <= dtime(15, 30))
                    if mask.any():
                        boundary_idx = mask[mask].index[-1]
                        expiry_boundaries.append(boundary_idx)
            except Exception as e:
                if progress_callback:
                    progress_callback(0.2, f"Expiry detection: {e}")
        if progress_callback and expiry_flag == "WEEK" and not any([exit_config.get("target_pct"), exit_config.get("stop_loss_pct"), exit_config.get("exit_bar_count")]):
            progress_callback(0.2, f"Found {len(expiry_boundaries)} expiry boundaries")
        expiry_set = set(expiry_boundaries)

        total_bars = len(opt_df)
        available_capital = float(capital)
        lot_size = 50

        for i in range(1, total_bars):
            if self.current_position is not None:
                pos = self.current_position
                exit_reason = None

                if exit_config.get("target_pct"):
                    entry_px = pos["entry_price"]
                    current_px = opt_df["close"].iloc[i]
                    if entry_px > 0:
                        pnl_pct = ((current_px - entry_px) / entry_px) * 100
                        if pnl_pct >= exit_config["target_pct"]:
                            exit_reason = "target"

                if not exit_reason and exit_config.get("stop_loss_pct"):
                    entry_px = pos["entry_price"]
                    current_px = opt_df["close"].iloc[i]
                    if entry_px > 0:
                        pnl_pct = ((current_px - entry_px) / entry_px) * 100
                        if pnl_pct <= -exit_config["stop_loss_pct"]:
                            exit_reason = "stop_loss"

                if not exit_reason and exit_config.get("exit_bar_count"):
                    bars_held = i - self.entry_bar_idx
                    if bars_held >= exit_config["exit_bar_count"]:
                        exit_reason = "candle_count"

                if not exit_reason and i in expiry_set:
                    exit_reason = "expiry"

                if not exit_reason and i == total_bars - 1:
                    exit_reason = "end_of_data"

                if exit_reason:
                    exit_price = opt_df["close"].iloc[i]
                    direction = 1 if option_type.upper() == "CALL" else -1
                    pnl = (exit_price - pos["entry_price"]) * pos["quantity"] * direction
                    self.trades.append({
                        "entry_time": pos["entry_time"],
                        "exit_time": opt_df["timestamp"].iloc[i],
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "quantity": pos["quantity"],
                        "pnl": pnl,
                        "bars_held": i - self.entry_bar_idx,
                        "exit_reason": exit_reason,
                    })
                    available_capital += pnl
                    if reinvest:
                        available_capital = max(available_capital, 0)
                    self.equity_curve.append({
                        "time": opt_df["timestamp"].iloc[i],
                        "capital": available_capital,
                    })
                    self.current_position = None
                    self.entry_bar_idx = None
                    continue

            if self.current_position is None and len(self.trades) < max_positions:
                window = opt_df.iloc[:i+1].copy()
                data_bundle = build_backtest_data_bundle(window)
                data_bundle_full = {timeframe: data_bundle}
                should_enter, eval_error = evaluate_formula_node(
                    parsed_entry, data_bundle_full, i
                )
                if eval_error:
                    if i < 5 or i % 500 == 0:
                        if progress_callback:
                            progress_callback(0.2 + 0.7 * (i / total_bars), f"Eval error at bar {i}: {eval_error}")
                if should_enter:
                    option_price = opt_df["close"].iloc[i]
                    if option_price > 0:
                        quantity = calculate_position_size(
                            position_method, available_capital, option_price,
                            lots=exit_config.get("fixed_lots", 1),
                            risk_per_trade_pct=exit_config.get("risk_per_trade_pct", 2),
                        )
                        if quantity >= lot_size:
                            quantity = (quantity // lot_size) * lot_size
                        if quantity > 0:
                            self.current_position = {
                                "entry_price": option_price,
                                "entry_time": opt_df["timestamp"].iloc[i],
                                "quantity": quantity,
                            }
                            self.entry_bar_idx = i

            if progress_callback and total_bars > 20 and i % max(1, total_bars // 20) == 0:
                progress_callback(
                    0.2 + 0.7 * (i / total_bars),
                    f"Bar {i}/{total_bars} | Trades: {len(self.trades)}",
                )

        if progress_callback:
            progress_callback(0.9, "Calculating metrics...")

        metrics = calculate_metrics(self.trades, capital)
        metrics["equity_curve"] = self.equity_curve
        return metrics
