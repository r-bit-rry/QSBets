# This file uses ta-lib and requires installationg of both the python library and the c++ library : arch -arm64 brew install ta-lib

import json
import pandas as pd
import talib
from storage.cache import cached, DAY_TTL
from collectors.nasdaq import fetch_historical_quotes
from logger import get_logger

logger = get_logger(__name__)

def prepare_dataframe(historical_json, date_format="%m/%d/%Y"):
    """
    Convert historical JSON data to a DataFrame with a datetime index and ensures
    numeric columns ('close', 'open', 'high', 'low') are converted to double precision.
    Any leading '$' characters in these values will be removed.
    The 'volume' column is assumed to already be numeric.
    """
    # Convert the JSON dictionary to a DataFrame (keys as rows)
    df = pd.DataFrame.from_dict(historical_json, orient="index")

    # For each numeric price column, remove leading '$' if present, then convert to float64.
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # Convert index to datetime using the provided format and sort the DataFrame by index.
    df.index = pd.to_datetime(df.index, format=date_format)
    df = df.sort_index()

    return df


def calculate_rsi(df, period=14):
    """
    Calculate the RSI of the 'close' price series.
    Returns the latest RSI value.
    """
    rsi = talib.RSI(df['close'].values, timeperiod=period)
    return float(rsi[-1]) if rsi.size > 0 else None

def calculate_macd(df):
    """
    Calculate MACD from the 'close' price series.
    Returns a dict with the latest MACD, signal, and histogram values.
    """
    macd, signal, hist = talib.MACD(df['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
    return {
        "macd": float(macd[-1]) if macd.size > 0 else None,
        "signal": float(signal[-1]) if signal.size > 0 else None,
        "hist": float(hist[-1]) if hist.size > 0 else None,
        "hist_prev": float(hist[-2]) if hist.size > 1 else None,
        "macd_trend": "up" if macd.size > 1 and macd[-1] > macd[-2] else "down",
    }


def find_support_resistance(df, lookback=30):
    """Find potential support and resistance levels"""
    supports = []
    resistances = []

    # Find recent local minima and maxima
    for i in range(5, min(lookback, len(df) - 1)):
        # Local minimum (support)
        if df["low"].iloc[-i - 1] > df["low"].iloc[-i] < df["low"].iloc[-i + 1]:
            supports.append(float(df["low"].iloc[-i]))
        # Local maximum (resistance)
        if df["high"].iloc[-i - 1] < df["high"].iloc[-i] > df["high"].iloc[-i + 1]:
            resistances.append(float(df["high"].iloc[-i]))

    # Return only the most recent levels (up to 3)
    return {
        "supports": sorted(supports)[:3],
        "resistances": sorted(resistances, reverse=True)[:3],
    }


def calculate_sma(df, period):
    """
    Calculate SMA for given period.
    Returns the latest SMA value.
    """
    sma = talib.SMA(df['close'].values, timeperiod=period)
    return float(sma[-1]) if sma.size > 0 else None

def calculate_bollinger_bands(df, period=20, nbdevup=2, nbdevdn=2):
    """
    Calculate Bollinger Bands.
    Returns a dict with the latest upper, middle, and lower band values.
    """
    upper, middle, lower = talib.BBANDS(df['close'].values, timeperiod=period, nbdevup=nbdevup, nbdevdn=nbdevdn, matype=0)
    return {
        "upper": float(upper[-1]) if upper.size > 0 else None,
        "middle": float(middle[-1]) if middle.size > 0 else None,
        "lower": float(lower[-1]) if lower.size > 0 else None
    }


def analyze_volume(df):
    if df.empty or len(df) == 0:
        # Return default values for empty DataFrames
        return {
            "avg_volume": 0,
            "recent_volume": 0,
            "relative_volume": 0,
            "volume_trend": "flat",
        }

    avg_volume = float(df["volume"].mean())
    recent_volume = float(df["volume"].iloc[-1])

    # Check if we have enough data points for trend analysis
    volume_trend = "flat"
    if len(df) >= 5:
        volume_trend = (
            "increasing"
            if df["volume"].iloc[-5:].is_monotonic_increasing
            else (
                "decreasing"
                if df["volume"].iloc[-5:].is_monotonic_decreasing
                else "flat"
            )
        )

    return {
        "avg_volume": avg_volume,
        "recent_volume": recent_volume,
        "relative_volume": (
            round(recent_volume / avg_volume, 2) if avg_volume > 0 else 0
        ),
        "volume_trend": volume_trend,
    }


def calculate_ema(df, period=20):
    """
    Calculate Exponential Moving Average (EMA) for a given period.
    Returns the latest EMA value.
    """
    ema = talib.EMA(df['close'].values, timeperiod=period)
    return float(ema[-1]) if ema.size > 0 else None

def calculate_atr(df, period=14):
    """
    Calculate the Average True Range (ATR) for a given period.
    Returns the latest ATR value.
    """
    atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=period)
    return float(atr[-1]) if atr.size > 0 else None

def calculate_adx(df, period=14):
    """
    Calculate the Average Directional Index (ADX) for a given period.
    Returns the latest ADX value.
    """
    adx = talib.ADX(df['high'].values, df['low'].values, df['close'].values, timeperiod=period)
    return float(adx[-1]) if adx.size > 0 else None

def calculate_stochastic(df, k_period=14, slowk_period=3, d_period=3):
    """
    Calculate the Stochastic Oscillator.
    Returns a dict with the latest %K and %D values.
    """
    slowk, slowd = talib.STOCH(
        df['high'].values,
        df['low'].values,
        df['close'].values,
        fastk_period=k_period,
        slowk_period=slowk_period,
        slowk_matype=0,
        slowd_period=d_period,
        slowd_matype=0
    )
    return {
        "stochastic_k": float(slowk[-1]) if slowk.size > 0 else None,
        "stochastic_d": float(slowd[-1]) if slowd.size > 0 else None,
    }

def calculate_cci(df, period=20):
    """
    Calculate Commodity Channel Index (CCI) for a given period.
    Returns the latest CCI value.
    """
    cci = talib.CCI(df['high'].values, df['low'].values, df['close'].values, timeperiod=period)
    return float(cci[-1]) if cci.size > 0 else None

def safe_get_last_item(value):
    """Safely get the last item of a list if it's a list and has items, otherwise return the value itself."""
    if isinstance(value, list) and value:
        return value[-1]
    return value

@cached(ttl_seconds=DAY_TTL)
def fetch_technical_indicators(symbol, period=150, days=30):
    # Fetch and parse the historical quotes JSON from NASDAQ.
    historical_data = fetch_historical_quotes(symbol, period)
    df = prepare_dataframe(historical_data, date_format="%m/%d/%Y")
    
    # Safety checks
    if df.empty or len(df) < 20:  # Need minimum data for reliable indicators
        return {}
    
    # Ensure days doesn't exceed available data and we have enough data for calculations
    days = min(days, len(df))
    
    min_data_needed = 100  # Ensure enough data for SMA100
    start_idx = max(min_data_needed, len(df) - days)
    end_idx = len(df) + 1
    
    indicators = {
        "rsi": [calculate_rsi(df.iloc[:i], period=14) for i in range(start_idx, end_idx)],
        "macd": [calculate_macd(df.iloc[:i]) for i in range(start_idx, end_idx)],
        "sma_20": [calculate_sma(df.iloc[:i], 20) for i in range(start_idx, end_idx)],
        "sma_50": [calculate_sma(df.iloc[:i], 50) for i in range(start_idx, end_idx)],
        "sma_100": [calculate_sma(df.iloc[:i], 100) for i in range(start_idx, end_idx)],
        "bollinger_bands": [calculate_bollinger_bands(df.iloc[:i]) for i in range(start_idx, end_idx)],
        "volume_profile": [analyze_volume(df.iloc[:i]) for i in range(start_idx, end_idx)],
        "ema_20": [calculate_ema(df.iloc[:i], period=20) for i in range(start_idx, end_idx)],
        "atr": [calculate_atr(df.iloc[:i], period=14) for i in range(start_idx, end_idx)],
        "adx": [calculate_adx(df.iloc[:i], period=14) for i in range(start_idx, end_idx)],
        "stochastic_14_3_3": [calculate_stochastic(df.iloc[:i]) for i in range(start_idx, end_idx)],
        "cci": [calculate_cci(df.iloc[:i], period=20) for i in range(start_idx, end_idx)],
        "support_resistance": [find_support_resistance(df.iloc[:i]) for i in range(start_idx, end_idx)]
    }

    indicators = round_numbers(indicators)
    return {k: (safe_get_last_item(v) if days == 1 else v) for k, v in indicators.items()}

def round_numbers(obj):
    if isinstance(obj, (int, float)):
        return round(obj, 2)
    elif isinstance(obj, dict):
        return {k: round_numbers(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [round_numbers(x) for x in obj]
    else:
        return obj


if __name__ == "__main__":
    symbol = "LPTH"
    indicators = fetch_technical_indicators(symbol)
    logger.debug(f"Technical indicators for {symbol}:")
    print(json.dumps(indicators, indent=2))
