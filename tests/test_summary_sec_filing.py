import sys
import time
from typing import Any, Dict, List, Optional
import os

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.language_models import LLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ml_serving.config import initialize_model_server
from ml_serving.mlx_model_server import get_model_server
from edgar import Company, set_identity


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
            self.model_server = get_model_server(model_path)
        else:
            # Use default initialization
            initialize_model_server("mlx")
            self.model_server = get_model_server()
    
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
            SystemMessage(content="You are a helpful assistant that summarizes SEC filings and financial documents."),
            HumanMessage(content=prompt)
        ]
        
        # Use synchronous processing
        result = self.model_server.process_sync(messages)
        
        if "error" in result:
            raise RuntimeError(f"MLX model error: {result['error']}")
        
        return result.get("content", "")


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
        print(f"Error loading SEC filing: {e}")
        return []


def map_reduce_summarize_sec_filing(documents: List[Document], chunk_size: int = 8000):
    """Implement map-reduce summarization using langchain with SEC filing-specific prompts"""
    # Initialize the LLM
    llm = MLXServerLLM()
    
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
    
    print(f"Split {len(documents)} documents into {len(splits)} chunks")
    
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
    print("Starting map step...")
    mapped_results = []
    
    for i, split in enumerate(splits):
        print(f"Processing chunk {i+1}/{len(splits)}...")
        result = map_chain.invoke({"text": split.page_content})
        mapped_results.append(result)
        print(f"Chunk {i+1} processed")
    
    # Execute reduce step
    print("Starting reduce step...")
    result = reduce_chain.invoke({"summaries": "\n\n".join(mapped_results)})
    
    return result


def main():
    """Main function to test map-reduce summarization of SEC filing"""
    # Initialize model server
    print("Initializing MLX model server...")
    set_identity("4k@gmail.com")
    initialize_model_server("mlx")
    
    # Load SEC filing
    print(f"Loading SEC filing from edgar ...")
    documents = load_sec_filing("NVDA")
    print(f"Loaded {len(documents)} documents")
    
    if not documents:
        print("No documents to summarize")
        return
    
    # Run map-reduce summarization
    print("Starting SEC filing summarization...")
    start_time = time.time()
    summary = map_reduce_summarize_sec_filing(documents)
    end_time = time.time()
    
    print("\n" + "="*80)
    print("SEC FILING SUMMARY:")
    print("="*80)
    print(summary)
    print("="*80)
    print(f"Summarization completed in {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
