"""
Resource management for automatic topic and subscription creation.
"""

import logging
from typing import Dict, Set, Optional, Any

from google.cloud import pubsub_v1
from google.api_core import exceptions


logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Manages PubSub topics and subscriptions with automatic creation capabilities.
    """
    
    def __init__(self, project_id: str, auto_create: bool = True):
        """
        Initialize the resource manager.
        
        Args:
            project_id: GCP project ID
            auto_create: Whether to automatically create missing resources
        """
        self.project_id = project_id
        self.auto_create = auto_create
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        
        # Cache to avoid repeated checks
        self._existing_topics: Set[str] = set()
        self._existing_subscriptions: Set[str] = set()
        self._checked_topics: Set[str] = set()
        self._checked_subscriptions: Set[str] = set()
    
    def ensure_topic_exists(self, topic_name: str, **topic_config) -> str:
        """
        Ensure a topic exists, creating it if necessary.
        
        Args:
            topic_name: Name of the topic
            **topic_config: Additional topic configuration options
            
        Returns:
            Topic path
            
        Raises:
            Exception: If topic creation fails and auto_create is False
        """
        topic_path = self.publisher.topic_path(self.project_id, topic_name)
        
        # Check cache first
        if topic_name in self._existing_topics:
            return topic_path
        
        # Skip check if we already verified it doesn't exist
        if topic_name not in self._checked_topics:
            if self._topic_exists(topic_path):
                self._existing_topics.add(topic_name)
                self._checked_topics.add(topic_name)
                return topic_path
            
            self._checked_topics.add(topic_name)
        
        # Topic doesn't exist
        if not self.auto_create:
            raise ValueError(f"Topic '{topic_name}' does not exist and auto_create is disabled")
        
        # Create the topic
        try:
            logger.info(f"Creating topic: {topic_path}")
            
            # Prepare topic configuration
            topic_config_obj = {}
            if topic_config:
                # Handle common topic settings
                if 'message_retention_duration' in topic_config:
                    topic_config_obj['message_retention_duration'] = topic_config['message_retention_duration']
                if 'schema_settings' in topic_config:
                    topic_config_obj['schema_settings'] = topic_config['schema_settings']
            
            topic = self.publisher.create_topic(
                request={
                    "name": topic_path,
                    **topic_config_obj
                }
            )
            
            self._existing_topics.add(topic_name)
            logger.info(f"Successfully created topic: {topic.name}")
            return topic_path
            
        except exceptions.AlreadyExists:
            # Race condition - topic was created by another process
            self._existing_topics.add(topic_name)
            logger.debug(f"Topic already exists: {topic_path}")
            return topic_path
            
        except Exception as e:
            logger.error(f"Failed to create topic '{topic_name}': {e}")
            raise
    
    def ensure_subscription_exists(
        self, 
        subscription_name: str, 
        topic_name: str,
        **subscription_config
    ) -> str:
        """
        Ensure a subscription exists, creating it if necessary.
        
        Args:
            subscription_name: Name of the subscription
            topic_name: Name of the topic to subscribe to
            **subscription_config: Additional subscription configuration
            
        Returns:
            Subscription path
            
        Raises:
            Exception: If subscription creation fails and auto_create is False
        """
        subscription_path = self.subscriber.subscription_path(self.project_id, subscription_name)
        
        # Check cache first
        if subscription_name in self._existing_subscriptions:
            return subscription_path
        
        # Skip check if we already verified it doesn't exist
        if subscription_name not in self._checked_subscriptions:
            if self._subscription_exists(subscription_path):
                self._existing_subscriptions.add(subscription_name)
                self._checked_subscriptions.add(subscription_name)
                return subscription_path
            
            self._checked_subscriptions.add(subscription_name)
        
        # Subscription doesn't exist
        if not self.auto_create:
            raise ValueError(f"Subscription '{subscription_name}' does not exist and auto_create is disabled")
        
        # Ensure topic exists first
        topic_path = self.ensure_topic_exists(topic_name)
        
        # Create the subscription
        try:
            logger.info(f"Creating subscription: {subscription_path} -> {topic_path}")
            
            # Prepare subscription configuration
            request = {
                "name": subscription_path,
                "topic": topic_path
            }
            
            # Handle common subscription settings
            if 'ack_deadline_seconds' in subscription_config:
                request['ack_deadline_seconds'] = subscription_config['ack_deadline_seconds']
            if 'retain_acked_messages' in subscription_config:
                request['retain_acked_messages'] = subscription_config['retain_acked_messages']
            if 'message_retention_duration' in subscription_config:
                request['message_retention_duration'] = subscription_config['message_retention_duration']
            if 'dead_letter_policy' in subscription_config:
                request['dead_letter_policy'] = subscription_config['dead_letter_policy']
            if 'retry_policy' in subscription_config:
                request['retry_policy'] = subscription_config['retry_policy']
            if 'filter' in subscription_config:
                request['filter'] = subscription_config['filter']
            
            subscription = self.subscriber.create_subscription(request=request)
            
            self._existing_subscriptions.add(subscription_name)
            logger.info(f"Successfully created subscription: {subscription.name}")
            return subscription_path
            
        except exceptions.AlreadyExists:
            # Race condition - subscription was created by another process
            self._existing_subscriptions.add(subscription_name)
            logger.debug(f"Subscription already exists: {subscription_path}")
            return subscription_path
            
        except Exception as e:
            logger.error(f"Failed to create subscription '{subscription_name}': {e}")
            raise
    
    def ensure_resources_for_subscriptions(self, subscriptions: Dict[str, Any]) -> Dict[str, str]:
        """
        Ensure all topics and subscriptions exist for a set of subscription configs.
        
        Args:
            subscriptions: Dictionary mapping subscription names to handler configs
            
        Returns:
            Dictionary mapping subscription names to subscription paths
        """
        subscription_paths = {}
        
        for subscription_name, handlers in subscriptions.items():
            # For auto-creation, we need to derive the topic name
            # We'll use a convention: topic name = subscription name unless specified
            topic_name = subscription_name
            
            # Check if any handler specifies a different topic (via decorator or config)
            for handler_info in handlers:
                if 'topic_name' in handler_info:
                    topic_name = handler_info['topic_name']
                    break
            
            try:
                subscription_path = self.ensure_subscription_exists(
                    subscription_name, 
                    topic_name
                )
                subscription_paths[subscription_name] = subscription_path
                
            except Exception as e:
                logger.error(f"Failed to ensure resources for subscription '{subscription_name}': {e}")
                # Re-raise to fail fast
                raise
        
        return subscription_paths
    
    def _topic_exists(self, topic_path: str) -> bool:
        """Check if a topic exists."""
        try:
            self.publisher.get_topic(request={"topic": topic_path})
            return True
        except exceptions.NotFound:
            return False
        except Exception as e:
            logger.warning(f"Error checking topic existence '{topic_path}': {e}")
            return False
    
    def _subscription_exists(self, subscription_path: str) -> bool:
        """Check if a subscription exists."""
        try:
            self.subscriber.get_subscription(request={"subscription": subscription_path})
            return True
        except exceptions.NotFound:
            return False
        except Exception as e:
            logger.warning(f"Error checking subscription existence '{subscription_path}': {e}")
            return False
    
    def list_topics(self) -> list:
        """List all topics in the project."""
        try:
            project_path = f"projects/{self.project_id}"
            topics = []
            for topic in self.publisher.list_topics(request={"project": project_path}):
                topics.append(topic.name.split('/')[-1])  # Extract topic name
            return topics
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []
    
    def list_subscriptions(self) -> list:
        """List all subscriptions in the project."""
        try:
            project_path = f"projects/{self.project_id}"
            subscriptions = []
            for subscription in self.subscriber.list_subscriptions(request={"project": project_path}):
                subscriptions.append(subscription.name.split('/')[-1])  # Extract subscription name
            return subscriptions
        except Exception as e:
            logger.error(f"Failed to list subscriptions: {e}")
            return []


def create_resource_manager(project_id: str, auto_create: bool = True) -> ResourceManager:
    """
    Create a resource manager instance.
    
    Args:
        project_id: GCP project ID
        auto_create: Whether to automatically create missing resources
        
    Returns:
        ResourceManager instance
    """
    return ResourceManager(project_id, auto_create)