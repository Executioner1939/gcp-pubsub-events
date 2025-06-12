"""
Message acknowledgement handling for Pub/Sub messages
"""

import logging

logger = logging.getLogger(__name__)


class Acknowledgement:
    """
    Acknowledgement handles the acknowledgment of a message, ensuring it is processed successfully or marked as failed.

    This class is designed to encapsulate the logic of acknowledging or negatively acknowledging
    a message, while also keeping track of whether the message has already been acknowledged.
    It provides methods to explicitly acknowledge (ack) or negatively acknowledge (nack) a message.
    Additionally, it allows checking the acknowledgment status via a property.
    """
    
    def __init__(self, message):
        self._message = message
        self._acknowledged = False
    
    def ack(self):
        """
        Acknowledges a message if it has not already been acknowledged.

        This method checks whether the message has been previously acknowledged. If not,
        it acknowledges the message, updates the acknowledgment status, and logs the
        acknowledgment action.

        Raises
        ------
        Raises an exception if any issue occurs during the acknowledgment process.
        """
        if not self._acknowledged:
            self._message.ack()
            self._acknowledged = True
            logger.debug(f"Message acknowledged: {self._message.message_id}")
    
    def nack(self):
        """
        Acknowledges the message as not successfully processed.

        This method marks the message as negatively acknowledged (nack) if it has not
        been already acknowledged. It also sets the internal acknowledged status to
        True and logs the message acknowledgement action with its message ID.

        Raises:
            No exceptions are explicitly raised, but the underlying implementation of
            `_message.nack()` might raise errors if it fails.
        """
        if not self._acknowledged:
            self._message.nack()
            self._acknowledged = True
            logger.debug(f"Message nacked: {self._message.message_id}")
    
    @property
    def acknowledged(self) -> bool:
        """
        Get the acknowledged status.

        This property method returns the current status of the `_acknowledged`
        attribute, which indicates whether a certain condition or action has
        been acknowledged.

        Returns:
            bool: The value of the `_acknowledged` attribute representing the
                  acknowledged status.
        """
        return self._acknowledged