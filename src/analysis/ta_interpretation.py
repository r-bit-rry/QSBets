"""
Technical analysis interpretation module that converts raw indicators to insights.
This reduces the LLM's workload by pre-analyzing technical data.
"""

from logger import get_logger

logger = get_logger(__name__)

def interpret_rsi(rsi):
    """Interpret RSI value and return standardized assessment"""
    if isinstance(rsi, list) and rsi:
        rsi = rsi[-1]  # Use the most recent RSI value

    if rsi is None:
        return {"status": "unknown", "strength": 0, "description": "No RSI data available"}
    
    if rsi > 70:
        return {"status": "overbought", "strength": 2, "description": f"RSI at {rsi:.2f} indicates overbought conditions"}
    elif rsi < 30:
        return {"status": "oversold", "strength": 2, "description": f"RSI at {rsi:.2f} indicates oversold conditions"}
    elif rsi > 60:
        return {"status": "bullish", "strength": 1, "description": f"RSI at {rsi:.2f} shows bullish momentum"}
    elif rsi < 40:
        return {"status": "bearish", "strength": 1, "description": f"RSI at {rsi:.2f} shows bearish momentum"}
    else:
        return {"status": "neutral", "strength": 0, "description": f"RSI at {rsi:.2f} is neutral"}

def interpret_macd(macd_data):
    """Interpret MACD values and return standardized assessment"""
    if isinstance(macd_data, list) and macd_data:
        macd_data = macd_data[-1]  # Use the most recent MACD values
    
    if not macd_data or None in (macd_data.get('macd'), macd_data.get('signal')):
        return {"status": "unknown", "strength": 0, "description": "No MACD data available"}
    
    macd_value = macd_data.get('macd')
    signal = macd_data.get('signal')
    hist = macd_data.get('hist')
    
    if macd_value > signal and hist > 0:
        if hist > macd_data.get('hist_prev', 0):  # Requires historical data
            return {"status": "bullish", "strength": 2, "description": f"MACD ({macd_value:.2f}) above signal line with increasing histogram"}
        return {"status": "bullish", "strength": 1, "description": f"MACD ({macd_value:.2f}) above signal line"}
    elif macd_value < signal and hist < 0:
        if hist < macd_data.get('hist_prev', 0):  # Requires historical data
            return {"status": "bearish", "strength": 2, "description": f"MACD ({macd_value:.2f}) below signal line with decreasing histogram"}
        return {"status": "bearish", "strength": 1, "description": f"MACD ({macd_value:.2f}) below signal line"}
    elif macd_value > signal and macd_value > 0:
        return {"status": "bullish", "strength": 1, "description": f"MACD ({macd_value:.2f}) crossing above signal line"}
    elif macd_value < signal and macd_value < 0:
        return {"status": "bearish", "strength": 1, "description": f"MACD ({macd_value:.2f}) crossing below signal line"}
    else:
        return {"status": "neutral", "strength": 0, "description": f"MACD ({macd_value:.2f}) showing mixed signals"}

def interpret_moving_averages(price, sma_20, sma_50, sma_100):
    """Analyze price relationship to multiple moving averages"""
    if isinstance(sma_20, list) and sma_20:
        sma_20 = sma_20[-1]
    if isinstance(sma_50, list) and sma_50:
        sma_50 = sma_50[-1]
    if isinstance(sma_100, list) and sma_100:
        sma_100 = sma_100[-1]
    results = []
    
    # Check price relative to moving averages
    if price > sma_20:
        results.append({"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above SMA20 (${sma_20:.2f})"})
    else:
        results.append({"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below SMA20 (${sma_20:.2f})"})
        
    if price > sma_50:
        results.append({"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above SMA50 (${sma_50:.2f})"})
    else:
        results.append({"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below SMA50 (${sma_50:.2f})"})
        
    if price > sma_100:
        results.append({"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above SMA100 (${sma_100:.2f})"})
    else:
        results.append({"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below SMA100 (${sma_100:.2f})"})
    
    # Check moving average alignment
    if sma_20 > sma_50 > sma_100:
        results.append({"status": "bullish", "strength": 2, "description": "Strong uptrend with SMA20 > SMA50 > SMA100"})
    elif sma_100 > sma_50 > sma_20:
        results.append({"status": "bearish", "strength": 2, "description": "Strong downtrend with SMA100 > SMA50 > SMA20"})
    
    return results

def interpret_bollinger_bands(price, bb_data):
    """Interpret price position relative to Bollinger Bands"""
    if isinstance(bb_data, list) and bb_data:
        bb_data = bb_data[-1]
    if not bb_data:
        return {"status": "unknown", "strength": 0, "description": "No Bollinger Bands data"}
        
    upper = bb_data.get('upper')
    lower = bb_data.get('lower')
    middle = bb_data.get('middle')
    
    if price > upper:
        return {"status": "overbought", "strength": 2, "description": f"Price (${price:.2f}) above upper Bollinger Band (${upper:.2f}), suggesting overbought conditions"}
    elif price < lower:
        return {"status": "oversold", "strength": 2, "description": f"Price (${price:.2f}) below lower Bollinger Band (${lower:.2f}), suggesting oversold conditions"}
    elif price > middle:
        return {"status": "bullish", "strength": 1, "description": f"Price (${price:.2f}) above BB middle band, showing upward momentum"}
    elif price < middle:
        return {"status": "bearish", "strength": 1, "description": f"Price (${price:.2f}) below BB middle band, showing downward momentum"}
    else:
        return {"status": "neutral", "strength": 0, "description": f"Price at BB middle band, showing equilibrium"}

def interpret_adx(adx):
    """Interpret ADX (Average Directional Index) for trend strength"""
    if isinstance(adx, list) and adx:
        adx = adx[-1]
    if adx is None:
        return {"status": "unknown", "strength": 0, "description": "No ADX data available"}
    
    if adx > 40:
        return {"status": "strong_trend", "strength": 3, "description": f"ADX at {adx:.2f} indicates very strong trend"}
    elif adx > 25:
        return {"status": "trending", "strength": 2, "description": f"ADX at {adx:.2f} indicates trending market"}
    elif adx > 20:
        return {"status": "weak_trend", "strength": 1, "description": f"ADX at {adx:.2f} indicates beginning trend"}
    else:
        return {"status": "no_trend", "strength": 0, "description": f"ADX at {adx:.2f} indicates ranging/sideways market"}

def interpret_insider_activity(insider_data):
    """Summarize insider trading activity"""
    if not insider_data:
        return {"status": "unknown", "description": "No insider trading data available"}

    # Fix: Handle string values that may contain commas and parentheses
    net_activity_raw = insider_data.get('net_insider_activity_3m', 0)
    if isinstance(net_activity_raw, str):
        # Remove parentheses, commas, and other non-numeric characters
        net_activity_clean = ''.join(c for c in net_activity_raw if c.isdigit() or c == '-')
        net_activity_3m = int(net_activity_clean) if net_activity_clean else 0
    else:
        net_activity_3m = int(net_activity_raw)

    recent_transactions = insider_data.get('recent_transactions', [])

    buys = sum(1 for tx in recent_transactions if tx.get('transactionType') == 'Buy')
    sells = sum(1 for tx in recent_transactions if tx.get('transactionType') == 'Sell')

    if sells > buys and sells >= 3:
        return {
            "status": "bearish", 
            "strength": 2 if abs(net_activity_3m) > 1000000 else 1,
            "description": f"Significant insider selling: {sells} sells vs {buys} buys, net {net_activity_3m:,} shares"
        }
    elif buys > sells and buys >= 3:
        return {
            "status": "bullish", 
            "strength": 2 if abs(net_activity_3m) > 1000000 else 1,
            "description": f"Significant insider buying: {buys} buys vs {sells} sells, net {net_activity_3m:,} shares"
        }
    else:
        return {
            "status": "neutral",
            "strength": 0,
            "description": f"Balanced insider activity: {buys} buys vs {sells} sells"
        }


def interpret_stochastic(stoch_data):
    """Interpret Stochastic Oscillator values"""
    if isinstance(stoch_data, list) and stoch_data:
        stoch_data = stoch_data[-1]
    if not stoch_data:
        return {
            "status": "unknown",
            "strength": 0,
            "description": "No stochastic data available",
        }

    k = stoch_data.get("stochastic_k")
    d = stoch_data.get("stochastic_d")

    if k > 80 and d > 80:
        return {
            "status": "overbought",
            "strength": 2,
            "description": f"Stochastic overbought with %K at {k:.1f} and %D at {d:.1f}",
        }
    elif k < 20 and d < 20:
        return {
            "status": "oversold",
            "strength": 2,
            "description": f"Stochastic oversold with %K at {k:.1f} and %D at {d:.1f}",
        }
    elif k > d and k < 80:
        return {
            "status": "bullish",
            "strength": 1,
            "description": f"Bullish stochastic crossover with %K at {k:.1f} crossing above %D at {d:.1f}",
        }
    elif k < d and k > 20:
        return {
            "status": "bearish",
            "strength": 1,
            "description": f"Bearish stochastic crossover with %K at {k:.1f} crossing below %D at {d:.1f}",
        }
    else:
        return {
            "status": "neutral",
            "strength": 0,
            "description": f"Neutral stochastic with %K at {k:.1f} and %D at {d:.1f}",
        }


def interpret_price_trend(price_data, days=10):
    """Analyze recent price action trend"""
    recent_prices = [
        price_data[date]["close"]
        for date in list(price_data.keys())[: min(days, len(price_data))]
    ]
    if len(recent_prices) < 5:
        return {
            "status": "unknown",
            "strength": 0,
            "description": "Not enough price data",
        }

    up_days = sum(
        1
        for i in range(1, len(recent_prices))
        if recent_prices[i] > recent_prices[i - 1]
    )
    down_days = sum(
        1
        for i in range(1, len(recent_prices))
        if recent_prices[i] < recent_prices[i - 1]
    )

    if up_days > down_days * 2:
        return {
            "status": "strong_uptrend",
            "strength": 3,
            "description": f"Strong uptrend with {up_days}/{len(recent_prices)-1} up days",
        }
    elif up_days > down_days:
        return {
            "status": "uptrend",
            "strength": 2,
            "description": f"Uptrend with {up_days}/{len(recent_prices)-1} up days",
        }
    elif down_days > up_days * 2:
        return {
            "status": "strong_downtrend",
            "strength": 3,
            "description": f"Strong downtrend with {down_days}/{len(recent_prices)-1} down days",
        }
    elif down_days > up_days:
        return {
            "status": "downtrend",
            "strength": 2,
            "description": f"Downtrend with {down_days}/{len(recent_prices)-1} down days",
        }
    else:
        return {
            "status": "sideways",
            "strength": 1,
            "description": "Sideways price action",
        }


def interpret_institutional_holdings(holdings_data):
    """Summarize institutional ownership"""
    if not holdings_data:
        return {"status": "unknown", "description": "No institutional holdings data available"}

    ownership_summary = holdings_data.get('ownership_summary', {})
    key_transactions = holdings_data.get('key_transactions', [])

    # Get institutional ownership percentage
    inst_ownership = ownership_summary.get("Institutional Ownership")

    if inst_ownership is None:
        return {"status": "unknown", "description": "Institutional ownership data not available"}

    # Calculate net institutional buying/selling
    buys = 0
    sells = 0
    for tx in key_transactions:
        if "+" in tx.get('sharesChangePCT', ''):
            buys += 1
        elif "-" in tx.get('sharesChangePCT', ''):
            sells += 1

    if inst_ownership > 0.7:
        status = "very_high_ownership"
        base_desc = f"Very high institutional ownership ({inst_ownership*100:.1f}%)"
    elif inst_ownership > 0.5:
        status = "high_ownership"
        base_desc = f"High institutional ownership ({inst_ownership*100:.1f}%)"
    elif inst_ownership > 0.3:
        status = "moderate_ownership"
        base_desc = f"Moderate institutional ownership ({inst_ownership*100:.1f}%)"
    else:
        status = "low_ownership"
        base_desc = f"Low institutional ownership ({inst_ownership*100:.1f}%)"

    # Add transaction trend to description
    if buys > sells and buys >= 3:
        return {
            "status": status, 
            "strength": 2,
            "description": f"{base_desc} with net accumulation ({buys} increases vs {sells} decreases)"
        }
    elif sells > buys and sells >= 3:
        return {
            "status": status, 
            "strength": 1,
            "description": f"{base_desc} with net distribution ({sells} decreases vs {buys} increases)"
        }
    else:
        return {
            "status": status,
            "strength": 1,
            "description": f"{base_desc} with balanced institutional activity"
        }

def interpret_support_resistance(price, support_resistance_data):
    """Analyze support and resistance levels relative to current price"""
    if isinstance(support_resistance_data, list) and support_resistance_data:
        support_resistance_data = support_resistance_data[-1]
    if not support_resistance_data:
        return {"status": "unknown", "description": "No support/resistance data available"}
    
    supports = support_resistance_data.get('supports', [])
    resistances = support_resistance_data.get('resistances', [])
    
    if not supports and not resistances:
        return {"status": "unknown", "description": "No support/resistance levels identified"}
    
    # Find closest support and resistance levels
    closest_support = None
    closest_support_dist = float('inf')
    for support in supports:
        if support < price and price - support < closest_support_dist:
            closest_support = support
            closest_support_dist = price - support
    
    closest_resistance = None
    closest_resistance_dist = float('inf')
    for resistance in resistances:
        if resistance > price and resistance - price < closest_resistance_dist:
            closest_resistance = resistance
            closest_resistance_dist = resistance - price
    
    # Calculate risk/reward based on closest levels
    if closest_support and closest_resistance:
        risk = price - closest_support
        reward = closest_resistance - price
        ratio = reward / risk if risk > 0 else 0
        
        if ratio >= 2:
            return {
                "status": "bullish",
                "strength": 2,
                "description": f"Strong risk/reward ratio ({ratio:.1f}:1) with support at ${closest_support:.2f} and resistance at ${closest_resistance:.2f}"
            }
        elif ratio > 1:
            return {
                "status": "bullish",
                "strength": 1,
                "description": f"Positive risk/reward ratio ({ratio:.1f}:1) with support at ${closest_support:.2f} and resistance at ${closest_resistance:.2f}"
            }
        else:
            return {
                "status": "bearish",
                "strength": 1,
                "description": f"Poor risk/reward ratio ({ratio:.1f}:1) with support at ${closest_support:.2f} and resistance at ${closest_resistance:.2f}"
            }
    elif closest_support:
        return {
            "status": "neutral",
            "strength": 1,
            "description": f"Support identified at ${closest_support:.2f} (${price-closest_support:.2f} below current price)"
        }
    elif closest_resistance:
        return {
            "status": "neutral",
            "strength": 1,
            "description": f"Resistance identified at ${closest_resistance:.2f} (${closest_resistance-price:.2f} above current price)"
        }
    
    return {"status": "unknown", "description": "Could not analyze support/resistance"}

def interpret_cci(cci):
    """Interpret Commodity Channel Index (CCI)"""
    if isinstance(cci, list) and cci:
        cci = cci[-1]
    if cci is None:
        return {"status": "unknown", "strength": 0, "description": "No CCI data available"}
    
    if cci > 100:
        return {"status": "overbought", "strength": 2, "description": f"CCI at {cci:.1f} indicates overbought conditions"}
    elif cci < -100:
        return {"status": "oversold", "strength": 2, "description": f"CCI at {cci:.1f} indicates oversold conditions"}
    elif cci > 0:
        return {"status": "bullish", "strength": 1, "description": f"CCI at {cci:.1f} shows mild bullish momentum"}
    else:
        return {"status": "bearish", "strength": 1, "description": f"CCI at {cci:.1f} shows mild bearish momentum"}

def generate_preliminary_rating(stock_data):
    """Calculate preliminary rating score (0-100) based on technical and fundamental factors"""
    tech_score = 0
    fund_score = 0
    max_tech = 70
    max_fund = 30
    explanations = []
    
    # Get current price and indicators
    indicators = stock_data.get('technical_indicators', {})
    price_data = stock_data.get('historical_quotes', {})
    
    if not price_data or not indicators:
        return {"rating": 50, "confidence": 1, "technical_score": "0/70", 
                "fundamental_score": "0/30", "explanations": ["Insufficient data"]}
    
    try:
        # Get most recent price
        recent_date = list(price_data.keys())[0]
        current_price = price_data[recent_date]['close']
        
        # Analyze technical indicators (all interpretation functions handle lists internally)
        # RSI analysis
        rsi_analysis = interpret_rsi(indicators.get('rsi'))
        rsi_value = indicators.get('rsi')
        if isinstance(rsi_value, list) and rsi_value:
            rsi_value = rsi_value[-1]
            
        if rsi_analysis['status'] == 'oversold':
            tech_score += 20
            explanations.append(f"RSI oversold ({rsi_value:.2f})")
        elif rsi_analysis['status'] == 'overbought':
            tech_score += 5
            explanations.append(f"RSI overbought ({rsi_value:.2f})")
        elif rsi_analysis['status'] == 'bullish':
            tech_score += 15
            explanations.append(f"RSI bullish ({rsi_value:.2f})")
        elif rsi_analysis['status'] == 'bearish':
            tech_score += 10
            explanations.append(f"RSI bearish ({rsi_value:.2f})")
        else:
            tech_score += 12
            explanations.append(f"RSI neutral ({rsi_value:.2f})")
        
        # MACD analysis
        macd_analysis = interpret_macd(indicators.get('macd', {}))
        if macd_analysis['status'] == 'bullish':
            tech_score += 15 if macd_analysis['strength'] == 2 else 12
            explanations.append("Strong bullish MACD signal" if macd_analysis['strength'] == 2 else "Bullish MACD signal")
        elif macd_analysis['status'] == 'bearish':
            tech_score += 5 if macd_analysis['strength'] == 2 else 8
            explanations.append("Strong bearish MACD signal" if macd_analysis['strength'] == 2 else "Bearish MACD signal")
        else:
            tech_score += 10
            explanations.append("Neutral MACD signal")
            
        # Moving averages
        ma_analyses = interpret_moving_averages(current_price, 
                                               indicators.get('sma_20'),
                                               indicators.get('sma_50'),
                                               indicators.get('sma_100'))
        
        ma_bullish = sum(1 for ma in ma_analyses if ma['status'] == 'bullish')
        ma_bearish = sum(1 for ma in ma_analyses if ma['status'] == 'bearish')
        
        if ma_bullish > ma_bearish:
            tech_score += 15
            explanations.append(f"Bullish moving average alignment ({ma_bullish}/{len(ma_analyses)})")
        elif ma_bearish > ma_bullish:
            tech_score += 5
            explanations.append(f"Bearish moving average alignment ({ma_bearish}/{len(ma_analyses)})")
        else:
            tech_score += 10
            explanations.append("Mixed moving average signals")
            
        # Bollinger Bands
        bb_analysis = interpret_bollinger_bands(current_price, indicators.get('bollinger_bands', {}))
        if bb_analysis['status'] == 'oversold':
            tech_score += 15
            explanations.append("Price below lower Bollinger Band (oversold)")
        elif bb_analysis['status'] == 'overbought':
            tech_score += 5
            explanations.append("Price above upper Bollinger Band (overbought)")
        elif bb_analysis['status'] == 'bullish':
            tech_score += 12
            explanations.append("Price above Bollinger middle band (bullish)")
        elif bb_analysis['status'] == 'bearish':
            tech_score += 8
            explanations.append("Price below Bollinger middle band (bearish)")
            
        # ADX (trend strength)
        adx_value = indicators.get('adx')
        adx_analysis = interpret_adx(indicators.get('adx'))
        if isinstance(adx_value, list) and adx_value:
            adx_value = adx_value[-1]
        if adx_analysis['status'] == 'strong_trend':
            # Add points based on which direction is trending
            tech_score += 5 if ma_bullish > ma_bearish else 3
            explanations.append(f"Strong trend with ADX {adx_value:.2f} ({('bullish' if ma_bullish > ma_bearish else 'bearish')})")
        elif adx_analysis['status'] == 'no_trend':
            tech_score += 3
            explanations.append(f"No clear trend with ADX {adx_value:.2f}")
            
        # Stochastic analysis
        stoch_analysis = interpret_stochastic(indicators.get('stochastic_14_3_3', {}))
        if stoch_analysis['status'] == 'oversold':
            tech_score += 12
            explanations.append("Stochastic oversold (bullish)")
        elif stoch_analysis['status'] == 'overbought':
            tech_score += 5
            explanations.append("Stochastic overbought (bearish)")
        elif stoch_analysis['status'] == 'bullish':
            tech_score += 8
            explanations.append("Bullish stochastic crossover")
        
        # CCI analysis
        cci_analysis = interpret_cci(indicators.get('cci'))
        if cci_analysis['status'] == 'oversold':
            tech_score += 10
            explanations.append("CCI oversold (bullish)")
        elif cci_analysis['status'] == 'overbought':
            tech_score += 4
            explanations.append("CCI overbought (bearish)")
        
        # Support/Resistance analysis
        sr_analysis = interpret_support_resistance(current_price, indicators.get('support_resistance', {}))
        if sr_analysis['status'] == 'bullish':
            tech_score += sr_analysis['strength'] * 5
            explanations.append(sr_analysis['description'])
        elif sr_analysis['status'] == 'bearish':
            tech_score += 3
            explanations.append(sr_analysis['description'])
        
    except (KeyError, IndexError) as e:
        explanations.append(f"Error analyzing technical indicators: {e}")
        logger.error(f"Error analyzing technical indicators: {e}")

    # Fundamental factors (30 points max)
    # Insider activity
    insider_analysis = interpret_insider_activity(stock_data.get('insider_trading', {}))
    if insider_analysis['status'] == 'bullish':
        fund_score += 8
    elif insider_analysis['status'] == 'bearish':
        fund_score += 2
    else:
        fund_score += 5
    explanations.append(insider_analysis['description'])
    
    # Institutional holdings
    inst_analysis = interpret_institutional_holdings(stock_data.get('institutional_holdings', {}))
    if 'high_ownership' in inst_analysis['status']:
        fund_score += 10 if 'accumulation' in inst_analysis['description'] else 8
    elif 'moderate_ownership' in inst_analysis['status']:
        fund_score += 7 if 'accumulation' in inst_analysis['description'] else 5
    else:
        fund_score += 3
    explanations.append(inst_analysis['description'])
    
    # Sentiment
    sentiment = stock_data.get('reddit_wallstreetbets_sentiment', {}).get('sentiment_score_from_neg10_to_pos10')
    if sentiment is not None:
        if sentiment > 5:
            fund_score += 7
            explanations.append(f"Very positive social sentiment (score: {sentiment})")
        elif sentiment > 2:
            fund_score += 5
            explanations.append(f"Positive social sentiment (score: {sentiment})")
        elif sentiment < -5:
            fund_score += 1
            explanations.append(f"Very negative social sentiment (score: {sentiment})")
        elif sentiment < -2:
            fund_score += 2
            explanations.append(f"Negative social sentiment (score: {sentiment})")
        else:
            fund_score += 3
            explanations.append(f"Neutral social sentiment (score: {sentiment})")
    
    # Revenue and earnings
    if stock_data.get('revenue_earnings'):
        has_revenue = any(isinstance(q, dict) and q.get('revenue') not in ('N/A', None) 
                         for q in stock_data.get('revenue_earnings', []))
        fund_score += 5 if has_revenue else 2
        explanations.append("Revenue-generating company" if has_revenue else "Pre-revenue company (higher risk)")
    
    # Calculate confidence and normalize scores
    data_points = len(explanations)
    confidence = max(1, min(10, data_points // 2))
    
    normalized_tech = int((tech_score / max_tech) * 70)
    normalized_fund = int((fund_score / max_fund) * 30)
    total_score = normalized_tech + normalized_fund
    
    return {
        "rating": total_score,
        "confidence": confidence,
        "technical_score": f"{normalized_tech}/70",
        "fundamental_score": f"{normalized_fund}/30",
        "explanations": explanations
    }

def generate_entry_exit_strategy(stock_data):
    """
    Generate entry and exit strategy based on technical indicators
    
    Args:
        stock_data: Dictionary containing parsed stock data
        
    Returns:
        dict: Entry and exit strategies
    """
    indicators = stock_data.get('technical_indicators', {})
    price_data = stock_data.get('historical_quotes', {})
    
    if not price_data or not indicators:
        return {}, {}
        
    try:
        # Get most recent price
        recent_date = list(price_data.keys())[0]
        current_price = price_data[recent_date]['close']
        
        # Entry strategy
        entry = {
            "entry_price": None,
            "entry_timing": None,
            "technical_indicators": []
        }
        
        # Exit strategy
        exit = {
            "profit_target": None,
            "stop_loss": None,
            "time_horizon": None,
            "exit_conditions": []
        }
        
        # SMA analysis
        sma_20 = indicators.get('sma_20')
        sma_50 = indicators.get('sma_50')
        sma_100 = indicators.get('sma_100')
        
        # Bollinger bands
        bb = indicators.get('bollinger_bands', {})
        bb_upper = bb.get('upper')
        bb_lower = bb.get('lower')
        
        # MACD
        macd_data = indicators.get('macd', {})
        
        # RSI
        rsi = indicators.get('rsi')
        
        # Volume
        volume_profile = indicators.get('volume_profile', {})
        avg_volume = volume_profile.get('avg_volume', 0) if isinstance(volume_profile, dict) else 0
        
        # Entry strategies based on technical setup
        if current_price < sma_20 and current_price < sma_50:
            entry["entry_price"] = f"Break above SMA20 (${sma_20:.2f})"
            entry["entry_timing"] = "Wait for bullish confirmation via MACD crossover"
            entry["technical_indicators"].append(f"SMA20 resistance at ${sma_20:.2f}")
        elif current_price > sma_20 and current_price > sma_50:
            entry["entry_price"] = f"Current price ${current_price:.2f} or pullback to SMA20 (${sma_20:.2f})"
            entry["entry_timing"] = "Immediate or on pullback"
            entry["technical_indicators"].append(f"SMA20 support at ${sma_20:.2f}")
        else:
            entry["entry_price"] = f"Confirm break above ${sma_20:.2f} with volume"
            entry["entry_timing"] = "Wait for confirmation"
            entry["technical_indicators"].append(f"Mixed signals at current price (${current_price:.2f})")
            
        # Volume condition
        if avg_volume:
            entry["technical_indicators"].append(f"Look for volume > {float(avg_volume/1000000)}M shares")
        
        # Use support/resistance levels for entry/exit
        support_resistance = indicators.get('support_resistance', {})
        supports = support_resistance.get('supports', [])
        resistances = support_resistance.get('resistances', [])
        
        # Add support level to stop loss considerations
        if supports and len(supports) > 0:
            closest_support = max([s for s in supports if s < current_price], default=None)
            if closest_support:
                entry["technical_indicators"].append(f"Support level at ${closest_support:.2f}")
                if exit.get("stop_loss") is None:
                    exit["stop_loss"] = f"${closest_support:.2f} (-{((current_price/closest_support)-1)*100:.1f}%)"
        
        # Add resistance level to profit target considerations
        if resistances and len(resistances) > 0:
            closest_resistance = min([r for r in resistances if r > current_price], default=None)
            if closest_resistance:
                entry["technical_indicators"].append(f"Resistance level at ${closest_resistance:.2f}")
                if exit.get("profit_target") is None:
                    exit["profit_target"] = f"${closest_resistance:.2f} (+{((closest_resistance/current_price)-1)*100:.1f}%)"

        if bb_upper:
            if not exit.get("profit_target"):
                exit["profit_target"] = f"${bb_upper:.2f} (Bollinger Upper Band, +{((bb_upper/current_price)-1)*100:.1f}%)"
            
        if bb_lower and sma_100:
            if current_price > sma_100 and not exit.get("stop_loss"):
                # If above SMA100, use it as stop loss
                exit["stop_loss"] = f"${sma_100:.2f} (-{((current_price/sma_100)-1)*100:.1f}%)"
            elif not exit.get("stop_loss"):
                # If below SMA100, use BB lower
                exit["stop_loss"] = f"${bb_lower:.2f} (-{((current_price/bb_lower)-1)*100:.1f}%)"
                
        exit["exit_conditions"].append("Close below SMA100")
        
        if rsi:
            exit["exit_conditions"].append("RSI > 70 (overbought)")
            
        stoch = indicators.get('stochastic_14_3_3', {})
        if stoch and stoch.get('stochastic_k') is not None:
            exit["exit_conditions"].append("Stochastic K line crosses below 80 from above")

        cci = indicators.get('cci')
        if cci is not None and cci > 100:
            exit["exit_conditions"].append(f"CCI falls below 100 from {cci:.1f}")

        atr = indicators.get('atr')
        if atr:
            # Conservative profit target: 2x ATR
            conservative_target = current_price + (2 * atr)
            # Aggressive profit target: 3x ATR
            aggressive_target = current_price + (3 * atr)
            # Conservative stop loss: 1x ATR
            tight_stop = current_price - atr
            
            exit["profit_targets"] = {
                "conservative": f"${conservative_target:.2f} (+{((conservative_target/current_price)-1)*100:.1f}%)",
                "aggressive": f"${aggressive_target:.2f} (+{((aggressive_target/current_price)-1)*100:.1f}%)"
            }
            exit["stop_options"] = {
                "tight": f"${tight_stop:.2f} (-{((current_price/tight_stop)-1)*100:.1f}%)",
                "standard": exit["stop_loss"]
            }

        # Key news catalysts
        if "Press_releases" in stock_data:
            exit["exit_conditions"].append("Negative news on product development")
        
        return entry, exit
    except Exception as e:
        logger.error(f"Error generating strategies: {e}")
        return {}, {}
