"""
GCP PubSub Events - A decorator-based library for handling Google Cloud Pub/Sub messages
"""

from .core.acknowledgement import Acknowledgement
from .core.client import PubSubClient, create_pubsub_app
from .core.manager import PubSubManager, async_pubsub_manager, pubsub_manager
from .core.registry import PubSubRegistry
from .core.resources import ResourceManager, create_resource_manager
from .decorators import pubsub_listener, subscription
from .simple import quick_listen, run_pubsub_app

__version__ = "1.3.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

__all__ = [
    "pubsub_listener",
    "subscription",
    "Acknowledgement",
    "PubSubClient",
    "create_pubsub_app",
    "PubSubRegistry",
    "PubSubManager",
    "pubsub_manager",
    "async_pubsub_manager",
    "ResourceManager",
    "create_resource_manager",
    "run_pubsub_app",
    "quick_listen",
]
