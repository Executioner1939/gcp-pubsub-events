#!/usr/bin/env python3
"""
Basic example usage of the GCP PubSub Events library
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from gcp_pubsub_events import pubsub_listener, subscription, Acknowledgement, create_pubsub_app


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Define your event classes using Pydantic
class RegistrationEvent(BaseModel):
    """Example event class for user registration."""
    email: str = Field(..., description="User's email address")
    gamer_tag: str = Field(..., min_length=3, max_length=20, description="User's gaming tag")
    id: str = Field(..., description="Unique user identifier")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Event timestamp")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()
    
    @field_validator('gamer_tag')
    @classmethod
    def validate_gamer_tag(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Gamer tag must be alphanumeric (underscores allowed)')
        return v


class PaymentEvent(BaseModel):
    """Example event class for payment events."""
    user_id: str = Field(..., description="User identifier")
    amount: float = Field(..., gt=0, description="Payment amount (must be positive)")
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$", description="3-letter currency code")
    transaction_id: str = Field(..., description="Unique transaction identifier")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Transaction timestamp")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional payment metadata")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Payment amount must be positive')
        return round(v, 2)  # Round to 2 decimal places


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