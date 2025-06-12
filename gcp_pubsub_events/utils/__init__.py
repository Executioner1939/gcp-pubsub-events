"""
Utility functions for GCP PubSub Events library
"""

from .serialization import deserialize_event

__all__ = [
    "deserialize_event",
]