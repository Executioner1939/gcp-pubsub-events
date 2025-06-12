"""
Subscription-related exceptions
"""

from .base import PubSubEventsError


class SubscriptionError(PubSubEventsError):
    """Raised when subscription-related operations fail."""
    pass