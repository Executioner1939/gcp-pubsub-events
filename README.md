# GCP PubSub Events

[![CI](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml/badge.svg)](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml)
[![PyPI version](https://badge.fury.io/py/gcp-pubsub-events.svg)](https://pypi.org/project/gcp-pubsub-events/)
[![codecov](https://codecov.io/gh/Executioner1939/gcp-pubsub-events/branch/main/graph/badge.svg)](https://codecov.io/gh/Executioner1939/gcp-pubsub-events)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A decorator-based Python library for handling Google Cloud Pub/Sub messages, inspired by Micronaut's `@PubSubListener` pattern. This library provides a clean, type-safe way to build event-driven microservices with automatic resource management and seamless FastAPI integration.

## 🚀 Features

- **🎯 Decorator-based**: Clean, annotation-style API similar to Micronaut
- **🔄 Context Manager Support**: Proper lifecycle management with `with` and `async with` syntax
- **⚡ FastAPI Integration**: Seamless integration with FastAPI using lifespan events
- **🛠️ Automatic Resource Creation**: Missing topics and subscriptions are created automatically
- **📝 Automatic Registration**: Classes marked with `@pubsub_listener` are automatically registered
- **🔒 Type-safe Event Handling**: Support for Pydantic models with automatic validation
- **⚙️ Async/Sync Support**: Handlers can be async or sync functions
- **❌ Smart Error Handling**: Automatic ack/nack based on handler success/failure
- **🧵 Thread Management**: Background thread handling with graceful shutdown
- **📦 Production Ready**: Comprehensive testing, CI/CD, and monitoring support

## 📦 Installation

Install from PyPI:
```bash
pip install gcp-pubsub-events
```

Or with Poetry:
```bash
poetry add gcp-pubsub-events
```

For development:
```bash
git clone https://github.com/Executioner1939/gcp-pubsub-events.git
cd gcp-pubsub-events
poetry install --with dev,test
```

## 🚀 Quick Start

Here's a complete example that shows how to set up event handling in under 10 lines of code:

```python
from gcp_pubsub_events import pubsub_listener, subscription, pubsub_manager, Acknowledgement
from pydantic import BaseModel

class UserEvent(BaseModel):
    user_id: str
    action: str

@pubsub_listener
class EventHandler:
    @subscription("user-events", UserEvent)
    def handle_user_event(self, event: UserEvent, ack: Acknowledgement):
        print(f"User {event.user_id} performed: {event.action}")
        ack.ack()

# Start listening
with pubsub_manager("your-project-id"):
    print("Listening for events...")
    # Your app runs here
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

## 📋 Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Detailed Usage](#-detailed-usage)
- [FastAPI Integration](#-fastapi-integration)
- [API Reference](#-api-reference)
- [Advanced Usage](#-advanced-usage)
- [Testing](#-testing)
- [Examples](#-examples)
- [Development](#️-development)
- [Contributing](#-contributing)

## 📚 Detailed Usage

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

The context manager automatically handles startup and shutdown:

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

## ⚡ FastAPI Integration

Perfect for building event-driven microservices:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from gcp_pubsub_events import async_pubsub_manager

# Global variable to store the manager
pubsub_manager_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pubsub_manager_instance
    # Startup: Initialize PubSub
    async with async_pubsub_manager("your-gcp-project-id") as manager:
        pubsub_manager_instance = manager
        yield
    # Shutdown: Automatic cleanup
    pubsub_manager_instance = None

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "running"}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "pubsub_running": pubsub_manager_instance.is_running if pubsub_manager_instance else False
    }
```

### Alternative FastAPI Pattern with Dependency Injection

```python
from fastapi import FastAPI, Depends
from gcp_pubsub_events import PubSubManager

# Create manager instance
manager = PubSubManager("your-project-id")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the manager
    manager.start()
    yield
    # Stop the manager
    manager.stop()

app = FastAPI(lifespan=lifespan)

# Use as dependency
def get_pubsub_manager() -> PubSubManager:
    return manager

@app.get("/status")
def get_status(pubsub: PubSubManager = Depends(get_pubsub_manager)):
    return {"pubsub_running": pubsub.is_running}
```

## 🔧 Manual Management

For advanced use cases where you need full control:

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

#### `create_pubsub_app(project_id, max_workers=10, max_messages=100, auto_create_resources=True, resource_config=None)`
Create and configure a PubSub application.

**Parameters:**
- `auto_create_resources` (bool): Whether to automatically create missing topics/subscriptions
- `resource_config` (dict): Configuration for resource creation

#### `pubsub_manager(project_id, max_workers=5, max_messages=100, auto_create_resources=True, resource_config=None, **flow_control_settings)`
Context manager for PubSub operations.

#### `async_pubsub_manager(project_id, max_workers=5, max_messages=100, auto_create_resources=True, resource_config=None, **flow_control_settings)`
Async context manager for PubSub operations (ideal for FastAPI).

#### `ResourceManager(project_id, auto_create=True)`
Direct resource management for topics and subscriptions.

**Methods:**
- `ensure_topic_exists(topic_name, **config)`: Ensure topic exists
- `ensure_subscription_exists(subscription_name, topic_name, **config)`: Ensure subscription exists
- `list_topics()`: List all topics in project
- `list_subscriptions()`: List all subscriptions in project

## 🔥 Performance & Monitoring

### Performance Configuration

```python
from gcp_pubsub_events import create_pubsub_app

# Configure for high throughput
client = create_pubsub_app(
    "your-project-id",
    max_workers=20,           # More concurrent handlers
    max_messages=500,         # Larger message batches
    flow_control_settings={
        "max_lease_duration": 600,  # 10 minutes max processing
        "max_extension_period": 300  # 5 minutes extension
    }
)
```

### Health Monitoring

```python
@app.get("/health/pubsub")
def pubsub_health():
    return {
        "status": "healthy" if pubsub_manager_instance.is_running else "unhealthy",
        "subscriptions": len(PubSubRegistry.get_subscriptions()),
        "listeners": len(PubSubRegistry.get_listeners())
    }
```

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

## 🔧 Automatic Resource Creation

The library automatically creates missing topics and subscriptions by default, making development and deployment easier.

### Default Behavior (Auto-Creation Enabled)

```python
from gcp_pubsub_events import create_pubsub_app

# Topics and subscriptions are created automatically
client = create_pubsub_app("my-project")
client.start_listening()  # Creates resources as needed
```

### Disable Auto-Creation

```python
# Disable auto-creation for production environments
client = create_pubsub_app("my-project", auto_create_resources=False)
```

### Resource Configuration

```python
# Configure resource creation
resource_config = {
    "ack_deadline_seconds": 30,
    "retain_acked_messages": True,
    "message_retention_duration": "7d"
}

client = create_pubsub_app(
    "my-project", 
    auto_create_resources=True,
    resource_config=resource_config
)
```

### Manual Resource Management

```python
from gcp_pubsub_events import ResourceManager

# Direct resource management
manager = ResourceManager("my-project", auto_create=True)

# Create topic with configuration
topic_path = manager.ensure_topic_exists("my-topic")

# Create subscription with configuration
subscription_path = manager.ensure_subscription_exists(
    "my-subscription",
    "my-topic",
    ack_deadline_seconds=60,
    dead_letter_policy={
        "dead_letter_topic": "projects/my-project/topics/dead-letters",
        "max_delivery_attempts": 5
    }
)

# List existing resources
topics = manager.list_topics()
subscriptions = manager.list_subscriptions()
```

### Resource Naming Convention

By default, the library uses the subscription name as the topic name. You can override this:

```python
@pubsub_listener
class CustomTopicService:
    @subscription("my-subscription", EventModel)
    def handle_event(self, event: EventModel, ack: Acknowledgement):
        # This creates:
        # - Topic: "my-subscription" 
        # - Subscription: "my-subscription"
        pass
```

## 🧪 Testing

The library includes comprehensive testing support with the PubSub emulator:

```bash
# Install development dependencies
poetry install --with dev,test

# Start the emulator
gcloud beta emulators pubsub start --host-port=localhost:8085

# Set environment variable
export PUBSUB_EMULATOR_HOST=localhost:8085

# Run tests
poetry run pytest tests/ -v

# Run tests with coverage
poetry run pytest tests/ --cov=gcp_pubsub_events --cov-report=html
```

### Test Coverage

We maintain high test coverage with comprehensive unit, integration, and end-to-end tests:
- **Unit tests**: Fast, isolated component tests
- **Integration tests**: Real PubSub emulator integration  
- **E2E tests**: Complete workflow scenarios
- **Performance tests**: Throughput and latency benchmarks

Coverage reports are automatically generated and uploaded to [Codecov](https://codecov.io/gh/Executioner1939/gcp-pubsub-events).

## 💡 Best Practices

### 1. Error Handling
```python
@pubsub_listener
class RobustEventHandler:
    @subscription("critical-events", CriticalEvent)
    async def handle_critical_event(self, event: CriticalEvent, ack: Acknowledgement):
        try:
            await self.process_event(event)
            ack.ack()
        except RetryableError as e:
            # Let PubSub retry by not acknowledging
            logger.warning(f"Retryable error: {e}")
            ack.nack()  
        except FatalError as e:
            # Acknowledge to prevent infinite retries
            logger.error(f"Fatal error: {e}")
            await self.send_to_dead_letter_queue(event)
            ack.ack()
```

### 2. Resource Configuration
```python
# Production-ready configuration
resource_config = {
    "ack_deadline_seconds": 60,
    "retain_acked_messages": False,
    "message_retention_duration": "7d",
    "dead_letter_policy": {
        "dead_letter_topic": "projects/my-project/topics/dead-letters",
        "max_delivery_attempts": 5
    }
}
```

### 3. Testing Strategy
```python
# Use emulator for integration tests
@pytest.fixture
def pubsub_emulator():
    # Start emulator, yield, cleanup
    pass

def test_event_handling(pubsub_emulator):
    # Test your handlers with real PubSub
    pass
```

## 📖 Examples

Check out the complete examples in the repository:
- **Basic Example**: `examples/basic_example.py` - Simple usage with Pydantic models
- **FastAPI Example**: `examples/fastapi_example.py` - Complete FastAPI integration
- **Advanced Example**: `examples/advanced_example.py` - Complex validation and multiple event types
- **Performance Example**: `examples/performance_example.py` - High-throughput configuration

## 🛠️ Development

### Setup Development Environment

```bash
git clone <repository-url>
cd gcp-pubsub-events
poetry install --with dev,test
```

### Running Tests

```bash
# Run tests with Poetry
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=gcp_pubsub_events --cov-report=html
```

## 📋 Requirements

- Python 3.11+
- google-cloud-pubsub>=2.0.0
- pydantic>=2.0.0

## 🐛 Troubleshooting

### Common Issues

#### "Subscription does not exist" Error
```python
# Enable auto-creation (default)
client = create_pubsub_app("project-id", auto_create_resources=True)

# Or create resources manually
from gcp_pubsub_events import ResourceManager
manager = ResourceManager("project-id")
manager.ensure_subscription_exists("my-sub", "my-topic")
```

#### Permission Errors
Ensure your service account has these IAM roles:
- `roles/pubsub.admin` (for auto-creation)
- `roles/pubsub.subscriber` (minimum for listening)

#### Memory Issues with High Throughput
```python
# Configure flow control
client = create_pubsub_app(
    "project-id",
    flow_control_settings={
        "max_messages": 100,  # Reduce batch size
        "max_bytes": 1024 * 1024  # 1MB limit
    }
)
```

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch**: `git checkout -b feature/amazing-feature`
4. **Make your changes** and add tests
5. **Run the test suite**: `poetry run pytest`
6. **Run linting**: `poetry run black . && poetry run flake8`
7. **Commit your changes**: `git commit -m "Add amazing feature"`
8. **Push to your fork**: `git push origin feature/amazing-feature`
9. **Submit a pull request**

### Development Guidelines
- Add tests for new features
- Update documentation as needed
- Follow existing code style
- Ensure all CI checks pass

## 📄 License

MIT License - see LICENSE file for details.

## 🔗 Links

- [Google Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Micronaut PubSub Documentation](https://micronaut-projects.github.io/micronaut-gcp/latest/guide/index.html#pubsub)