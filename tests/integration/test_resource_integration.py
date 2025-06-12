"""
Integration tests for automatic resource creation with PubSub emulator
"""

import pytest
import time
from datetime import datetime
from pydantic import BaseModel, Field

from gcp_pubsub_events import (
    pubsub_listener, 
    subscription, 
    Acknowledgement, 
    create_pubsub_app,
    ResourceManager,
    async_pubsub_manager
)


class AutoCreateEvent(BaseModel):
    """Test event for auto-creation testing."""
    id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now)


class TestResourceAutoCreation:
    """Test automatic resource creation with real PubSub emulator."""
    
    def test_auto_create_topic_and_subscription(self):
        """Test that missing topics and subscriptions are created automatically."""
        
        # Use unique names to avoid conflicts
        subscription_name = f"auto-test-sub-{int(time.time())}"
        
        @pubsub_listener
        class AutoCreateListener:
            def __init__(self):
                self.received_events = []
            
            @subscription(subscription_name, AutoCreateEvent)
            def handle_event(self, event: AutoCreateEvent, ack: Acknowledgement):
                self.received_events.append(event)
                ack.ack()
        
        listener = AutoCreateListener()
        
        # Create client with auto-creation enabled (default)
        client = create_pubsub_app("test-project", auto_create_resources=True)
        
        # This should create the topic and subscription automatically
        try:
            client.start_listening(timeout=1)
        except Exception:
            pass  # Timeout is expected
        finally:
            client.stop_listening()
        
        # Verify resources were created by checking they exist
        resource_manager = ResourceManager("test-project")
        
        # Check if topic exists (using subscription name as topic name by convention)
        topics = resource_manager.list_topics()
        assert subscription_name in topics
        
        # Check if subscription exists
        subscriptions = resource_manager.list_subscriptions()
        assert subscription_name in subscriptions
    
    def test_auto_create_disabled(self):
        """Test that auto-creation can be disabled."""
        
        subscription_name = f"no-auto-create-{int(time.time())}"
        
        @pubsub_listener
        class NoAutoCreateListener:
            @subscription(subscription_name, AutoCreateEvent)
            def handle_event(self, event: AutoCreateEvent, ack: Acknowledgement):
                pass
        
        listener = NoAutoCreateListener()
        
        # Create client with auto-creation disabled
        client = create_pubsub_app("test-project", auto_create_resources=False)
        
        # This should fail because resources don't exist
        with pytest.raises(Exception):
            client.start_listening(timeout=1)
    
    @pytest.mark.asyncio
    async def test_async_manager_auto_create(self):
        """Test auto-creation with async context manager."""
        
        subscription_name = f"async-auto-create-{int(time.time())}"
        
        @pubsub_listener
        class AsyncAutoCreateListener:
            def __init__(self):
                self.received_events = []
            
            @subscription(subscription_name, AutoCreateEvent)
            async def handle_event(self, event: AutoCreateEvent, ack: Acknowledgement):
                self.received_events.append(event)
                ack.ack()
        
        listener = AsyncAutoCreateListener()
        
        # Use async context manager
        async with async_pubsub_manager("test-project", auto_create_resources=True) as manager:
            # Give it time to start and create resources
            import asyncio
            await asyncio.sleep(2)
        
        # Verify resources were created
        resource_manager = ResourceManager("test-project")
        topics = resource_manager.list_topics()
        subscriptions = resource_manager.list_subscriptions()
        
        assert subscription_name in topics
        assert subscription_name in subscriptions
    
    def test_multiple_subscriptions_auto_create(self):
        """Test auto-creation with multiple subscriptions."""
        
        base_name = f"multi-auto-{int(time.time())}"
        sub1_name = f"{base_name}-1"
        sub2_name = f"{base_name}-2"
        
        @pubsub_listener
        class MultiAutoCreateListener:
            def __init__(self):
                self.received_events = []
            
            @subscription(sub1_name, AutoCreateEvent)
            def handle_event_1(self, event: AutoCreateEvent, ack: Acknowledgement):
                self.received_events.append(("sub1", event))
                ack.ack()
            
            @subscription(sub2_name, AutoCreateEvent)
            def handle_event_2(self, event: AutoCreateEvent, ack: Acknowledgement):
                self.received_events.append(("sub2", event))
                ack.ack()
        
        listener = MultiAutoCreateListener()
        
        # Create client with auto-creation
        client = create_pubsub_app("test-project", auto_create_resources=True)
        
        try:
            client.start_listening(timeout=1)
        except Exception:
            pass
        finally:
            client.stop_listening()
        
        # Verify both resources were created
        resource_manager = ResourceManager("test-project")
        topics = resource_manager.list_topics()
        subscriptions = resource_manager.list_subscriptions()
        
        assert sub1_name in topics
        assert sub2_name in topics
        assert sub1_name in subscriptions
        assert sub2_name in subscriptions


class TestResourceManagerDirect:
    """Test ResourceManager directly with emulator."""
    
    def test_resource_manager_create_topic(self):
        """Test direct topic creation with ResourceManager."""
        
        topic_name = f"direct-topic-{int(time.time())}"
        
        manager = ResourceManager("test-project", auto_create=True)
        
        # Topic shouldn't exist initially
        topics_before = manager.list_topics()
        assert topic_name not in topics_before
        
        # Create topic
        topic_path = manager.ensure_topic_exists(topic_name)
        assert topic_path == f"projects/test-project/topics/{topic_name}"
        
        # Verify topic was created
        topics_after = manager.list_topics()
        assert topic_name in topics_after
    
    def test_resource_manager_create_subscription(self):
        """Test direct subscription creation with ResourceManager."""
        
        base_name = f"direct-sub-{int(time.time())}"
        topic_name = f"{base_name}-topic"
        subscription_name = f"{base_name}-sub"
        
        manager = ResourceManager("test-project", auto_create=True)
        
        # Neither should exist initially
        topics_before = manager.list_topics()
        subs_before = manager.list_subscriptions()
        assert topic_name not in topics_before
        assert subscription_name not in subs_before
        
        # Create subscription (should also create topic)
        sub_path = manager.ensure_subscription_exists(subscription_name, topic_name)
        assert sub_path == f"projects/test-project/subscriptions/{subscription_name}"
        
        # Verify both were created
        topics_after = manager.list_topics()
        subs_after = manager.list_subscriptions()
        assert topic_name in topics_after
        assert subscription_name in subs_after
    
    def test_resource_manager_with_config(self):
        """Test resource creation with configuration."""
        
        base_name = f"config-test-{int(time.time())}"
        topic_name = f"{base_name}-topic"
        subscription_name = f"{base_name}-sub"
        
        manager = ResourceManager("test-project", auto_create=True)
        
        # Create topic first
        manager.ensure_topic_exists(topic_name)
        
        # Create subscription with configuration
        sub_path = manager.ensure_subscription_exists(
            subscription_name, 
            topic_name,
            ack_deadline_seconds=30,
            retain_acked_messages=True
        )
        
        assert sub_path == f"projects/test-project/subscriptions/{subscription_name}"
        
        # Verify subscription was created
        subs_after = manager.list_subscriptions()
        assert subscription_name in subs_after
    
    def test_resource_manager_caching(self):
        """Test that ResourceManager caches existence checks."""
        
        topic_name = f"cache-test-{int(time.time())}"
        
        manager = ResourceManager("test-project", auto_create=True)
        
        # First call should create topic
        topic_path1 = manager.ensure_topic_exists(topic_name)
        assert topic_name in manager._existing_topics
        
        # Second call should use cache (no API call)
        topic_path2 = manager.ensure_topic_exists(topic_name)
        assert topic_path1 == topic_path2
        assert topic_name in manager._existing_topics
    
    def test_resource_manager_no_auto_create_error(self):
        """Test ResourceManager raises error when auto_create is False."""
        
        topic_name = f"no-create-{int(time.time())}"
        
        manager = ResourceManager("test-project", auto_create=False)
        
        # Should raise error for non-existent topic
        with pytest.raises(ValueError, match="does not exist and auto_create is disabled"):
            manager.ensure_topic_exists(topic_name)


class TestResourceCreationEndToEnd:
    """End-to-end tests for resource creation with message flow."""
    
    def test_full_flow_with_auto_creation(self, pubsub_publisher):
        """Test complete flow: auto-create → publish → receive."""
        
        subscription_name = f"e2e-flow-{int(time.time())}"
        
        @pubsub_listener
        class E2EListener:
            def __init__(self):
                self.received_events = []
            
            @subscription(subscription_name, AutoCreateEvent)
            def handle_event(self, event: AutoCreateEvent, ack: Acknowledgement):
                self.received_events.append(event)
                ack.ack()
        
        listener = E2EListener()
        
        # Start client with auto-creation
        client = create_pubsub_app("test-project", auto_create_resources=True)
        
        import threading
        
        def run_client():
            try:
                client.start_listening(timeout=5)
            except Exception:
                pass
            finally:
                client.stop_listening()
        
        # Start client in background
        client_thread = threading.Thread(target=run_client, daemon=True)
        client_thread.start()
        
        # Give time for resources to be created
        time.sleep(2)
        
        # Publish test message
        test_event = AutoCreateEvent(
            id="e2e-test",
            message="End-to-end test message"
        )
        
        # Use the topic path that matches our subscription (by convention)
        topic_path = f"projects/test-project/topics/{subscription_name}"
        message_data = test_event.model_dump_json().encode('utf-8')
        
        future = pubsub_publisher.publish(topic_path, message_data)
        message_id = future.result(timeout=10)
        assert message_id
        
        # Wait for message processing
        time.sleep(3)
        
        # Stop client
        client.stop_listening()
        client_thread.join(timeout=5)
        
        # Verify message was received
        assert len(listener.received_events) > 0
        received = listener.received_events[0]
        assert received.id == "e2e-test"
        assert received.message == "End-to-end test message"