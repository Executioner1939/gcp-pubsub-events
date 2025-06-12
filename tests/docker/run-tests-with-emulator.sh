#!/bin/bash
set -e

echo "🐳 Running tests in Docker with PubSub emulator"

# Start PubSub emulator in background
echo "🚀 Starting PubSub emulator..."
gcloud beta emulators pubsub start --host-port=0.0.0.0:8085 &
EMULATOR_PID=$!

# Function to cleanup
cleanup() {
    echo "🧹 Cleaning up..."
    kill $EMULATOR_PID 2>/dev/null || true
    wait $EMULATOR_PID 2>/dev/null || true
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Wait for emulator to start
echo "⏳ Waiting for emulator to start..."
timeout=30
while [ $timeout -gt 0 ]; do
    if curl -f http://localhost:8085 >/dev/null 2>&1; then
        echo "✅ Emulator is ready!"
        break
    fi
    sleep 1
    timeout=$((timeout-1))
done

if [ $timeout -eq 0 ]; then
    echo "❌ Emulator failed to start!"
    exit 1
fi

# Set environment
export PUBSUB_EMULATOR_HOST=localhost:8085

# Run tests
echo "🧪 Running unit tests..."
pytest tests/unit/ -v

echo "🧪 Running integration tests..."
pytest tests/integration/ -v --timeout=60

echo "🧪 Running e2e tests..."
pytest tests/e2e/ -v --timeout=120

echo "🧪 Running comprehensive test..."
python test_library_emulator.py

echo "✅ All Docker tests completed successfully!"