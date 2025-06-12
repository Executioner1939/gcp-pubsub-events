"""
Pytest configuration and shared fixtures for all tests
"""

import os
import pytest
import asyncio
import threading
import time
from typing import Generator, List
from unittest.mock import Mock

# Set emulator environment for all tests
os.environ['PUBSUB_EMULATOR_HOST'] = 'localhost:8085'

from google.cloud import pubsub_v1
from gcp_pubsub_events import create_pubsub_app, PubSubClient
from gcp_pubsub_events.core.registry import get_registry


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def emulator_host():
    """Return the emulator host address."""
    return os.environ.get('PUBSUB_EMULATOR_HOST', 'localhost:8085')


@pytest.fixture(scope="session")
def project_id():
    """Return the test project ID."""
    return "test-project"


@pytest.fixture(scope="session")
def pubsub_publisher(project_id, emulator_host):
    """Create a PubSub publisher client for testing."""
    return pubsub_v1.PublisherClient()


@pytest.fixture(scope="session")
def pubsub_subscriber(project_id, emulator_host):
    """Create a PubSub subscriber client for testing."""
    return pubsub_v1.SubscriberClient()


@pytest.fixture
def clean_registry():
    """Ensure registry is clean before each test."""
    registry = get_registry()
    registry.clear()
    yield registry
    registry.clear()


@pytest.fixture
def topic_name():
    """Generate a unique topic name for each test."""
    import uuid
    return f"test-topic-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def subscription_name():
    """Generate a unique subscription name for each test."""
    import uuid
    return f"test-subscription-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_topic(pubsub_publisher, project_id, topic_name):
    """Create and cleanup a test topic."""
    topic_path = pubsub_publisher.topic_path(project_id, topic_name)
    
    # Create topic
    try:
        pubsub_publisher.create_topic(request={"name": topic_path})
    except Exception:
        pass  # Topic might already exist
    
    yield topic_path
    
    # Cleanup - delete topic
    try:
        pubsub_publisher.delete_topic(request={"topic": topic_path})
    except Exception:
        pass  # Topic might not exist


@pytest.fixture
def test_subscription(pubsub_subscriber, project_id, subscription_name, test_topic):
    """Create and cleanup a test subscription."""
    subscription_path = pubsub_subscriber.subscription_path(project_id, subscription_name)
    
    # Create subscription
    try:
        pubsub_subscriber.create_subscription(
            request={"name": subscription_path, "topic": test_topic}
        )
    except Exception:
        pass  # Subscription might already exist
    
    yield subscription_path
    
    # Cleanup - delete subscription
    try:
        pubsub_subscriber.delete_subscription(request={"subscription": subscription_path})
    except Exception:
        pass  # Subscription might not exist


@pytest.fixture
def pubsub_client(project_id, clean_registry):
    """Create a PubSub client for testing."""
    client = create_pubsub_app(project_id, max_workers=2, max_messages=5)
    yield client
    try:
        client.stop_listening()
    except Exception:
        pass


class MockMessage:
    """Mock PubSub message for unit tests."""
    
    def __init__(self, data: bytes, message_id: str = "test-msg-123"):
        self.data = data
        self.message_id = message_id
        self._acked = False
        self._nacked = False
    
    def ack(self):
        self._acked = True
    
    def nack(self):
        self._nacked = True
    
    @property
    def is_acked(self):
        return self._acked
    
    @property
    def is_nacked(self):
        return self._nacked


@pytest.fixture
def mock_message():
    """Create a mock PubSub message."""
    def _create_message(data: str, message_id: str = "test-msg-123"):
        return MockMessage(data.encode('utf-8'), message_id)
    return _create_message


@pytest.fixture
def received_messages():
    """Thread-safe list to collect received messages in tests."""
    return []


class TestListener:
    """Base test listener class."""
    
    def __init__(self):
        self.received_messages: List = []
        self.errors: List = []
        self.processing_times: List[float] = []
    
    def reset(self):
        """Reset all collected data."""
        self.received_messages.clear()
        self.errors.clear()
        self.processing_times.clear()


@pytest.fixture
def test_listener():
    """Create a test listener instance."""
    return TestListener()


def wait_for_condition(condition_func, timeout: float = 10.0, check_interval: float = 0.1):
    """Wait for a condition to become true with timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(check_interval)
    return False


@pytest.fixture
def wait_for():
    """Provide wait_for_condition helper."""
    return wait_for_condition


def run_client_with_timeout(client: PubSubClient, timeout: float = 5.0):
    """Run PubSub client in a thread with timeout."""
    def run():
        try:
            client.start_listening(timeout=timeout)
        except Exception:
            pass  # Expected when timeout occurs
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


@pytest.fixture
def run_client():
    """Provide client runner helper."""
    return run_client_with_timeout