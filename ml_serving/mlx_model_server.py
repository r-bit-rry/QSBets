"""
Thread-based MLX model server for parallel processing of requests.
"""
import os
import threading
import queue
import time
from typing import Dict, Any, Callable, List, Optional
import traceback
from dataclasses import dataclass

from ml_serving.model_base import ModelServer
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX
from logger import get_logger

# Constants
DEFAULT_NUM_WORKERS = 3
DEFAULT_TIMEOUT = 600  # seconds
MAX_QUEUE_SIZE = 200
QWQ_KWARGS = {"max_tokens": 64000, "verbose": True, "temp": 0.6, "top_p": 0.95, "min_p":0.00, "top_k": 40, "repetition_penalty": 1.0, "repetition_context_size": 20}

logger = get_logger(__name__)

@dataclass
class MLXRequest:
    """Represents a request for MLX processing"""
    id: str
    messages: List[Any]
    callback: Callable[[str, Dict[str, Any]], None]
    metadata: Dict[str, Any]


class MLXModelServer(ModelServer):
    """
    Thread-based MLX model server that processes multiple requests in parallel
    while keeping the model in memory and providing fresh contexts for each request.
    """
    model_path: str = None
    num_workers: int = DEFAULT_NUM_WORKERS
    request_queue: queue.Queue = None
    running: bool = False
    workers: List[threading.Thread] = None
    model_lock: threading.RLock = None
    llm: Optional[MLXPipeline] = None

    def __init__(self, model_path: str, num_workers: int = DEFAULT_NUM_WORKERS):
        """
        Initialize the MLX model server.
        
        Args:
            model_path: Path to the MLX model
            num_workers: Number of worker threads for parallel processing
        """
        super().__init__()
        self.model_path = model_path
        self.num_workers = num_workers
        self.request_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self.running = False
        self.workers = []

        # Load model once (shared across workers)
        logger.info(f"Loading MLX model from {model_path}...")
        self.llm = MLXPipeline.from_model_id(
            model_id=model_path, pipeline_kwargs={"max_tokens": 4096, "verbose": True}
        )
        logger.info("MLX model loaded successfully")

        # Initialize lock for model access
        self.model_lock = threading.RLock()

        # Start the server
        self.start()

    def _llm_type(self) -> str:
        return "mlx_server"

    def start(self):
        """Start the model server with worker threads"""
        if self.running:
            return

        self.running = True

        # Start worker threads
        self.workers = []
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"MLXWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        logger.info(f"MLX Model Server started with {self.num_workers} workers")

    def stop(self):
        """Stop the model server and all worker threads"""
        self.running = False

        # Wait for all worker threads to finish
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1.0)

        logger.info("MLX Model Server stopped")

    def submit_request(self, 
                      request_id: str,
                      messages: List[Any],
                      callback: Callable[[str, Dict[str, Any]], None],
                      metadata: Dict[str, Any] = None) -> bool:
        """
        Submit a request to the model server for processing
        
        Args:
            request_id: Unique identifier for this request
            messages: List of messages to process (SystemMessage, HumanMessage, etc)
            callback: Function to call with the result
            metadata: Additional metadata to pass along with the request
            
        Returns:
            True if request was accepted, False if queue is full
        """
        if not self.running:
            self.start()

        try:
            self.request_queue.put_nowait(MLXRequest(
                id=request_id,
                messages=messages,
                callback=callback,
                metadata=metadata or {}
            ))
            return True
        except queue.Full:
            logger.error(f"Request queue is full, rejecting request {request_id}")
            return False

    def process_sync(self, messages: List[Any], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a request synchronously
        
        Args:
            messages: List of messages to process
            metadata: Additional metadata
            
        Returns:
            Dictionary with model response
        """
        request_id = f"sync_{time.time()}"
        result_event = threading.Event()
        result_container = {}
        metadata = metadata or {}

        def on_complete(req_id, result):
            result_container['response'] = result
            result_event.set()

        self.submit_request(
            request_id=request_id,
            messages=messages,
            callback=on_complete,
            metadata=metadata
        )

        if not result_event.wait(timeout=DEFAULT_TIMEOUT):
            return {"error": "Request timed out", "metadata": metadata}

        return result_container['response']

    def _worker_loop(self):
        """Worker thread main loop"""
        thread_name = threading.current_thread().name
        logger.info(f"{thread_name} started")

        while self.running:
            try:
                # Get next request from queue with timeout
                try:
                    request = self.request_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                start_time = time.time()
                logger.info(f"{thread_name} processing request {request.id}")

                try:
                    # Create a new ChatMLX instance for this request to ensure a fresh context
                    with self.model_lock:
                        chat_mlx = ChatMLX(llm=self.llm)

                    # Process the request
                    response = chat_mlx.invoke(request.messages)

                    # Calculate processing time
                    proc_time = time.time() - start_time
                    logger.info(f"{thread_name} completed request {request.id} in {proc_time:.2f}s")

                    # Call the callback with the result
                    if request.callback:
                        request.callback(request.id, {
                            "content": response.content,
                            "metadata": request.metadata,
                            "processing_time": proc_time
                        })

                except Exception as e:
                    logger.error(f"{thread_name} error processing request {request.id}: {str(e)}")
                    traceback.print_exc()
                    # Call the callback with the error
                    if request.callback:
                        request.callback(request.id, {
                            "error": str(e),
                            "metadata": request.metadata
                        })
                finally:
                    self.request_queue.task_done()

            except Exception as e:
                logger.error(f"Unexpected error in {thread_name}: {str(e)}")
                traceback.print_exc()

        logger.info(f"{thread_name} stopped")

    def get_queue_size(self) -> int:
        """Get the current size of the request queue"""
        return self.request_queue.qsize()

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get stats about the request queue"""
        return {
            "queue_size": self.request_queue.qsize(),
            "queue_empty": self.request_queue.empty(),
            "queue_full": self.request_queue.full(),
            "max_queue_size": self.request_queue.maxsize,
            "num_workers": self.num_workers,
            "running": self.running
        }


# Singleton instance
_model_server = None

def get_model_server(model_path: str = None, num_workers: int = DEFAULT_NUM_WORKERS):
    """Get or create the singleton model server instance"""
    global _model_server
    
    if _model_server is None and model_path:
        _model_server = MLXModelServer(model_path, num_workers)
    
    return _model_server
