"""
Simple high-level API for common PubSub use cases.

This module provides simplified functions for the most common use cases,
hiding the complexity of managers, clients, and registries.
"""

import logging
import signal
import sys
from typing import Callable, Optional

from .core.manager import PubSubManager
from .core.registry import get_registry

logger = logging.getLogger(__name__)


def run_pubsub_app(
    project_id: str,
    max_workers: int = 5,
    max_messages: int = 100,
    auto_create_resources: bool = True,
    clear_registry: bool = True,
    log_level: str = "INFO",
    on_startup: Optional[Callable] = None,
    on_shutdown: Optional[Callable] = None,
    **kwargs,
) -> None:
    """
    Run a PubSub application with all registered listeners.

    This is a simplified API that handles all the setup and teardown for you.
    Just decorate your listener classes with @pubsub_listener and their methods
    with @subscription, then call this function.

    Args:
        project_id: GCP project ID
        max_workers: Maximum number of worker threads (default: 5)
        max_messages: Maximum number of messages to pull at once (default: 100)
        auto_create_resources: Whether to automatically create missing topics/subscriptions (default: True)
        clear_registry: Whether to clear the registry on start (default: True, recommended for development)
        log_level: Logging level (default: "INFO")
        on_startup: Optional callback to run after startup
        on_shutdown: Optional callback to run before shutdown
        **kwargs: Additional arguments passed to PubSubManager

    Example:
        from gcp_pubsub_events import pubsub_listener, subscription, run_pubsub_app

        @pubsub_listener
        class MyService:
            @subscription("my-subscription")
            def handle_message(self, data: dict, ack):
                print(f"Received: {data}")
                ack.ack()

        # Create instance (this registers it automatically)
        service = MyService()

        # Run the app
        run_pubsub_app("my-project-id")
    """
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create manager
    manager = PubSubManager(
        project_id=project_id,
        max_workers=max_workers,
        max_messages=max_messages,
        auto_create_resources=auto_create_resources,
        clear_registry_on_start=clear_registry,
        **kwargs,
    )

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        manager.stop()
        if on_shutdown:
            on_shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Check if any listeners are registered
        registry = get_registry()
        if not registry.get_all_subscriptions():
            logger.warning("No subscriptions registered! Make sure to:")
            logger.warning("1. Decorate your classes with @pubsub_listener")
            logger.warning("2. Decorate your methods with @subscription('subscription-name')")
            logger.warning(
                "3. Create instances of your listener classes before calling run_pubsub_app()"
            )
            return

        # Start the manager
        logger.info(f"Starting PubSub app for project: {project_id}")
        manager.start()

        # Run startup callback
        if on_startup:
            on_startup()

        logger.info("PubSub app is running. Press Ctrl+C to stop.")

        # Keep the main thread alive
        import time

        while manager.is_running:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Error running PubSub app: {e}", exc_info=True)
    finally:
        # Ensure cleanup
        if manager.is_running:
            manager.stop()
        if on_shutdown:
            on_shutdown()
        logger.info("PubSub app stopped")


def quick_listen(
    project_id: str,
    subscription_name: str,
    handler: Callable,
    event_type: Optional[type] = None,
    **kwargs,
) -> None:
    """
    Quickly listen to a single subscription with a handler function.

    This is the simplest possible API - just provide a project, subscription,
    and handler function.

    Args:
        project_id: GCP project ID
        subscription_name: Name of the subscription to listen to
        handler: Function to handle messages. Should accept (event, ack) parameters.
        event_type: Optional type for automatic deserialization
        **kwargs: Additional arguments passed to run_pubsub_app

    Example:
        from gcp_pubsub_events import quick_listen

        def handle_message(data, ack):
            print(f"Received: {data}")
            ack.ack()

        quick_listen("my-project", "my-subscription", handle_message)
    """
    from .decorators import pubsub_listener, subscription

    # Create a dynamic listener class
    @pubsub_listener
    class QuickListener:
        @subscription(subscription_name, event_type)
        def handle(self, event, ack):
            handler(event, ack)

    # Create instance to register it
    QuickListener()

    # Run the app
    run_pubsub_app(project_id, **kwargs)
