import os
import uuid
from datetime import datetime
from typing import List

import trafilatura
from ollama import Client
from logger import get_logger

logger = get_logger(__name__)

# Initialize a local Ollama client for embedding and query synthesis.
ollama_client = Client(
    host="http://127.0.0.1:11434",
    timeout=300,
)

class SECAnalyzer:
    def __init__(self, chunk_size: int = 512, persist_directory: str = "chroma_db_sec"):
        self.chunk_size = chunk_size
        # Create or connect to a persistent chromadb instance.

    def process_filing(self, html_file: str, symbol: str, filing_type: str):
        """
        Process a SEC filing HTML file:
        - Extract text using trafilatura.
        - Chunk the text.
        - For each chunk, compute an embedding.
        - Store chunks with embeddings into a Chromadb collection.
        """
        # Read and extract content.
        with open(html_file, encoding="utf-8") as f:
            html_content = f.read()
        extracted_text = trafilatura.extract(html_content)
        if not extracted_text:
            raise ValueError("Failed to extract text from the HTML.")

        # Chunk the text.
        chunks = self.chunk_text(extracted_text, self.chunk_size)

        # Define collection name per symbol and filing_type.
        collection_name = f"{symbol}_{filing_type}"
        collection = self.chroma_client.get_or_create_collection(collection_name)

        # Process each chunk: get embedding and store.
        document_ids = []
        documents = []
        embeddings = []

        for chunk in chunks:
            emb = self.get_embedding(chunk)
            doc_id = f"{symbol}_{uuid.uuid4().hex}"
            document_ids.append(doc_id)
            documents.append(chunk)
            embeddings.extend(emb)

        # Insert chunks into Chromadb.
        collection.add(
            documents=documents,
            metadatas=[{"ingested_at": datetime.now().isoformat()} for _ in documents],
            ids=document_ids,
            embeddings=embeddings
        )
        logger.debug(f"Processed filing and stored {len(documents)} chunks in collection '{collection_name}'.")

    def query_filing(self, symbol: str, filing_type: str, query: str, top_k: int = 5) -> str:
        """
        Query the filing by:
        - Generating a query embedding.
        - Searching the appropriate Chromadb collection.
        - Combining the retrieved chunks and using a local LLM to answer.
        """
        collection_name = f"{symbol}_{filing_type}"
        collection = self.chroma_client.get_or_create_collection(collection_name)

        # Generate query embedding.
        query_embedding = self.get_embedding(query)
        results = collection.query(query_embeddings=query_embedding, n_results=top_k)

        # Combine retrieved chunks.
        retrieved_chunks = " ".join(results.get("documents", [])[0])
        if not retrieved_chunks:
            return "No relevant information found in the filing."

        # Call local LLM (e.g., fine-tuned LLAMA3.1-8B) to synthesize answer.
        synthesis_prompt = (
            f"Using the excerpts from a SEC filing, answer the query below in a concise, technical way, mention figures and entities:\n\n"
            f"Query: {query}\n\n"
            f"Excerpts:\n{retrieved_chunks}\n\n"
        )
        response = ollama_client.generate(
            prompt=synthesis_prompt,
            model="plutus8b",
            options={"temperature": 0.05},
        )
        answer = response.response.strip()
        return answer

    def chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """
        A simple chunking method that splits text into chunks with approximately
        'chunk_size' words.
        """
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            chunks.append(chunk)
        return chunks

    def get_embedding(self, text: str) -> List[float]:
        """
        Compute an embedding for the text using a locally available Ollama embedding model.
        Assumes the model returns a JSON object with an "embedding" key containing a list of floats.
        """
        response = ollama_client.embed(
            input=text,
            model="mxbai-embed-large",
        )
        try:
            embeddings = response.get("embeddings")
            if embeddings is None:
                raise ValueError("Embeddings key not found in response.")
        except Exception as e:
            raise ValueError(f"Failed to parse embedding: {e}")
        return embeddings

if __name__ == "__main__":
    # Instantiate the analyzer.
    analyzer = SECAnalyzer()

    # Determine the path to the HTML filing.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_file_path = os.path.join(current_dir, "sec_filings", "tclg-10q.html")

    logger.debug(f"Loading filing from {html_file_path}")

    # Process the filing using trafilatura for text extraction.
    analyzer.process_filing(html_file_path, symbol="TCLG", filing_type="10q")
    logger.debug(analyzer.query_filing("TCLG", "10q", "What are the key financial figures reported for the recent quarter?"))
