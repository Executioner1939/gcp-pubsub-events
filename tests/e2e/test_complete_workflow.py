"""
End-to-end tests for complete workflow scenarios
"""

import asyncio
import json
import time
from datetime import datetime
from enum import Enum
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field, field_validator, model_validator

from gcp_pubsub_events import Acknowledgement, pubsub_listener, subscription


class EventType(str, Enum):
    USER_REGISTERED = "user_registered"
    ORDER_CREATED = "order_created"
    PAYMENT_PROCESSED = "payment_processed"


class BaseEvent(BaseModel):
    """Base event with common fields."""

    event_id: str = Field(..., min_length=1)
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: str = Field(..., min_length=1)


class UserRegisteredEvent(BaseEvent):
    """User registration event."""

    event_type: EventType = Field(default=EventType.USER_REGISTERED)
    email: str = Field(..., description="User email")
    username: str = Field(..., min_length=3, max_length=50)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class OrderCreatedEvent(BaseEvent):
    """Order creation event."""

    event_type: EventType = Field(default=EventType.ORDER_CREATED)
    order_id: str = Field(..., min_length=1)
    items: List[dict] = Field(..., min_items=1)
    total_amount: float = Field(..., gt=0)

    @field_validator("total_amount")
    @classmethod
    def validate_amount(cls, v):
        return round(float(v), 2)


class PaymentProcessedEvent(BaseEvent):
    """Payment processing event."""

    event_type: EventType = Field(default=EventType.PAYMENT_PROCESSED)
    payment_id: str = Field(..., min_length=1)
    order_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    status: str = Field(..., description="Payment status")

    @model_validator(mode="after")
    def validate_payment(self):
        if self.status not in ["success", "failed", "pending"]:
            raise ValueError("Invalid payment status")
        return self


class WorkflowState:
    """Track workflow state across multiple events."""

    def __init__(self):
        self.users: dict = {}
        self.orders: dict = {}
        self.payments: dict = {}
        self.workflow_completed: dict = {}


class TestCompleteWorkflow:
    """End-to-end workflow tests."""

    def test_user_order_payment_workflow(
        self, pubsub_client, pubsub_publisher, project_id, run_client, wait_for
    ):
        """Test complete user registration -> order -> payment workflow."""

        # Create workflow state tracker
        workflow_state = WorkflowState()

        # Create topics and subscriptions for each event type
        topic_names = {
            "user": f"user-events-{int(time.time())}",
            "order": f"order-events-{int(time.time())}",
            "payment": f"payment-events-{int(time.time())}",
        }

        subscription_names = {
            "user": f"user-sub-{int(time.time())}",
            "order": f"order-sub-{int(time.time())}",
            "payment": f"payment-sub-{int(time.time())}",
        }

        # Create topics
        topic_paths = {}
        for event_type, topic_name in topic_names.items():
            topic_path = pubsub_publisher.topic_path(project_id, topic_name)
            pubsub_publisher.create_topic(request={"name": topic_path})
            topic_paths[event_type] = topic_path

        # Create subscriptions
        subscriber = pubsub_client.subscriber
        for event_type, sub_name in subscription_names.items():
            sub_path = subscriber.subscription_path(project_id, sub_name)
            subscriber.create_subscription(
                request={"name": sub_path, "topic": topic_paths[event_type]}
            )

        @pubsub_listener
        class WorkflowEventHandler:
            def __init__(self, state: WorkflowState):
                self.state = state

            @subscription(subscription_names["user"], UserRegisteredEvent)
            async def handle_user_registration(
                self, event: UserRegisteredEvent, ack: Acknowledgement
            ):
                """Handle user registration and trigger order creation."""
                try:
                    # Store user
                    self.state.users[event.user_id] = {
                        "email": event.email,
                        "username": event.username,
                        "registered_at": event.timestamp,
                    }

                    # Simulate order creation after user registration
                    await asyncio.sleep(0.1)

                    order_event = OrderCreatedEvent(
                        event_id=f"order-{event.user_id}",
                        user_id=event.user_id,
                        order_id=f"ord-{event.user_id}-001",
                        items=[{"product": "Widget", "quantity": 2, "price": 10.00}],
                        total_amount=20.00,
                    )

                    # Publish order event
                    order_data = order_event.model_dump_json().encode("utf-8")
                    future = pubsub_publisher.publish(topic_paths["order"], order_data)
                    future.result(timeout=5)

                    ack.ack()

                except Exception as e:
                    ack.nack()
                    raise e

            @subscription(subscription_names["order"], OrderCreatedEvent)
            async def handle_order_creation(self, event: OrderCreatedEvent, ack: Acknowledgement):
                """Handle order creation and trigger payment."""
                try:
                    # Store order
                    self.state.orders[event.order_id] = {
                        "user_id": event.user_id,
                        "items": event.items,
                        "total_amount": event.total_amount,
                        "created_at": event.timestamp,
                    }

                    # Simulate payment processing
                    await asyncio.sleep(0.1)

                    payment_event = PaymentProcessedEvent(
                        event_id=f"payment-{event.order_id}",
                        user_id=event.user_id,
                        payment_id=f"pay-{event.order_id}-001",
                        order_id=event.order_id,
                        amount=event.total_amount,
                        status="success",
                    )

                    # Publish payment event
                    payment_data = payment_event.model_dump_json().encode("utf-8")
                    future = pubsub_publisher.publish(topic_paths["payment"], payment_data)
                    future.result(timeout=5)

                    ack.ack()

                except Exception as e:
                    ack.nack()
                    raise e

            @subscription(subscription_names["payment"], PaymentProcessedEvent)
            async def handle_payment_processing(
                self, event: PaymentProcessedEvent, ack: Acknowledgement
            ):
                """Handle payment completion and mark workflow complete."""
                try:
                    # Store payment
                    self.state.payments[event.payment_id] = {
                        "user_id": event.user_id,
                        "order_id": event.order_id,
                        "amount": event.amount,
                        "status": event.status,
                        "processed_at": event.timestamp,
                    }

                    # Mark workflow as completed for this user
                    self.state.workflow_completed[event.user_id] = True

                    ack.ack()

                except Exception as e:
                    ack.nack()
                    raise e

        # Create handler
        handler = WorkflowEventHandler(workflow_state)

        # Start client
        client_thread = run_client(pubsub_client, timeout=30)
        time.sleep(2)  # Let client start and register handlers

        # Start the workflow by publishing user registration event
        user_id = f"user-{int(time.time())}"
        registration_event = UserRegisteredEvent(
            event_id=f"reg-{user_id}",
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        # Publish initial event
        reg_data = registration_event.model_dump_json().encode("utf-8")
        future = pubsub_publisher.publish(topic_paths["user"], reg_data)
        future.result(timeout=10)

        # Wait for complete workflow
        def workflow_complete():
            return (
                user_id in workflow_state.users
                and len(workflow_state.orders) > 0
                and len(workflow_state.payments) > 0
                and workflow_state.workflow_completed.get(user_id, False)
            )

        assert wait_for(workflow_complete, timeout=25)

        # Verify complete workflow
        assert user_id in workflow_state.users
        assert workflow_state.users[user_id]["email"] == "test@example.com"
        assert workflow_state.users[user_id]["username"] == "testuser"

        # Should have one order
        assert len(workflow_state.orders) == 1
        order = list(workflow_state.orders.values())[0]
        assert order["user_id"] == user_id
        assert order["total_amount"] == 20.00

        # Should have one payment
        assert len(workflow_state.payments) == 1
        payment = list(workflow_state.payments.values())[0]
        assert payment["user_id"] == user_id
        assert payment["amount"] == 20.00
        assert payment["status"] == "success"

        # Workflow should be marked complete
        assert workflow_state.workflow_completed[user_id] is True

    def test_error_recovery_workflow(
        self, pubsub_client, pubsub_publisher, project_id, run_client, wait_for
    ):
        """Test workflow with error handling and recovery."""

        # Track attempts and errors
        processing_state = {
            "user_attempts": 0,
            "order_attempts": 0,
            "payment_attempts": 0,
            "errors": [],
            "success": False,
        }

        # Create resources
        topic_name = f"error-test-{int(time.time())}"
        sub_name = f"error-test-sub-{int(time.time())}"

        topic_path = pubsub_publisher.topic_path(project_id, topic_name)
        pubsub_publisher.create_topic(request={"name": topic_path})

        subscriber = pubsub_client.subscriber
        sub_path = subscriber.subscription_path(project_id, sub_name)
        subscriber.create_subscription(request={"name": sub_path, "topic": topic_path})

        @pubsub_listener
        class ErrorRecoveryHandler:
            def __init__(self, state):
                self.state = state

            @subscription(sub_name, UserRegisteredEvent)
            def handle_with_retry(self, event: UserRegisteredEvent, ack: Acknowledgement):
                """Handler that fails first few times then succeeds."""
                self.state["user_attempts"] += 1

                # Fail first 2 attempts, succeed on 3rd
                if self.state["user_attempts"] < 3:
                    self.state["errors"].append(f"Attempt {self.state['user_attempts']} failed")
                    raise Exception(f"Simulated failure on attempt {self.state['user_attempts']}")

                # Success on 3rd attempt
                self.state["success"] = True
                ack.ack()

        # Create handler
        handler = ErrorRecoveryHandler(processing_state)

        # Start client
        client_thread = run_client(pubsub_client, timeout=20)
        time.sleep(2)

        # Publish event that will initially fail
        user_id = f"error-user-{int(time.time())}"
        event = UserRegisteredEvent(
            event_id=f"error-test-{user_id}",
            user_id=user_id,
            email="error@example.com",
            username="erroruser",
        )

        event_data = event.model_dump_json().encode("utf-8")
        future = pubsub_publisher.publish(topic_path, event_data)
        future.result(timeout=10)

        # Wait for eventual success (PubSub will retry failed messages)
        assert wait_for(lambda: processing_state["success"], timeout=18)

        # Verify retry behavior
        assert processing_state["user_attempts"] >= 3
        assert len(processing_state["errors"]) >= 2
        assert processing_state["success"] is True
