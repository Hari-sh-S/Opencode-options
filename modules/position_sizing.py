import math

NIFTY_LOT_SIZE = 50

def fixed_lot(lots=1):
    return NIFTY_LOT_SIZE * lots

def volatility_based(capital, risk_per_trade_pct, option_price, atr_value=None, vix=None):
    risk_amount = capital * (risk_per_trade_pct / 100)
    if vix and vix > 0:
        vol_factor = vix / 100
        risk_amount = risk_amount * (1 / vol_factor)
    quantity = risk_amount / option_price if option_price > 0 else 0
    lots = max(1, round(quantity / NIFTY_LOT_SIZE))
    return lots * NIFTY_LOT_SIZE

def full_capital_allocation(capital, option_price, max_risk_pct=100):
    if option_price <= 0:
        return 0
    max_capital = capital * (max_risk_pct / 100)
    quantity = max_capital / option_price
    lots = math.floor(quantity / NIFTY_LOT_SIZE)
    return max(0, lots * NIFTY_LOT_SIZE)

def kelly_criterion(capital, win_rate, avg_win, avg_loss, option_price):
    if avg_loss <= 0:
        return 0
    if win_rate <= 0 or win_rate >= 1:
        return 0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    kelly_pct = (p * b - q) / b
    kelly_pct = max(0, min(kelly_pct, 0.25))
    risk_capital = capital * kelly_pct
    if option_price <= 0:
        return 0
    quantity = risk_capital / option_price
    lots = math.floor(quantity / NIFTY_LOT_SIZE)
    return max(0, lots * NIFTY_LOT_SIZE)

def calculate_position_size(method, capital, option_price, **kwargs):
    if method == "Fixed Lot":
        lots = kwargs.get("lots", 1)
        return fixed_lot(lots)
    elif method == "Volatility Based":
        return volatility_based(
            capital,
            kwargs.get("risk_per_trade_pct", 2),
            option_price,
            kwargs.get("atr_value"),
            kwargs.get("vix"),
        )
    elif method == "Full Capital":
        return full_capital_allocation(capital, option_price, kwargs.get("max_risk_pct", 100))
    elif method == "Kelly Criterion":
        return kelly_criterion(
            capital,
            kwargs.get("win_rate", 0.5),
            kwargs.get("avg_win", 0),
            kwargs.get("avg_loss", 0),
            option_price,
        )
    return 0
