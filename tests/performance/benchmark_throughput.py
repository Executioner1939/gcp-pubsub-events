#!/usr/bin/env python3
"""
Performance benchmarks for the library
"""

import asyncio
import json
import os
import statistics
import threading
import time
from datetime import datetime
from typing import List

from google.cloud import pubsub_v1
from pydantic import BaseModel, Field

from gcp_pubsub_events import Acknowledgement, create_pubsub_app, pubsub_listener, subscription

# Set emulator environment
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8085"


class BenchmarkEvent(BaseModel):
    """Event for benchmarking."""

    id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)
    payload: str = Field(...)
    sequence: int = Field(...)


class PerformanceMetrics:
    """Track performance metrics."""

    def __init__(self):
        self.message_times: List[float] = []
        self.processing_times: List[float] = []
        self.throughput_samples: List[float] = []
        self.start_time: float = 0
        self.end_time: float = 0
        self.total_messages: int = 0
        self.processed_messages: int = 0
        self.errors: int = 0

    def start_benchmark(self):
        """Start timing the benchmark."""
        self.start_time = time.time()

    def end_benchmark(self):
        """End timing the benchmark."""
        self.end_time = time.time()

    def record_message_processed(self, processing_time: float):
        """Record a processed message."""
        self.processed_messages += 1
        self.processing_times.append(processing_time)

    def record_error(self):
        """Record an error."""
        self.errors += 1

    def get_summary(self) -> dict:
        """Get performance summary."""
        total_time = self.end_time - self.start_time

        return {
            "total_messages": self.total_messages,
            "processed_messages": self.processed_messages,
            "errors": self.errors,
            "total_time_seconds": total_time,
            "messages_per_second": self.processed_messages / total_time if total_time > 0 else 0,
            "avg_processing_time_ms": (
                statistics.mean(self.processing_times) * 1000 if self.processing_times else 0
            ),
            "median_processing_time_ms": (
                statistics.median(self.processing_times) * 1000 if self.processing_times else 0
            ),
            "p95_processing_time_ms": (
                statistics.quantiles(self.processing_times, n=20)[18] * 1000
                if len(self.processing_times) >= 20
                else 0
            ),
            "p99_processing_time_ms": (
                statistics.quantiles(self.processing_times, n=100)[98] * 1000
                if len(self.processing_times) >= 100
                else 0
            ),
        }


def run_throughput_benchmark(message_count: int = 1000, payload_size: int = 1024):
    """Run throughput benchmark."""
    print(
        f"🚀 Running throughput benchmark: {message_count} messages, {payload_size} bytes payload"
    )

    project_id = "benchmark-project"
    topic_name = f"benchmark-topic-{int(time.time())}"
    subscription_name = f"benchmark-sub-{int(time.time())}"

    # Setup PubSub resources
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    topic_path = publisher.topic_path(project_id, topic_name)
    subscription_path = subscriber.subscription_path(project_id, subscription_name)

    # Create topic and subscription
    publisher.create_topic(request={"name": topic_path})
    subscriber.create_subscription(request={"name": subscription_path, "topic": topic_path})

    # Performance tracking
    metrics = PerformanceMetrics()
    metrics.total_messages = message_count

    @pubsub_listener
    class BenchmarkListener:
        def __init__(self, metrics: PerformanceMetrics):
            self.metrics = metrics

        @subscription(subscription_name, BenchmarkEvent)
        async def handle_benchmark_message(self, event: BenchmarkEvent, ack: Acknowledgement):
            start_time = time.time()

            try:
                # Simulate some processing work
                await asyncio.sleep(0.001)  # 1ms of work

                processing_time = time.time() - start_time
                self.metrics.record_message_processed(processing_time)
                ack.ack()

            except Exception:
                self.metrics.record_error()
                ack.nack()

    # Create listener instance - this registers the handlers via decorators
    BenchmarkListener(metrics)
    client = create_pubsub_app(project_id, max_workers=10, max_messages=50)

    # Start client in thread
    def run_client():
        client.start_listening(timeout=60)

    client_thread = threading.Thread(target=run_client, daemon=True)
    client_thread.start()
    time.sleep(2)  # Let client start

    # Start benchmark timing
    metrics.start_benchmark()

    # Publish messages
    print(f"📤 Publishing {message_count} messages...")
    payload = "x" * payload_size  # Create payload of specified size

    publish_start = time.time()

    for i in range(message_count):
        event = BenchmarkEvent(id=f"bench-{i:06d}", payload=payload, sequence=i + 1)

        message_data = event.model_dump_json().encode("utf-8")
        publisher.publish(topic_path, message_data)

        # Don't wait for result to maximize throughput
        if i % 100 == 0:
            print(f"  📤 Published {i} messages...")

    publish_time = time.time() - publish_start
    print(
        f"📤 Publishing completed in {publish_time:.2f}s ({message_count/publish_time:.1f} msg/s)"
    )

    # Wait for all messages to be processed
    print("⏳ Waiting for messages to be processed...")
    timeout = 120  # 2 minutes timeout
    start_wait = time.time()

    while time.time() - start_wait < timeout:
        if metrics.processed_messages >= message_count:
            break

        if time.time() - start_wait > 10 and metrics.processed_messages == 0:
            print("❌ No messages processed after 10 seconds, something might be wrong")
            break

        print(f"  📨 Processed {metrics.processed_messages}/{message_count} messages...")
        time.sleep(2)

    # End benchmark timing
    metrics.end_benchmark()

    # Stop client
    client.stop_listening()

    # Cleanup
    try:
        subscriber.delete_subscription(request={"subscription": subscription_path})
        publisher.delete_topic(request={"topic": topic_path})
    except Exception:
        pass

    return metrics


def run_latency_benchmark(message_count: int = 100):
    """Run latency benchmark with detailed timing."""
    print(f"🕐 Running latency benchmark: {message_count} messages")

    project_id = "latency-project"
    topic_name = f"latency-topic-{int(time.time())}"
    subscription_name = f"latency-sub-{int(time.time())}"

    # Setup
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    topic_path = publisher.topic_path(project_id, topic_name)
    subscription_path = subscriber.subscription_path(project_id, subscription_name)

    publisher.create_topic(request={"name": topic_path})
    subscriber.create_subscription(request={"name": subscription_path, "topic": topic_path})

    # Track end-to-end latency
    sent_times = {}
    received_times = {}

    @pubsub_listener
    class LatencyListener:
        @subscription(subscription_name, BenchmarkEvent)
        def handle_latency_message(self, event: BenchmarkEvent, ack: Acknowledgement):
            received_times[event.id] = time.time()
            ack.ack()

    # Setup client - this registers the handlers via decorators
    LatencyListener()
    client = create_pubsub_app(project_id, max_workers=5, max_messages=10)

    def run_client():
        client.start_listening(timeout=30)

    client_thread = threading.Thread(target=run_client, daemon=True)
    client_thread.start()
    time.sleep(2)

    # Send messages one by one with timing
    print(f"📤 Sending {message_count} messages for latency measurement...")

    for i in range(message_count):
        event = BenchmarkEvent(
            id=f"latency-{i:04d}", payload="latency test payload", sequence=i + 1
        )

        send_time = time.time()
        sent_times[event.id] = send_time

        message_data = event.model_dump_json().encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        future.result()  # Wait for publish confirmation

        time.sleep(0.1)  # Small delay between messages

    # Wait for all messages
    timeout = 30
    start_wait = time.time()

    while time.time() - start_wait < timeout:
        if len(received_times) >= message_count:
            break
        time.sleep(0.5)

    client.stop_listening()

    # Calculate latencies
    latencies = []
    for event_id in sent_times:
        if event_id in received_times:
            latency = received_times[event_id] - sent_times[event_id]
            latencies.append(latency * 1000)  # Convert to milliseconds

    # Cleanup
    try:
        subscriber.delete_subscription(request={"subscription": subscription_path})
        publisher.delete_topic(request={"topic": topic_path})
    except Exception:
        pass

    if latencies:
        return {
            "message_count": len(latencies),
            "avg_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "p95_latency_ms": (
                statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else 0
            ),
            "p99_latency_ms": (
                statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else 0
            ),
        }
    else:
        return {"error": "No messages received for latency measurement"}


def main():
    """Run all benchmarks."""
    print("🏁 Starting Performance Benchmarks")
    print("=" * 50)

    results = {}

    # Throughput benchmarks
    for msg_count, payload_size in [(100, 512), (500, 1024), (1000, 2048)]:
        print(f"\n📊 Throughput Benchmark: {msg_count} messages, {payload_size}B payload")
        metrics = run_throughput_benchmark(msg_count, payload_size)
        summary = metrics.get_summary()

        results[f"throughput_{msg_count}_{payload_size}"] = summary

        print("✅ Results:")
        print(f"   Messages/sec: {summary['messages_per_second']:.1f}")
        print(f"   Avg processing: {summary['avg_processing_time_ms']:.2f}ms")
        print(f"   P95 processing: {summary['p95_processing_time_ms']:.2f}ms")
        print(f"   Errors: {summary['errors']}")

    # Latency benchmark
    print("\n🕐 Latency Benchmark")
    latency_results = run_latency_benchmark(50)
    results["latency"] = latency_results

    if "error" not in latency_results:
        print("✅ Latency Results:")
        print(f"   Avg latency: {latency_results['avg_latency_ms']:.2f}ms")
        print(f"   Median latency: {latency_results['median_latency_ms']:.2f}ms")
        print(f"   P95 latency: {latency_results['p95_latency_ms']:.2f}ms")
        print(f"   P99 latency: {latency_results['p99_latency_ms']:.2f}ms")
    else:
        print(f"❌ Latency test failed: {latency_results['error']}")

    # Save results
    with open("performance-results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n📊 Performance results saved to performance-results.json")
    print("🏁 Benchmarks completed!")


if __name__ == "__main__":
    main()
