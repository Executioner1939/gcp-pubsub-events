"""
Event serialization and deserialization utilities
"""

import logging
from typing import Any, Type

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = None
    ValidationError = None
    PYDANTIC_AVAILABLE = False


def deserialize_event(data: dict, event_type: Type) -> Any:
    """
    Deserializes a given dictionary into an instance of the specified event type.

    The function attempts to deserialize a dictionary into an object of the
    specified event type. It prioritizes the use of Pydantic models (if
    available and applicable), followed by a custom `from_dict` method,
    and lastly by attempting direct instantiation as a dataclass or a
    regular Python class.

    Parameters:
    data: dict
        The dictionary containing the event data to deserialize.
    event_type: Type
        The target type into which the event data should be deserialized.
        This can be a Pydantic model, a class with a `from_dict` method,
        or a data class/regular Python class with matching attributes.

    Returns:
    Any
        An instance of the event_type containing the deserialized data.

    Raises:
    ValidationError
        Raised when Pydantic validation fails for the provided data and
        event_type.
    Exception
        Raised when the deserialization process encounters general errors.
    """
    try:
        # Try Pydantic first if available and event_type is a Pydantic model
        if PYDANTIC_AVAILABLE and BaseModel and issubclass(event_type, BaseModel):
            return event_type.model_validate(data)
        
        # Try custom from_dict method
        elif hasattr(event_type, 'from_dict'):
            return event_type.from_dict(data)
        
        # Try dataclass or simple class instantiation
        else:
            return event_type(**data)
            
    except ValidationError as e:
        logger.error(f"Pydantic validation error for {event_type.__name__}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error deserializing event to {event_type.__name__}: {e}")
        raise