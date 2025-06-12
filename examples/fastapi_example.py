"""
FastAPI example with PubSub integration using context managers.

This example shows how to integrate the gcp-pubsub-events library with FastAPI
using the new context manager support for proper lifecycle management.

To run this example:
1. Start the PubSub emulator: gcloud beta emulators pubsub start --host-port=localhost:8085
2. Set environment: export PUBSUB_EMULATOR_HOST=localhost:8085  
3. Run: uvicorn examples.fastapi_example:app --reload
4. Visit http://localhost:8000/docs for API documentation
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from gcp_pubsub_events import (
    pubsub_listener, 
    subscription, 
    Acknowledgement, 
    async_pubsub_manager
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = "demo-project"
USER_EVENTS_SUBSCRIPTION = "user-events"
ORDER_EVENTS_SUBSCRIPTION = "order-events"

# Event Models
class UserEvent(BaseModel):
    """User event model."""
    user_id: str = Field(..., min_length=1, description="User ID")
    action: str = Field(..., min_length=1, description="Action performed")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class OrderEvent(BaseModel):
    """Order event model."""
    order_id: str = Field(..., min_length=1, description="Order ID")
    user_id: str = Field(..., min_length=1, description="User ID")
    status: str = Field(..., min_length=1, description="Order status")
    amount: float = Field(..., ge=0, description="Order amount")
    timestamp: datetime = Field(default_factory=datetime.now)


# API Models
class EventStats(BaseModel):
    """Statistics about processed events."""
    total_events: int
    user_events: int
    order_events: int
    avg_processing_time: float
    last_event_time: Optional[datetime] = None


class PublishEventRequest(BaseModel):
    """Request model for publishing events."""
    topic: str = Field(..., min_length=1)
    data: dict = Field(..., min_items=1)


# Event Listeners
@pubsub_listener
class UserEventService:
    """Service for handling user events."""
    
    def __init__(self):
        self.processed_events: List[UserEvent] = []
        self.processing_times: List[float] = []
        logger.info("UserEventService initialized")
    
    @subscription(USER_EVENTS_SUBSCRIPTION, UserEvent)
    async def handle_user_event(self, event: UserEvent, ack: Acknowledgement):
        """Handle incoming user events."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Processing user event: {event.user_id} - {event.action}")
            
            # Simulate some async processing
            await asyncio.sleep(0.1)
            
            # Store the event
            self.processed_events.append(event)
            
            # Track processing time
            processing_time = asyncio.get_event_loop().time() - start_time
            self.processing_times.append(processing_time)
            
            # Log processing
            logger.info(f"User event processed in {processing_time:.3f}s")
            
            # Acknowledge successful processing
            ack.ack()
            
        except Exception as e:
            logger.error(f"Error processing user event: {e}")
            ack.nack()


@pubsub_listener  
class OrderEventService:
    """Service for handling order events."""
    
    def __init__(self):
        self.processed_events: List[OrderEvent] = []
        self.processing_times: List[float] = []
        logger.info("OrderEventService initialized")
    
    @subscription(ORDER_EVENTS_SUBSCRIPTION, OrderEvent)
    async def handle_order_event(self, event: OrderEvent, ack: Acknowledgement):
        """Handle incoming order events."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Processing order event: {event.order_id} - {event.status}")
            
            # Simulate async processing (e.g., database operations)
            await asyncio.sleep(0.05)
            
            # Business logic based on order status
            if event.status == "created":
                logger.info(f"New order created: ${event.amount}")
            elif event.status == "completed":
                logger.info(f"Order completed: ${event.amount}")
            elif event.status == "cancelled":
                logger.info(f"Order cancelled: {event.order_id}")
            
            # Store the event
            self.processed_events.append(event)
            
            # Track processing time
            processing_time = asyncio.get_event_loop().time() - start_time
            self.processing_times.append(processing_time)
            
            logger.info(f"Order event processed in {processing_time:.3f}s")
            
            # Acknowledge successful processing
            ack.ack()
            
        except Exception as e:
            logger.error(f"Error processing order event: {e}")
            ack.nack()


# Initialize services
user_service = UserEventService()
order_service = OrderEventService()


# FastAPI Lifespan Management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage FastAPI application lifespan with PubSub integration."""
    logger.info("Starting FastAPI application...")
    
    # Startup: Initialize PubSub manager
    async with async_pubsub_manager(
        project_id=PROJECT_ID,
        max_workers=5,
        max_messages=50
    ) as pubsub_manager:
        
        # Store manager in app state for access in endpoints
        app.state.pubsub_manager = pubsub_manager
        app.state.user_service = user_service
        app.state.order_service = order_service
        
        logger.info("PubSub manager started successfully")
        logger.info(f"Listening on subscriptions: {USER_EVENTS_SUBSCRIPTION}, {ORDER_EVENTS_SUBSCRIPTION}")
        
        # Give PubSub time to start listening
        await asyncio.sleep(1)
        
        yield
        
        # Shutdown: Cleanup handled automatically by context manager
        logger.info("Shutting down FastAPI application...")


# Create FastAPI app
app = FastAPI(
    title="PubSub Events API",
    description="FastAPI application with Google Cloud Pub/Sub event processing",
    version="1.0.0",
    lifespan=lifespan
)


# API Endpoints
@app.get("/")
def read_root():
    """Root endpoint."""
    return {
        "message": "PubSub Events API",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "stats": "/stats",
            "events": "/events",
            "health": "/health"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    pubsub_running = (
        hasattr(app.state, 'pubsub_manager') and 
        app.state.pubsub_manager.is_running
    )
    
    return {
        "status": "healthy" if pubsub_running else "degraded",
        "pubsub_manager_running": pubsub_running,
        "timestamp": datetime.now()
    }


@app.get("/stats", response_model=EventStats)
def get_event_stats():
    """Get event processing statistics."""
    user_events = len(user_service.processed_events)
    order_events = len(order_service.processed_events)
    total_events = user_events + order_events
    
    # Calculate average processing time
    all_times = user_service.processing_times + order_service.processing_times
    avg_time = sum(all_times) / len(all_times) if all_times else 0
    
    # Get last event time
    last_event_time = None
    if user_service.processed_events or order_service.processed_events:
        user_last = user_service.processed_events[-1].timestamp if user_service.processed_events else datetime.min
        order_last = order_service.processed_events[-1].timestamp if order_service.processed_events else datetime.min
        last_event_time = max(user_last, order_last)
    
    return EventStats(
        total_events=total_events,
        user_events=user_events,
        order_events=order_events,
        avg_processing_time=avg_time,
        last_event_time=last_event_time
    )


@app.get("/events/user")
def get_user_events():
    """Get processed user events."""
    return {
        "count": len(user_service.processed_events),
        "events": [event.model_dump() for event in user_service.processed_events[-10:]]  # Last 10
    }


@app.get("/events/order") 
def get_order_events():
    """Get processed order events."""
    return {
        "count": len(order_service.processed_events),
        "events": [event.model_dump() for event in order_service.processed_events[-10:]]  # Last 10
    }


@app.post("/events/simulate/user")
async def simulate_user_event(event: UserEvent):
    """Simulate processing a user event (for testing)."""
    try:
        # Create mock acknowledgement
        ack = Acknowledgement(None)
        
        # Process the event directly
        await user_service.handle_user_event(event, ack)
        
        return {
            "status": "processed",
            "event_id": event.user_id,
            "action": event.action
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/events/simulate/order")
async def simulate_order_event(event: OrderEvent):
    """Simulate processing an order event (for testing)."""
    try:
        # Create mock acknowledgement
        ack = Acknowledgement(None)
        
        # Process the event directly
        await order_service.handle_order_event(event, ack)
        
        return {
            "status": "processed", 
            "order_id": event.order_id,
            "status_event": event.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    # Check if emulator is configured
    emulator_host = os.getenv('PUBSUB_EMULATOR_HOST')
    if not emulator_host:
        print("⚠️  PUBSUB_EMULATOR_HOST not set!")
        print("Start emulator with: gcloud beta emulators pubsub start --host-port=localhost:8085")
        print("Then set: export PUBSUB_EMULATOR_HOST=localhost:8085")
    else:
        print(f"✅ Using PubSub emulator at: {emulator_host}")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)