"""
Tests for ResourceManager functionality
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from google.api_core import exceptions

from gcp_pubsub_events.core.resources import ResourceManager, create_resource_manager


class TestResourceManager:
    """Test ResourceManager class functionality."""

    def test_resource_manager_initialization(self):
        """Test resource manager initializes correctly."""
        manager = ResourceManager("test-project", auto_create=True)

        assert manager.project_id == "test-project"
        assert manager.auto_create is True
        assert len(manager._existing_topics) == 0
        assert len(manager._existing_subscriptions) == 0

    def test_resource_manager_no_auto_create(self):
        """Test resource manager with auto_create disabled."""
        manager = ResourceManager("test-project", auto_create=False)
        assert manager.auto_create is False

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_topic_exists_check(self, mock_publisher_class):
        """Test checking if topic exists."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"

        manager = ResourceManager("test-project")

        # Topic exists
        mock_publisher.get_topic.return_value = Mock()
        result = manager._topic_exists("projects/test/topics/test-topic")
        assert result is True

        # Topic doesn't exist
        mock_publisher.get_topic.side_effect = exceptions.NotFound("Topic not found")
        result = manager._topic_exists("projects/test/topics/test-topic")
        assert result is False

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    def test_subscription_exists_check(self, mock_subscriber_class):
        """Test checking if subscription exists."""
        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"

        manager = ResourceManager("test-project")

        # Subscription exists
        mock_subscriber.get_subscription.return_value = Mock()
        result = manager._subscription_exists("projects/test/subscriptions/test-sub")
        assert result is True

        # Subscription doesn't exist
        mock_subscriber.get_subscription.side_effect = exceptions.NotFound("Subscription not found")
        result = manager._subscription_exists("projects/test/subscriptions/test-sub")
        assert result is False

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_ensure_topic_exists_already_exists(self, mock_publisher_class):
        """Test ensuring topic exists when it already exists."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.return_value = Mock()

        manager = ResourceManager("test-project")
        result = manager.ensure_topic_exists("test-topic")

        assert result == "projects/test/topics/test-topic"
        assert "test-topic" in manager._existing_topics
        mock_publisher.create_topic.assert_not_called()

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_ensure_topic_exists_create_new(self, mock_publisher_class):
        """Test ensuring topic exists by creating new topic."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.side_effect = exceptions.NotFound("Topic not found")

        # Mock successful creation
        mock_topic = Mock()
        mock_topic.name = "projects/test/topics/test-topic"
        mock_publisher.create_topic.return_value = mock_topic

        manager = ResourceManager("test-project", auto_create=True)
        result = manager.ensure_topic_exists("test-topic")

        assert result == "projects/test/topics/test-topic"
        assert "test-topic" in manager._existing_topics
        mock_publisher.create_topic.assert_called_once()

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_ensure_topic_exists_no_auto_create(self, mock_publisher_class):
        """Test ensuring topic exists with auto_create disabled."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.side_effect = exceptions.NotFound("Topic not found")

        manager = ResourceManager("test-project", auto_create=False)

        with pytest.raises(
            ValueError, match="Topic 'test-topic' does not exist and auto_create is disabled"
        ):
            manager.ensure_topic_exists("test-topic")

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_ensure_topic_exists_already_exists_race_condition(self, mock_publisher_class):
        """Test ensuring topic exists with race condition (created by another process)."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.side_effect = exceptions.NotFound("Topic not found")
        mock_publisher.create_topic.side_effect = exceptions.AlreadyExists("Topic already exists")

        manager = ResourceManager("test-project", auto_create=True)
        result = manager.ensure_topic_exists("test-topic")

        assert result == "projects/test/topics/test-topic"
        assert "test-topic" in manager._existing_topics

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_ensure_subscription_exists_create_new(
        self, mock_publisher_class, mock_subscriber_class
    ):
        """Test ensuring subscription exists by creating new subscription."""
        # Setup publisher mock
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.return_value = Mock()  # Topic exists

        # Setup subscriber mock
        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"
        mock_subscriber.get_subscription.side_effect = exceptions.NotFound("Subscription not found")

        # Mock successful creation
        mock_subscription = Mock()
        mock_subscription.name = "projects/test/subscriptions/test-sub"
        mock_subscriber.create_subscription.return_value = mock_subscription

        manager = ResourceManager("test-project", auto_create=True)
        result = manager.ensure_subscription_exists("test-sub", "test-topic")

        assert result == "projects/test/subscriptions/test-sub"
        assert "test-sub" in manager._existing_subscriptions
        mock_subscriber.create_subscription.assert_called_once()

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    def test_ensure_subscription_exists_no_auto_create(self, mock_subscriber_class):
        """Test ensuring subscription exists with auto_create disabled."""
        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"
        mock_subscriber.get_subscription.side_effect = exceptions.NotFound("Subscription not found")

        manager = ResourceManager("test-project", auto_create=False)

        with pytest.raises(
            ValueError, match="Subscription 'test-sub' does not exist and auto_create is disabled"
        ):
            manager.ensure_subscription_exists("test-sub", "test-topic")

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_ensure_subscription_with_config(self, mock_publisher_class, mock_subscriber_class):
        """Test ensuring subscription exists with additional configuration."""
        # Setup mocks
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.return_value = Mock()

        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"
        mock_subscriber.get_subscription.side_effect = exceptions.NotFound("Subscription not found")

        mock_subscription = Mock()
        mock_subscription.name = "projects/test/subscriptions/test-sub"
        mock_subscriber.create_subscription.return_value = mock_subscription

        manager = ResourceManager("test-project", auto_create=True)
        result = manager.ensure_subscription_exists(
            "test-sub", "test-topic", ack_deadline_seconds=30, retain_acked_messages=True
        )

        assert result == "projects/test/subscriptions/test-sub"

        # Verify create_subscription was called with correct config
        call_args = mock_subscriber.create_subscription.call_args
        request = call_args.kwargs["request"]
        assert request["ack_deadline_seconds"] == 30
        assert request["retain_acked_messages"] is True

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_ensure_resources_for_subscriptions(self, mock_publisher_class, mock_subscriber_class):
        """Test ensuring resources for multiple subscriptions."""
        # Setup mocks
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.side_effect = (
            lambda project, topic: f"projects/{project}/topics/{topic}"
        )
        mock_publisher.get_topic.return_value = Mock()

        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber
        mock_subscriber.subscription_path.side_effect = (
            lambda project, sub: f"projects/{project}/subscriptions/{sub}"
        )
        mock_subscriber.get_subscription.side_effect = exceptions.NotFound("Subscription not found")

        def create_sub_side_effect(request):
            mock_sub = Mock()
            mock_sub.name = request["name"]
            return mock_sub

        mock_subscriber.create_subscription.side_effect = create_sub_side_effect

        manager = ResourceManager("test-project", auto_create=True)

        # Test data
        subscriptions = {"sub1": [{"handler": Mock()}], "sub2": [{"handler": Mock()}]}

        result = manager.ensure_resources_for_subscriptions(subscriptions)

        assert len(result) == 2
        assert "sub1" in result
        assert "sub2" in result
        assert result["sub1"] == "projects/test-project/subscriptions/sub1"
        assert result["sub2"] == "projects/test-project/subscriptions/sub2"

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_list_topics(self, mock_publisher_class):
        """Test listing topics."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher

        # Mock topics with proper name attributes
        mock_topic1 = Mock()
        mock_topic1.name = "projects/test/topics/topic1"
        mock_topic2 = Mock()
        mock_topic2.name = "projects/test/topics/topic2"

        mock_publisher.list_topics.return_value = [mock_topic1, mock_topic2]

        manager = ResourceManager("test-project")
        topics = manager.list_topics()

        assert topics == ["topic1", "topic2"]

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    def test_list_subscriptions(self, mock_subscriber_class):
        """Test listing subscriptions."""
        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber

        # Mock subscriptions with proper name attributes
        mock_sub1 = Mock()
        mock_sub1.name = "projects/test/subscriptions/sub1"
        mock_sub2 = Mock()
        mock_sub2.name = "projects/test/subscriptions/sub2"

        mock_subscriber.list_subscriptions.return_value = [mock_sub1, mock_sub2]

        manager = ResourceManager("test-project")
        subs = manager.list_subscriptions()

        assert subs == ["sub1", "sub2"]

    def test_create_resource_manager_factory(self):
        """Test create_resource_manager factory function."""
        manager = create_resource_manager("test-project", auto_create=False)

        assert isinstance(manager, ResourceManager)
        assert manager.project_id == "test-project"
        assert manager.auto_create is False


class TestResourceManagerCaching:
    """Test caching behavior of ResourceManager."""

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_topic_caching(self, mock_publisher_class):
        """Test that topics are cached after first check."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.return_value = Mock()

        manager = ResourceManager("test-project")

        # First call should check existence
        result1 = manager.ensure_topic_exists("test-topic")
        assert result1 == "projects/test/topics/test-topic"
        assert mock_publisher.get_topic.call_count == 1

        # Second call should use cache
        result2 = manager.ensure_topic_exists("test-topic")
        assert result2 == "projects/test/topics/test-topic"
        assert mock_publisher.get_topic.call_count == 1  # No additional calls

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_subscription_caching(self, mock_publisher_class, mock_subscriber_class):
        """Test that subscriptions are cached after first check."""
        # Setup mocks
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.return_value = Mock()

        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"
        mock_subscriber.get_subscription.return_value = Mock()

        manager = ResourceManager("test-project")

        # First call should check existence
        result1 = manager.ensure_subscription_exists("test-sub", "test-topic")
        assert result1 == "projects/test/subscriptions/test-sub"
        assert mock_subscriber.get_subscription.call_count == 1

        # Second call should use cache
        result2 = manager.ensure_subscription_exists("test-sub", "test-topic")
        assert result2 == "projects/test/subscriptions/test-sub"
        assert mock_subscriber.get_subscription.call_count == 1  # No additional calls


class TestResourceManagerErrorHandling:
    """Test error handling in ResourceManager."""

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_topic_creation_failure(self, mock_publisher_class):
        """Test handling of topic creation failure."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.side_effect = exceptions.NotFound("Topic not found")
        mock_publisher.create_topic.side_effect = Exception("Creation failed")

        manager = ResourceManager("test-project", auto_create=True)

        with pytest.raises(Exception, match="Creation failed"):
            manager.ensure_topic_exists("test-topic")

    @patch("gcp_pubsub_events.core.resources.pubsub_v1.SubscriberClient")
    @patch("gcp_pubsub_events.core.resources.pubsub_v1.PublisherClient")
    def test_subscription_creation_failure(self, mock_publisher_class, mock_subscriber_class):
        """Test handling of subscription creation failure."""
        # Setup publisher (topic exists)
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
        mock_publisher.get_topic.return_value = Mock()

        # Setup subscriber (creation fails)
        mock_subscriber = Mock()
        mock_subscriber_class.return_value = mock_subscriber
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"
        mock_subscriber.get_subscription.side_effect = exceptions.NotFound("Subscription not found")
        mock_subscriber.create_subscription.side_effect = Exception("Creation failed")

        manager = ResourceManager("test-project", auto_create=True)

        with pytest.raises(Exception, match="Creation failed"):
            manager.ensure_subscription_exists("test-sub", "test-topic")
