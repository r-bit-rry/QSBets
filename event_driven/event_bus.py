"""
Asynchronous event bus implementation for the QSBets event-driven architecture.
"""
import asyncio
import json
import os
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, TypeVar, Coroutine, Union, Optional

from logger import get_logger

T = TypeVar('T')
EventHandler = Union[
    Callable[[Dict[str, Any]], None],       
    Callable[[Dict[str, Any]], Coroutine]   
]

class EventType(Enum):
    """System event types"""
    # Core architecture events
    STOCK_REQUEST = "stock_request"
    ANALYSIS_COMPLETE = "analysis_complete"
    
    # Telegram events
    TELEGRAM_MESSAGE = "telegram_message"
    TELEGRAM_COMMAND = "telegram_command"

class EventBus:
    """
    Singleton event bus that manages event publishing and subscription
    with support for async processing and optional persistence.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Set up the event bus initial state"""
        self.logger = get_logger("event_bus")
        self.subscribers = {event_type: [] for event_type in EventType}
        self.event_queues = {}
        self.running = False
        self.persist_dir = os.path.join(os.getcwd(), ".events")
        os.makedirs(self.persist_dir, exist_ok=True)
        self.worker_tasks = []
        self.loop = None
        self.persistence_enabled = False
        
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for a specific event type"""
        self.subscribers[event_type].append(handler)
        
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a handler from a specific event type"""
        if handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
    
    def publish(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """
        Send an event to all subscribers.
        Thread-safe - can be called from any thread.
        """
        event_id = str(uuid.uuid4())
        enriched_data = {
            **data,
            "_event_id": event_id,
            "_timestamp": datetime.now().isoformat(),
            "_event_type": event_type.value
        }
        
        if self.persistence_enabled:
            self._save_event_to_disk(event_type, enriched_data)
        
        if self.loop and self.running:
            asyncio.run_coroutine_threadsafe(
                self.event_queues[event_type].put(enriched_data), 
                self.loop
            )
        else:
            self.logger.warning(f"Event bus not running, event {event_type} not processed")
            
    def enable_persistence(self, enabled=True):
        """Toggle event persistence to disk"""
        self.persistence_enabled = enabled
        
    def _save_event_to_disk(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Save event data to disk for recovery"""
        file_path = os.path.join(
            self.persist_dir, 
            f"{event_type.value}_{data['_event_id']}.json"
        )
        with open(file_path, 'w') as f:
            json.dump(data, f)
    
    async def _process_events(self, event_type: EventType) -> None:
        """Process events of a specific type"""
        queue = self.event_queues[event_type]
        
        while self.running:
            try:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                
                for handler in self.subscribers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event_data)
                        else:
                            await asyncio.to_thread(handler, event_data)
                    except Exception as e:
                        self.logger.error(f"Handler error for {event_type}: {e}", exc_info=True)
                
                queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Event loop error for {event_type}: {e}", exc_info=True)
    
    def start(self) -> None:
        """Start the event bus"""
        if self.running:
            return
            
        self.running = True
        self.loop = self._get_or_create_event_loop()
        
        # Create queues and start workers for each event type
        for event_type in EventType:
            self.event_queues[event_type] = asyncio.Queue()
            task = self.loop.create_task(self._process_events(event_type))
            self.worker_tasks.append(task)
            
        self.logger.info("Event bus started")
    
    def _get_or_create_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get existing event loop or create a new one"""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def start_background_loop(self) -> None:
        """Start the event loop in a background thread"""
        if self.loop and self.loop.is_running():
            return
        
        def run_event_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
            
        threading.Thread(target=run_event_loop, daemon=True).start()
        self.logger.info("Event bus background loop started")
    
    def stop(self) -> None:
        """Stop the event bus"""
        if not self.running:
            return
            
        self.logger.info("Stopping event bus...")
        self.running = False
        
        if self.loop and self.loop.is_running():
            for task in self.worker_tasks:
                task.cancel()
                
            asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
    
    async def _shutdown(self) -> None:
        """Clean shutdown of the event loop"""
        try:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
        self.loop.stop()
        self.logger.info("Event bus stopped")
