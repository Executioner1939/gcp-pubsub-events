# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GCP PubSub Events is a decorator-based Python library for Google Cloud Pub/Sub event handling. It provides a clean, Pythonic API for building event-driven microservices with minimal boilerplate, inspired by frameworks like Micronaut's @PubSubListener.

## Architecture & Key Components

### Core Architecture Pattern

The library uses a **Registry Pattern** with **Decorators** for automatic handler registration:

1. **Global Registry** (`core/registry.py`): Singleton that maintains all handler-to-subscription mappings
2. **Decorators** auto-register handlers when classes are instantiated:
   - `@pubsub_listener` on classes → registers instance with registry on `__init__`
   - `@subscription("name")` on methods → maps method to subscription name
3. **Client** (`core/client.py`) queries registry for handlers and routes messages
4. **Manager** (`core/manager.py`) provides lifecycle management with context managers

### Message Flow

```
PubSub Message → Client → Registry lookup → Handler method → Acknowledgment (ack/nack)
```

### Key Design Decisions

- **No explicit registration**: Decorators handle registration automatically when instances are created
- **Thread-safe execution**: Uses ThreadPoolExecutor for concurrent message processing
- **Async support**: Handlers can be sync or async; async handlers are run with `asyncio.run()`
- **Type safety**: Optional Pydantic model validation for message payloads
- **Resource management**: Can auto-create topics/subscriptions (configurable)

## Development Commands

```bash
# Install all dependencies (including dev/test)
poetry install --with dev,test

# Run all tests
poetry run pytest

# Run specific test suites
poetry run pytest tests/unit/              # Unit tests only
poetry run pytest tests/integration/       # Integration tests (requires emulator)
poetry run pytest tests/e2e/              # End-to-end tests
poetry run pytest -k "test_name"          # Run specific test

# Code quality
poetry run black src/ tests/              # Format code
poetry run flake8 src/ tests/             # Lint
poetry run mypy src/                      # Type check

# Test with PubSub emulator
export PUBSUB_EMULATOR_HOST=localhost:8085
gcloud beta emulators pubsub start --host-port=localhost:8085

# Build and publish
poetry build                              # Build wheel/sdist
poetry publish --dry-run                  # Test PyPI publish
```

## Testing Approach

### Test Structure
- **Unit tests**: Mock PubSub clients, test decorators and registry in isolation
- **Integration tests**: Use PubSub emulator, test real message flow
- **E2E tests**: Complete workflows including error scenarios
- **Performance tests**: Throughput benchmarks with concurrent publishers

### Key Test Fixtures (in `conftest.py`)
- `clean_registry`: Ensures registry is cleared between tests
- `test_topic`/`test_subscription`: Creates test resources
- `mock_message`: Creates mock PubSub messages for unit tests

## Common Development Tasks

### Adding a New Feature
1. Check if it fits the existing decorator pattern
2. Consider registry implications (thread safety)
3. Add unit tests first, then integration tests
4. Update examples if it's a user-facing feature

### Debugging Message Flow
1. Enable debug logging: `logging.getLogger("gcp_pubsub_events").setLevel(logging.DEBUG)`
2. Check registry state: `registry.get_all_subscriptions()`
3. Verify handler registration happened (instances must be created before starting the manager)

### Performance Considerations
- `max_workers`: Controls ThreadPoolExecutor size (default 10)
- `max_messages`: Flow control for concurrent messages (default 100)
- Long-running handlers block worker threads - use async handlers for I/O

## FastAPI Integration Pattern

The library provides `async_pubsub_manager` for proper lifecycle management:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create service instances FIRST (registers handlers)
    service = MyService()
    
    # Then start manager
    async with async_pubsub_manager(project_id, ...) as manager:
        app.state.service = service
        yield
```

## Code Style & Conventions

- Python 3.11+ with full type annotations
- Black formatting (100 char lines)
- Imports organized by isort (black profile)
- Docstrings on all public APIs
- Async methods prefixed with `async_` when there's a sync equivalent

## Important Files for Context

- `src/gcp_pubsub_events/__init__.py`: Public API exports
- `src/gcp_pubsub_events/core/registry.py`: Central handler registry
- `src/gcp_pubsub_events/decorators/`: Decorator implementations
- `src/gcp_pubsub_events/core/manager.py`: Context managers for lifecycle management
- `src/gcp_pubsub_events/core/client.py`: PubSub client implementation

## Release Process

1. Update version in `pyproject.toml`
2. Commit with message: `chore: bump version to X.Y.Z`
3. Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z - <summary>"`
4. Push: `git push origin main && git push origin vX.Y.Z`
5. GitHub Actions handles PyPI publishing automatically

## Known Gotchas

1. **Handler Registration Timing**: Service instances must be created BEFORE starting the manager
2. **Registry State**: Use `clear_registry_on_start=False` in production to avoid losing handlers
3. **Import Side Effects**: Decorators register on import, but handlers register on instantiation
4. **Async Context**: The manager runs PubSub in a background thread, even in async contexts