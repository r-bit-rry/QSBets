import os
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from langchain.schema import Document
import requests
import yaml
from datetime import datetime
from analysis.macroeconomic import get_macroeconomic_context
from ml_serving.ai_service import map_reduce_summarize
from storage.cache import HOURS2_TTL, cached, DAY_TTL
from logger import get_logger

logger = get_logger(__name__)

@cached(1800)
def fetch_economic_news(url: str = "https://hotgrog.com/business/") -> Optional[str]:
    """
    Fetch the economic news webpage content.
    
    Args:
        url: URL of the economic news webpage
        
    Returns:
        HTML content of the page or None if failed
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch economic news: {e}")
        return None

def extract_news_items(html_content: str) -> List[Tuple[str, str, str]]:
    """
    Extract news headlines, their context, and source from the HTML content.
    
    Args:
        html_content: HTML content of the economic news webpage
        
    Returns:
        List of tuples containing (headline, context, source)
    """
    news_items = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all table headings (h1) that contain source information
        current_source = "Unknown Source"
        
        for element in soup.find_all(['h1', 'tr']):
            if element.name == 'h1':
                # Update the current source
                source_link = element.find('a')
                if source_link:
                    current_source = source_link.text.strip()
            
            elif element.name == 'tr':
                td = element.find('td')
                if not td:
                    continue
                    
                # Look specifically for the second link in each TD (the one with the actual headline)
                links = td.find_all('a', href=True)
                if len(links) >= 2:
                    link = links[1]  # The second link has the headline and title
                    
                    if link.has_attr('title'):
                        headline = link.text.strip()
                        context = link.get('title', '').strip()
                        
                        if headline and context:
                            news_items.append((headline, context, current_source))
    
    except Exception as e:
        logger.error(f"Failed to parse news items: {e}")
    
    return news_items

def compile_news_document(news_items: List[Tuple[str, str, str]]) -> Document:
    """
    Compile news items into a langchain Document.
    
    Args:
        news_items: List of tuples containing (headline, context, source)
        
    Returns:
        Langchain Document containing formatted news content
    """
    formatted_items = []

    for headline, context, source in news_items:
        formatted_items.append(f"Source: {source}\nHeadline: {headline}\nContext: {context}")

    # Join all items with double newline separator
    content = "\n\n".join(formatted_items)

    return Document(
        page_content=content,
        metadata={"source": "hotgrog.com/business", "type": "economic_news"}
    )


@cached(HOURS2_TTL)
def summarize_economic_news() -> str:
    """
    Fetch, process and summarize economic news
    
        
    Returns:
        Summarized economic news
    """
    # Fetch the news
    html_content = fetch_economic_news()
    if not html_content:
        logger.error("No content to summarize")
        return "Failed to fetch economic news"
    
    # Extract and compile news items
    news_items = extract_news_items(html_content)
    
    if not news_items:
        logger.warning("No news items found to summarize")
        return "No economic news found to summarize"
    
    document = compile_news_document(news_items)
    
    # Use appropriate summarization method based on whether stock_ticker is provided
    try:
        # Use generic economic news summarization
        system_prompt = """You are an expert economic analyst. Summarize economic news 
        from various sources into a coherent analysis that highlights key trends, 
        market movements, and significant economic events."""
        
        map_template = """Summarize the following economic news text:
        {text}
        
        Summary:"""
        
        reduce_template = """You are given a set of summaries extracted from economic news sources.
        Create a comprehensive analysis that identifies the most important economic trends, 
        governmental policies, market movements, and business developments.
        
        Include any relevant statistics, forecasts, or data points mentioned.
        Be concise, clear, technical, and professional.
        SUMMARIES:
        {summaries}
        
        COMPREHENSIVE ECONOMIC ANALYSIS:"""
        
        summary = map_reduce_summarize(
            documents=[document],
            backend="lmstudio",
            model="glm-4-9b-chat-abliterated",
            system_prompt=system_prompt,
            map_template=map_template,
            reduce_template=reduce_template,
            params={}
        )
    
        return summary
    except Exception as e:
        logger.error(f"Failed to summarize economic news: {e}")
        return f"Error summarizing economic news: {str(e)}"

if __name__ == "__main__":
    # Example usage
    summary = summarize_economic_news()
    logger.info(summary)


@cached(ttl_seconds=DAY_TTL)
def make_yaml():
    """
    Generate a YAML file combining macroeconomic data and economic news summary.
    Saves the file to ./analysis_docs/yyyy/mm/dd/macro.yaml.

    Returns:
        str: YAML string representation of the combined data.
    """
    # Fetch macroeconomic data and news summary
    macro_data = get_macroeconomic_context()
    news_summary = summarize_economic_news()

    # Combine data
    combined_data = {
        "macroeconomic": macro_data,
        "economic_news": news_summary
    }

    # Convert to YAML
    yaml_string = yaml.dump(
        combined_data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True
    )

    # Save YAML to file
    today = datetime.now()
    date_path = os.path.join(
        "analysis_docs",
        today.strftime("%Y"),
        today.strftime("%m"),
        today.strftime("%d")
    )
    os.makedirs(date_path, exist_ok=True)
    file_path = os.path.join(date_path, "macro.yaml")

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(yaml_string)

    logger.info(f"Macro YAML saved to {file_path}")

    return yaml_string

if __name__ == "__main__":
    print(make_yaml())