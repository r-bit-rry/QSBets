from datetime import datetime
import json
import functools

import chromadb
from chromadb.config import Settings

class ChromaDBSaver:
    def __init__(self, collection_name: str, persist_directory: str = "chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(collection_name)
    
    def add_document(self, document: dict, doc_id: str):
        # Convert document to a JSON string for the vector search, store the original dict as metadata.
        self.collection.add(
            documents=[json.dumps(document)],
            metadatas=[document],
            ids=[doc_id]
        )
        print(f"[DEBUG] Document inserted with id {doc_id} into collection {self.collection.name}")

def chromadb_insert(collection_name: str):
    """
    A decorator that:
    - calls the decorated function,
    - expects a dict as a return value,
    - builds a unique document key (using 'symbol' and current timestamp),
    - and saves the document in the ChromaDB collection.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not isinstance(result, dict):
                raise ValueError("Return value of the decorated function must be a dictionary.")
            # Use the 'symbol' field and current timestamp to build a unique key.
            symbol = result.get("symbol", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            doc_id = f"{symbol}_{timestamp}"
            saver = ChromaDBSaver(collection_name)
            saver.add_document(result, doc_id)
            return result
        return wrapper
    return decorator