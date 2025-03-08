"""
Event bus implementation for the QSBets event-driven architecture.
Implements an asynchronous event bus for improved performance.
"""
import asyncio
import json
import os
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, TypeVar, Coroutine, Union

# Type for event handlers
T = TypeVar('T')
EventHandler = Union[
    Callable[[Dict[str, Any]], None],            # Synchronous handler
    Callable[[Dict[str, Any]], Coroutine]        # Asynchronous handler
]

class EventType(Enum):
    """Types of events in the system"""
    # Core events for the three-loop architecture
    STOCK_REQUEST = "stock_request"              # Request to analyze a stock
    ANALYSIS_COMPLETE = "analysis_complete"      # Analysis result is ready
    
    # Telegram integration events
    TELEGRAM_MESSAGE = "telegram_message"        # Send a message to Telegram
    TELEGRAM_COMMAND = "telegram_command"        # Process a command from Telegram

class EventBus:
    """
    Central event bus that manages event publishing and subscription.
    Provides both in-memory queuing and persistence with async support.
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
        """Initialize the event bus components"""
        self.subscribers: Dict[EventType, List[EventHandler]] = {et: [] for et in EventType}
        self.event_queues: Dict[EventType, asyncio.Queue] = {}
        self.running = False
        self.persist_dir = os.path.join(os.getcwd(), ".events")
        os.makedirs(self.persist_dir, exist_ok=True)
        self._worker_tasks: List[asyncio.Task] = []
        self._loop = None
        self._enable_persistence = False  # Default to not persist events
        
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe a handler from a specific event type"""
        if event_type in self.subscribers and handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
    
    def publish(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """
        Publish an event to all subscribers.
        This method can be called from any thread.
        """
        # Add metadata to the event
        event_data = data.copy()
        event_data["_event_id"] = str(uuid.uuid4())
        event_data["_timestamp"] = datetime.now().isoformat()
        event_data["_event_type"] = event_type.value
        
        # Persist event if enabled
        if self._enable_persistence:
            self._persist_event(event_type, event_data)
        
        # Add to queue - using thread-safe method to add to async queue from any thread
        if self._loop and self.running:
            asyncio.run_coroutine_threadsafe(
                self.event_queues[event_type].put(event_data), 
                self._loop
            )
        else:
            # If event bus not started, log warning - this is helpful for debugging
            print(f"Warning: Event bus not running, event {event_type} not processed")
            
    def enable_persistence(self, enabled=True):
        """Enable or disable event persistence"""
        self._enable_persistence = enabled
        
    def _persist_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Persist an event to disk for recovery"""
        event_file = os.path.join(
            self.persist_dir, 
            f"{event_type.value}_{data['_event_id']}.json"
        )
        with open(event_file, 'w') as f:
            json.dump(data, f)
    
    async def _process_events(self, event_type: EventType) -> None:
        """Process events for a specific type in a separate task"""
        while self.running:
            try:
                # Wait for an event with timeout to allow for clean shutdown
                try:
                    event_data = await asyncio.wait_for(
                        self.event_queues[event_type].get(), 
                        timeout=0.5
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the event with all registered handlers
                for handler in self.subscribers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            # Async handler
                            await handler(event_data)
                        else:
                            # Sync handler - run in executor to avoid blocking
                            await asyncio.to_thread(handler, event_data)
                    except Exception as e:
                        print(f"Error handling event {event_type}: {e}")
                
                # Mark as done
                self.event_queues[event_type].task_done()
                
            except Exception as e:
                print(f"Error in event processing loop for {event_type}: {e}")
    
    def start(self) -> None:
        """Start the event bus"""
        if self.running:
            return
            
        self.running = True
        
        # Get or create event loop
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        
        # Create async queues
        for event_type in EventType:
            self.event_queues[event_type] = asyncio.Queue()
            
        # Start worker tasks for each event type
        for event_type in EventType:
            task = self._loop.create_task(self._process_events(event_type))
            self._worker_tasks.append(task)
            
        print("Event bus started")
    
    def start_background_loop(self) -> None:
        """Start the event loop in a background thread"""
        if self._loop and self._loop.is_running():
            return
            
        # Create a new thread for running the event loop
        def run_event_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
            
        loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        loop_thread.start()
        print("Event bus background loop started")
    
    def stop(self) -> None:
        """Stop the event bus"""
        if not self.running:
            return
            
        print("Stopping event bus...")
        self.running = False
        
        if self._loop and self._loop.is_running():
            # Cancel all tasks
            for task in self._worker_tasks:
                task.cancel()
                
            # Schedule stop of event loop
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
    
    async def _shutdown(self) -> None:
        """Shutdown the event loop cleanly"""
        # Wait for all tasks to complete with a timeout
        try:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
        # Stop the event loop
        self._loop.stop()
        print("Event bus stopped")
