"""
PubSub Manager with context manager support for better integration.
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager, asynccontextmanager

from .client import PubSubClient, create_pubsub_app


logger = logging.getLogger(__name__)


class PubSubManager:
    """
    Enhanced PubSub manager with context manager support for better integration
    with web frameworks like FastAPI.
    
    Supports both sync and async context managers for proper lifecycle management.
    """
    
    def __init__(
        self,
        project_id: str,
        max_workers: int = 5,
        max_messages: int = 100,
        flow_control_settings: Optional[Dict[str, Any]] = None,
        auto_create_resources: bool = True,
        resource_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize PubSub manager.
        
        Args:
            project_id: GCP project ID
            max_workers: Maximum number of worker threads
            max_messages: Maximum number of messages to pull at once
            flow_control_settings: Flow control configuration
            auto_create_resources: Whether to automatically create missing resources
            resource_config: Configuration for resource creation
        """
        self.project_id = project_id
        self.max_workers = max_workers
        self.max_messages = max_messages
        self.flow_control_settings = flow_control_settings or {}
        self.auto_create_resources = auto_create_resources
        self.resource_config = resource_config or {}
        
        self._client: Optional[PubSubClient] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
    @property
    def client(self) -> Optional[PubSubClient]:
        """Get the underlying PubSub client."""
        return self._client
        
    @property
    def is_running(self) -> bool:
        """Check if the manager is currently running."""
        return self._running and self._thread is not None and self._thread.is_alive()
        
    def start(self) -> None:
        """Start the PubSub listener in a background thread."""
        if self._running:
            logger.warning("PubSub manager is already running")
            return
            
        logger.info("Starting PubSub manager...")
        
        # Create client
        self._client = create_pubsub_app(
            self.project_id,
            max_workers=self.max_workers,
            max_messages=self.max_messages,
            auto_create_resources=self.auto_create_resources,
            resource_config=self.resource_config
        )
        
        # Reset stop event
        self._stop_event.clear()
        
        # Start listening in background thread
        self._thread = threading.Thread(
            target=self._run_listener,
            name="PubSubManager-Listener",
            daemon=True
        )
        self._thread.start()
        self._running = True
        
        # Give it a moment to start
        time.sleep(0.1)
        logger.info("PubSub manager started successfully")
        
    def _run_listener(self) -> None:
        """Run the PubSub listener with stop event monitoring."""
        try:
            # Start listening with a reasonable timeout
            while not self._stop_event.is_set():
                try:
                    # Listen for a short period, then check stop event
                    self._client.start_listening(timeout=5.0)
                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.error(f"Error in PubSub listener: {e}")
                        time.sleep(1)  # Brief pause before retry
                    break
        except Exception as e:
            logger.error(f"Fatal error in PubSub listener thread: {e}")
        finally:
            logger.info("PubSub listener thread stopped")
            
    def stop(self, timeout: float = 10.0) -> None:
        """
        Stop the PubSub listener and cleanup resources.
        
        Args:
            timeout: Maximum time to wait for clean shutdown
        """
        if not self._running:
            logger.warning("PubSub manager is not running")
            return
            
        logger.info("Stopping PubSub manager...")
        
        # Signal stop
        self._stop_event.set()
        
        # Stop client
        if self._client:
            try:
                self._client.stop_listening()
            except Exception as e:
                logger.warning(f"Error stopping client: {e}")
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(f"PubSub listener thread did not stop within {timeout}s")
            else:
                logger.info("PubSub listener thread stopped cleanly")
        
        # Cleanup
        self._running = False
        self._thread = None
        self._client = None
        
        logger.info("PubSub manager stopped")
        
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        
    async def __aenter__(self):
        """Async context manager entry."""
        # Run start in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.start)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Run stop in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.stop)


@contextmanager
def pubsub_manager(
    project_id: str,
    max_workers: int = 5,
    max_messages: int = 100,
    auto_create_resources: bool = True,
    resource_config: Optional[Dict[str, Any]] = None,
    **flow_control_settings
):
    """
    Context manager for PubSub operations.
    
    Usage:
        with pubsub_manager("my-project") as manager:
            # Your application code here
            pass
    """
    manager = PubSubManager(
        project_id=project_id,
        max_workers=max_workers,
        max_messages=max_messages,
        flow_control_settings=flow_control_settings,
        auto_create_resources=auto_create_resources,
        resource_config=resource_config
    )
    
    try:
        manager.start()
        yield manager
    finally:
        manager.stop()


@asynccontextmanager
async def async_pubsub_manager(
    project_id: str,
    max_workers: int = 5,
    max_messages: int = 100,
    auto_create_resources: bool = True,
    resource_config: Optional[Dict[str, Any]] = None,
    **flow_control_settings
):
    """
    Async context manager for PubSub operations.
    
    Usage:
        async with async_pubsub_manager("my-project") as manager:
            # Your application code here
            pass
    """
    manager = PubSubManager(
        project_id=project_id,
        max_workers=max_workers,
        max_messages=max_messages,
        flow_control_settings=flow_control_settings,
        auto_create_resources=auto_create_resources,
        resource_config=resource_config
    )
    
    try:
        await manager.__aenter__()
        yield manager
    finally:
        await manager.__aexit__(None, None, None)