import numpy as np
import pandas as pd

def sma(series, period):
    return series.rolling(window=period).mean()

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(series, period=20, std_dev=2):
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower

def supertrend(df, period=10, multiplier=3):
    hl2 = (df["high"] + df["low"]) / 2
    atr = hl2.rolling(window=period).apply(
        lambda x: (x[-1] - x[0]) if len(x) > 0 else 0, raw=True
    )
    atr = atr.fillna(method="bfill")
    src = hl2
    upper_band = src + (multiplier * atr)
    lower_band = src - (multiplier * atr)
    supertrend_values = pd.Series(np.nan, index=df.index)
    direction = pd.Series(1, index=df.index)
    for i in range(period, len(df)):
        if df["close"].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
        if direction.iloc[i] == 1:
            supertrend_values.iloc[i] = lower_band.iloc[i]
        else:
            supertrend_values.iloc[i] = upper_band.iloc[i]
    return supertrend_values, direction

def adx(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    up_move = high - high.shift()
    down_move = low.shift() - low
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index)
    plus_di = 100 * (plus_dm.rolling(window=period).sum() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(window=period).sum() / atr.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx_line = dx.rolling(window=period).mean()
    return adx_line, plus_di, minus_di

def atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def roc(series, period=10):
    return ((series - series.shift(period)) / series.shift(period).replace(0, np.nan)) * 100

def williams_r(df, period=14):
    highest_high = df["high"].rolling(window=period).max()
    lowest_low = df["low"].rolling(window=period).min()
    return -100 * ((highest_high - df["close"]) / (highest_high - lowest_low).replace(0, np.nan))

def stoch_k(df, period=14):
    lowest_low = df["low"].rolling(window=period).min()
    highest_high = df["high"].rolling(window=period).max()
    return 100 * ((df["close"] - lowest_low) / (highest_high - lowest_low).replace(0, np.nan))

def ichimoku(df):
    high, low, close = df["high"], df["low"], df["close"]
    nine_high = high.rolling(window=9).max()
    nine_low = low.rolling(window=9).min()
    tenkan = (nine_high + nine_low) / 2
    twentysix_high = high.rolling(window=26).max()
    twentysix_low = low.rolling(window=26).min()
    kijun = (twentysix_high + twentysix_low) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    fiftytwo_high = high.rolling(window=52).max()
    fiftytwo_low = low.rolling(window=52).min()
    senkou_b = ((fiftytwo_high + fiftytwo_low) / 2).shift(26)
    chikou = close.shift(-26)
    return tenkan, kijun, senkou_a, senkou_b, chikou

def heikin_ashi(df):
    ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ha_open = (df["open"].shift(1) + df["close"].shift(1)) / 2
    ha_open.iloc[0] = df["open"].iloc[0]
    ha_high = pd.concat([df["high"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["low"], ha_open, ha_close], axis=1).min(axis=1)
    return ha_open, ha_high, ha_low, ha_close

def detect_doji(df, body_pct=0.1):
    body = abs(df["close"] - df["open"])
    range_candle = df["high"] - df["low"]
    return body <= (range_candle * body_pct)

def detect_engulfing(df):
    bullish = (df["close"] > df["open"]) & (df["open"].shift(1) > df["close"].shift(1))
    bearish = (df["close"] < df["open"]) & (df["open"].shift(1) < df["close"].shift(1))
    bullish = bullish & (df["close"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1))
    bearish = bearish & (df["close"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1))
    return pd.Series(np.where(bullish, 1, np.where(bearish, -1, 0)), index=df.index)

def detect_hammer(df, body_pct=0.3, wick_pct=2.0):
    body = abs(df["close"] - df["open"])
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    return (lower_wick >= body * wick_pct) & (upper_wick <= body * 0.3) & (body > 0)

def detect_shooting_star(df, body_pct=0.3, wick_pct=2.0):
    body = abs(df["close"] - df["open"])
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    return (upper_wick >= body * wick_pct) & (lower_wick <= body * 0.3) & (body > 0)

def positive_candles(df, n):
    return (df["close"] > df["open"]).rolling(window=n).sum()

def negative_candles(df, n):
    return (df["close"] < df["open"]).rolling(window=n).sum()

def pct_return(df, n):
    return ((df["close"] - df["close"].shift(n)) / df["close"].shift(n).replace(0, np.nan)) * 100
