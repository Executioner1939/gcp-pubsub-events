#!/usr/bin/env python3
"""
Example usage of the GCP PubSub Listener library
"""

import asyncio
import logging
from dataclasses import dataclass
from pubsub_listener import pubsub_listener, subscription, Acknowledgement, create_pubsub_app


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Define your event classes
@dataclass
class RegistrationEvent:
    """Example event class for user registration."""
    email: str
    gamer_tag: str
    id: str
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class PaymentEvent:
    """Example event class for payment events."""
    user_id: str
    amount: float
    currency: str
    transaction_id: str
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


# Mock payment service for demonstration
class MockPaymentService:
    async def create_customer(self, email: str, gamer_tag: str, user_id: str):
        # Simulate async operation
        await asyncio.sleep(0.1)
        return MockResult(f"Customer created for {email}")
    
    async def process_payment(self, user_id: str, amount: float):
        # Simulate payment processing
        await asyncio.sleep(0.2)
        return MockResult(f"Payment of ${amount} processed for user {user_id}")


class MockResult:
    def __init__(self, value):
        self.value = value
        self.error = None
        
    def is_success(self):
        return self.error is None


# Create your service - this matches your Micronaut example
@pubsub_listener
class PaymentEventService:
    """
    Service responsible for handling payment-related events received via Pub/Sub.
    
    This service listens to events, such as registration events, and processes them by interacting
    with the PaymentService. It ensures message acknowledgements are properly managed based on
    the success or failure of the event processing.
    """
    
    def __init__(self, payment_service):
        self.payment_service = payment_service
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @subscription("payments.user.registered", RegistrationEvent)
    async def on_registration(self, event: RegistrationEvent, acknowledgement: Acknowledgement):
        """
        Handles the registration event received via PubSub subscription.
        
        Args:
            event: The registration event containing relevant data such as email, gamer tag, and ID.
            acknowledgement: The acknowledgement object used to indicate successful or failed message processing.
        """
        try:
            result = await self.payment_service.create_customer(
                event.email, event.gamer_tag, event.id
            )
            
            if result.is_success():
                acknowledgement.ack()
                self.logger.info(f"Registration event processed successfully: {result.value}")
            else:
                acknowledgement.nack()
                self.logger.error(f"Error processing registration event: {result.error}")
                
        except Exception as error:
            acknowledgement.nack()
            self.logger.error(f"Error processing registration event: {error}", exc_info=True)
    
    @subscription("payments.transaction.completed", PaymentEvent)
    async def on_payment_completed(self, event: PaymentEvent, acknowledgement: Acknowledgement):
        """Handle completed payment events."""
        try:
            self.logger.info(f"Processing payment completion for user {event.user_id}: ${event.amount}")
            result = await self.payment_service.process_payment(event.user_id, event.amount)
            
            if result.is_success():
                acknowledgement.ack()
                self.logger.info(f"Payment event processed successfully: {result.value}")
            else:
                acknowledgement.nack()
                self.logger.error(f"Error processing payment event: {result.error}")
                
        except Exception as error:
            acknowledgement.nack()
            self.logger.error(f"Error processing payment event: {error}", exc_info=True)


if __name__ == "__main__":
    # Initialize services
    payment_service = MockPaymentService()
    payment_event_service = PaymentEventService(payment_service)
    
    # Start the PubSub client
    client = create_pubsub_app("your-project-id")
    client.start_listening()