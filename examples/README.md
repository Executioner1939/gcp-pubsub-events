# Examples

This directory contains examples showing how to use the gcp-pubsub-events library in different scenarios.

## FastAPI Integration

### FastAPI Example (`fastapi_example.py`)

A complete FastAPI application demonstrating:

- Context manager integration with `async_pubsub_manager`
- Proper lifecycle management (startup/shutdown)
- Multiple event types (User and Order events)
- RESTful API endpoints for monitoring and testing
- Error handling and logging

**Features:**
- Health check endpoint
- Event statistics and monitoring
- Simulation endpoints for testing
- Automatic cleanup on shutdown

**Running the example:**

1. Start the PubSub emulator:
   ```bash
   gcloud beta emulators pubsub start --host-port=localhost:8085
   ```

2. Set environment variable:
   ```bash
   export PUBSUB_EMULATOR_HOST=localhost:8085
   ```

3. Install FastAPI (if not already installed):
   ```bash
   pip install fastapi uvicorn
   ```

4. Run the application:
   ```bash
   uvicorn examples.fastapi_example:app --reload
   ```

5. Visit `http://localhost:8000/docs` for interactive API documentation

**API Endpoints:**

- `GET /` - Root endpoint with API overview
- `GET /health` - Health check with PubSub status
- `GET /stats` - Event processing statistics
- `GET /events/user` - Get processed user events
- `GET /events/order` - Get processed order events
- `POST /events/simulate/user` - Simulate a user event
- `POST /events/simulate/order` - Simulate an order event

**Testing the example:**

1. Check health: `curl http://localhost:8000/health`
2. View stats: `curl http://localhost:8000/stats`
3. Simulate a user event:
   ```bash
   curl -X POST "http://localhost:8000/events/simulate/user" \
        -H "Content-Type: application/json" \
        -d '{
          "user_id": "user123",
          "action": "login",
          "metadata": {"ip": "192.168.1.1"}
        }'
   ```

## Integration Patterns

### Context Manager Usage

**Sync Context Manager:**
```python
from gcp_pubsub_events import pubsub_manager

with pubsub_manager("my-project") as manager:
    # Your application code here
    pass  # Cleanup happens automatically
```

**Async Context Manager (FastAPI):**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from gcp_pubsub_events import async_pubsub_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_pubsub_manager("my-project") as manager:
        app.state.pubsub = manager
        yield

app = FastAPI(lifespan=lifespan)
```

**Manual Management:**
```python
from gcp_pubsub_events import PubSubManager

manager = PubSubManager("my-project")
try:
    manager.start()
    # Your application code
finally:
    manager.stop()
```

### Event Listeners

```python
from gcp_pubsub_events import pubsub_listener, subscription, Acknowledgement
from pydantic import BaseModel

class MyEvent(BaseModel):
    id: str
    data: str

@pubsub_listener
class MyService:
    @subscription("my-subscription", MyEvent)
    async def handle_event(self, event: MyEvent, ack: Acknowledgement):
        # Process the event
        print(f"Received: {event.id}")
        
        # Acknowledge successful processing
        ack.ack()
```

## Configuration Options

### PubSubManager Parameters

- `project_id`: GCP project ID (required)
- `max_workers`: Maximum worker threads (default: 5)
- `max_messages`: Maximum messages to pull at once (default: 100)
- `flow_control_settings`: Additional flow control settings

### Flow Control Settings

```python
manager = PubSubManager(
    "my-project",
    max_workers=10,
    max_messages=200,
    flow_control_settings={
        "max_bytes": 100 * 1024 * 1024,  # 100MB
        "max_lease_duration": 600,       # 10 minutes
    }
)
```

## Best Practices

### 1. Use Context Managers
Always use context managers for proper resource cleanup:

```python
# Good
async with async_pubsub_manager("project") as manager:
    # Your code

# Better for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_pubsub_manager("project") as manager:
        app.state.pubsub = manager
        yield
```

### 2. Error Handling
Handle errors gracefully in event handlers:

```python
@subscription("my-sub", MyEvent)
async def handle_event(self, event: MyEvent, ack: Acknowledgement):
    try:
        # Process event
        await process_event(event)
        ack.ack()
    except RetryableError:
        ack.nack()  # Will retry
    except FatalError:
        ack.ack()   # Don't retry, log error
        logger.error("Fatal error processing event")
```

### 3. Resource Configuration
Configure resources based on your needs:

```python
# High throughput
manager = PubSubManager(
    "project",
    max_workers=20,
    max_messages=500
)

# Low latency
manager = PubSubManager(
    "project", 
    max_workers=5,
    max_messages=10
)
```

### 4. Monitoring
Add monitoring and logging:

```python
@subscription("events", Event)
async def handle_event(self, event: Event, ack: Acknowledgement):
    start_time = time.time()
    try:
        await process(event)
        ack.ack()
        duration = time.time() - start_time
        logger.info(f"Processed event in {duration:.3f}s")
    except Exception as e:
        ack.nack()
        logger.error(f"Error processing event: {e}")
```

## Troubleshooting

### Common Issues

1. **PubSub Emulator Not Running**
   ```bash
   gcloud beta emulators pubsub start --host-port=localhost:8085
   export PUBSUB_EMULATOR_HOST=localhost:8085
   ```

2. **Subscriptions Not Found**
   - Create topics and subscriptions in emulator
   - Check subscription names match decorator parameters

3. **Events Not Processing**
   - Check logs for connection errors
   - Verify event serialization matches Pydantic models
   - Ensure acknowledgment is called in handlers

4. **Memory Issues**
   - Reduce `max_messages` for memory-constrained environments
   - Implement backpressure in event handlers
   - Monitor processing times and adjust `max_workers`

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('gcp_pubsub_events')
logger.setLevel(logging.DEBUG)
```