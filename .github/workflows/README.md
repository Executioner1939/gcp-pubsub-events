# CI/CD Workflows

This directory contains GitHub Actions workflows for automated testing and deployment.

## Workflows

### `build-and-publish.yml`
- **Trigger**: Push to main/master, tags, PRs
- **Purpose**: Build package and publish to GitHub artifacts
- **Features**:
  - Multi-Python version testing (3.8-3.11)
  - Package building and validation
  - Artifact publishing
  - Release creation on tags

### `integration-tests.yml`
- **Trigger**: Push to main/master/develop, PRs, manual
- **Purpose**: Comprehensive testing with PubSub emulator
- **Features**:
  - Unit, integration, and e2e tests
  - PubSub emulator integration
  - Performance benchmarks
  - Docker-based testing
  - Coverage reporting
  - Multi-environment testing

## Test Structure

```
tests/
├── unit/                 # Unit tests (no external dependencies)
├── integration/          # Integration tests with emulator
├── e2e/                 # End-to-end workflow tests
├── performance/         # Performance benchmarks
├── docker/              # Docker-based testing
└── conftest.py          # Shared test configuration
```

## Running Tests Locally

### Quick Test
```bash
./test_step_by_step.sh
```

### Manual Testing
```bash
# Start emulator
gcloud beta emulators pubsub start --host-port=localhost:8085

# Run tests
export PUBSUB_EMULATOR_HOST=localhost:8085
pytest tests/ -v
```

### Docker Testing
```bash
docker build -f tests/docker/Dockerfile -t gcp-pubsub-events-test .
docker run --rm gcp-pubsub-events-test
```

## CI Features

### 🧪 **Comprehensive Testing**
- **Unit Tests**: Fast, isolated component tests
- **Integration Tests**: Real PubSub emulator integration
- **E2E Tests**: Complete workflow scenarios
- **Performance Tests**: Throughput and latency benchmarks

### 🚀 **Multi-Environment**
- **Python Versions**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Operating System**: Ubuntu (Linux)
- **Docker**: Containerized testing environment

### 📊 **Reporting & Artifacts**
- **Test Results**: JUnit XML format
- **Coverage Reports**: XML and HTML formats
- **Performance Metrics**: JSON benchmark results
- **Build Artifacts**: Wheels and source distributions

### 🔧 **Quality Assurance**
- **Linting**: Code style validation
- **Type Checking**: Static type analysis
- **Coverage**: Code coverage measurement
- **Performance**: Regression detection

## Environment Variables

### Required for Testing
- `PUBSUB_EMULATOR_HOST`: Emulator endpoint (set automatically in CI)

### Optional
- `CODECOV_TOKEN`: For coverage uploads (set in GitHub secrets)

## Secrets Configuration

For full CI functionality, configure these GitHub secrets:

```
CODECOV_TOKEN=<your-codecov-token>  # Optional: for coverage reporting
```

## Performance Baselines

The CI tracks performance metrics:
- **Throughput**: Messages per second
- **Latency**: End-to-end message processing time
- **Resource Usage**: Memory and CPU utilization

Performance regression detection coming soon!

## Troubleshooting CI

### Common Issues

1. **Emulator Start Failure**
   - Check Java installation
   - Verify port availability
   - Review emulator logs

2. **Test Timeouts**
   - Increase timeout values in pytest.ini
   - Check emulator connectivity
   - Review resource limits

3. **Flaky Tests**
   - Add retry mechanisms
   - Increase wait times
   - Improve test isolation

### Debug Steps

1. Check workflow logs in GitHub Actions
2. Run tests locally with same configuration
3. Use Docker environment for consistency
4. Enable debug logging in tests