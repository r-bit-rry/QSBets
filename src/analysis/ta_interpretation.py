"""Technical Analysis Interpretation Module

This module provides comprehensive analysis and interpretation of technical indicators,
including candlestick patterns, structured for efficient LLM comprehension and decision making.
"""

import os
from typing import Dict, List, Optional, Union, Any, Tuple, cast
from dataclasses import dataclass
from datetime import datetime
from logger import get_logger

logger = get_logger(__name__)

# Configurable minimum history days
MIN_HISTORY_DAYS = int(os.getenv('MIN_HISTORY_DAYS', '150'))

@dataclass
class IndicatorSummary:
    """Structured summary of a single technical indicator"""
    name: str
    value: Union[float, Dict[str, Any]]
    interpretation: str
    signal_type: str  # "bullish", "bearish", "neutral" 
    signal_strength: int  # 0-3 (0=weak, 3=strong)
    confidence: float  # 0-1

@dataclass
class ComprehensiveSummary:
    """Complete technical analysis summary"""
    price_action: Dict[str, float]
    trend_indicators: List[IndicatorSummary]
    momentum_indicators: List[IndicatorSummary]
    volume_analysis: IndicatorSummary
    volatility_metrics: IndicatorSummary
    support_resistance: Dict[str, Any]  # Updated to include pattern confluence
    candlestick_patterns: Dict[str, Any]  # New field for candlestick patterns
    overall_signal: str
    signal_strength: int
    key_levels: Dict[str, Optional[float]]
    risk_metrics: Dict[str, Union[float, str]]
    ma_crosses: Dict[str, str]  # New field for MA crossovers

def get_candlestick_patterns(summary: ComprehensiveSummary) -> Dict[str, Any]:
    """Extract valid candlestick patterns from technical summary"""
    patterns = {}
    try:
        # First check if attribute exists and is a dict
        if not hasattr(summary, 'candlestick_patterns'):
            return patterns

        # Safely get the patterns dictionary
        candlestick_patterns = getattr(summary, 'candlestick_patterns', {})
        if not isinstance(candlestick_patterns, dict):
            return patterns

        # Use dict.items() safely with additional checks
        for key in ('engulfing', 'doji', 'hammer', 'star', 'harami'):
            try:
                pattern = candlestick_patterns.get(key)
                if isinstance(pattern, dict) and pattern.get('signal') in ['bullish', 'bearish']:
                    patterns[key] = pattern
            except (AttributeError, TypeError):
                continue
    except (AttributeError, TypeError) as e:
        logger.debug(f"Error processing candlestick patterns: {e}")
        
    return patterns

def validate_historical_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, bool]]:
    """Validate historical data and return availability for different indicators
    
    Returns:
        Tuple containing:
        - bool: True if enough data for core indicators (20-day lookback)
        - Dict[str, bool]: Indicator availability map
    """
    quotes = data.get('historical_quotes', {})
    quote_count = len(quotes)
    
    # Define minimum days needed for each indicator
    requirements = {
        'sma_20': 20,
        'sma_50': 50,
        'sma_100': 100,
        'macd': 26,  # MACD default is 12,26,9
        'rsi': 14,
        'bollinger': 20,
        'adx': 14,
        'stoch': 14,
        'volume_ma': 20
    }
    
    # Check which indicators can be calculated
    availability = {
        name: quote_count >= days
        for name, days in requirements.items()
    }
    
    # Log availability
    if quote_count < MIN_HISTORY_DAYS:
        available = [name for name, can_use in availability.items() if can_use]
        unavailable = [name for name, can_use in availability.items() if not can_use]
        logger.warning(
            f"Limited historical data: {quote_count} days. "
            f"Available indicators: {', '.join(available)}. "
            f"Unavailable: {', '.join(unavailable)}"
        )
    
    # Return True if we have at least enough data for core indicators (20-day)
    return quote_count >= 20, availability

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def interpret_rsi(rsi: Optional[float]) -> Dict[str, Any]:
    """Interpret RSI value"""
    rsi_value = safe_float(rsi)
    if rsi is None or rsi_value == 0:
        return {"status": "unknown", "strength": 0, "description": "No RSI data available"}
    
    if rsi_value > 70:
        return {"status": "overbought", "strength": 2, "description": f"RSI at {rsi_value:.2f} indicates overbought conditions"}
    elif rsi_value < 30:
        return {"status": "oversold", "strength": 2, "description": f"RSI at {rsi_value:.2f} indicates oversold conditions"}
    elif rsi_value > 60:
        return {"status": "bullish", "strength": 1, "description": f"RSI at {rsi_value:.2f} shows bullish momentum"}
    elif rsi_value < 40:
        return {"status": "bearish", "strength": 1, "description": f"RSI at {rsi_value:.2f} shows bearish momentum"}
    else:
        return {"status": "neutral", "strength": 0, "description": f"RSI at {rsi_value:.2f} is neutral"}

def interpret_macd(macd_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Interpret MACD values"""
    if not macd_data:
        return {"status": "unknown", "strength": 0, "description": "No MACD data available"}
    
    macd_value = safe_float(macd_data.get('macd'))
    signal = safe_float(macd_data.get('signal'))
    hist = safe_float(macd_data.get('hist'))
    hist_prev = safe_float(macd_data.get('hist_prev'))
    
    if macd_value > signal and hist > 0:
        if hist > hist_prev:
            return {"status": "bullish", "strength": 2, "description": f"MACD ({macd_value:.2f}) above signal line with increasing histogram"}
        return {"status": "bullish", "strength": 1, "description": f"MACD ({macd_value:.2f}) above signal line"}
    elif macd_value < signal and hist < 0:
        if hist < hist_prev:
            return {"status": "bearish", "strength": 2, "description": f"MACD ({macd_value:.2f}) below signal line with decreasing histogram"}
        return {"status": "bearish", "strength": 1, "description": f"MACD ({macd_value:.2f}) below signal line"}
    else:
        return {"status": "neutral", "strength": 0, "description": f"MACD ({macd_value:.2f}) showing mixed signals"}

def interpret_moving_averages(price: float, sma_20: Optional[float], sma_50: Optional[float], sma_100: Optional[float]) -> List[Dict[str, Any]]:
    """Analyze moving averages"""
    results = []
    
    sma_20_val = safe_float(sma_20)
    sma_50_val = safe_float(sma_50)
    sma_100_val = safe_float(sma_100)
    
    if sma_20_val > 0:
        if price > sma_20_val:
            results.append({"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above SMA20 (${sma_20_val:.2f})"})
        else:
            results.append({"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below SMA20 (${sma_20_val:.2f})"})
        
    if sma_50_val > 0:
        if price > sma_50_val:
            results.append({"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above SMA50 (${sma_50_val:.2f})"})
        else:
            results.append({"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below SMA50 (${sma_50_val:.2f})"})
        
    if sma_100_val > 0:
        if price > sma_100_val:
            results.append({"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above SMA100 (${sma_100_val:.2f})"})
        else:
            results.append({"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below SMA100 (${sma_100_val:.2f})"})
    
    # Check moving average alignment
    if all(x > 0 for x in [sma_20_val, sma_50_val, sma_100_val]):
        if sma_20_val > sma_50_val > sma_100_val:
            results.append({"status": "bullish", "strength": 2, "description": "Strong uptrend with SMA20 > SMA50 > SMA100"})
        elif sma_20_val < sma_50_val < sma_100_val:
            results.append({"status": "bearish", "strength": 2, "description": "Strong downtrend with SMA100 > SMA50 > SMA20"})
    
    return results if results else [{"status": "unknown", "strength": 0, "description": "Insufficient moving average data"}]

def interpret_bollinger_bands(price: float, bb_data: Optional[Dict[str, float]]) -> Dict[str, Any]:
    """Interpret Bollinger Bands"""
    if not bb_data:
        return {"status": "unknown", "strength": 0, "description": "No Bollinger Bands data"}
        
    # Get BB values safely
    bb_upper = bb_data.get('upper') if bb_data else None
    bb_lower = bb_data.get('lower') if bb_data else None
    bb_middle = bb_data.get('middle') if bb_data else None
    
    # Convert to floats after getting the values
    upper_val = safe_float(bb_upper)
    lower_val = safe_float(bb_lower)
    middle_val = safe_float(bb_middle)
    
    if upper_val > 0 and lower_val > 0 and middle_val > 0:
        if price > upper_val:
            return {"status": "overbought", "strength": 2, "description": f"Price (${price:.2f}) above upper Bollinger Band (${upper_val:.2f})"}
        elif price < lower_val:
            return {"status": "oversold", "strength": 2, "description": f"Price (${price:.2f}) below lower Bollinger Band (${lower_val:.2f})"}
        elif price > middle_val:
            return {"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above BB middle band"}
        else:
            return {"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below BB middle band"}
    
    return {"status": "unknown", "strength": 0, "description": "Incomplete Bollinger Bands data"}

def interpret_adx(adx: Optional[float]) -> Dict[str, Any]:
    """Interpret ADX (Average Directional Index)"""
    adx_value = safe_float(adx)
    if adx_value == 0:
        return {"status": "unknown", "strength": 0, "description": "No ADX data available"}
    
    if adx_value > 40:
        return {"status": "strong_trend", "strength": 3, "description": f"ADX at {adx_value:.2f} indicates very strong trend"}
    elif adx_value > 25:
        return {"status": "trending", "strength": 2, "description": f"ADX at {adx_value:.2f} indicates trending market"}
    elif adx_value > 20:
        return {"status": "weak_trend", "strength": 1, "description": f"ADX at {adx_value:.2f} indicates beginning trend"}
    else:
        return {"status": "no_trend", "strength": 0, "description": f"ADX at {adx_value:.2f} indicates ranging market"}

def interpret_insider_activity(insider_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze insider trading activity"""
    if not insider_data:
        return {"status": "unknown", "strength": 0, "description": "No insider trading data"}
    
    net_3m = safe_float(insider_data.get('net_insider_activity_3m', 0))
    net_12m = safe_float(insider_data.get('net_insider_activity_12m', 0))
    recent = insider_data.get('recent_transactions', [])
    
    buys = sum(1 for tx in recent if tx.get('transactionType') == 'Buy')
    sells = sum(1 for tx in recent if tx.get('transactionType') == 'Sell')
    
    if sells > buys and sells >= 3:
        return {
            "status": "bearish",
            "strength": 2 if abs(net_3m) > 1000000 else 1,
            "description": f"Significant insider selling: {sells} sells vs {buys} buys in recent transactions"
        }
    elif buys > sells and buys >= 3:
        return {
            "status": "bullish",
            "strength": 2 if abs(net_3m) > 1000000 else 1,
            "description": f"Significant insider buying: {buys} buys vs {sells} sells in recent transactions"
        }
    
    return {
        "status": "neutral",
        "strength": 0,
        "description": f"Balanced insider activity: {buys} buys vs {sells} sells"
    }

def interpret_institutional_holdings(holdings_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze institutional ownership patterns"""
    if not holdings_data or 'ownership_summary' not in holdings_data:
        return {"status": "unknown", "strength": 0, "description": "No institutional holdings data"}
    
    ownership = holdings_data.get('ownership_summary', {})
    transactions = holdings_data.get('key_transactions', [])
    
    inst_ownership = None
    for key, value in ownership.items():
        if 'institutional' in key.lower():
            inst_ownership = safe_float(value)
            break
    
    if inst_ownership is None:
        return {"status": "unknown", "strength": 0, "description": "Cannot determine institutional ownership level"}
    
    # Count recent institutional activity
    increases = sum(1 for tx in transactions if safe_float(tx.get('sharesChange', 0)) > 0)
    decreases = sum(1 for tx in transactions if safe_float(tx.get('sharesChange', 0)) < 0)
    
    status = "high_ownership" if inst_ownership > 0.7 else "moderate_ownership" if inst_ownership > 0.4 else "low_ownership"
    activity = "accumulating" if increases > decreases else "distributing" if decreases > increases else "neutral"
    
    return {
        "status": status,
        "strength": 2 if abs(increases - decreases) >= 3 else 1,
        "description": f"Institutional ownership at {inst_ownership*100:.1f}% with {activity} activity"
    }

def generate_preliminary_rating(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a preliminary rating based on technical and fundamental factors"""
    has_core_data, indicator_availability = validate_historical_data(data)
    if not has_core_data:
        return {"rating": 0, "confidence": 0, "explanations": ["Insufficient data for core indicators"]}
    
    technical_score = 0
    fundamental_score = 0
    explanations = []
    
    # Technical Analysis (70% weight)
    if "technical_summary" in data:
        ta_summary = data["technical_summary"]
        if isinstance(ta_summary, ComprehensiveSummary):
            # Calculate technical score based on trend and momentum
            trend_confidence = sum(ind.confidence for ind in ta_summary.trend_indicators) / len(ta_summary.trend_indicators)
            momentum_confidence = sum(ind.confidence for ind in ta_summary.momentum_indicators) / len(ta_summary.momentum_indicators)
            technical_score = (trend_confidence + momentum_confidence) * 50  # Same as technical rating
            explanations.append(f"Technical analysis suggests {ta_summary.overall_signal} trend (Score: {technical_score:.0f})")
    
    # Fundamental Analysis (30% weight)
    inst_analysis = interpret_institutional_holdings(data.get('institutional_holdings', {}))
    insider_analysis = interpret_insider_activity(data.get('insider_trading', {}))
    
    if inst_analysis['status'] != "unknown":
        if "high_ownership" in inst_analysis['status']:
            fundamental_score += 15
        elif "moderate_ownership" in inst_analysis['status']:
            fundamental_score += 10
        explanations.append(inst_analysis['description'])
    
    if insider_analysis['status'] == "bullish":
        fundamental_score += 15
    elif insider_analysis['status'] == "bearish":
        fundamental_score -= 10
    explanations.append(insider_analysis['description'])
    
    total_score = min(100, max(0, technical_score + fundamental_score))
    confidence = 7 + (len(explanations) / 5)  # Base confidence + bonus for more signals
    
    return {
        "rating": total_score,
        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
        "confidence": min(10, confidence),
        "explanations": explanations
    }

def generate_entry_exit_strategy(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generate entry and exit strategies based on technical analysis"""
    has_core_data, indicator_availability = validate_historical_data(data)
    if not has_core_data:
        return ({"error": "Insufficient data for core indicators"}, {"error": "Insufficient data for core indicators"})
    
    entry_strategy = {}
    exit_strategy = {}
    current_price = 0
    
    # Get current price from historical quotes
    quotes = data.get('historical_quotes', {})
    if quotes:
        latest_quote = next(iter(quotes.values()))
        current_price = safe_float(latest_quote.get('close'))
    
    if "technical_summary" in data:
        ta_summary = data["technical_summary"]
        if isinstance(ta_summary, (dict, ComprehensiveSummary)):
            signal_strength = ta_summary.signal_strength if isinstance(ta_summary, ComprehensiveSummary) else ta_summary.get('signal_strength', 0)
            overall_signal = ta_summary.overall_signal if isinstance(ta_summary, ComprehensiveSummary) else ta_summary.get('overall_signal', 'neutral')
            
            # Entry strategy
            entry_strategy = {
                "entry_price": current_price,
                "entry_timing": "Immediate" if signal_strength >= 2 else "Staged",
                "technical_indicators": []
            }
            
            # Collect technical indicators
            if isinstance(ta_summary, ComprehensiveSummary):
                indicators = [ind.interpretation for ind in ta_summary.trend_indicators + ta_summary.momentum_indicators
                            if ind.signal_type == ta_summary.overall_signal]
            else:
                indicators = [ind['interpretation'] for indicators in (ta_summary.get('trend_indicators', []) + ta_summary.get('momentum_indicators', []))
                            for ind in [indicators] if ind.get('signal_type') == overall_signal]
            
            entry_strategy["technical_indicators"] = indicators
            
            # Exit strategy
            if isinstance(ta_summary, ComprehensiveSummary):
                volatility_metrics = ta_summary.volatility_metrics.value
                if isinstance(volatility_metrics, dict):
                    atr = safe_float(volatility_metrics.get('atr', 0))
                    volatility_pct = safe_float(ta_summary.risk_metrics.get('volatility_percent', 0))
                    
                    exit_strategy = {
                        "profit_target": current_price * 1.15,  # 15% target
                        "stop_loss": current_price - (2 * atr) if atr else current_price * 0.92,
                        "time_horizon": "Short-term" if volatility_pct > 5 else "Medium-term",
                        "exit_conditions": [
                            f"Price drops below {current_price * 0.92:.2f} (8% loss)",
                            f"Technical indicators reverse to {overall_signal}"
                        ]
                    }
            else:
                volatility_metrics = ta_summary.get('volatility_metrics', {}).get('value', {})
                risk_metrics = ta_summary.get('risk_metrics', {})
                atr = safe_float(volatility_metrics.get('atr', 0))
                volatility_pct = safe_float(risk_metrics.get('volatility_percent', 0))
                
                exit_strategy = {
                    "profit_target": current_price * 1.15,
                    "stop_loss": current_price - (2 * atr) if atr else current_price * 0.92,
                    "time_horizon": "Short-term" if volatility_pct > 5 else "Medium-term",
                    "exit_conditions": [
                        f"Price drops below {current_price * 0.92:.2f} (8% loss)",
                        f"Technical indicators reverse to {overall_signal}"
                    ]
                }
    
    return entry_strategy, exit_strategy

def generate_comprehensive_summary(stock_data: Dict[str, Any]) -> ComprehensiveSummary:
    """Generate comprehensive technical analysis summary using available indicators"""
    has_core_data, indicator_availability = validate_historical_data(stock_data)
    if not has_core_data:
        raise ValueError("Insufficient data for core indicators (minimum 20 days required)")
        
    indicators = stock_data.get('technical_indicators', {})
    if not indicators:
        raise ValueError("No technical indicators data available")
        
    price_data = stock_data.get('historical_quotes', {})
    prices = list(price_data.values())
    if len(prices) < 2:
        raise ValueError("At least 2 days of price history required")
        
    current_price = float(prices[0]['close'])
    prev_price = float(prices[1]['close'])
    
    # Price action summary
    price_action = {
        "current_price": current_price,
        "daily_change": round(current_price - prev_price, 2),
        "daily_change_percent": round((current_price / prev_price - 1) * 100, 2),
        "weekly_high": max(float(x['high']) for x in prices[:5]),
        "weekly_low": min(float(x['low']) for x in prices[:5])
    }
    
    # Technical indicators
    trend_indicators = []
    momentum_indicators = []
    
    # Moving Averages - use what's available
    sma_20 = safe_float(indicators.get('sma_20')) if indicator_availability.get('sma_20') else None
    sma_50 = safe_float(indicators.get('sma_50')) if indicator_availability.get('sma_50') else None
    sma_100 = safe_float(indicators.get('sma_100')) if indicator_availability.get('sma_100') else None
    
    ma_analysis = interpret_moving_averages(current_price, sma_20, sma_50, sma_100)
    
    trend_indicators.append(
        IndicatorSummary(
            name="Moving Averages",
            value={
                "sma20": sma_20,
                "sma50": sma_50,
                "sma100": sma_100
            },
            interpretation=ma_analysis[0]['description'],
            signal_type=ma_analysis[0]['status'],
            signal_strength=ma_analysis[0]['strength'],
            confidence=0.8
        )
    )
    
    # ADX
    adx_value = safe_float(indicators.get('adx'))
    adx_analysis = interpret_adx(adx_value if adx_value > 0 else None)
    trend_indicators.append(
        IndicatorSummary(
            name="ADX",
            value=adx_value,
            interpretation=adx_analysis['description'],
            signal_type=adx_analysis['status'],
            signal_strength=adx_analysis['strength'],
            confidence=0.9
        )
    )
    
    # MACD - only if available (needs 26 days)
    if indicator_availability.get('macd'):
        macd_data = indicators.get('macd', {})
        if isinstance(macd_data, dict) and macd_data:
            macd_analysis = interpret_macd(macd_data)
            momentum_indicators.append(
                IndicatorSummary(
                    name="MACD",
                    value=macd_data,
                    interpretation=macd_analysis['description'],
                    signal_type=macd_analysis['status'],
                    signal_strength=macd_analysis['strength'],
                    confidence=0.85
                )
            )
    
    # RSI
    rsi_value = safe_float(indicators.get('rsi'))
    rsi_analysis = interpret_rsi(rsi_value if rsi_value > 0 else None)
    momentum_indicators.append(
        IndicatorSummary(
            name="RSI",
            value=rsi_value,
            interpretation=rsi_analysis['description'],
            signal_type=rsi_analysis['status'],
            signal_strength=rsi_analysis['strength'],
            confidence=0.9
        )
    )
    
    # Volume analysis
    volume_data = indicators.get('volume_profile', {})
    volume_analysis = IndicatorSummary(
        name="Volume",
        value=volume_data,
        interpretation=f"Volume {volume_data.get('volume_trend', 'unknown')} with {volume_data.get('relative_volume', 1)}x relative volume",
        signal_type="bullish" if safe_float(volume_data.get('relative_volume', 1)) > 1.5 else "neutral",
        signal_strength=2 if safe_float(volume_data.get('relative_volume', 1)) > 2 else 1,
        confidence=0.7
    )
    
    # Overall analysis
    bullish_signals = sum(1 for x in trend_indicators + momentum_indicators if x.signal_type == "bullish")
    bearish_signals = sum(1 for x in trend_indicators + momentum_indicators if x.signal_type == "bearish")
    
    overall_signal = "bullish" if bullish_signals > bearish_signals else "bearish" if bearish_signals > bullish_signals else "neutral"
    signal_strength = max(1, min(3, abs(bullish_signals - bearish_signals)))
    
    # Risk metrics
    atr = safe_float(indicators.get('atr'))
    # Calculate risk metrics safely
    vol_pct = (atr / current_price * 100) if atr and current_price else 0
    risk_metrics = {
        "volatility": atr,
        "volatility_percent": float(vol_pct),
        "trend_strength": safe_float(adx_value),
        "risk_level": (str("high") if adx_value > 40 
                      else str("moderate") if adx_value > 20 
                      else str("low"))
    }
    
    # Support/Resistance levels
    support_resistance_data = indicators.get('support_resistance', {})
    def convert_to_float(val: Any) -> Optional[float]:
        """Convert a value to float safely"""
        try:
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                # First try direct conversion
                return float(val)
            return None
        except (ValueError, TypeError):
            return None

    raw_supports = support_resistance_data.get('supports', [])
    raw_resistances = support_resistance_data.get('resistances', [])
    
    supports = [f for f in (convert_to_float(s) for s in raw_supports) if f is not None]
    resistances = [f for f in (convert_to_float(r) for r in raw_resistances) if f is not None]
    
    immediate_support = next((s for s in supports if safe_float(s) > 0 and safe_float(s) < safe_float(current_price)), None)
    immediate_resistance = next((r for r in resistances if safe_float(r) > 0 and safe_float(r) > safe_float(current_price)), None)
    
    # Get MA crossovers
    ma_crosses = indicators.get('ma_crossovers', {})

    # Get candlestick patterns
    candlestick_patterns = indicators.get('candlestick_patterns', {})

    # Enhanced support/resistance with pattern confluence
    support_resistance = {
        "supports": supports,
        "resistances": resistances,
        "pattern_confluence": indicators.get('support_resistance', {}).get('pattern_confluence', [])
    }

    return ComprehensiveSummary(
        price_action=price_action,
        trend_indicators=trend_indicators,
        momentum_indicators=momentum_indicators,
        volume_analysis=volume_analysis,
        volatility_metrics=IndicatorSummary(
            name="Volatility",
            value={"atr": atr},
            interpretation=f"ATR at {atr:.2f} ({risk_metrics['volatility_percent']:.1f}% of price)",
            signal_type="neutral",
            signal_strength=2 if risk_metrics['volatility_percent'] > 5 else 1,
            confidence=0.8
        ),
        support_resistance=support_resistance,
        candlestick_patterns=candlestick_patterns,
        overall_signal=overall_signal,
        signal_strength=signal_strength,
        key_levels={
            "immediate_support": immediate_support,
            "immediate_resistance": immediate_resistance,
            "ma_support": float(sma_20) if isinstance(sma_20, (int, float)) and sma_20 > 0 else None
        },
        risk_metrics=risk_metrics,
        ma_crosses=ma_crosses
    )

def generate_trading_signals(summary: ComprehensiveSummary) -> Dict[str, Any]:
    """Generate actionable trading signals"""
    trend_confidence = sum(ind.confidence for ind in summary.trend_indicators) / len(summary.trend_indicators)
    momentum_confidence = sum(ind.confidence for ind in summary.momentum_indicators) / len(summary.momentum_indicators)
    
    # Additional confidence from candlestick patterns
    pattern_confidence = 0.0
    pattern_count = 0
    for pattern in summary.candlestick_patterns.values():
        pattern_count += 1
        pattern_confidence += pattern.get('strength', 0)
    if pattern_count > 0:
        pattern_confidence = pattern_confidence / pattern_count
    
    # Combine confidences with higher weight for candlestick patterns near S/R levels
    total_confidence = (trend_confidence * 0.4 + 
                       momentum_confidence * 0.4 + 
                       pattern_confidence * 0.2)
    
    signals = {
        "primary_signal": summary.overall_signal,
        "signal_strength": summary.signal_strength,
        "risk_level": summary.risk_metrics["risk_level"],
        "confidence": total_confidence,
        "suggested_stops": {
            "tight": summary.price_action["current_price"] * 0.98,
            "wide": summary.price_action["current_price"] * 0.95
        }
    }
    
    return signals

def calculate_risk_reward(current_price: float, target: float, stop_loss: float) -> float:
    """Calculate risk/reward ratio"""
    if stop_loss >= current_price or current_price >= target:
        return 0.0
    risk = current_price - stop_loss
    reward = target - current_price
    return reward / risk if risk > 0 else 0.0

def format_summary_for_llm(summary: ComprehensiveSummary, indicators: Dict[str, Any]) -> str:
    """Format the technical analysis summary for LLM consumption"""
    trend_confidence = sum(ind.confidence for ind in summary.trend_indicators) / len(summary.trend_indicators)
    momentum_confidence = sum(ind.confidence for ind in summary.momentum_indicators) / len(summary.momentum_indicators)
    overall_confidence = min(trend_confidence, momentum_confidence)
    
    # Calculate nearest support and resistance
    price = summary.price_action['current_price']
    supports = sorted([s for s in summary.support_resistance['supports'] if safe_float(s) < safe_float(price)], reverse=True)
    resistances = sorted([r for r in summary.support_resistance['resistances'] if safe_float(r) > safe_float(price)])
    
    support = supports[0] if supports else "N/A"
    resistance = resistances[0] if resistances else "N/A"
    
    # Calculate risk/reward for the trade
    # Use ATR-based stop if no support level available
    atr = indicators.get('atr', 0)
    default_stop = price - (2 * atr) if atr else price * 0.92
    
    # Use MA20 as support if available
    ma_support = summary.key_levels.get('ma_support')
    # Set effective support and target levels
    effective_support = (
        support if isinstance(support, (int, float)) 
        else (ma_support if ma_support and safe_float(ma_support) < safe_float(price) else default_stop)
    )
    effective_target = (
        resistance if isinstance(resistance, (int, float))
        else price * 1.15  # 15% target
    )
    
    # Calculate risk/reward
    risk_reward = calculate_risk_reward(price, effective_target, effective_support)
    
    # Update support display value to show the effective level
    support = effective_support
    
    return f"""
Price Action: ${summary.price_action['current_price']:.2f} ({summary.price_action['daily_change_percent']:+.2f}%)
Overall Signal: {summary.overall_signal.upper()} (Strength: {summary.signal_strength}/3)

Key Indicators:
1. Trend Analysis:
   - {''.join(f"{ind.name}: {ind.interpretation}\n   " for ind in summary.trend_indicators)}

2. Momentum and Oscillators:
   - {''.join(f"{ind.name}: {ind.interpretation}\n   " for ind in summary.momentum_indicators)}
   - CCI: {indicators.get('cci', 'N/A'):.1f} ({'Overbought' if safe_float(indicators.get('cci', 0)) > 100 
                                               else 'Oversold' if safe_float(indicators.get('cci', 0)) < -100 
                                               else 'Neutral'})
   - Stochastic: %K={indicators.get('stoch', {}).get('k', 'N/A'):.1f}, %D={indicators.get('stoch', {}).get('d', 'N/A'):.1f}

3. Volume: {summary.volume_analysis.interpretation}

4. Price Levels and Support/Resistance:
   - Current: ${price:.2f}
   - Support: ${support}
   - Resistance: ${resistance}
   - Risk/Reward Ratio: {risk_reward:.1f}

5. Technical Rating:
   - Trend Score: {trend_confidence * 100:.0f}/100
   - Momentum Score: {momentum_confidence * 100:.0f}/100
   - Overall Rating: {(trend_confidence + momentum_confidence) * 50:.0f}/100

6. Risk Assessment:
   - Volatility: {summary.risk_metrics['volatility_percent']:.1f}% ATR
   - Trend Strength: {summary.risk_metrics['trend_strength']:.1f}
   - Risk Level: {str(summary.risk_metrics['risk_level']).upper()}

Bollinger Bands:
- Band Width: {indicators.get('bollinger_bands', {}).get('width', 'N/A'):.1f}%
- Position: {'Outside Upper' if indicators.get('bollinger_bands') and safe_float(summary.price_action['current_price']) > safe_float(indicators['bollinger_bands'].get('upper', float('inf')))
            else 'Outside Lower' if indicators.get('bollinger_bands') and safe_float(summary.price_action['current_price']) < safe_float(indicators['bollinger_bands'].get('lower', float('-inf')))
            else 'Inside Bands' if indicators.get('bollinger_bands')
            else 'No Bollinger Band Data'}

Signal Confidence: {overall_confidence:.1%}
Trade Setup:
- Entry: ${price:.2f}
- Target: ${resistance if isinstance(resistance, (int, float)) else 'N/A'}
- Stop: ${support if isinstance(support, (int, float)) else 'N/A'}
""".strip()
