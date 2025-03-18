"""
Service layer for AI operations using the model server abstraction.
Provides high-level methods for consulting and summarization.
"""
import asyncio
import json
import os
import random

import time
import traceback
from typing import Any, Dict, Callable, List, Optional, Union
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser

from langchain.schema.messages import SystemMessage, HumanMessage
from ml_serving.utils import SummaryResponse, dump_failed_text
from ml_serving.prompts import CONSULT_PROMPT_V7, OWNERSHIP_PROMPT, SUMMARIZE_PROMPT_V2, SUMMARIZE_PROMPT_V3, SYSTEM_PROMPT
from ml_serving.model_server import get_model_server
from ml_serving.model_base import extract_json_from_response

# System prompt for stock analysis
STOCK_SYSTEM_PROMPT = "You are an expert stock analyst. Always provide your analysis in the requested JSON format."

# Default settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0


def map_reduce_summarize(
    documents: List[Document],
    stock: str,
    callback: Callable = StrOutputParser(),
    backend: str = "mlx",
    chunk_size: int = 10000,
)-> str:
    """Implement map-reduce summarization using langchain"""
    llm = get_model_server(backend=backend)

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

    print(f"Split {len(documents)} documents into {len(splits)} chunks")

    # Map: Summarize each chunk
    map_template = """Summarize the following text for the stock {stock}:
    {text}
    
    Summary:"""
    map_prompt = PromptTemplate.from_template(map_template)

    map_chain = map_prompt | llm | callback

    # Reduce: Combine summaries
    reduce_template = """You are given a set of summaries extracted from a longer text about stock news.
    Create a concise, technical, comprehensive summary that combines all the important information about this stock {stock}.
    Focus on quantitative data: revenue growth percentages, earnings, EPS, P/E ratios, margins, risks, and opportunities, year-over-year comparisons.
    
    SUMMARIES:
    {summaries}
    
    COMPREHENSIVE SUMMARY:"""
    reduce_prompt = PromptTemplate.from_template(reduce_template)

    reduce_chain = reduce_prompt | llm | callback

    # Execute map step
    # print("Starting map step...")
    # mapped_results = []

    # for i, split in enumerate(splits):
    #     print(f"Processing chunk {i+1}/{len(splits)}...")
    #     result = map_chain.ainvoke({"text": split.page_content, "stock": stock})
    #     mapped_results.append(result)
    #     print(f"Chunk {i+1} processed")
    print("Starting map step...")

    async def process_chunks_async():
        tasks = []
        for i, split in enumerate(splits):
            print(f"Queuing chunk {i+1}/{len(splits)}...")
            # Create task for each chunk
            task = asyncio.create_task(
                map_chain.ainvoke({"text": split.page_content, "stock": stock})
            )
            tasks.append((i, task))

        # Process results in order
        mapped_results = []
        for i, task in sorted(tasks):  # Maintain original order
            try:
                result = await task
                print(f"Chunk {i+1}/{len(splits)} processed")
                mapped_results.append(result)
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                # Fall back to sync processing for failed chunks
                result = map_chain.invoke(
                    {"text": splits[i].page_content, "stock": stock}
                )
                mapped_results.append(result)
                print(f"Chunk {i+1} processed (sequential fallback)")

        return mapped_results

    # Run the async function
    mapped_results = asyncio.run(process_chunks_async())

    # Execute reduce step
    print("Starting reduce step...")
    result = reduce_chain.invoke(
        {"summaries": "\n\n".join(mapped_results), "stock": stock}
    )

    return result


def summarize(text: str, prompt_version: int = 3, callback: Callable = None, 
              backend: str = "mlx", metadata: Dict[str, Any] = None) -> Union[Dict[str, Any], None]:
    """
    Summarize given text using the configured model server.
    
    Args:
        text: The text to summarize
        prompt_version: Version of prompt to use (2 or 3)
        callback: Optional callback function for async processing
        backend: Backend to use ('mlx', 'azure', 'ollama')
        metadata: Additional metadata to include in result

    Returns:
        Dictionary with summarized information or None if callback provided
    """
    max_attempts = DEFAULT_MAX_RETRIES
    attempt = 1
    metadata = metadata or {}

    # Get the appropriate prompt
    prompt = SUMMARIZE_PROMPT_V3 if prompt_version == 3 else SUMMARIZE_PROMPT_V2
    formatted_prompt = prompt.format(text=text)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=formatted_prompt)
    ]

    # Get model server
    model_server = get_model_server(backend=backend)

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
                result["metadata"] = metadata
                callback(result)
            except Exception as e:
                print(f"Error processing summary result: {e}")
                callback({"error": str(e), "metadata": metadata})

        # Submit request
        model_server.submit_request(
            request_id=request_id,
            messages=messages,
            callback=on_complete,
            metadata=metadata
        )
        return None

    # Process synchronously
    while attempt <= max_attempts:
        try:
            # Process request
            result = model_server.process_sync(messages, metadata=metadata)
            
            if "error" in result:
                raise Exception(f"Model server error: {result['error']}")

            # Extract the JSON response from the text output
            json_text = extract_json_from_response(result["content"])
            
            # Validate against the schema
            summarized_json = SummaryResponse.model_validate_json(json_text)
            result = summarized_json.model_dump()
            result["metadata"] = metadata
            return result
            
        except Exception as e:
            print(f"Attempt {attempt} summarize failed: {e}")
            attempt += 1
            if attempt > max_attempts:
                dump_failed_text(formatted_prompt)
                return {"error": str(e), "metadata": metadata}
                
            # Exponential backoff with jitter
            delay = DEFAULT_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 1)
            time.sleep(delay)


def consult(filepath: str, metadata: Dict[str, Any] = None, callback: Callable = None, 
            backend: str = "mlx", max_retries: int = DEFAULT_MAX_RETRIES) -> Union[Dict[str, Any], None]:
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
    retry_count = 0
    result = {}
    metadata = metadata or {}

    try:
        with open(filepath, 'r') as file:
            document = file.read()
    except Exception as e:
        error_msg = f"Error reading file {filepath}: {e}"
        print(error_msg)
        result = {"error": error_msg, "metadata": metadata}
        if callback:
            callback(result)
            return None
        return result

    # Determine which prompt to use based on purchase_price presence
    try:
        purchase_price = metadata.get("purchase_price")
        if purchase_price is not None and str(purchase_price).strip() and float(purchase_price) > 0:
            formatted_prompt = OWNERSHIP_PROMPT.format(loadedDocument=document, purchase_price=purchase_price)
        else:
            formatted_prompt = CONSULT_PROMPT_V7.format(loadedDocument=document)
    except (ValueError, TypeError):
        formatted_prompt = CONSULT_PROMPT_V7.format(loadedDocument=document)

    # Create messages
    messages = [
        SystemMessage(content=STOCK_SYSTEM_PROMPT),
        HumanMessage(content=formatted_prompt)
    ]

    # Get model server
    model_server = get_model_server(backend=backend)

    # Process asynchronously if callback provided
    if callback:
        request_id = f"consult_{os.path.basename(filepath)}_{time.time()}"
        
        def on_complete(req_id, model_result):
            try:
                if "error" in model_result:
                    callback({"error": model_result["error"], "metadata": metadata})
                    return

                # Extract and parse JSON
                json_str = extract_json_from_response(model_result["content"])
                result = json.loads(json_str)
                result["metadata"] = metadata
                callback(result)
            except Exception as e:
                print(f"Error processing consult result: {e}")
                callback({"error": str(e), "metadata": metadata})

        # Submit request
        model_server.submit_request(
            request_id=request_id,
            messages=messages,
            callback=on_complete,
            metadata=metadata
        )
        return None

    # Process synchronously with retries
    while retry_count <= max_retries:
        try:
            print(f"Processing file: {filepath}")

            # Get response from model
            model_result = model_server.process_sync(messages, metadata=metadata)
            
            if "error" in model_result:
                raise Exception(f"Model server error: {model_result['error']}")

            # Extract and parse the JSON from the response
            json_str = extract_json_from_response(model_result["content"])
            result = json.loads(json_str)
            # Add metadata to the result
            result["metadata"] = metadata
            print(f"Analysis completed successfully")
            break
            
        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                print(f"Failed after {max_retries} retries: {e}")
                result = {"error": str(e), "metadata": metadata}
                break

            # Exponential backoff with jitter
            delay = DEFAULT_BASE_DELAY * (2 ** (retry_count - 1)) + random.uniform(0, 1)
            traceback.print_exc()
            print(f"Error: {e}. Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(delay)

    return result
