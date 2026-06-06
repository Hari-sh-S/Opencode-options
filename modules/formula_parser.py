import re
import pandas as pd
import numpy as np
from modules.indicators import (
    sma, ema, rsi, macd, bollinger_bands, supertrend, adx, atr, roc,
    williams_r, stoch_k, ichimoku, heikin_ashi, detect_doji, detect_engulfing,
    detect_hammer, detect_shooting_star, positive_candles, negative_candles, pct_return
)

VALID_TIMEFRAMES = ["1m", "5m", "15m", "25m", "30m", "60m", "1D"]
VALID_ENTITIES = ["Index", "Opt"]
VALID_FIELDS = ["Open", "High", "Low", "Close", "Volume", "OI", "IV", "Spot"]
VALID_INDICATORS = [
    "SMA", "EMA", "RSI", "MACD", "BB", "Supertrend", "ADX", "ATR", "ROC",
    "WilliamsR", "StochK", "Ichimoku", "HeikinAshi",
]
VALID_PATTERNS = ["Doji", "Engulfing", "Hammer", "ShootingStar"]
VALID_SPECIAL = [
    "VIX", "PCR", "MaxPain", "IVPercentile", "Delta", "Gamma", "Theta", "Vega",
    "Return", "PositiveCandles", "BidAskSpread", "OIChange",
    "HourFilter", "DayFilter",
]
VALID_OPERATORS = [">", "<", ">=", "<=", "==", "!="]
VALID_COMBINATORS = ["AND", "OR"]

class FormulaToken:
    def __init__(self, raw_text):
        self.raw = raw_text.strip()

class Condition(FormulaToken):
    def __init__(self, raw_text):
        super().__init__(raw_text)
        self.timeframe = None
        self.entity = None
        self.indicator = None
        self.field = None
        self.period = None
        self.operator = None
        self.compare_value = None
        self.pattern_name = None
        self.special_name = None
        self._parse()

    def _parse(self):
        text = self.raw.strip()
        tf_entity_match = re.match(r"^(\w+)/(\w+):\s*(.*)", text)
        if not tf_entity_match:
            return
        self.timeframe = tf_entity_match.group(1)
        self.entity = tf_entity_match.group(2)
        rest = tf_entity_match.group(3).strip()
        op_match = re.match(r"(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+)", rest)
        if op_match:
            expr = op_match.group(1).strip()
            self.operator = op_match.group(2)
            self.compare_value = op_match.group(3).strip()
        else:
            expr = rest
        indicator_match = re.match(r"(\w+)\(([^)]*)\)", expr)
        if indicator_match:
            name = indicator_match.group(1)
            params = indicator_match.group(2)
            if name in VALID_INDICATORS + ["Return", "PositiveCandles", "NegativeCandles"]:
                self.indicator = name
                parts = [p.strip() for p in params.split(",") if p.strip()]
                if len(parts) >= 1:
                    if parts[0] in ["Open", "High", "Low", "Close", "Volume", "OI", "IV", "Spot"]:
                        self.field = parts[0]
                        self.period = int(parts[1]) if len(parts) > 1 else None
                    else:
                        self.period = int(parts[0]) if parts[0].isdigit() else None
                        self.field = None
            elif name in VALID_PATTERNS:
                self.pattern_name = name
            elif name in ["VIX", "PCR", "MaxPain", "IVPercentile", "Delta", "Gamma", "Theta", "Vega", "BidAskSpread", "OIChange", "HourFilter", "DayFilter"]:
                self.special_name = name
                if params:
                    self.period = int(params) if params.isdigit() else params
        else:
            if expr in VALID_SPECIAL:
                self.special_name = expr

    @property
    def is_valid(self):
        if not self.timeframe or self.timeframe not in VALID_TIMEFRAMES:
            return False
        if not self.entity or self.entity not in VALID_ENTITIES:
            return False
        if self.indicator:
            return True
        if self.pattern_name:
            return True
        if self.special_name:
            return True
        return False

    @property
    def error(self):
        if not self.timeframe:
            return f"Invalid timeframe. Valid: {', '.join(VALID_TIMEFRAMES)}"
        if self.timeframe not in VALID_TIMEFRAMES:
            return f"Invalid timeframe '{self.timeframe}'. Valid: {', '.join(VALID_TIMEFRAMES)}"
        if not self.entity:
            return "Missing entity (Index/Opt). Format: TF/Entity: expression"
        if self.entity not in VALID_ENTITIES:
            return f"Invalid entity '{self.entity}'. Use 'Index' or 'Opt'"
        if not (self.indicator or self.pattern_name or self.special_name):
            return "No valid indicator, pattern, or special function detected"
        return None

    def __repr__(self):
        return f"Condition(tf={self.timeframe}, entity={self.entity}, ind={self.indicator}, field={self.field}, period={self.period}, op={self.operator}, val={self.compare_value}, pattern={self.pattern_name}, special={self.special_name})"

def parse_formula(formula_text):
    if not formula_text or not formula_text.strip():
        return None, "Empty formula"
    text = formula_text.strip()
    for combo in VALID_COMBINATORS:
        if f" {combo} " in text:
            parts = re.split(rf"\s+{combo}\s+", text, maxsplit=1)
            left_result, left_error = parse_formula(parts[0])
            right_result, right_error = parse_formula(parts[1])
            if left_error:
                return None, f"Left condition error: {left_error}"
            if right_error:
                return None, f"Right condition error: {right_error}"
            if left_result and right_result:
                return {"type": "combo", "operator": combo, "left": left_result, "right": right_result}, None
            return None, "Invalid combination"
    condition = Condition(text)
    if condition.is_valid:
        return {"type": "condition", "condition": condition}, None
    return None, condition.error

def validate_formula(formula_text):
    if not formula_text or not formula_text.strip():
        return False, "Formula is empty"
    result, error = parse_formula(formula_text)
    if error:
        return False, error
    if result["type"] == "condition" and not result["condition"].operator:
        return True, "Valid (no comparison operator — will evaluate as True/False)"
    return True, "Valid syntax"

def evaluate_formula_node(node, data_bundle, current_idx):
    if node["type"] == "combo":
        left_val, left_err = evaluate_formula_node(node["left"], data_bundle, current_idx)
        right_val, right_err = evaluate_formula_node(node["right"], data_bundle, current_idx)
        if left_err:
            return False, left_err
        if right_err:
            return False, right_err
        if node["operator"] == "AND":
            return left_val and right_val, None
        else:
            return left_val or right_val, None
    condition = node["condition"]
    tf_data = data_bundle.get(condition.timeframe)
    if tf_data is None:
        return False, f"No data for timeframe {condition.timeframe}"
    df = tf_data.get(condition.entity if condition.entity != "Index" else "index")
    if df is None:
        df = tf_data.get("index")
    if df is None or df.empty:
        return False, f"No data for {condition.entity} in {condition.timeframe} timeframe"
    if current_idx >= len(df):
        current_idx = len(df) - 1
    if condition.indicator:
        values = compute_indicator(condition, df)
        if values is None or len(values) == 0:
            return False, f"Could not compute {condition.indicator}"
        current_value = values.iloc[current_idx] if current_idx < len(values) else values.iloc[-1]
        if condition.operator and condition.compare_value is not None:
            compare_field_map = {
                "Open": "open", "High": "high", "Low": "low", "Close": "close",
                "Volume": "volume", "OI": "oi", "IV": "iv", "Spot": "spot",
            }
            if condition.compare_value in compare_field_map:
                col = compare_field_map[condition.compare_value]
                cv = float(df[col].iloc[current_idx]) if col in df.columns else None
            else:
                try:
                    cv = float(condition.compare_value)
                except ValueError:
                    return False, f"Invalid comparison value: {condition.compare_value}"
            if cv is None:
                return False, f"Field '{condition.compare_value}' not in data"
            if condition.operator == ">":
                return bool(current_value > cv), None
            elif condition.operator == ">=":
                return bool(current_value >= cv), None
            elif condition.operator == "<":
                return bool(current_value < cv), None
            elif condition.operator == "<=":
                return bool(current_value <= cv), None
            elif condition.operator == "==":
                return bool(current_value == cv), None
            elif condition.operator == "!=":
                return bool(current_value != cv), None
        return bool(current_value), None
    elif condition.pattern_name:
        return evaluate_pattern(condition, df, current_idx)
    elif condition.special_name:
        return evaluate_special(condition, df, current_idx, data_bundle)
    return False, "Unknown condition type"

def compute_indicator(condition, df):
    ind = condition.indicator.upper()
    field = condition.field if condition.field else "Close"
    period = condition.period if condition.period else 14
    series_map = {
        "Open": df["open"].astype(float),
        "High": df["high"].astype(float),
        "Low": df["low"].astype(float),
        "Close": df["close"].astype(float),
        "Volume": df["volume"].astype(float),
    }
    if "spot" in df.columns:
        series_map["Spot"] = df["spot"].astype(float)
    if "oi" in df.columns:
        series_map["OI"] = df["oi"].astype(float)
    if "iv" in df.columns:
        series_map["IV"] = df["iv"].astype(float)
    series = series_map.get(field) if field in series_map else df["close"].astype(float)
    if ind == "SMA":
        return sma(series, period)
    elif ind == "EMA":
        return ema(series, period)
    elif ind == "RSI":
        return rsi(series, period)
    elif ind == "MACD":
        macd_line, signal, hist = macd(series, 12, 26, 9)
        return macd_line
    elif ind == "BB":
        upper, middle, lower = bollinger_bands(series, period)
        return middle
    elif ind == "SUPERTREND":
        _, direction = supertrend(df, period, 3)
        return direction
    elif ind == "ADX":
        adx_line, _, _ = adx(df, period)
        return adx_line
    elif ind == "ATR":
        return atr(df, period)
    elif ind == "ROC":
        return roc(series, period)
    elif ind == "WILLIAMSR":
        return williams_r(df, period)
    elif ind == "STOCHK":
        return stoch_k(df, period)
    elif ind == "RETURN":
        return pct_return(df, period)
    elif ind == "POSITIVECANDLES":
        return positive_candles(df, period)
    elif ind == "NEGATIVECANDLES":
        return negative_candles(df, period)
    return None

def evaluate_pattern(condition, df, current_idx):
    pattern = condition.pattern_name.upper()
    if pattern == "DOJI":
        return bool(detect_doji(df).iloc[current_idx]), None
    elif pattern == "ENGULFING":
        val = detect_engulfing(df).iloc[current_idx]
        return bool(val != 0), None
    elif pattern == "HAMMER":
        return bool(detect_hammer(df).iloc[current_idx]), None
    elif pattern == "SHOOTINGSTAR":
        return bool(detect_shooting_star(df).iloc[current_idx]), None
    return False, f"Unknown pattern: {pattern}"

def evaluate_special(condition, df, current_idx, data_bundle):
    name = condition.special_name.upper()
    if name == "VIX":
        vix_data = data_bundle.get("vix")
        if vix_data is None:
            return False, "VIX data not available"
        if condition.operator and condition.compare_value:
            try:
                cv = float(condition.compare_value)
                if condition.operator == ">":
                    return vix_data["current"] > cv, None
                elif condition.operator == "<":
                    return vix_data["current"] < cv, None
            except ValueError:
                pass
        return bool(vix_data["current"]), None
    elif name == "PCR":
        pcr = data_bundle.get("pcr")
        if pcr is None:
            return False, "PCR data not available"
        if condition.operator and condition.compare_value:
            try:
                cv = float(condition.compare_value)
                if condition.operator == ">":
                    return pcr > cv, None
                elif condition.operator == "<":
                    return pcr < cv, None
            except ValueError:
                pass
        return bool(pcr), None
    elif name == "MAXPAIN":
        max_pain = data_bundle.get("max_pain")
        spot = data_bundle.get("spot")
        if max_pain is None or spot is None:
            return False, "MaxPain data not available"
        distance = abs(spot - max_pain)
        if condition.operator and condition.compare_value:
            try:
                cv = float(condition.compare_value)
                if condition.operator == ">":
                    return distance > cv, None
                elif condition.operator == "<":
                    return distance < cv, None
            except ValueError:
                pass
        return distance, None
    elif name == "IVPERCENTILE":
        iv_rank = data_bundle.get("iv_percentile")
        if iv_rank is None:
            return False, "IV percentile not available"
        if condition.operator and condition.compare_value:
            try:
                cv = float(condition.compare_value)
                if condition.operator == ">":
                    return iv_rank > cv, None
                elif condition.operator == "<":
                    return iv_rank < cv, None
            except ValueError:
                pass
        return iv_rank, None
    elif name in ["DELTA", "GAMMA", "THETA", "VEGA"]:
        greek_val = data_bundle.get(f"opt_{name.lower()}")
        if greek_val is None:
            return False, f"Option {name} not available"
        if condition.operator and condition.compare_value:
            try:
                cv = float(condition.compare_value)
                if condition.operator == ">":
                    return greek_val > cv, None
                elif condition.operator == "<":
                    return greek_val < cv, None
            except ValueError:
                pass
        return bool(greek_val), None
    elif name == "BIDASKSPREAD":
        spread = data_bundle.get("bid_ask_spread")
        if spread is None:
            return False, "Bid-ask spread not available"
        if condition.operator and condition.compare_value:
            try:
                cv = float(condition.compare_value)
                if condition.operator == ">":
                    return spread > cv, None
                elif condition.operator == "<":
                    return spread < cv, None
            except ValueError:
                pass
        return spread, None
    elif name == "OICHANGE":
        oi_change = data_bundle.get("oi_change")
        if oi_change is None:
            return False, "OI change not available"
        if condition.operator and condition.compare_value:
            try:
                cv = float(condition.compare_value)
                if condition.operator == ">":
                    return oi_change > cv, None
                elif condition.operator == "<":
                    return oi_change < cv, None
            except ValueError:
                pass
        return bool(oi_change), None
    elif name == "HOURFILTER":
        hour_filter = data_bundle.get("hour_filter")
        if hour_filter is None:
            return True, None
        return hour_filter, None
    elif name == "DAYFILTER":
        day_filter = data_bundle.get("day_filter")
        if day_filter is None:
            return True, None
        return day_filter, None
    return False, f"Unknown special: {name}"
