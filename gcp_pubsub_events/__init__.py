"""
GCP PubSub Events - A decorator-based library for handling Google Cloud Pub/Sub messages
"""

from .decorators import pubsub_listener, subscription
from .core.acknowledgement import Acknowledgement
from .core.client import PubSubClient, create_pubsub_app
from .core.registry import PubSubRegistry
from .core.manager import PubSubManager, pubsub_manager, async_pubsub_manager
from .core.resources import ResourceManager, create_resource_manager

__version__ = "1.1.1"
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
]