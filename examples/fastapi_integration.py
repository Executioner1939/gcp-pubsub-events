#!/usr/bin/env python3
"""
Example of proper FastAPI integration with gcp-pubsub-events.

This example shows how to correctly use the async_pubsub_manager with FastAPI's
lifespan context manager to avoid issues like "Client is already listening" warnings.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
from gcp_pubsub_events import (
    async_pubsub_manager,
    pubsub_listener,
    subscription,
    Acknowledgement
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# Example event models
class UserCreatedEvent(BaseModel):
    user_id: str
    email: str
    created_at: str


class OrderPlacedEvent(BaseModel):
    order_id: str
    user_id: str
    amount: float


# Global state for services
event_service: Optional['EventService'] = None


@pubsub_listener
class EventService:
    """Example event service that handles multiple event types."""
    
    def __init__(self):
        self.events_processed = 0
        logger.info("EventService initialized")
    
    @subscription("user-created-subscription", UserCreatedEvent)
    async def handle_user_created(self, event: UserCreatedEvent, ack: Acknowledgement):
        """Handle user created events."""
        logger.info(f"User created: {event.user_id} - {event.email}")
        # Simulate some async processing
        await asyncio.sleep(0.1)
        self.events_processed += 1
        ack.ack()
    
    @subscription("order-placed-subscription", OrderPlacedEvent)
    async def handle_order_placed(self, event: OrderPlacedEvent, ack: Acknowledgement):
        """Handle order placed events."""
        logger.info(f"Order placed: {event.order_id} by user {event.user_id} for ${event.amount}")
        # Simulate some async processing
        await asyncio.sleep(0.1)
        self.events_processed += 1
        ack.ack()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager with proper PubSub integration."""
    global event_service
    
    logger.info("Starting FastAPI app with PubSub...")
    
    # Initialize your event service BEFORE starting the PubSub manager
    # This ensures all listeners are registered before the manager starts
    event_service = EventService()
    
    # Store service in app state for access in endpoints
    app.state.event_service = event_service
    
    # Use async_pubsub_manager for proper lifecycle management
    async with async_pubsub_manager(
        project_id="your-project-id",
        max_workers=10,
        max_messages=100,
        auto_create_resources=True,
        clear_registry_on_start=False  # Important: Don't clear in production
    ) as manager:
        # Store manager in app state if needed
        app.state.pubsub_manager = manager
        
        logger.info("FastAPI app started successfully with PubSub")
        
        # Yield control to FastAPI
        yield
        
        # Cleanup happens automatically when exiting the context manager
        logger.info("Shutting down FastAPI app...")
    
    logger.info("FastAPI app shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="FastAPI with PubSub Example",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "FastAPI with PubSub",
        "status": "running",
        "events_processed": event_service.events_processed if event_service else 0
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "pubsub_connected": hasattr(app.state, 'pubsub_manager') and app.state.pubsub_manager is not None,
        "service_initialized": event_service is not None
    }


if __name__ == "__main__":
    import uvicorn
    
    # Run the FastAPI app
    uvicorn.run(
        "fastapi_integration:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )