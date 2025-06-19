# GCP PubSub Events

[![CI](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml/badge.svg)](https://github.com/Executioner1939/gcp-pubsub-events/actions/workflows/build-and-publish.yml)
[![PyPI version](https://badge.fury.io/py/gcp-pubsub-events.svg)](https://pypi.org/project/gcp-pubsub-events/)
[![codecov](https://codecov.io/gh/Executioner1939/gcp-pubsub-events/branch/main/graph/badge.svg)](https://codecov.io/gh/Executioner1939/gcp-pubsub-events)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, decorator-based Python library for Google Cloud Pub/Sub event handling. Inspired by event-driven architectures and frameworks like Micronaut, this library makes it incredibly easy to build scalable, event-driven microservices with minimal boilerplate.

## 🎯 Why Use This Library?

- **Minimal Boilerplate**: Just 3 lines of code to start listening to events
- **Type Safety**: Full Pydantic model support with automatic validation
- **Production Ready**: Battle-tested with automatic retries, error handling, and graceful shutdowns
- **Framework Agnostic**: Works standalone or integrates seamlessly with FastAPI, Flask, Django
- **Developer Friendly**: Automatic resource creation, comprehensive logging, easy testing

## 🚀 Quick Start

### Installation

```bash
pip install gcp-pubsub-events
```

### Simplest Example - Just 3 Lines!

```python
from gcp_pubsub_events import quick_listen

def handle_message(data, ack):
    print(f"Received: {data}")
    ack.ack()

quick_listen("my-project", "my-subscription", handle_message)
```

That's it! The library handles everything else - connection management, error handling, graceful shutdown, and more.

## 📚 Core Concepts

### 1. The Decorator Pattern

This library uses two main decorators:

- `@pubsub_listener`: Marks a class as containing event handlers
- `@subscription("subscription-name")`: Marks a method as handling messages from a specific subscription

### 2. Message Acknowledgment

Every handler receives an `Acknowledgement` object to control message flow:
- `ack.ack()`: Message processed successfully, remove from queue
- `ack.nack()`: Processing failed, retry later

### 3. Automatic Resource Creation

By default, the library creates missing topics and subscriptions automatically. Perfect for development and optional for production.

## 🎓 Examples by Use Case

### Basic Event Handler

```python
from gcp_pubsub_events import pubsub_listener, subscription, run_pubsub_app

@pubsub_listener
class EventHandler:
    @subscription("user-events")
    def handle_user_event(self, data: dict, ack):
        """Handle raw dictionary data"""
        user_id = data.get("user_id")
        action = data.get("action")
        
        print(f"User {user_id} performed {action}")
        
        # Process the event
        if self.process_user_action(user_id, action):
            ack.ack()  # Success - remove from queue
        else:
            ack.nack()  # Failed - retry later
    
    def process_user_action(self, user_id: str, action: str) -> bool:
        # Your business logic here
        return True

# Create handler and run
handler = EventHandler()
run_pubsub_app("my-project-id")
```

### Type-Safe Events with Pydantic

```python
from datetime import datetime
from pydantic import BaseModel, Field
from gcp_pubsub_events import pubsub_listener, subscription, Acknowledgement

class UserRegistered(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    plan: str = Field(default="free", description="Subscription plan")
    timestamp: datetime = Field(default_factory=datetime.now)

@pubsub_listener
class UserService:
    def __init__(self, database, email_service):
        self.db = database
        self.email = email_service
    
    @subscription("user-registrations", UserRegistered)
    async def on_user_registered(self, event: UserRegistered, ack: Acknowledgement):
        """Handle user registration with automatic validation"""
        try:
            # Event is already validated and typed!
            await self.db.create_user(
                id=event.user_id,
                email=event.email,
                plan=event.plan
            )
            
            await self.email.send_welcome_email(event.email)
            
            print(f"✅ User {event.user_id} registered successfully")
            ack.ack()
            
        except Exception as e:
            print(f"❌ Failed to process registration: {e}")
            ack.nack()
```

### FastAPI Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from gcp_pubsub_events import async_pubsub_manager, pubsub_listener, subscription

@pubsub_listener
class OrderService:
    def __init__(self):
        self.orders = []
    
    @subscription("order-events")
    async def handle_order(self, data: dict, ack):
        self.orders.append(data)
        print(f"📦 New order: {data['order_id']}")
        ack.ack()

# Initialize service
order_service = OrderService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage PubSub lifecycle with FastAPI"""
    async with async_pubsub_manager("my-project") as manager:
        yield

app = FastAPI(lifespan=lifespan)

@app.get("/orders")
def get_orders():
    return {"orders": order_service.orders}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "order-processor"}
```

### Multiple Subscription Handlers

```python
@pubsub_listener
class PaymentProcessor:
    @subscription("payment-requests")
    async def handle_payment_request(self, data: dict, ack):
        """Process incoming payment requests"""
        amount = data.get("amount", 0)
        
        if amount <= 0:
            print(f"❌ Invalid amount: {amount}")
            ack.ack()  # Don't retry invalid requests
            return
            
        success = await self.process_payment(data)
        if success:
            ack.ack()
        else:
            ack.nack()
    
    @subscription("payment-confirmations")
    async def handle_confirmation(self, data: dict, ack):
        """Handle payment confirmations from payment provider"""
        await self.update_payment_status(data["transaction_id"], "confirmed")
        await self.notify_customer(data["customer_id"])
        ack.ack()
    
    @subscription("refund-requests")
    async def handle_refund(self, data: dict, ack):
        """Process refund requests"""
        try:
            await self.process_refund(data["transaction_id"], data["amount"])
            ack.ack()
        except RefundError:
            ack.nack()  # Retry refund later
```

### Advanced Validation and Error Handling

```python
from pydantic import BaseModel, validator, root_validator
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class Order(BaseModel):
    order_id: str
    customer_id: str
    items: list[dict]
    total_amount: float
    status: OrderStatus = OrderStatus.PENDING
    
    @validator("total_amount")
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Total amount must be positive")
        return round(v, 2)
    
    @validator("items")
    def validate_items(cls, v):
        if not v:
            raise ValueError("Order must contain at least one item")
        return v

@pubsub_listener
class OrderProcessor:
    @subscription("orders", Order)
    async def process_order(self, order: Order, ack: Acknowledgement):
        """Process orders with full validation"""
        try:
            # Order is automatically validated before reaching here
            if order.status == OrderStatus.CANCELLED:
                print(f"⚠️ Skipping cancelled order {order.order_id}")
                ack.ack()
                return
            
            # Process based on order status
            if order.status == OrderStatus.PENDING:
                await self.confirm_inventory(order)
                await self.charge_customer(order)
                order.status = OrderStatus.CONFIRMED
            
            elif order.status == OrderStatus.CONFIRMED:
                tracking = await self.ship_order(order)
                await self.send_tracking_email(order.customer_id, tracking)
                order.status = OrderStatus.SHIPPED
            
            ack.ack()
            
        except InventoryError:
            # Retry later when inventory might be available
            ack.nack()
        except PaymentError:
            # Payment failed - don't retry
            await self.notify_payment_failure(order.customer_id)
            ack.ack()
        except Exception as e:
            # Unexpected error - log and retry
            print(f"❌ Unexpected error: {e}")
            ack.nack()
```

### Context Manager for Lifecycle Management

```python
from gcp_pubsub_events import pubsub_manager

# Automatic setup and cleanup
with pubsub_manager("my-project") as manager:
    # Your application runs here
    # PubSub connections are managed automatically
    run_application()
    # Graceful shutdown happens automatically

# Or manually control the lifecycle
manager = PubSubManager("my-project")
manager.start()

# Your application code
try:
    run_application()
finally:
    manager.stop()  # Ensures clean shutdown
```

### Development vs Production Settings

```python
# Development - Auto-create resources, verbose logging
run_pubsub_app(
    "my-project",
    auto_create_resources=True,  # Create topics/subscriptions automatically
    clear_registry=True,          # Clear previous registrations (hot-reload friendly)
    log_level="DEBUG",            # Verbose logging
    max_workers=2,                # Less resource usage
    max_messages=10               # Smaller batches for testing
)

# Production - Strict mode, optimized settings
run_pubsub_app(
    "my-project",
    auto_create_resources=False,  # Resources must exist
    clear_registry=False,         # Keep registry between restarts
    log_level="WARNING",          # Less verbose
    max_workers=20,               # More parallel processing
    max_messages=1000,            # Larger batches for throughput
    clear_registry_on_start=False # Prevent accidental registry clearing
)
```

## 🏗️ Architecture

### Project Structure

```
my-service/
├── src/
│   └── my_service/
│       ├── events/          # Event handlers
│       │   ├── __init__.py
│       │   ├── user_events.py
│       │   └── order_events.py
│       ├── models/          # Pydantic models
│       │   ├── __init__.py
│       │   └── events.py
│       └── main.py         # Application entry point
├── tests/
├── pyproject.toml
└── README.md
```

### Component Overview

1. **Decorators**: `@pubsub_listener` and `@subscription` for easy handler registration
2. **Registry**: Global registry tracks all handlers and subscriptions
3. **Client**: Manages Pub/Sub connections and message routing
4. **Manager**: Provides context managers and lifecycle management
5. **Resources**: Automatic topic and subscription creation/validation

## 🔧 Configuration

### Environment Variables

```bash
# Required
export GOOGLE_CLOUD_PROJECT="my-project-id"

# Optional
export PUBSUB_EMULATOR_HOST="localhost:8085"  # For local development
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### Programmatic Configuration

```python
from gcp_pubsub_events import PubSubManager

manager = PubSubManager(
    project_id="my-project",
    max_workers=10,              # Thread pool size
    max_messages=100,            # Max concurrent messages
    clear_registry_on_start=True # Clear handlers on restart
)

# Resource creation configuration
resource_config = {
    "ack_deadline_seconds": 600,  # 10 minutes to process
    "message_retention_duration": "7d",
    "retry_policy": {
        "minimum_backoff": "10s",
        "maximum_backoff": "600s"
    }
}

manager = PubSubManager(
    project_id="my-project",
    resource_config=resource_config
)
```

## 🧪 Testing

### Unit Testing Handlers

```python
import pytest
from unittest.mock import Mock
from my_service.events import UserEventHandler

def test_user_registration_handler():
    # Create handler instance
    handler = UserEventHandler()
    
    # Create mock acknowledgement
    ack = Mock()
    
    # Test data
    event_data = {
        "user_id": "123",
        "email": "test@example.com"
    }
    
    # Call handler
    handler.handle_registration(event_data, ack)
    
    # Assert acknowledgement
    ack.ack.assert_called_once()
```

### Integration Testing with Emulator

```python
@pytest.mark.integration
def test_pubsub_integration():
    # Set emulator
    os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8085"
    
    # Create test client
    with pubsub_manager("test-project") as manager:
        # Publish test message
        publisher = PublisherClient()
        topic_path = publisher.topic_path("test-project", "test-topic")
        
        future = publisher.publish(
            topic_path,
            b'{"test": "data"}',
            encoding="utf-8"
        )
        future.result()
        
        # Wait for processing
        time.sleep(2)
        
        # Assert handler was called
        assert handler.call_count == 1
```

## 📊 Performance Considerations

### Throughput Optimization

```python
# High-throughput configuration
run_pubsub_app(
    "my-project",
    max_workers=50,        # More parallel workers
    max_messages=1000,     # Larger batches
    flow_control_settings={
        "max_messages": 1000,
        "max_bytes": 1e9,  # 1GB
        "max_lease_duration": "3600s"
    }
)
```

### Memory Management

```python
@pubsub_listener
class LargeFileProcessor:
    @subscription("large-files")
    async def process_file(self, data: dict, ack):
        file_url = data["file_url"]
        
        # Stream file instead of loading into memory
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                async for chunk in response.content.iter_chunked(8192):
                    await self.process_chunk(chunk)
        
        ack.ack()
```

## 🐛 Troubleshooting

### Common Issues and Solutions

#### "Client is already listening" Warning
This typically occurs during development with hot-reload:

```python
# Solution 1: Use clear_registry
run_pubsub_app("my-project", clear_registry=True)

# Solution 2: For FastAPI/Flask development
async with async_pubsub_manager(
    "my-project",
    clear_registry_on_start=True
) as manager:
    # Your app
    pass
```

#### "No subscriptions registered" Error
Ensure you've created instances of your listener classes:

```python
# ❌ Wrong - Class not instantiated
@pubsub_listener
class MyHandler:
    @subscription("my-sub")
    def handle(self, data, ack):
        pass

# ✅ Correct - Create instance
handler = MyHandler()  # This registers the handlers
run_pubsub_app("my-project")
```

#### Memory Leaks
Monitor and limit concurrent message processing:

```python
# Prevent memory overload
manager = PubSubManager(
    "my-project",
    max_messages=50,      # Limit concurrent messages
    max_workers=5,        # Limit threads
    flow_control_settings={
        "max_bytes": 100_000_000  # 100MB max
    }
)
```

## 🛡️ Security Best Practices

1. **Use Service Accounts**: Never use user credentials in production
2. **Minimum Permissions**: Grant only `roles/pubsub.subscriber` for consumers
3. **Message Validation**: Always validate incoming messages
4. **Encryption**: Enable message encryption for sensitive data
5. **Dead Letter Queues**: Configure DLQs for failed messages

```python
# Configure dead letter queue
resource_config = {
    "dead_letter_policy": {
        "dead_letter_topic": "projects/my-project/topics/dead-letters",
        "max_delivery_attempts": 5
    }
}
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Resources

- [Google Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Library API Reference](https://gcp-pubsub-events.readthedocs.io)
- [Example Projects](https://github.com/Executioner1939/gcp-pubsub-events/tree/main/examples)
- [Issue Tracker](https://github.com/Executioner1939/gcp-pubsub-events/issues)

## 💡 Credits

Inspired by:
- [Micronaut's @PubSubListener](https://micronaut-projects.github.io/micronaut-gcp/latest/guide/)
- [Spring Cloud GCP](https://spring.io/projects/spring-cloud-gcp)
- Modern Python async patterns

---

<p align="center">
  Made with ❤️ by developers, for developers
</p>