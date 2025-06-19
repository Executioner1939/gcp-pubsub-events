# GCP PubSub Events

[![CI](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml/badge.svg)](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml)
[![PyPI version](https://badge.fury.io/py/gcp-pubsub-events.svg)](https://pypi.org/project/gcp-pubsub-events/)
[![codecov](https://codecov.io/gh/Executioner1939/gcp-pubsub-events/branch/main/graph/badge.svg)](https://codecov.io/gh/Executioner1939/gcp-pubsub-events)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, decorator-based Python library for Google Cloud Pub/Sub event handling. Inspired by event-driven architectures and frameworks like Micronaut, this library makes it easy to build scalable, event-driven microservices with minimal boilerplate.

## Features

- **Decorator-based API**: Simple `@pubsub_listener` and `@subscription` decorators
- **Type Safety**: Full Pydantic model support with automatic validation
- **Async Support**: Works with both sync and async message handlers
- **Framework Integration**: Works seamlessly with FastAPI, Flask, Django
- **Auto-retry Logic**: Built-in retry mechanism with ack/nack support
- **Resource Management**: Optional automatic topic and subscription creation
- **Comprehensive Testing**: Well-tested with unit, integration, and e2e tests

## Installation

```bash
pip install gcp-pubsub-events
```

## Core Concepts

### Decorators

- `@pubsub_listener`: Marks a class as containing event handlers
- `@subscription("subscription-name")`: Marks a method as handling messages from a specific subscription

### Message Acknowledgment

Every handler receives an `Acknowledgement` object:
- `ack.ack()`: Message processed successfully, remove from queue
- `ack.nack()`: Processing failed, retry later

### Context Managers

The library provides context managers for lifecycle management:
- `pubsub_manager`: Synchronous context manager
- `async_pubsub_manager`: Asynchronous context manager for async frameworks

## Basic Usage

```python
from gcp_pubsub_events import pubsub_listener, subscription, PubSubManager

@pubsub_listener
class EventHandler:
    @subscription("my-subscription")
    def handle_message(self, data: dict, ack):
        # Process the message
        print(f"Received: {data}")
        ack.ack()

# Create handler instance
handler = EventHandler()

# Use context manager for lifecycle management
with PubSubManager("my-project-id") as manager:
    # Application runs here
    # Manager handles all setup and cleanup
    pass
```

## FastAPI Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from gcp_pubsub_events import async_pubsub_manager, pubsub_listener, subscription

@pubsub_listener
class MyService:
    @subscription("my-subscription")
    async def handle_event(self, data: dict, ack):
        # Process event
        ack.ack()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create service instance first
    service = MyService()
    
    # Then start the manager
    async with async_pubsub_manager("my-project") as manager:
        yield

app = FastAPI(lifespan=lifespan)
```

## Configuration

### Environment Variables

```bash
# Required
export GOOGLE_CLOUD_PROJECT="my-project-id"

# Optional
export PUBSUB_EMULATOR_HOST="localhost:8085"  # For local development
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### Manager Configuration

```python
from gcp_pubsub_events import PubSubManager

manager = PubSubManager(
    project_id="my-project",
    max_workers=10,              # Thread pool size
    max_messages=100,            # Max concurrent messages
    auto_create_resources=True,  # Auto-create topics/subscriptions
    clear_registry_on_start=False # Clear handlers on restart
)
```

## Testing

The library includes comprehensive test support:

```bash
# Run all tests
poetry run pytest

# Run with emulator
export PUBSUB_EMULATOR_HOST=localhost:8085
gcloud beta emulators pubsub start
poetry run pytest tests/integration/
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Resources

- [Google Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Issue Tracker](https://github.com/Executioner1939/gcp-pubsub-events/issues)