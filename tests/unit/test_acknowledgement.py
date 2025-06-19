"""
Unit tests for Acknowledgement class
"""

from gcp_pubsub_events.core.acknowledgement import Acknowledgement


class TestAcknowledgement:
    """Test cases for Acknowledgement class."""

    def test_ack_success(self, mock_message):
        """Test successful message acknowledgement."""
        message = mock_message("test data")
        ack = Acknowledgement(message)

        assert not ack.acknowledged

        ack.ack()

        assert ack.acknowledged
        assert message.is_acked
        assert not message.is_nacked

    def test_nack_success(self, mock_message):
        """Test successful message negative acknowledgement."""
        message = mock_message("test data")
        ack = Acknowledgement(message)

        assert not ack.acknowledged

        ack.nack()

        assert ack.acknowledged
        assert not message.is_acked
        assert message.is_nacked

    def test_double_ack_ignored(self, mock_message):
        """Test that double acknowledgement is ignored."""
        message = mock_message("test data")
        ack = Acknowledgement(message)

        ack.ack()
        assert ack.acknowledged

        # Second ack should be ignored
        ack.ack()
        assert ack.acknowledged

    def test_ack_after_nack_ignored(self, mock_message):
        """Test that ack after nack is ignored."""
        message = mock_message("test data")
        ack = Acknowledgement(message)

        ack.nack()
        assert ack.acknowledged
        assert message.is_nacked

        # Ack after nack should be ignored
        ack.ack()
        assert ack.acknowledged
        assert message.is_nacked
        assert not message.is_acked

    def test_nack_after_ack_ignored(self, mock_message):
        """Test that nack after ack is ignored."""
        message = mock_message("test data")
        ack = Acknowledgement(message)

        ack.ack()
        assert ack.acknowledged
        assert message.is_acked

        # Nack after ack should be ignored
        ack.nack()
        assert ack.acknowledged
        assert message.is_acked
        assert not message.is_nacked
