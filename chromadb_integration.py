from datetime import datetime, timedelta
import json
import functools

import chromadb

class ChromaDBSaver:
    def __init__(self, collection_name: str, persist_directory: str = "chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.collection_name = collection_name
        self.cleanup_documents()

    def cleanup_documents(self):
        # Retrieve all documents with metadata from the collection
        try:
            results = self.collection.get()
        except Exception as e:
            print(f"[DEBUG] Unable to retrieve documents for cleanup: {e}")
            return

        now = datetime.now()
        expired_ids = []
        for doc_id, metadata in zip(results.get("ids", []), results.get("metadatas", [])):
            if metadata and "expires_at" in metadata:
                try:
                    expires_at = datetime.fromisoformat(metadata["expires_at"])
                    if expires_at < now:
                        expired_ids.append(doc_id)
                except Exception as e:
                    print(f"[DEBUG] Error parsing expiration for doc {doc_id}: {e}")
        if expired_ids:
            try:
                self.collection.delete(ids=expired_ids)
                print(f"[DEBUG] Cleaned up {len(expired_ids)} expired documents.")
            except Exception as e:
                print(f"[DEBUG] Error deleting expired documents: {e}")

    def add_document(self, document: dict, doc_id: str, expires_at: datetime = None):
        # Optionally add an expiration timestamp into metadata.
        metadata = document.copy()
        if expires_at:
            metadata['expires_at'] = expires_at.isoformat()
        self.collection.add(
            documents=[json.dumps(document)],
            metadatas=[metadata],
            ids=[doc_id]
        )
        print(f"[DEBUG] Document inserted with id {doc_id} into collection {self.collection.name}")

def chromadb_insert(collection_name: str, ttl_seconds: int = None):
    """
    A decorator that:
    - calls the decorated function,
    - expects a dict as a return value,
    - builds a unique document key (using 'symbol' and current timestamp),
    - sets a default expiration time to one week unless ttl_seconds is provided,
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
            # Set default TTL to one week (7 days) if none is provided.
            if ttl_seconds is None:
                ttl_seconds = 7 * 24 * 3600
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            saver = ChromaDBSaver(collection_name)
            saver.add_document(result, doc_id, expires_at)
            return result
        return wrapper
    return decorator