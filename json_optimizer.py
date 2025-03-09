"""
Utility for optimizing JSON data before sending to LLM to reduce token count
"""

import json

def optimize_json_for_llm(filepath: str) -> str:
    """
    Optimize a JSON file to reduce token count before sending to LLM.
    
    This function:
    1. Removes less important fields
    2. Truncates long lists
    3. Keeps critical pre-analyzed data
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Path to the optimized JSON file
    """
    with open(filepath, 'r') as file:
        data = json.load(file)
    
    # Keep only essential data
    optimized = {
        "description": data.get("description", ""),
        "meta": _optimize_meta(data.get("meta", {})),
        "technical_analysis": data.get("technical_analysis", {}),
        "insider_analysis": data.get("insider_analysis", {}),
        "institutional_analysis": data.get("institutional_analysis", {}),
        "preliminary_rating": data.get("preliminary_rating", {}),
        "preliminary_entry_strategy": data.get("preliminary_entry_strategy", {}),
        "preliminary_exit_strategy": data.get("preliminary_exit_strategy", {}),
    }
    
    # Add macroeconomic context if available but simplify it
    if "macroeconomic_context" in data:
        optimized["macroeconomic_context"] = {
            "interest_rates": data["macroeconomic_context"].get("interest_rates", {}),
            "inflation": data["macroeconomic_context"].get("inflation", {})
        }
    
    # Add revenue data but limit fields
    if "revenue_earnings" in data and data["revenue_earnings"]:
        optimized["revenue_earnings"] = data["revenue_earnings"][:2]  # Just most recent quarters
    
    # Add sentiment if available
    if "reddit_wallstreetbets_sentiment" in data:
        optimized["sentiment"] = {
            "score": data["reddit_wallstreetbets_sentiment"].get("sentiment_score_from_neg10_to_pos10"),
            "positive": data["reddit_wallstreetbets_sentiment"].get("positive_reddit_mentions"),
            "negative": data["reddit_wallstreetbets_sentiment"].get("negative_reddit_mentions"),
        }
    
    # Add latest quote
    if "historical_quotes" in data and data["historical_quotes"]:
        # Get first key-value pair (most recent quote)
        recent_date = next(iter(data["historical_quotes"]))
        optimized["latest_quote"] = {
            "date": recent_date,
            **data["historical_quotes"][recent_date]
        }
    
    # Add news headlines without full content
    news = []
    if "news" in data:
        for item in data["news"][:3]:  # Limit to 3 most recent
            if "headline" in item:
                news.append({"headline": item["headline"]})
            elif "summary" in item and isinstance(item["summary"], dict):
                news.append({"headline": item["summary"].get("key_point", "")})
    optimized["recent_news"] = news
    
    # Write optimized data to a new file
    optimized_path = filepath.replace(".json", "_optimized.json")
    with open(optimized_path, 'w') as file:
        json.dump(optimized, file)
    
    return optimized_path

def _optimize_meta(meta):
    """Optimize meta data by removing less critical fields"""
    # Keep only essential meta fields
    essential_fields = [
        "symbol", "name", "marketCap", "volume", "industry", 
        "sector", "next_earning_call", "sentiment_rating"
    ]
    return {k: v for k, v in meta.items() if k in essential_fields}

# Update the consult function to use optimized JSON
def optimized_consult(filepath: str):
    """Wrapper for consult that first optimizes the JSON"""
    from ml_serving.deepseek_lc import consult
    optimized_path = optimize_json_for_llm(filepath)
    return consult(optimized_path)
