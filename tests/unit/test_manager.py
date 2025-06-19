"""
Tests for PubSubManager context manager functionality
"""

import time
from unittest.mock import Mock, patch

import pytest

from gcp_pubsub_events.core.manager import PubSubManager, async_pubsub_manager, pubsub_manager


class TestPubSubManager:
    """Test PubSubManager class functionality."""

    def test_manager_initialization(self):
        """Test manager initializes correctly."""
        manager = PubSubManager("test-project", max_workers=3, max_messages=50)

        assert manager.project_id == "test-project"
        assert manager.max_workers == 3
        assert manager.max_messages == 50
        assert manager.client is None
        assert not manager.is_running

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    def test_manager_start_stop(self, mock_create_app):
        """Test manager start and stop functionality."""
        # Mock the client
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")

        # Test start
        manager.start()
        assert manager.is_running
        assert manager.client == mock_client
        assert manager._thread is not None
        mock_create_app.assert_called_once_with(
            "test-project",
            max_workers=5,
            max_messages=100,
            auto_create_resources=True,
            resource_config={},
        )

        # Give thread a moment to start
        time.sleep(0.2)

        # Test stop
        manager.stop()
        assert not manager.is_running
        assert manager.client is None
        assert manager._thread is None
        mock_client.stop_listening.assert_called_once()

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    def test_manager_start_already_running(self, mock_create_app):
        """Test starting manager when already running."""
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")
        manager.start()

        # Try to start again
        with patch("gcp_pubsub_events.core.manager.logger") as mock_logger:
            manager.start()
            mock_logger.warning.assert_called_with("PubSub manager is already running")

        manager.stop()

    def test_manager_stop_not_running(self):
        """Test stopping manager when not running."""
        manager = PubSubManager("test-project")

        with patch("gcp_pubsub_events.core.manager.logger") as mock_logger:
            manager.stop()
            mock_logger.warning.assert_called_with("PubSub manager is not running")

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    def test_context_manager_sync(self, mock_create_app):
        """Test sync context manager functionality."""
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")

        # Test context manager
        with manager as mgr:
            assert mgr is manager
            assert manager.is_running
            assert manager.client == mock_client

        # After context, should be stopped
        assert not manager.is_running
        assert manager.client is None
        mock_client.stop_listening.assert_called_once()

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    def test_context_manager_with_exception(self, mock_create_app):
        """Test context manager cleanup on exception."""
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")

        # Test exception handling
        try:
            with manager:
                assert manager.is_running
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still cleanup
        assert not manager.is_running
        assert manager.client is None
        mock_client.stop_listening.assert_called_once()

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_create_app):
        """Test async context manager functionality."""
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")

        # Test async context manager
        async with manager as mgr:
            assert mgr is manager
            assert manager.is_running
            assert manager.client == mock_client

        # After context, should be stopped
        assert not manager.is_running
        assert manager.client is None
        mock_client.stop_listening.assert_called_once()

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    @pytest.mark.asyncio
    async def test_async_context_manager_with_exception(self, mock_create_app):
        """Test async context manager cleanup on exception."""
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")

        # Test exception handling
        try:
            async with manager:
                assert manager.is_running
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still cleanup
        assert not manager.is_running
        assert manager.client is None
        mock_client.stop_listening.assert_called_once()


class TestPubSubManagerHelpers:
    """Test helper functions for context managers."""

    @patch("gcp_pubsub_events.core.manager.PubSubManager")
    def test_pubsub_manager_function(self, mock_manager_class):
        """Test pubsub_manager helper function."""
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Test the context manager function
        with pubsub_manager("test-project", max_workers=3, max_messages=50) as manager:
            assert manager == mock_manager
            mock_manager.start.assert_called_once()

        mock_manager.stop.assert_called_once()
        mock_manager_class.assert_called_once_with(
            project_id="test-project",
            max_workers=3,
            max_messages=50,
            flow_control_settings={},
            auto_create_resources=True,
            resource_config=None,
            clear_registry_on_start=False,
        )

    @patch("gcp_pubsub_events.core.manager.PubSubManager")
    def test_pubsub_manager_with_flow_control(self, mock_manager_class):
        """Test pubsub_manager with flow control settings."""
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Test with additional flow control settings
        flow_settings = {"max_messages_per_second": 10}
        with pubsub_manager("test-project", **flow_settings) as manager:
            assert manager == mock_manager

        mock_manager_class.assert_called_once_with(
            project_id="test-project",
            max_workers=5,
            max_messages=100,
            flow_control_settings=flow_settings,
            auto_create_resources=True,
            resource_config=None,
            clear_registry_on_start=False,
        )

    @patch("gcp_pubsub_events.core.manager.PubSubManager")
    @pytest.mark.asyncio
    async def test_async_pubsub_manager_function(self, mock_manager_class):
        """Test async_pubsub_manager helper function."""
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock async methods to return coroutines
        async def mock_aenter(self):
            return mock_manager

        async def mock_aexit(self, exc_type, exc_val, exc_tb):
            return None

        mock_manager.__aenter__ = mock_aenter
        mock_manager.__aexit__ = mock_aexit

        # Test the async context manager function
        async with async_pubsub_manager("test-project", max_workers=3) as manager:
            assert manager == mock_manager

        mock_manager_class.assert_called_once_with(
            project_id="test-project",
            max_workers=3,
            max_messages=100,
            flow_control_settings={},
            auto_create_resources=True,
            resource_config=None,
            clear_registry_on_start=False,
        )


class TestPubSubManagerThreading:
    """Test threading behavior of PubSubManager."""

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    def test_thread_lifecycle(self, mock_create_app):
        """Test thread creation and cleanup."""
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")

        # Start manager
        manager.start()
        assert manager._thread is not None
        assert manager._thread.is_alive()
        assert manager._thread.daemon  # Should be daemon thread

        # Store reference to thread before stopping
        thread = manager._thread

        # Stop manager
        manager.stop()
        time.sleep(0.1)  # Give thread time to stop

        # Check the stored thread reference
        assert not thread.is_alive()
        assert manager._thread is None  # Should be cleared

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    def test_stop_timeout(self, mock_create_app):
        """Test stop with timeout."""
        mock_client = Mock()
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")
        manager.start()

        # Mock a thread that doesn't stop quickly
        original_thread = manager._thread
        slow_thread = Mock()
        slow_thread.is_alive.side_effect = [True, True, False]  # Simulate slow stop
        slow_thread.join.return_value = None
        manager._thread = slow_thread

        with patch("gcp_pubsub_events.core.manager.logger"):
            manager.stop(timeout=0.1)
            # Should warn about timeout (mock setup makes it look like it didn't stop)

        # Cleanup the real thread
        if original_thread and original_thread.is_alive():
            manager._stop_event.set()
            original_thread.join(timeout=1)


class TestPubSubManagerIntegration:
    """Integration tests for PubSubManager with actual components."""

    @patch("gcp_pubsub_events.core.registry.get_registry")
    @patch("google.cloud.pubsub_v1.SubscriberClient")
    def test_manager_with_no_subscriptions(self, mock_subscriber, mock_get_registry):
        """Test manager behavior when no subscriptions are registered."""
        # Mock empty registry
        mock_registry = Mock()
        mock_registry.get_all_subscriptions.return_value = {}
        mock_get_registry.return_value = mock_registry

        # Mock subscriber client
        mock_subscriber_instance = Mock()
        mock_subscriber.return_value = mock_subscriber_instance

        manager = PubSubManager("test-project")

        with manager:
            # Should start and stop cleanly even with no subscriptions
            pass

        assert not manager.is_running

    @patch("gcp_pubsub_events.core.manager.create_pubsub_app")
    def test_manager_client_error_handling(self, mock_create_app):
        """Test manager handles client errors gracefully."""
        # Mock client that raises error on stop
        mock_client = Mock()
        mock_client.stop_listening.side_effect = Exception("Stop error")
        mock_create_app.return_value = mock_client

        manager = PubSubManager("test-project")

        with patch("gcp_pubsub_events.core.manager.logger") as mock_logger:
            with manager:
                pass

            # Should log warning about stop error
            mock_logger.warning.assert_called()

        # Should still cleanup properly
        assert not manager.is_running
        assert manager.client is None
