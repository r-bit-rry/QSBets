import sys
import time
from typing import List
import os

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain.callbacks.tracers import ConsoleCallbackHandler

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logger import get_logger
from ml_serving.utils import get_chat

from edgar import Company, set_identity
logger = get_logger("sec_summary")

def load_sec_filing(company: str) -> List[Document]:
    """
    Load SEC filing from the given file path and convert to Document objects
    using edgar for parsing
    """
    try:
        # Use edgar to parse the SEC filing
        # Note: This implementation depends on edgar' API - adjust as needed
        filing = Company(company).latest_tenk

        # Create document
        docuemnts = [
            Document(
                page_content=filing[item],
                metadata={
                    "source": "edgar",
                    "type": filing.form,
                    "company": filing.company,
                    "filing_date": filing.filing_date.strftime("%YY-%m-%d"),
                },
            )
            for item in filing.items
        ]
        return docuemnts
    except Exception as e:
        logger.info(f"Error loading SEC filing: {e}")
        return []


def map_reduce_summarize_sec_filing(documents: List[Document], chunk_size: int = 64000):
    """Implement map-reduce summarization using langchain with SEC filing-specific prompts"""
    # Initialize the LLM
    llm = get_chat(backend="ollama", model="glm4:9b-chat-q8_0")

    # Create text splitter for chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""],
        keep_separator=False
    )

    # Split documents into chunks
    splits = []
    for doc in documents:
        chunks = text_splitter.split_text(doc.page_content)
        for chunk in chunks:
            splits.append(Document(page_content=chunk, metadata=doc.metadata))

    logger.info(f"Split {len(documents)} documents into {len(splits)} chunks")

    # Map: Summarize each chunk
    map_template = """You are an expert financial analyst specializing in SEC filings.
    Summarize the following section of an SEC filing, focusing on key financial information, 
    risk factors, business developments, and material changes:
    
    {text}
    
    Provide a concise, factual summary focusing on financial data, significant events, and risks:"""
    map_prompt = PromptTemplate.from_template(map_template)

    map_chain = map_prompt | llm | StrOutputParser()

    # Reduce: Combine summaries
    reduce_template = """You are an expert financial analyst reviewing SEC filings.
    Below are summaries from different sections of an SEC 10-Q filing.
    Create a comprehensive analytical summary that covers:
    
    1. Company overview and business description
    2. Financial performance and key metrics
    3. Balance sheet highlights and changes
    4. Cash flow information
    5. Material events and developments
    6. Risk factors and contingencies
    7. Management's discussion and analysis
    
    The summary should be well-structured with clear sections and highlight the most important 
    information for potential investors.
    
    SECTION SUMMARIES:
    {summaries}
    
    COMPREHENSIVE SEC FILING ANALYSIS:"""
    reduce_prompt = PromptTemplate.from_template(reduce_template)

    reduce_chain = reduce_prompt | llm | StrOutputParser()

    # Execute map step
    logger.info("Starting map step...")
    mapped_results = []

    for i, split in enumerate(splits):
        logger.info(f"Processing chunk {i+1}/{len(splits)}...")

        result = map_chain.invoke({"text": split.page_content})
        logger.info(f"Chunk {i+1} summary: {result}")
        mapped_results.append(result)

    # Execute reduce step
    logger.info("Starting reduce step...")
    result = reduce_chain.invoke({"summaries": "\n\n".join(mapped_results)})

    return result


def main():
    """Main function to test map-reduce summarization of SEC filing"""
    # Set up logger
    set_identity("4k@gmail.com")

    # Load SEC filing
    logger.info(f"Loading SEC filing from edgar ...")
    documents = load_sec_filing("ACHR")
    logger.info(f"Loaded {len(documents)} documents")

    if not documents:
        logger.info("No documents to summarize")
        return

    # Run map-reduce summarization
    logger.info("Starting SEC filing summarization...")
    start_time = time.time()
    summary = map_reduce_summarize_sec_filing(documents)
    end_time = time.time()

    logger.info("\n" + "=" * 80)
    logger.info("SEC FILING SUMMARY:")
    logger.info("=" * 80)
    logger.info(summary)
    logger.info("=" * 80)
    logger.info(f"Summarization completed in {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
