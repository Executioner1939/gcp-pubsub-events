# GCP PubSub Listener

A decorator-based Python library for handling Google Cloud Pub/Sub messages, inspired by Micronaut's `@PubSubListener` pattern.

## Features

- **Decorator-based**: Clean, annotation-style API similar to Micronaut
- **Automatic registration**: Classes marked with `@pubsub_listener` are automatically registered
- **Type-safe event handling**: Support for custom event classes with automatic deserialization
- **Async support**: Handlers can be async or sync
- **Error handling**: Proper ack/nack based on handler success/failure
- **Logging**: Built-in logging for debugging and monitoring

## Installation

```bash
pip install google-cloud-pubsub
```

Then download the `pubsub_listener.py` file or install the package when published.

## Quick Start

### 1. Define Event Classes

```python
from dataclasses import dataclass

@dataclass
class RegistrationEvent:
    email: str
    gamer_tag: str
    id: str
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)
```

### 2. Create a Listener Service

```python
from pubsub_listener import pubsub_listener, subscription, Acknowledgement

@pubsub_listener
class PaymentEventService:
    def __init__(self, payment_service):
        self.payment_service = payment_service
    
    @subscription("payments.user.registered", RegistrationEvent)
    async def on_registration(self, event: RegistrationEvent, acknowledgement: Acknowledgement):
        try:
            result = await self.payment_service.create_customer(
                event.email, event.gamer_tag, event.id
            )
            acknowledgement.ack()
            logging.info(f"Registration processed: {result}")
        except Exception as error:
            acknowledgement.nack()
            logging.error(f"Error: {error}")
```

### 3. Start Listening

```python
from pubsub_listener import create_pubsub_app

# Initialize your services
payment_service = YourPaymentService()
payment_event_service = PaymentEventService(payment_service)

# Start listening
client = create_pubsub_app("your-gcp-project-id")
client.start_listening()
```

## API Reference

### Decorators

#### `@pubsub_listener`
Class decorator that marks a class as a PubSub listener. Instances are automatically registered.

#### `@subscription(subscription_name, event_type=None)`
Method decorator that marks a method as a subscription handler.

**Parameters:**
- `subscription_name`: The GCP Pub/Sub subscription name
- `event_type`: Optional event class for automatic deserialization

### Classes

#### `Acknowledgement`
Handles message acknowledgement.

**Methods:**
- `ack()`: Acknowledge successful processing
- `nack()`: Negative acknowledge (mark as failed)

#### `PubSubClient`
Main client for managing subscriptions.

**Methods:**
- `start_listening()`: Start listening to all registered subscriptions
- `stop_listening()`: Stop listening

### Functions

#### `create_pubsub_app(project_id, max_workers=10)`
Create and configure a PubSub application.

## Advanced Usage

### Custom Event Deserialization

```python
@dataclass
class CustomEvent:
    data: dict
    timestamp: str
    
    @classmethod
    def from_dict(cls, data: dict):
        # Custom deserialization logic
        return cls(
            data=data.get('payload', {}),
            timestamp=data.get('timestamp', '')
        )
```

### Error Handling

The library automatically handles acknowledgements based on handler success:
- If handler completes without exception: `ack()` is called
- If handler raises exception: `nack()` is called
- Manual acknowledgement is also supported

### Sync and Async Handlers

Both sync and async handlers are supported:

```python
@subscription("sync.topic")
def sync_handler(self, event, acknowledgement):
    # Synchronous processing
    pass

@subscription("async.topic")
async def async_handler(self, event, acknowledgement):
    # Asynchronous processing
    await some_async_operation()
```

## Publishing

To publish this library:

1. Update `setup.py` with your details
2. Build and upload:

```bash
python setup.py sdist bdist_wheel
pip install twine
twine upload dist/*
```

## Requirements

- Python 3.7+
- google-cloud-pubsub>=2.0.0

## License

MIT License