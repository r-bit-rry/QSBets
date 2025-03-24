"""
Service layer for AI operations using the model server abstraction.
Provides high-level methods for consulting and summarization.
"""
import asyncio

import time
from typing import Any, Dict, Callable, List, Union
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from storage.cache import HOURS2_TTL, cached
from ml_serving.config import FIN_R1_ARGS
from ml_serving.prompts import CONSULT_PROMPT_V7, OWNERSHIP_PROMPT, STOCK_CONSULT_SYSTEM_PROMPT, STOCK_SUMMARIZE_SYSTEM_PROMPT, SUMMARIZE_PROMPT_V3
from ml_serving.utils import JsonOutputParser, SummaryResponse, dump_failed_text, extract_json_from_response, get_chat
from logger import get_logger

logger = get_logger("qsbets")

# Default settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0

@cached(HOURS2_TTL)
def map_reduce_summarize(
    documents: List[Document],
    stock: str,
    callback: Callable = StrOutputParser(),
    backend: str = "ollama",
    chunk_size: int = 32000,
    batch_size: int = 4,  # Control parallel processing
) -> str:
    """Implement map-reduce summarization using langchain with optimized memory usage"""
    llm = get_chat(
        backend=backend,
        model="glm4:9b-chat-q8_0",
        system_message=SystemMessage(STOCK_SUMMARIZE_SYSTEM_PROMPT)
    )

    # Create text splitter for chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=100,
        separators=["\n\n", "\n", " ", ""],
        keep_separator=False,
    )

    # Split documents into chunks
    splits = []
    for doc in documents:
        chunks = text_splitter.split_text(doc.page_content)
        for chunk in chunks:
            splits.append(Document(page_content=chunk, metadata=doc.metadata))

    logger.info(f"Split {len(documents)} documents into {len(splits)} chunks")

    # Map: Summarize each chunk
    map_template = """Summarize the following text for the stock {stock}:
    {text}
    
    Summary:"""

    messages = ChatPromptTemplate.from_messages(
        [
            ("user", map_template),
        ]
    )
    map_chain = messages | llm | callback
    map_chain = map_chain.with_retry(
        stop_after_attempt=DEFAULT_MAX_RETRIES,
    )
    # Reduce: Combine summaries
    reduce_template = """You are given a set of summaries extracted from a longer text about stock news.
    Create a concise, technical, comprehensive summary that combines all the important information about this stock {stock}.
    Focus on quantitative data: revenue growth percentages, earnings, EPS, P/E ratios, margins, risks, and opportunities, year-over-year comparisons.
    
    SUMMARIES:
    {summaries}
    
    COMPREHENSIVE SUMMARY:"""

    messages = ChatPromptTemplate.from_messages(
        [
            ("user", reduce_template)
        ]
    )
    reduce_chain = messages | llm | callback
    reduce_chain = reduce_chain.with_retry(
        stop_after_attempt=DEFAULT_MAX_RETRIES,
    )

    logger.info("Starting map step...")

    async def process_chunks_in_batches():
        mapped_results = [None] * len(splits)  # Pre-allocate result list

        # Process in batches to limit concurrent model loads
        for batch_start in range(0, len(splits), batch_size):
            batch_end = min(batch_start + batch_size, len(splits))
            logger.info(
                f"Processing batch {batch_start//batch_size + 1}, chunks {batch_start+1}-{batch_end}"
            )

            # Create tasks for this batch only
            batch_tasks = []
            for i in range(batch_start, batch_end):
                task = asyncio.create_task(
                    map_chain.ainvoke({"text": splits[i].page_content, "stock": stock})
                )
                batch_tasks.append((i, task))

            # Process batch results
            for i, task in batch_tasks:
                try:
                    result = await task
                    logger.info(f"Chunk {i+1}/{len(splits)} processed")
                    mapped_results[i] = result
                except Exception as e:
                    logger.error(f"Error processing chunk {i+1}: {e}")
                    # Fall back to sync processing for failed chunks
                    result = map_chain.invoke(
                        {"text": splits[i].page_content, "stock": stock}
                    )
                    mapped_results[i] = result
                    logger.info(f"Chunk {i+1} processed (sequential fallback)")

        # Remove any None values (shouldn't happen but just in case)
        return [r for r in mapped_results if r is not None]

    # Choose processing strategy based on number of chunks
    if len(splits) > 20:  # Many chunks - use batched approach
        mapped_results = asyncio.run(process_chunks_in_batches())
    else:  # Fewer chunks - can use original approach
        mapped_results = asyncio.run(
            process_chunks_in_batches()
        )  # Still use batches for safety

    # Execute reduce step
    logger.info("Starting reduce step...")
    result = reduce_chain.invoke(
        {"summaries": "\n".join(mapped_results), "stock": stock}
    )

    return result


def summarize(text: str, callback: Callable = None, 
              backend: str = "ollama", metadata: Dict[str, Any] = None) -> Union[Dict[str, Any], None]:
    """
    Summarize given text using the configured model server.
    
    Args:
        text: The text to summarize
        callback: Optional callback function for async processing
        backend: Backend to use ('mlx', 'azure', 'ollama')
        metadata: Additional metadata to include in result

    Returns:
        Dictionary with summarized information or None if callback provided
    """
    max_attempts = DEFAULT_MAX_RETRIES
    metadata = metadata or {}

    formatted_prompt = SUMMARIZE_PROMPT_V3.format(text=text)

    messages = [
        SystemMessage(content=STOCK_SUMMARIZE_SYSTEM_PROMPT),
        HumanMessage(content=formatted_prompt)
    ]

    # Get model server
    model_server = get_chat(backend=backend, model="glm4:9b-chat-q8_0")

    # Process asynchronously if callback provided
    if callback:
        request_id = f"summarize_{hash(text)[:20]}_{time.time()}"

        def on_complete(req_id, result):
            try:
                if "error" in result:
                    callback({"error": result["error"], "metadata": metadata})
                    return

                # Extract the JSON response
                json_text = extract_json_from_response(result["content"])
                summarized_json = SummaryResponse.model_validate_json(json_text)
                result = summarized_json.model_dump()
                callback(result)
            except Exception as e:
                logger.error(f"Error processing summary result: {e}")
                callback({"error": str(e), "metadata": metadata})

        # Submit request
        model_server.submit_request(
            request_id=request_id,
            messages=messages,
            callback=on_complete,
            metadata=metadata
        )
        return None

    def process_summary():
        res = model_server.process_sync(messages, metadata=metadata)
        if "error" in res:
            raise Exception(f"Model server error: {res['error']}")
        json_text = extract_json_from_response(res["content"])
        SummaryResponse.model_validate_json(json_text)
        return json_text

    return _process_sync_with_retry(process_summary, formatted_prompt, metadata, max_attempts, "Analysis completed successfully")


def consult(
    filepath: str,
    metadata: Dict[str, Any] = None,
    callback: Callable = StrOutputParser(),
    backend: str = "ollama",
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Union[Dict[str, Any], None]:
    """
    Consult the model with a stock data file for analysis
    
    Args:
        filepath: Path to the JSON/YAML file containing stock data
        metadata: Additional metadata to include in the result
        callback: Function to call with the result when complete
        backend: Backend to use ('mlx', 'azure', 'ollama')
        max_retries: Maximum number of retry attempts
        
    Returns:
        Parsed JSON response with stock analysis or empty dict on failure
        If callback is provided, the result is passed to the callback and None is returned
    """
    metadata = metadata or {}

    try:
        with open(filepath, 'r') as file:
            document = file.read()
    except Exception as e:
        error_msg = f"Error reading file {filepath}: {e}"
        logger.error(error_msg)
        result = {"error": error_msg, "metadata": metadata}
        if callback:
            callback(result)
            return None
        return result

    # Determine which prompt to use based on purchase_price presence
    purchase_price = metadata.get("purchase_price")

    prompt = OWNERSHIP_PROMPT if purchase_price else CONSULT_PROMPT_V7

    messages = ChatPromptTemplate.from_messages(
        [
            ("user", prompt.template)
        ]
    )
    # Get model server
    llm = get_chat(backend=backend, model="finr1", system_message=SystemMessage(STOCK_CONSULT_SYSTEM_PROMPT), **FIN_R1_ARGS)
    chain = messages | llm | StrOutputParser() | JsonOutputParser() 
    chain = chain.with_retry(
        stop_after_attempt=max_retries
    )
    res = chain.invoke({"loadedDocument": document, "purchase_price": purchase_price})
    if "error" in res:
        raise Exception(f"Model server error: {res['error']}")
    if callback:
        callback(res)

    return res
