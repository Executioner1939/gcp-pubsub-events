"""
Decorator for marking classes as PubSub listeners
"""

from functools import wraps
from ..core.registry import get_registry


def pubsub_listener(cls):
    """
    Class decorator to mark a class as a PubSub listener.
    
    Usage:
        @pubsub_listener
        class PaymentEventService:
            pass
    """
    registry = get_registry()
    
    def __init_wrapper(original_init):
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            registry.register_listener(self)
        return new_init
    
    # Wrap the __init__ method
    if hasattr(cls, '__init__'):
        cls.__init__ = __init_wrapper(cls.__init__)
    else:
        # If no __init__, create one
        def __init__(self, *args, **kwargs):
            super(cls, self).__init__()
            registry.register_listener(self)
        cls.__init__ = __init__
    
    return cls