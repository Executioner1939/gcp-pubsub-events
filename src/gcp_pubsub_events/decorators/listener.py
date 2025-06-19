"""
Decorator for marking classes as PubSub listeners
"""

from functools import wraps
from typing import Any, Callable, Type, TypeVar

from ..core.registry import get_registry

C = TypeVar('C', bound=Type[Any])


def pubsub_listener(cls: C) -> C:
    """
    Class decorator to mark a class as a PubSub listener.

    Usage:
        @pubsub_listener
        class PaymentEventService:
            pass
    """
    registry = get_registry()

    def __init_wrapper(original_init: Callable[..., None]) -> Callable[..., None]:
        @wraps(original_init)
        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            registry.register_listener(self)

        return new_init

    # Store original init if it exists
    original_init = getattr(cls, "__init__", None)
    
    # Wrap the __init__ method
    if original_init:
        cls.__init__ = __init_wrapper(original_init)
    else:
        # If no __init__, create one
        cls.__init__ = __init_wrapper(lambda self: None)

    return cls
