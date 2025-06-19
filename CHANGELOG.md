# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-06-19

### BREAKING CHANGES
- Removed `run_pubsub_app()` function - use context managers instead
- Removed `quick_listen()` function - use decorators with context managers
- Removed `simple.py` module entirely
- Removed examples directory from the package

### Changed
- Simplified API surface to focus on decorator pattern and context managers
- Updated README to reflect the streamlined API
- Improved documentation clarity

### Fixed
- Fixed "Client is already listening" warning by improving state management
- Fixed UnboundLocalError with time module imports
- Fixed thread lifecycle issues in unit tests

### Migration Guide

If you were using `run_pubsub_app()`:

```python
# Old way (removed)
from gcp_pubsub_events import run_pubsub_app
run_pubsub_app("my-project")

# New way
from gcp_pubsub_events import PubSubManager

with PubSubManager("my-project") as manager:
    # Your application code here
    pass
```

If you were using `quick_listen()`:

```python
# Old way (removed)
from gcp_pubsub_events import quick_listen
quick_listen("my-project", "my-subscription", handler)

# New way
from gcp_pubsub_events import pubsub_listener, subscription, PubSubManager

@pubsub_listener
class MyListener:
    @subscription("my-subscription")
    def handle(self, data, ack):
        handler(data, ack)

listener = MyListener()
with PubSubManager("my-project") as manager:
    # Keep running
    pass
```

## [1.3.1] - 2025-06-19

### Fixed
- Fixed UnboundLocalError with time module
- Improved warning messages for "Client is already listening"

## [1.3.0] - 2025-06-19

### Added
- Comprehensive type annotations throughout the codebase
- Better error messages and logging

### Fixed
- Various linting issues (flake8, mypy)
- Import ordering problems

## [1.2.1] - 2025-06-19

### Improved
- Documentation and user experience
- Better examples in README

## [1.2.0] - 2025-06-19

### Added
- Initial stable release with decorator-based API
- Context manager support
- FastAPI integration
- Automatic resource creation
- Comprehensive test suite