import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from ml_serving.utils import get_chat
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import Document
from langchain.schema.runnable import RunnableConfig
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.language_models import LLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from nasdaq import fetch_stock_news
from ml_serving.config import initialize_model_server
from langchain_core.messages import SystemMessage, HumanMessage


class MLXServerLLM(LLM):
    """LangChain LLM implementation for MLX model server"""

    model_server: Any = None
    model_path: str = None

    def __init__(self, model_server=None, model_path=None):
        """Initialize with a model server or path"""
        super().__init__()
        if model_server:
            self.model_server = model_server
        elif model_path:
            self.model_path = model_path
            self.model_server = get_chat(model=model_path)
        else:
            # Use default initialization
            initialize_model_server("mlx")
            self.model_server = get_chat()

    def _llm_type(self) -> str:
        return "mlx_server"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[BaseCallbackHandler] = None,
        **kwargs
    ) -> str:
        """Process a prompt synchronously with the MLX model server"""
        messages = [
            SystemMessage(content="You are a helpful assistant that summarizes text."),
            HumanMessage(content=prompt)
        ]

        # Use synchronous processing
        result = self.model_server.process_sync(messages)

        if "error" in result:
            raise RuntimeError(f"MLX model error: {result['error']}")

        return result.get("content", "")


def map_reduce_summarize(documents: List[Document], stock: str, chunk_size: int = 10000):
    """Implement map-reduce summarization using langchain"""
    # Initialize the LLM
    llm = MLXServerLLM()

    # Create text splitter for chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=100,
        separators=["\n\n", "\n", " ", ""],
        keep_separator=False
    )

    # Split documents into chunks
    splits = []
    for doc in documents:
        chunks = text_splitter.split_text(doc.page_content)
        for chunk in chunks:
            splits.append(Document(page_content=chunk, metadata=doc.metadata))

    print(f"Split {len(documents)} documents into {len(splits)} chunks")

    # Map: Summarize each chunk
    map_template = """Summarize the following text for the stock {stock}:
    {text}
    
    Summary:"""
    map_prompt = PromptTemplate.from_template(map_template)

    map_chain = map_prompt | llm | StrOutputParser()

    # Reduce: Combine summaries
    reduce_template = """You are given a set of summaries extracted from a longer text about stock news.
    Create a concise, technical, comprehensive summary that combines all the important information about this stock {stock}.
    Focus on quantitative data: revenue growth percentages, earnings, EPS, P/E ratios, margins, risks, and opportunities, year-over-year comparisons.
    
    SUMMARIES:
    {summaries}
    
    COMPREHENSIVE SUMMARY:"""
    reduce_prompt = PromptTemplate.from_template(reduce_template)

    reduce_chain = reduce_prompt | llm | StrOutputParser()

    # Execute map step
    print("Starting map step...")
    mapped_results = []

    for i, split in enumerate(splits):
        print(f"Processing chunk {i+1}/{len(splits)}...")
        result = map_chain.invoke({"text": split.page_content, "stock": stock})
        mapped_results.append(result)
        print(f"Chunk {i+1} processed")

    # Execute reduce step
    print("Starting reduce step...")
    result = reduce_chain.invoke({"summaries": "\n\n".join(mapped_results) , "stock": stock})

    return result


def main():
    """Main function to test map-reduce summarization of stock news"""
    # Initialize model server
    print("Initializing MLX model server...")
    initialize_model_server("mlx")
    
    # Fetch news for NVDA
    print("Fetching news for NVDA...")
    news_items = fetch_stock_news("NVDA")
    print(f"Found {len(news_items)} news items")
    
    # Convert news items to documents
    documents = []
    for news_item_json in news_items:
        try:
            news_item = json.loads(news_item_json)
            content = news_item.get("content", "")
            if content:
                doc = Document(
                    page_content=content,
                    metadata={
                        "title": news_item.get("title", ""),
                        "url": news_item.get("url", ""),
                        "created": news_item.get("created", "")
                    }
                )
                documents.append(doc)
        except json.JSONDecodeError as e:
            print(f"Error parsing news item: {e}")
    
    print(f"Converted {len(documents)} news items to documents")
    
    if not documents:
        print("No documents to summarize")
        return
    
    # Run map-reduce summarization
    print("Starting summarization...")
    start_time = time.time()
    summary = map_reduce_summarize(documents, "Nvidia (NVDA)")
    end_time = time.time()
    
    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80)
    print(summary)
    print("="*80)
    print(f"Summarization completed in {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
