from datetime import datetime, timedelta

class ExitConditionChecker:
    def __init__(self):
        self.conditions = {}

    def set_time_based(self, exit_time_str):
        self.conditions["time_based"] = exit_time_str

    def set_candle_count(self, timeframe, count):
        self.conditions["candle_count"] = {"timeframe": timeframe, "count": count}

    def set_target(self, target_type, value):
        self.conditions["target"] = {"type": target_type, "value": value}

    def set_stop_loss(self, sl_type, value):
        self.conditions["stop_loss"] = {"type": sl_type, "value": value}

    def set_indicator_formula(self, formula_text):
        self.conditions["indicator"] = formula_text

    def set_expiry_exit(self, enabled=True):
        self.conditions["exit_at_expiry"] = enabled

    def check_exit(self, entry_price, current_price, entry_time, current_time,
                   current_bar_idx=None, total_bars=None, option_data=None):
        reasons = []
        for cond_type, config in self.conditions.items():
            if cond_type == "time_based":
                exit_time = datetime.strptime(config, "%H:%M").time()
                if current_time.time() >= exit_time:
                    reasons.append("time_based")
            elif cond_type == "candle_count":
                if current_bar_idx is not None and entry_bar_idx is not None:
                    bars_held = current_bar_idx - entry_bar_idx
                    if bars_held >= config["count"]:
                        reasons.append("candle_count")
            elif cond_type == "target":
                if entry_price > 0 and current_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    pnl_rs = current_price - entry_price
                    if config["type"] == "%":
                        if pnl_pct >= config["value"]:
                            reasons.append("target")
                    elif config["type"] == "Rs":
                        if pnl_rs >= config["value"]:
                            reasons.append("target")
            elif cond_type == "stop_loss":
                if entry_price > 0 and current_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    pnl_rs = entry_price - current_price
                    if config["type"] == "%":
                        if pnl_pct <= -config["value"]:
                            reasons.append("stop_loss")
                    elif config["type"] == "Rs":
                        if pnl_rs >= config["value"]:
                            reasons.append("stop_loss")
            elif cond_type == "indicator":
                if option_data is not None:
                    from modules.formula_parser import parse_formula, evaluate_formula_node
                    result, error = parse_formula(config)
                    if not error and result:
                        exited, _ = evaluate_formula_node(result, option_data, current_bar_idx)
                        if exited:
                            reasons.append("indicator")
        return reasons

    @property
    def has_conditions(self):
        return len(self.conditions) > 0
