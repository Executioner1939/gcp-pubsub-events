"""
Python PubSub Listener Library
A decorator-based library for handling Google Cloud Pub/Sub messages similar to Micronaut's @PubSubListener
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
from google.cloud import pubsub_v1
import inspect


logger = logging.getLogger(__name__)


@dataclass
class Acknowledgement:
    """Handles message acknowledgement for Pub/Sub messages."""
    
    def __init__(self, message):
        self._message = message
        self._acknowledged = False
    
    def ack(self):
        """Acknowledge the message as successfully processed."""
        if not self._acknowledged:
            self._message.ack()
            self._acknowledged = True
            logger.debug(f"Message acknowledged: {self._message.message_id}")
    
    def nack(self):
        """Negative acknowledge the message (mark as failed)."""
        if not self._acknowledged:
            self._message.nack()
            self._acknowledged = True
            logger.debug(f"Message nacked: {self._message.message_id}")


class PubSubRegistry:
    """Registry to store subscription handlers and their metadata."""
    
    def __init__(self):
        self.listeners: List[Any] = []
        self.subscriptions: Dict[str, List[Dict]] = {}
    
    def register_listener(self, instance: Any):
        """Register a PubSub listener instance."""
        self.listeners.append(instance)
        self._scan_subscriptions(instance)
    
    def _scan_subscriptions(self, instance: Any):
        """Scan an instance for subscription handlers."""
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


# Global registry instance
_registry = PubSubRegistry()


def pubsub_listener(cls):
    """
    Class decorator to mark a class as a PubSub listener.
    
    Usage:
        @pubsub_listener
        class PaymentEventService:
            pass
    """
    def __init_wrapper(original_init):
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            _registry.register_listener(self)
        return new_init
    
    # Wrap the __init__ method
    if hasattr(cls, '__init__'):
        cls.__init__ = __init_wrapper(cls.__init__)
    else:
        # If no __init__, create one
        def __init__(self, *args, **kwargs):
            super(cls, self).__init__()
            _registry.register_listener(self)
        cls.__init__ = __init__
    
    return cls


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


class PubSubClient:
    """Main client for managing Pub/Sub subscriptions and message processing."""
    
    def __init__(self, project_id: str, max_workers: int = 10):
        self.project_id = project_id
        self.subscriber = pubsub_v1.SubscriberClient()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
    
    def start_listening(self):
        """Start listening to all registered subscriptions."""
        self.running = True
        futures = []
        
        for subscription_name, handlers in _registry.subscriptions.items():
            subscription_path = self.subscriber.subscription_path(
                self.project_id, subscription_name
            )
            
            logger.info(f"Starting to listen on subscription: {subscription_path}")
            
            def callback(message, handlers=handlers):
                self._process_message(message, handlers)
            
            # Configure flow control settings
            flow_control = pubsub_v1.types.FlowControl(max_messages=100)
            
            future = self.subscriber.subscribe(
                subscription_path, 
                callback=callback,
                flow_control=flow_control
            )
            futures.append(future)
        
        # Keep the main thread running
        try:
            logger.info("PubSub listener started. Press Ctrl+C to stop.")
            while self.running:
                for future in futures:
                    try:
                        future.result(timeout=1.0)
                    except TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Error in subscription: {e}")
        except KeyboardInterrupt:
            logger.info("Shutting down PubSub listener...")
            self.stop_listening()
            for future in futures:
                future.cancel()
    
    def stop_listening(self):
        """Stop listening to subscriptions."""
        self.running = False
        self.executor.shutdown(wait=True)
    
    def _process_message(self, message, handlers: List[Dict]):
        """Process a received message with the appropriate handlers."""
        try:
            # Parse message data
            data = json.loads(message.data.decode('utf-8'))
            acknowledgement = Acknowledgement(message)
            
            for handler_info in handlers:
                handler = handler_info['handler']
                event_type = handler_info.get('event_type')
                
                try:
                    # Prepare arguments for the handler
                    if event_type:
                        # Deserialize to event type
                        if hasattr(event_type, 'from_dict'):
                            event = event_type.from_dict(data)
                        else:
                            # Simple dataclass instantiation
                            event = event_type(**data)
                    else:
                        # Pass raw data
                        event = data
                    
                    # Check if handler is async
                    if inspect.iscoroutinefunction(handler):
                        asyncio.run(handler(event, acknowledgement))
                    else:
                        handler(event, acknowledgement)
                    
                    # If we get here without exception, handler succeeded
                    if not acknowledgement._acknowledged:
                        acknowledgement.ack()
                    break
                    
                except Exception as e:
                    logger.error(f"Error in handler {handler.__name__}: {e}", exc_info=True)
                    if not acknowledgement._acknowledged:
                        acknowledgement.nack()
                    break
                    
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            message.nack()


def create_pubsub_app(project_id: str, max_workers: int = 10) -> PubSubClient:
    """
    Create and configure a PubSub application.
    
    Args:
        project_id: Google Cloud project ID
        max_workers: Maximum number of worker threads
        
    Returns:
        Configured PubSubClient instance
    """
    return PubSubClient(project_id, max_workers)