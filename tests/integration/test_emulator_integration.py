"""
Integration tests with PubSub emulator
"""

import asyncio
import json
import time
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from gcp_pubsub_events import Acknowledgement, pubsub_listener, subscription


class EventModel(BaseModel):
    """Test event model."""

    id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now)
    sequence: int = Field(..., ge=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        return v.strip()


class TestIntegrationWithEmulator:
    """Integration tests with PubSub emulator."""

    def test_basic_message_flow(
        self,
        pubsub_client,
        pubsub_publisher,
        test_topic,
        test_subscription,
        test_listener,
        run_client,
        wait_for,
    ):
        """Test basic message publishing and receiving."""

        # Extract subscription name from path
        subscription_name = test_subscription.split("/")[-1]

        @pubsub_listener
        class MessageListener:
            def __init__(self, listener):
                self.listener = listener

            @subscription(subscription_name, EventModel)
            async def handle_message(self, event: EventModel, ack: Acknowledgement):
                start_time = time.time()
                self.listener.received_messages.append(event)
                processing_time = time.time() - start_time
                self.listener.processing_times.append(processing_time)
                ack.ack()

        # Create listener instance - this registers the handlers via decorators
        MessageListener(test_listener)

        # Start client
        run_client(pubsub_client, timeout=10)
        time.sleep(2)  # Let client start and register handlers

        # Publish test message
        test_event = EventModel(id="test-1", content="Hello World", sequence=1)
        message_data = test_event.model_dump_json().encode("utf-8")

        future = pubsub_publisher.publish(test_topic, message_data)
        message_id = future.result(timeout=10)
        assert message_id

        # Wait for message to be received
        assert wait_for(lambda: len(test_listener.received_messages) > 0, timeout=15)

        # Verify results
        assert len(test_listener.received_messages) == 1
        received = test_listener.received_messages[0]
        assert received.id == "test-1"
        assert received.content == "Hello World"
        assert received.sequence == 1
        assert len(test_listener.errors) == 0

    def test_multiple_messages(
        self,
        pubsub_client,
        pubsub_publisher,
        test_topic,
        test_subscription,
        test_listener,
        run_client,
        wait_for,
    ):
        """Test handling multiple messages."""

        # Extract subscription name from path
        subscription_name = test_subscription.split("/")[-1]

        @pubsub_listener
        class MultiMessageListener:
            def __init__(self, listener):
                self.listener = listener

            @subscription(subscription_name, EventModel)
            def handle_message(self, event: EventModel, ack: Acknowledgement):
                self.listener.received_messages.append(event)
                ack.ack()

        # Create listener
        MultiMessageListener(test_listener)

        # Start client
        run_client(pubsub_client, timeout=15)
        time.sleep(2)

        # Publish multiple messages
        message_count = 5
        for i in range(1, message_count + 1):
            test_event = EventModel(id=f"test-{i}", content=f"Message {i}", sequence=i)
            message_data = test_event.model_dump_json().encode("utf-8")
            future = pubsub_publisher.publish(test_topic, message_data)
            future.result(timeout=10)
            time.sleep(0.1)  # Small delay between messages

        # Wait for all messages
        assert wait_for(lambda: len(test_listener.received_messages) >= message_count, timeout=20)

        # Verify all messages received
        assert len(test_listener.received_messages) == message_count

        # Verify message order and content
        received_ids = [msg.id for msg in test_listener.received_messages]
        expected_ids = [f"test-{i}" for i in range(1, message_count + 1)]

        # Messages might arrive out of order, so check all are present
        assert set(received_ids) == set(expected_ids)

    def test_validation_error_handling(
        self,
        pubsub_client,
        pubsub_publisher,
        test_topic,
        test_subscription,
        test_listener,
        run_client,
        wait_for,
    ):
        """Test handling of validation errors."""

        # Extract subscription name from path
        subscription_name = test_subscription.split("/")[-1]

        @pubsub_listener
        class ValidationListener:
            def __init__(self, listener):
                self.listener = listener

            @subscription(subscription_name, EventModel)
            def handle_message(self, event: EventModel, ack: Acknowledgement):
                self.listener.received_messages.append(event)
                ack.ack()

        # Create listener
        ValidationListener(test_listener)

        # Start client
        run_client(pubsub_client, timeout=10)
        time.sleep(1)

        # Publish invalid message (missing required fields)
        invalid_data = json.dumps({"id": "", "content": ""}).encode("utf-8")
        future = pubsub_publisher.publish(test_topic, invalid_data)
        future.result(timeout=10)

        # Wait a bit to see if any messages are processed
        time.sleep(3)

        # Should not receive any messages due to validation error
        assert len(test_listener.received_messages) == 0

    def test_async_handler(
        self,
        pubsub_client,
        pubsub_publisher,
        test_topic,
        test_subscription,
        test_listener,
        run_client,
        wait_for,
    ):
        """Test async message handler."""

        # Extract subscription name from path
        subscription_name = test_subscription.split("/")[-1]

        @pubsub_listener
        class AsyncListener:
            def __init__(self, listener):
                self.listener = listener

            @subscription(subscription_name, EventModel)
            async def handle_message_async(self, event: EventModel, ack: Acknowledgement):
                # Simulate async work
                await asyncio.sleep(0.1)
                self.listener.received_messages.append(event)
                ack.ack()

        # Create listener
        AsyncListener(test_listener)

        # Start client
        run_client(pubsub_client, timeout=10)
        time.sleep(1)

        # Publish message
        test_event = EventModel(id="async-test", content="Async Handler Test", sequence=1)
        message_data = test_event.model_dump_json().encode("utf-8")

        future = pubsub_publisher.publish(test_topic, message_data)
        future.result(timeout=10)

        # Wait for message
        assert wait_for(lambda: len(test_listener.received_messages) > 0, timeout=15)

        # Verify
        assert len(test_listener.received_messages) == 1
        received = test_listener.received_messages[0]
        assert received.id == "async-test"
        assert received.content == "Async Handler Test"

    def test_error_in_handler(
        self,
        pubsub_client,
        pubsub_publisher,
        test_topic,
        test_subscription,
        test_listener,
        run_client,
        wait_for,
    ):
        """Test error handling in message handler."""

        # Extract subscription name from path
        subscription_name = test_subscription.split("/")[-1]

        @pubsub_listener
        class ErrorListener:
            def __init__(self, listener):
                self.listener = listener
                self.call_count = 0

            @subscription(subscription_name, EventModel)
            def handle_message_with_error(self, event: EventModel, ack: Acknowledgement):
                self.call_count += 1
                if event.id == "error-test":
                    # Simulate an error
                    raise Exception("Simulated processing error")
                self.listener.received_messages.append(event)
                ack.ack()

        # Create listener
        listener = ErrorListener(test_listener)

        # Start client
        run_client(pubsub_client, timeout=10)
        time.sleep(1)

        # Publish message that will cause error
        error_event = EventModel(id="error-test", content="This will fail", sequence=1)
        message_data = error_event.model_dump_json().encode("utf-8")

        future = pubsub_publisher.publish(test_topic, message_data)
        future.result(timeout=10)

        # Wait a bit for processing
        time.sleep(3)

        # Should not have any successfully processed messages
        assert len(test_listener.received_messages) == 0
        # But handler should have been called
        assert listener.call_count > 0
