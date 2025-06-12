"""
Serialization-related exceptions
"""

from .base import PubSubEventsError


class SerializationError(PubSubEventsError):
    """Raised when event serialization/deserialization fails."""
    pass