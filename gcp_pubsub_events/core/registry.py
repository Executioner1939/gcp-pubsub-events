"""
Registry for managing PubSub listeners and their subscription handlers
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PubSubRegistry:
    """
    Manages the registration and handling of Pub/Sub listeners and subscriptions.

    The PubSubRegistry class is responsible for managing Pub/Sub system components, such as
    listener instances and their associated subscriptions. It provides a way to register
    listeners, scan for subscription handlers, retrieve handlers for specific subscriptions,
    view all registered subscriptions, and clear all registry data.
    """
    
    def __init__(self):
        self.listeners: List[Any] = []
        self.subscriptions: Dict[str, List[Dict]] = {}
    
    def register_listener(self, instance: Any):
        """
        Registers a listener to the current instance. The provided instance will be
        added to the list of listeners, and its subscriptions will be scanned to ensure
        proper handling. This method enables dynamic interaction with listeners and
        their corresponding subscriptions.

        Args:
            instance: Any
                The instance to be registered as a listener.

        """
        self.listeners.append(instance)
        self._scan_subscriptions(instance)
    
    def _scan_subscriptions(self, instance: Any):
        """
        Scans instance methods for subscription configurations and registers them as subscription
        handlers within the application's subscription registry.

        This function inspects all methods of the given instance to determine if they are marked
        with a subscription configuration attribute (`_subscription_config`). For each eligible
        method, it extracts the configuration, organizes the subscription registry, and logs the
        registration of the handler.

        Parameters:
            instance (Any): An object instance whose methods are to be inspected for subscription
                configurations.

        Raises:
            None

        Returns:
            None
        """
        for method_name in dir(instance):
            method = getattr(instance, method_name)
            if hasattr(method, '_subscription_config'):
                config = method._subscription_config
                subscription_name = config['subscription_name']
                
                if subscription_name not in self.subscriptions:
                    self.subscriptions[subscription_name] = []
                
                self.subscriptions[subscription_name].append({
                    'handler': method,
                    'instance': instance,
                    'event_type': config.get('event_type')
                })
                
                logger.info(f"Registered subscription handler: {subscription_name} -> {instance.__class__.__name__}.{method_name}")
    
    def get_handlers(self, subscription_name: str) -> List[Dict]:
        """
        Retrieve a list of handlers for a given subscription.

        This method looks up the provided subscription name in the subscriptions
        dictionary and returns its associated handlers. If the subscription name
        does not exist in the dictionary, an empty list is returned.

        Args:
            subscription_name: Name of the subscription whose handlers are being
                retrieved.

        Returns:
            List containing dictionaries that represent the handlers associated
            with the subscription name. If the subscription name is not found,
            an empty list is returned.
        """
        return self.subscriptions.get(subscription_name, [])
    
    def get_all_subscriptions(self) -> Dict[str, List[Dict]]:
        """
        Returns a copy of all subscriptions.

        This method provides an immutable copy of the subscriptions, allowing access
        to the information without modifying the original subscription data.

        Returns
        -------
        Dict[str, List[Dict]]
            A copy of the current subscriptions stored as a dictionary, where keys
            are subscription identifiers, and values are lists of subscription
            details represented as dictionaries.
        """
        return self.subscriptions.copy()
    
    def clear(self):
        """
        Clears all registered listeners and subscriptions for the current object. This ensures that the registry is emptied
        and ready for reuse without retaining any existing data. Logs an informational message indicating that the registry
        has been cleared.

        Raises:
            None

        Returns:
            None
        """
        self.listeners.clear()
        self.subscriptions.clear()
        logger.info("Registry cleared")


# Global registry instance
_registry = PubSubRegistry()


def get_registry() -> PubSubRegistry:
    """Get the global registry instance."""
    return _registry