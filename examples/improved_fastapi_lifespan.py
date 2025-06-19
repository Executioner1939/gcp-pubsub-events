"""
Improved FastAPI lifespan example based on your usage pattern.
This shows best practices for integrating gcp-pubsub-events with FastAPI.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from gcp_pubsub_events import async_pubsub_manager

# Example imports (replace with your actual imports)
# from hermod.api.v1.api import api_router
# from hermod.core.analysis.services.ssh_event_service import SSHEventService
# from hermod.shared.config import settings
# from hermod.shared.database import MongoDatabase

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Improved FastAPI lifespan context manager."""
    logger.info("Starting application...")
    
    # Initialize database first
    database = MongoDatabase(settings.MONGODB_URI, settings.MONGODB_DATABASE)
    await database.aconnect()
    
    # Store in app state for dependency injection
    app.state.database = database
    
    try:
        if settings.is_pubsub_enabled():
            logger.info("Initializing with Pub/Sub...")
            
            # Important: Initialize the service BEFORE starting the manager
            # This ensures all subscriptions are registered
            ssh_event_service = SSHEventService(database)
            
            # Start the PubSub manager
            async with async_pubsub_manager(
                settings.GOOGLE_CLOUD_PROJECT,
                auto_create_resources=settings.PUBSUB_AUTO_CREATE_RESOURCES,
                max_messages=settings.PUBSUB_MAX_MESSAGES,
                max_workers=settings.PUBSUB_MAX_WORKERS,
                # Important: Don't clear registry in production
                clear_registry_on_start=settings.is_development(),
                # Optional: Configure flow control
                flow_control_settings={
                    "max_messages": settings.PUBSUB_MAX_MESSAGES,
                    "max_bytes": 500 * 1024 * 1024,  # 500MB
                    "max_lease_duration": 3600,  # 1 hour
                }
            ) as manager:
                # Store references in app state
                app.state.pubsub_manager = manager
                app.state.ssh_event_service = ssh_event_service
                
                # Initialize health service with all dependencies
                health_service = HealthService(
                    database=database,
                    pubsub_manager=manager,
                    project_id=settings.GOOGLE_CLOUD_PROJECT
                )
                app.state.health_service = health_service
                
                # Mark startup as complete
                health_service.mark_startup_complete()
                logger.info("Application started successfully with Pub/Sub")
                
                # Yield control to FastAPI
                yield
                
                # Cleanup will happen automatically when exiting the context
                logger.info("Shutting down Pub/Sub...")
        else:
            # No Pub/Sub mode
            logger.info("Running without Pub/Sub...")
            
            app.state.pubsub_manager = None
            app.state.ssh_event_service = None
            
            # Initialize health service without Pub/Sub
            health_service = HealthService(
                database=database,
                pubsub_manager=None,
                project_id=None
            )
            app.state.health_service = health_service
            
            health_service.mark_startup_complete()
            logger.info("Application started successfully (no Pub/Sub)")
            
            yield
            
    finally:
        # Ensure database cleanup happens regardless of errors
        logger.info("Shutting down application...")
        if database:
            await database.disconnect()
        logger.info("Shutdown complete")


# Additional recommendations:

# 1. Add a readiness check that verifies PubSub is working
@app.get("/api/health/readyz")
async def readiness_check():
    """Check if the service is ready to accept traffic."""
    checks = {
        "database": False,
        "pubsub": False,
        "service": False
    }
    
    # Check database
    if hasattr(app.state, 'database') and app.state.database:
        try:
            # Perform a simple database operation
            await app.state.database.ping()
            checks["database"] = True
        except Exception as e:
            logger.error(f"Database check failed: {e}")
    
    # Check PubSub
    if hasattr(app.state, 'pubsub_manager') and app.state.pubsub_manager:
        # The manager being present and the client running indicates readiness
        if app.state.pubsub_manager.is_running:
            checks["pubsub"] = True
    elif not settings.is_pubsub_enabled():
        # If PubSub is disabled, consider it "ready"
        checks["pubsub"] = True
    
    # Check service
    if hasattr(app.state, 'ssh_event_service'):
        checks["service"] = True
    
    # Determine overall readiness
    all_ready = all(checks.values())
    
    return {
        "ready": all_ready,
        "checks": checks
    }, 200 if all_ready else 503


# 2. Add graceful shutdown handling for long-running handlers
class GracefulShutdown:
    """Helper class to manage graceful shutdown of async tasks."""
    
    def __init__(self):
        self.should_exit = False
    
    def exit(self):
        self.should_exit = True


# 3. Example of how to properly handle long-running operations
@subscription("long-running-subscription")
async def handle_long_running_task(event: dict, ack: Acknowledgement, shutdown: GracefulShutdown):
    """Example of handling long-running tasks with graceful shutdown."""
    try:
        for i in range(100):
            if shutdown.should_exit:
                logger.info("Graceful shutdown requested, stopping task")
                ack.nack()  # Return message to queue
                return
            
            # Do some work
            await asyncio.sleep(1)
        
        ack.ack()
    except Exception as e:
        logger.error(f"Error in long-running task: {e}")
        ack.nack()