"""
PubSub Manager with context manager support for better integration.
"""

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional

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
        resource_config: Optional[Dict[str, Any]] = None,
        clear_registry_on_start: bool = False,
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
            clear_registry_on_start: Whether to clear the registry when starting (useful for development)
        """
        self.project_id = project_id
        self.max_workers = max_workers
        self.max_messages = max_messages
        self.flow_control_settings = flow_control_settings or {}
        self.auto_create_resources = auto_create_resources
        self.resource_config = resource_config or {}
        self.clear_registry_on_start = clear_registry_on_start

        self._client: Optional[PubSubClient] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._start_lock = threading.Lock()

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
        with self._start_lock:
            if self._running or (self._thread and self._thread.is_alive()):
                logger.warning("PubSub manager is already running")
                return

            logger.info("Starting PubSub manager...")

            # Clear registry if requested
            if self.clear_registry_on_start:
                from ..core.registry import get_registry

                registry = get_registry()
                registry.clear()
                logger.info("Registry cleared on startup")

            # Create client
            self._client = create_pubsub_app(
                self.project_id,
                max_workers=self.max_workers,
                max_messages=self.max_messages,
                auto_create_resources=self.auto_create_resources,
                resource_config=self.resource_config,
            )

            # Reset stop event
            self._stop_event.clear()

            # Start listening in background thread
            self._thread = threading.Thread(
                target=self._run_listener, name="PubSubManager-Listener", daemon=True
            )
            self._thread.start()
            self._running = True

            # Give it a moment to start
            time.sleep(0.1)
            logger.info("PubSub manager started successfully")

    def _run_listener(self) -> None:
        """Run the PubSub listener with stop event monitoring and error recovery."""
        max_retries = 5
        base_delay = 1.0  # seconds
        max_delay = 60.0  # seconds
        retry_count = 0

        while not self._stop_event.is_set() and retry_count < max_retries:
            try:
                # Start listening with stop callback
                logger.info(f"Starting PubSub listener (attempt {retry_count + 1}/{max_retries})")
                if self._client:
                    self._client.start_listening(stop_callback=lambda: self._stop_event.is_set())

                # If we exit normally (stop event), break the retry loop
                if self._stop_event.is_set():
                    logger.info("PubSub listener stopped by stop event")
                    break
                
                # If we reach here, the listener exited without stop event
                # This might be due to no subscriptions or other normal exit
                logger.info("PubSub listener exited normally")
                break

            except Exception as e:
                logger.error(f"Error in PubSub listener: {e}", exc_info=True)

                # If stop event is set, don't retry
                if self._stop_event.is_set():
                    logger.info("Stop event set, not retrying")
                    break

                retry_count += 1

                if retry_count < max_retries:
                    # Calculate exponential backoff with jitter
                    delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
                    thread_id = threading.current_thread().ident or 0
                    jitter = delay * 0.1 * (0.5 - thread_id % 10 / 10)
                    actual_delay = delay + jitter

                    logger.warning(
                        f"PubSub listener failed, retrying in {actual_delay:.1f}s (attempt {retry_count}/{max_retries})"
                    )

                    # Wait with stop event checking
                    if self._stop_event.wait(actual_delay):
                        logger.info("Stop event set during retry delay")
                        break
                else:
                    logger.error(f"PubSub listener failed after {max_retries} attempts, giving up")

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

        # Optional: Clear registry on stop if it was cleared on start
        # This helps ensure clean state between runs
        if self.clear_registry_on_start:
            from ..core.registry import get_registry

            registry = get_registry()
            registry.clear()
            logger.info("Registry cleared on shutdown")

        logger.info("PubSub manager stopped")

    def __enter__(self) -> 'PubSubManager':
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()

    async def __aenter__(self) -> 'PubSubManager':
        """Async context manager entry."""
        # Run start in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.start)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
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
    clear_registry_on_start: bool = False,
    **flow_control_settings: Any,
) -> Any:
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
        resource_config=resource_config,
        clear_registry_on_start=clear_registry_on_start,
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
    clear_registry_on_start: bool = False,
    **flow_control_settings: Any,
) -> Any:
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
        resource_config=resource_config,
        clear_registry_on_start=clear_registry_on_start,
    )

    try:
        await manager.__aenter__()
        yield manager
    finally:
        await manager.__aexit__(None, None, None)
