# This file uses ta-lib and requires installationg of both the python library and the c++ library : arch -arm64 brew install ta-lib

import json
import pandas as pd
import talib
from cache import cached
from nasdaq import fetch_historical_quotes
from utils import DAY_TTL


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
        df[col] = df[col].astype(str).str.replace(r"[\$,]", "", regex=True)
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # 'volume' is assumed to be numeric already and is left as is.

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
        "hist": float(hist[-1]) if hist.size > 0 else None
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
    """
    Analyze volume by returning the average volume over the period.
    """
    return float(df['volume'].mean())

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

@cached(ttl_seconds=DAY_TTL)
def fetch_technical_indicators(symbol, period=150):
    # Fetch and parse the historical quotes JSON from NASDAQ.
    historical_json = json.loads(fetch_historical_quotes(symbol, period))
    df = prepare_dataframe(historical_json, date_format="%m/%d/%Y")

    indicators = {
        "rsi": calculate_rsi(df, period=14),
        "macd": calculate_macd(df),
        "sma_20": calculate_sma(df, 20),
        "sma_50": calculate_sma(df, 50),
        "sma_100": calculate_sma(df, 100),
        "bollinger_bands": calculate_bollinger_bands(df),
        "volume_profile": analyze_volume(df),
        "ema_20": calculate_ema(df, period=20),
        "atr": calculate_atr(df, period=14),
        "adx": calculate_adx(df, period=14),
        "stochastic_14_3_3": calculate_stochastic(df),
        "cci": calculate_cci(df, period=20)
    }
    indicators = round_numbers(indicators)
    return indicators

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
    print(f"Technical indicators for {symbol}:")
    print(json.dumps(indicators, indent=2))
