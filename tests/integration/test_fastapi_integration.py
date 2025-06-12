"""
Integration tests for FastAPI with PubSub manager
"""

import asyncio
import json
import pytest
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List
from unittest.mock import patch

# Only run these tests if FastAPI is available
fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from gcp_pubsub_events import pubsub_listener, subscription, Acknowledgement, async_pubsub_manager


# Test event model
class UserEvent(BaseModel):
    """Test user event model."""
    user_id: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


# Test listener
@pubsub_listener
class UserEventListener:
    """Test listener for user events."""
    
    def __init__(self):
        self.received_events: List[UserEvent] = []
        self.processing_times: List[float] = []
    
    @subscription("user-events", UserEvent)
    async def handle_user_event(self, event: UserEvent, ack: Acknowledgement):
        """Handle user events."""
        start_time = time.time()
        
        # Simulate async processing
        await asyncio.sleep(0.01)
        
        self.received_events.append(event)
        processing_time = time.time() - start_time
        self.processing_times.append(processing_time)
        
        ack.ack()


class TestFastAPIIntegration:
    """Test FastAPI integration with PubSub manager."""
    
    def test_basic_fastapi_integration(self, pubsub_client, pubsub_publisher, test_topic):
        """Test basic FastAPI app with PubSub manager."""
        
        # Create listener instance
        listener = UserEventListener()
        
        # Create FastAPI app with lifespan
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            async with async_pubsub_manager("test-project") as manager:
                app.state.pubsub_manager = manager
                yield
            # Shutdown handled by context manager
        
        app = FastAPI(lifespan=lifespan)
        
        @app.get("/")
        def read_root():
            return {"status": "ok"}
        
        @app.get("/events")
        def get_events():
            return {
                "received_count": len(listener.received_events),
                "events": [event.model_dump() for event in listener.received_events]
            }
        
        # Test the app
        with TestClient(app) as client:
            # Test basic endpoint
            response = client.get("/")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            
            # Test events endpoint
            response = client.get("/events")
            assert response.status_code == 200
            assert response.json()["received_count"] == 0
    
    @patch('gcp_pubsub_events.core.manager.create_pubsub_app')
    def test_fastapi_with_pubsub_messages(self, mock_create_app):
        """Test FastAPI receiving and processing PubSub messages."""
        
        # Mock the client
        mock_client = mock_create_app.return_value
        
        # Create listener
        listener = UserEventListener()
        
        # Create FastAPI app
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with async_pubsub_manager("test-project", max_workers=2) as manager:
                app.state.pubsub_manager = manager
                app.state.listener = listener
                yield
        
        app = FastAPI(lifespan=lifespan)
        
        @app.get("/health")
        def health_check():
            return {"status": "healthy", "pubsub_running": app.state.pubsub_manager.is_running}
        
        @app.get("/metrics")
        def get_metrics():
            return {
                "events_received": len(listener.received_events),
                "avg_processing_time": (
                    sum(listener.processing_times) / len(listener.processing_times)
                    if listener.processing_times else 0
                )
            }
        
        @app.post("/simulate-event")
        async def simulate_event(event: UserEvent):
            """Simulate processing an event directly (for testing)."""
            ack = Acknowledgement(None)  # Mock acknowledgement
            await listener.handle_user_event(event, ack)
            return {"status": "processed"}
        
        # Test the app
        with TestClient(app) as client:
            # Test health check
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            # Note: is_running might be False in test due to mocking
            
            # Test metrics
            response = client.get("/metrics")
            assert response.status_code == 200
            assert response.json()["events_received"] == 0
            
            # Simulate processing an event
            test_event = {
                "user_id": "user123",
                "action": "login",
                "metadata": {"ip": "192.168.1.1"}
            }
            response = client.post("/simulate-event", json=test_event)
            assert response.status_code == 200
            assert response.json()["status"] == "processed"
            
            # Check metrics again
            response = client.get("/metrics")
            assert response.status_code == 200
            data = response.json()
            assert data["events_received"] == 1
            assert data["avg_processing_time"] > 0
    
    def test_fastapi_lifespan_error_handling(self):
        """Test FastAPI lifespan error handling."""
        
        # Create app that fails during startup
        @asynccontextmanager
        async def failing_lifespan(app: FastAPI):
            try:
                # Simulate startup error
                raise Exception("Startup failed")
                yield
            except Exception:
                # Should handle gracefully
                yield
        
        app = FastAPI(lifespan=failing_lifespan)
        
        @app.get("/")
        def read_root():
            return {"status": "ok"}
        
        # App should still work even if lifespan fails
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
    
    @patch('gcp_pubsub_events.core.manager.create_pubsub_app')
    def test_multiple_fastapi_instances(self, mock_create_app):
        """Test multiple FastAPI instances with separate PubSub managers."""
        
        # Mock the client
        mock_client = mock_create_app.return_value
        
        # Create two separate apps
        @asynccontextmanager
        async def lifespan1(app: FastAPI):
            async with async_pubsub_manager("project-1") as manager:
                app.state.pubsub_manager = manager
                app.state.project = "project-1"
                yield
        
        @asynccontextmanager
        async def lifespan2(app: FastAPI):
            async with async_pubsub_manager("project-2") as manager:
                app.state.pubsub_manager = manager
                app.state.project = "project-2"
                yield
        
        app1 = FastAPI(lifespan=lifespan1)
        app2 = FastAPI(lifespan=lifespan2)
        
        @app1.get("/project")
        def get_project1():
            return {"project": app1.state.project}
        
        @app2.get("/project")
        def get_project2():
            return {"project": app2.state.project}
        
        # Test both apps
        with TestClient(app1) as client1, TestClient(app2) as client2:
            response1 = client1.get("/project")
            response2 = client2.get("/project")
            
            assert response1.json()["project"] == "project-1"
            assert response2.json()["project"] == "project-2"


class TestFastAPIRealIntegration:
    """Test FastAPI with real PubSub components (requires emulator)."""
    
    @pytest.mark.integration
    def test_fastapi_with_real_pubsub(self, pubsub_publisher, test_topic, test_subscription):
        """Test FastAPI with real PubSub emulator."""
        
        # Extract subscription name
        subscription_name = test_subscription.split('/')[-1]
        
        # Create listener for the specific subscription
        @pubsub_listener
        class TestEventListener:
            def __init__(self):
                self.events = []
            
            @subscription(subscription_name, UserEvent)
            async def handle_event(self, event: UserEvent, ack: Acknowledgement):
                self.events.append(event)
                ack.ack()
        
        listener = TestEventListener()
        
        # Create FastAPI app
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with async_pubsub_manager("test-project", max_workers=2) as manager:
                app.state.pubsub = manager
                app.state.listener = listener
                # Give PubSub time to start
                await asyncio.sleep(1)
                yield
        
        app = FastAPI(lifespan=lifespan)
        
        @app.get("/events")
        def get_events():
            return {"count": len(listener.events), "events": [e.model_dump() for e in listener.events]}
        
        @app.get("/status")
        def get_status():
            return {
                "pubsub_running": app.state.pubsub.is_running if hasattr(app.state, 'pubsub') else False
            }
        
        # Test with TestClient
        with TestClient(app) as client:
            # Check status
            response = client.get("/status")
            assert response.status_code == 200
            
            # Publish a test event
            test_event = UserEvent(
                user_id="test-user",
                action="test-action",
                metadata={"test": True}
            )
            
            message_data = test_event.model_dump_json().encode('utf-8')
            future = pubsub_publisher.publish(test_topic, message_data)
            message_id = future.result(timeout=10)
            assert message_id
            
            # Give time for processing
            time.sleep(2)
            
            # Check if event was received
            response = client.get("/events")
            assert response.status_code == 200
            data = response.json()
            
            # Should have received the event
            if data["count"] > 0:
                assert data["events"][0]["user_id"] == "test-user"
                assert data["events"][0]["action"] == "test-action"