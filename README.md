# GCP PubSub Events

[![CI](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml/badge.svg)](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml)
[![codecov](https://codecov.io/gh/Executioner1939/gcp-pubsub-events/branch/main/graph/badge.svg)](https://codecov.io/gh/Executioner1939/gcp-pubsub-events)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A decorator-based Python library for handling Google Cloud Pub/Sub messages, inspired by Micronaut's `@PubSubListener` pattern.

## 🚀 Features

- **Decorator-based**: Clean, annotation-style API similar to Micronaut
- **Context Manager Support**: Proper lifecycle management with `with` and `async with` syntax
- **FastAPI Integration**: Seamless integration with FastAPI using lifespan events
- **Automatic registration**: Classes marked with `@pubsub_listener` are automatically registered
- **Type-safe event handling**: Support for Pydantic models with automatic validation
- **Async support**: Handlers can be async or sync
- **Error handling**: Proper ack/nack based on handler success/failure
- **Thread management**: Automatic background thread handling with graceful shutdown
- **Modular design**: Well-organized package structure for maintainability

## 📦 Installation

```bash
pip install gcp-pubsub-events
```

Or install from source:
```bash
git clone <repository-url>
cd gcp-pubsub-events
pip install -e .
```

## 🏗️ Project Structure

```
gcp_pubsub_events/
├── __init__.py              # Main package exports
├── core/                    # Core functionality
│   ├── __init__.py
│   ├── acknowledgement.py   # Message acknowledgment handling
│   ├── client.py           # Main PubSub client
│   └── registry.py         # Listener registry management
├── decorators/             # Decorator implementations
│   ├── __init__.py
│   ├── listener.py         # @pubsub_listener decorator
│   └── subscription.py     # @subscription decorator
├── utils/                  # Utility functions
│   ├── __init__.py
│   └── serialization.py    # Event serialization utilities
└── exceptions/             # Custom exceptions
    ├── __init__.py
    ├── base.py
    ├── serialization.py
    └── subscription.py
```

## 🚀 Quick Start

### 1. Define Event Classes

```python
from pydantic import BaseModel, Field, field_validator

class RegistrationEvent(BaseModel):
    email: str = Field(..., description="User's email address")
    user_id: str = Field(..., description="Unique user identifier")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()
```

### 2. Create a Listener Service

```python
from gcp_pubsub_events import pubsub_listener, subscription, Acknowledgement

@pubsub_listener
class UserEventService:
    def __init__(self, user_service):
        self.user_service = user_service
    
    @subscription("user.registered", RegistrationEvent)
    async def on_user_registered(self, event: RegistrationEvent, acknowledgement: Acknowledgement):
        try:
            await self.user_service.create_profile(event.email, event.user_id)
            acknowledgement.ack()
            print(f"User registered: {event.email}")
        except Exception as error:
            acknowledgement.nack()
            print(f"Error: {error}")
```

### 3. Start Listening

#### Option A: Context Manager (Recommended)

```python
from gcp_pubsub_events import pubsub_manager

# Initialize your services
user_service = UserService()
user_event_service = UserEventService(user_service)

# Use context manager for automatic cleanup
with pubsub_manager("your-gcp-project-id") as manager:
    print("PubSub listener started. Press Ctrl+C to stop.")
    # Your application runs here
    # Cleanup happens automatically when exiting the context
```

#### Option B: FastAPI Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from gcp_pubsub_events import async_pubsub_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize PubSub
    async with async_pubsub_manager("your-gcp-project-id") as manager:
        app.state.pubsub = manager
        yield
    # Shutdown: Automatic cleanup

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "running"}
```

#### Option C: Manual Management

```python
from gcp_pubsub_events import create_pubsub_app

# Initialize your services
user_service = UserService()
user_event_service = UserEventService(user_service)

# Manual management (not recommended for production)
client = create_pubsub_app("your-gcp-project-id")
try:
    client.start_listening()
except KeyboardInterrupt:
    client.stop_listening()
```

## 📚 API Reference

### Core Components

#### `@pubsub_listener`
Class decorator that marks a class as a PubSub listener. Instances are automatically registered.

#### `@subscription(subscription_name, event_type=None)`
Method decorator that marks a method as a subscription handler.

**Parameters:**
- `subscription_name`: The GCP Pub/Sub subscription name
- `event_type`: Optional event class for automatic deserialization

#### `Acknowledgement`
Handles message acknowledgement.

**Methods:**
- `ack()`: Acknowledge successful processing
- `nack()`: Negative acknowledge (mark as failed)
- `acknowledged` (property): Check if message was acknowledged

#### `PubSubClient`
Main client for managing subscriptions.

**Methods:**
- `start_listening(timeout=None)`: Start listening to all registered subscriptions
- `stop_listening()`: Stop listening

#### `PubSubManager` (Recommended)
Enhanced manager with context manager support for proper lifecycle management.

**Methods:**
- `start()`: Start the PubSub listener in a background thread
- `stop(timeout=10.0)`: Stop listening with optional timeout
- `is_running` (property): Check if manager is currently running

**Context Manager Support:**
```python
# Sync context manager
with PubSubManager("project-id") as manager:
    # Your code here
    pass

# Async context manager  
async with PubSubManager("project-id") as manager:
    # Your async code here
    pass
```

### Factory Functions

#### `create_pubsub_app(project_id, max_workers=10, max_messages=100)`
Create and configure a PubSub application (legacy approach).

#### `pubsub_manager(project_id, max_workers=5, max_messages=100, **flow_control_settings)`
Context manager for PubSub operations.

#### `async_pubsub_manager(project_id, max_workers=5, max_messages=100, **flow_control_settings)`
Async context manager for PubSub operations (ideal for FastAPI).

## 🔧 Advanced Usage

### Custom Event Validation

```python
from pydantic import BaseModel, Field, field_validator

class PaymentEvent(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., pattern="^[A-Z]{3}$")
    user_id: str
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        return round(v, 2)  # Round to 2 decimal places
```

### Error Handling

The library automatically handles acknowledgements based on handler success:
- If handler completes without exception: `ack()` is called
- If handler raises exception: `nack()` is called
- Manual acknowledgement is also supported

### Sync and Async Handlers

```python
@pubsub_listener
class EventService:
    @subscription("sync.topic")
    def sync_handler(self, event, acknowledgement):
        # Synchronous processing
        pass

    @subscription("async.topic")
    async def async_handler(self, event, acknowledgement):
        # Asynchronous processing
        await some_async_operation()
```

## 🧪 Testing

The library includes comprehensive testing support with the PubSub emulator:

```bash
# Install development dependencies
pip install -e .[dev]

# Start the emulator
gcloud beta emulators pubsub start --host-port=localhost:8085

# Set environment variable
export PUBSUB_EMULATOR_HOST=localhost:8085

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=gcp_pubsub_events --cov-report=html
```

### Test Coverage

We maintain high test coverage with comprehensive unit, integration, and end-to-end tests:
- **Unit tests**: Fast, isolated component tests
- **Integration tests**: Real PubSub emulator integration  
- **E2E tests**: Complete workflow scenarios
- **Performance tests**: Throughput and latency benchmarks

Coverage reports are automatically generated and uploaded to [Codecov](https://codecov.io/gh/Executioner1939/gcp-pubsub-events).

## 📖 Examples

- **Basic Example**: `examples/basic_example.py` - Simple usage with Pydantic models
- **Advanced Example**: `examples/advanced_example.py` - Complex validation and multiple event types

## 🛠️ Development

### Setup Development Environment

```bash
git clone <repository-url>
cd gcp-pubsub-events
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

## 📋 Requirements

- Python 3.7+
- google-cloud-pubsub>=2.0.0
- pydantic>=2.0.0

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🔗 Links

- [Google Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Micronaut PubSub Documentation](https://micronaut-projects.github.io/micronaut-gcp/latest/guide/index.html#pubsub)