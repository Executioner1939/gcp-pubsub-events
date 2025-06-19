# FastAPI Integration Best Practices

This guide covers best practices for integrating `gcp-pubsub-events` with FastAPI applications.

## Key Principles

### 1. Initialize Services Before Starting PubSub Manager

Always create your service instances (decorated with `@pubsub_listener`) **before** starting the PubSub manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Good: Create service first
    event_service = EventService()
    
    # Then start the manager
    async with async_pubsub_manager(...) as manager:
        yield
```

### 2. Use the Async Context Manager

For FastAPI, always use `async_pubsub_manager` instead of the synchronous version:

```python
# ✅ Good: Async context manager
async with async_pubsub_manager(...) as manager:
    yield

# ❌ Bad: Synchronous manager in async context
with pubsub_manager(...) as manager:  # Don't do this in FastAPI
    yield
```

### 3. Don't Clear Registry in Production

The `clear_registry_on_start` option should typically be `False` in production:

```python
async with async_pubsub_manager(
    project_id="your-project",
    clear_registry_on_start=False  # Important for production
) as manager:
```

### 4. Store References in App State

Store service and manager references in FastAPI's app state for access in endpoints:

```python
app.state.event_service = event_service
app.state.pubsub_manager = manager
```

## Common Issues and Solutions

### Issue: "Client is already listening" warnings

**Cause**: Multiple initialization attempts or improper cleanup.

**Solution**: Ensure you're:
1. Creating service instances only once
2. Using the context manager properly
3. Not manually calling start/stop methods

### Issue: Services not receiving messages

**Cause**: Services created after PubSub manager starts.

**Solution**: Always create service instances before entering the `async_pubsub_manager` context.

### Issue: Shutdown hangs

**Cause**: Long-running message handlers or improper acknowledgment.

**Solution**: 
1. Always acknowledge messages (ack/nack)
2. Use timeouts in handlers
3. Handle exceptions properly

## Complete Example Structure

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from gcp_pubsub_events import async_pubsub_manager, pubsub_listener, subscription

# Global service reference
service = None

@pubsub_listener
class MyService:
    def __init__(self, dependencies):
        self.dependencies = dependencies
    
    @subscription("my-subscription")
    async def handle_event(self, event, ack):
        try:
            # Process event
            await self.process(event)
            ack.ack()
        except Exception as e:
            logger.error(f"Error: {e}")
            ack.nack()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global service
    
    # Initialize dependencies
    database = await connect_database()
    
    # Create service with dependencies
    service = MyService(database)
    
    # Start PubSub manager
    async with async_pubsub_manager(
        project_id="your-project",
        max_workers=10,
        max_messages=100,
        auto_create_resources=True,
        clear_registry_on_start=False
    ) as manager:
        app.state.pubsub_manager = manager
        app.state.service = service
        
        yield
    
    # Cleanup
    await database.disconnect()

app = FastAPI(lifespan=lifespan)
```

## Testing Considerations

When testing, you might want to:

1. Use `clear_registry_on_start=True` for test isolation
2. Create a separate test configuration
3. Mock the PubSub manager for unit tests

```python
# For testing
if settings.TESTING:
    manager_config = {
        "clear_registry_on_start": True,
        "auto_create_resources": False
    }
else:
    manager_config = {
        "clear_registry_on_start": False,
        "auto_create_resources": True
    }

async with async_pubsub_manager(**manager_config) as manager:
    ...
```

## Performance Tips

1. **Set appropriate worker counts**: Match `max_workers` to your expected load
2. **Configure flow control**: Use `max_messages` to prevent overwhelming your service
3. **Use async handlers**: Leverage FastAPI's async capabilities
4. **Monitor memory usage**: Long-running services should monitor for memory leaks

## Debugging Tips

Enable debug logging to troubleshoot issues:

```python
import logging

# See all gcp-pubsub-events logs
logging.getLogger("gcp_pubsub_events").setLevel(logging.DEBUG)

# But reduce noise from Google libraries
logging.getLogger("google").setLevel(logging.WARNING)
```