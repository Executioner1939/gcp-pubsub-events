"""
Decorator for marking methods as subscription handlers
"""

from typing import Optional, Type


def subscription(subscription_name: str, event_type: Optional[Type] = None):
    """
    Method decorator to mark a method as a subscription handler.
    
    Args:
        subscription_name: The name of the Pub/Sub subscription
        event_type: Optional event type class for automatic deserialization
    
    Usage:
        @subscription("payments.user.registered")
        def on_registration(self, event: RegistrationEvent, acknowledgement: Acknowledgement):
            pass
    """
    def decorator(func):
        func._subscription_config = {
            'subscription_name': subscription_name,
            'event_type': event_type
        }
        return func
    return decorator