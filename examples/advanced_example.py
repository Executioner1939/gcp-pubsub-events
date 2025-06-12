#!/usr/bin/env python3
"""
Advanced Pydantic example showing validation, serialization, and error handling
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

from gcp_pubsub_events import pubsub_listener, subscription, Acknowledgement, create_pubsub_app


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Enums for better type safety
class EventType(str, Enum):
    USER_REGISTERED = "user_registered"
    PAYMENT_COMPLETED = "payment_completed"
    ORDER_CREATED = "order_created"
    ORDER_CANCELLED = "order_cancelled"


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"


# Advanced Pydantic models with validation
class BaseEvent(BaseModel):
    """Base event class with common fields."""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    source: str = Field(default="api", description="Event source system")
    version: str = Field(default="1.0", description="Event schema version")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserRegisteredEvent(BaseEvent):
    """User registration event with full validation."""
    event_type: EventType = Field(default=EventType.USER_REGISTERED)
    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    email: str = Field(..., description="User's email address")
    username: str = Field(..., min_length=3, max_length=30, description="Username")
    profile: Optional[dict] = Field(default_factory=dict, description="User profile data")
    preferences: Optional[dict] = Field(default_factory=dict, description="User preferences")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v.lower().strip()
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens and underscores')
        return v.lower()


class PaymentCompletedEvent(BaseEvent):
    """Payment completion event with financial validation."""
    event_type: EventType = Field(default=EventType.PAYMENT_COMPLETED)
    payment_id: str = Field(..., description="Unique payment identifier")
    user_id: str = Field(..., description="User who made the payment")
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: Currency = Field(default=Currency.USD, description="Payment currency")
    payment_method: str = Field(..., description="Payment method used")
    transaction_fee: Optional[float] = Field(default=0.0, ge=0, description="Transaction fee")
    metadata: dict = Field(default_factory=dict, description="Additional payment metadata")
    
    @field_validator('amount', 'transaction_fee')
    @classmethod
    def validate_monetary_amount(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v
    
    @model_validator(mode='after')
    def validate_payment_data(self):
        if self.transaction_fee > self.amount * 0.1:  # Fee shouldn't exceed 10% of amount
            raise ValueError('Transaction fee is unusually high')
        return self


# Service implementations
class UserService:
    async def create_user_profile(self, user_id: str, email: str, username: str, profile: dict):
        # Simulate user profile creation
        await asyncio.sleep(0.1)
        return {"user_id": user_id, "status": "created", "profile_complete": bool(profile)}


class PaymentService:
    async def process_payment_completion(self, payment_id: str, amount: float, user_id: str):
        # Simulate payment processing
        await asyncio.sleep(0.2)
        return {"payment_id": payment_id, "status": "processed", "amount": amount}


# Event listeners with Pydantic validation
@pubsub_listener
class UserEventService:
    """Service for handling user-related events."""
    
    def __init__(self, user_service: UserService):
        self.user_service = user_service
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @subscription("events.user.registered", UserRegisteredEvent)
    async def on_user_registered(self, event: UserRegisteredEvent, acknowledgement: Acknowledgement):
        """Handle user registration events with full validation."""
        try:
            self.logger.info(f"Processing user registration: {event.user_id} ({event.email})")
            
            result = await self.user_service.create_user_profile(
                event.user_id, event.email, event.username, event.profile
            )
            
            acknowledgement.ack()
            self.logger.info(f"User registration processed successfully: {result}")
            
        except Exception as error:
            acknowledgement.nack()
            self.logger.error(f"Error processing user registration: {error}", exc_info=True)


@pubsub_listener
class PaymentEventService:
    """Service for handling payment-related events."""
    
    def __init__(self, payment_service: PaymentService):
        self.payment_service = payment_service
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @subscription("events.payment.completed", PaymentCompletedEvent)
    async def on_payment_completed(self, event: PaymentCompletedEvent, acknowledgement: Acknowledgement):
        """Handle payment completion events."""
        try:
            self.logger.info(f"Processing payment completion: {event.payment_id} - ${event.amount} {event.currency}")
            
            result = await self.payment_service.process_payment_completion(
                event.payment_id, event.amount, event.user_id
            )
            
            acknowledgement.ack()
            self.logger.info(f"Payment completion processed: {result}")
            
        except Exception as error:
            acknowledgement.nack()
            self.logger.error(f"Error processing payment completion: {error}", exc_info=True)


if __name__ == "__main__":
    # Initialize services
    user_service = UserService()
    payment_service = PaymentService()
    
    # Initialize event services
    user_event_service = UserEventService(user_service)
    payment_event_service = PaymentEventService(payment_service)
    
    # Start the PubSub client
    client = create_pubsub_app("your-project-id")
    
    # Example of how Pydantic validation works
    try:
        # This will work
        valid_event = UserRegisteredEvent(
            event_id="evt_123",
            user_id="user_456",
            email="user@example.com",
            username="valid_user"
        )
        print(f"Valid event created: {valid_event.model_dump_json()}")
        
    except Exception as e:
        print(f"Validation error: {e}")
    
    client.start_listening()