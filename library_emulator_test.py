#!/usr/bin/env python3
"""
Comprehensive test for gcp-pubsub-events library with emulator
This script tests the complete flow: setup -> publish -> subscribe -> verify
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import List, Optional

# Set up emulator environment FIRST
os.environ['PUBSUB_EMULATOR_HOST'] = 'localhost:8085'

try:
    from google.cloud import pubsub_v1
    from pydantic import BaseModel, Field, field_validator
    from gcp_pubsub_events import pubsub_listener, subscription, Acknowledgement, create_pubsub_app
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure to install: pip install google-cloud-pubsub pydantic")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
PROJECT_ID = "test-project"
TOPIC_NAME = "test-topic"
SUBSCRIPTION_NAME = "test-subscription"
TEST_TIMEOUT = 15  # seconds


# Test event model
class Message(BaseModel):
    """Test message with validation."""
    id: str = Field(..., min_length=1, description="Message ID")
    content: str = Field(..., min_length=1, description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    sequence: int = Field(..., ge=1, description="Message sequence number")
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if len(v.strip()) == 0:
            raise ValueError('Content cannot be empty')
        return v.strip()


# Test listener to collect received messages
@pubsub_listener
class MessageListener:
    """Test listener to collect received messages."""
    
    def __init__(self):
        self.received_messages: List[Message] = []
        self.processing_times: List[float] = []
        self.errors: List[str] = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @subscription(SUBSCRIPTION_NAME, Message)
    async def handle_test_message(self, message: Message, ack: Acknowledgement):
        """Handle incoming test messages."""
        start_time = time.time()
        
        try:
            self.logger.info(f"Received message: {message.id} - {message.content}")
            
            # Simulate some processing
            await asyncio.sleep(0.1)
            
            # Store the message
            self.received_messages.append(message)
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            # Acknowledge the message
            ack.ack()
            self.logger.info(f"Processed message {message.id} in {processing_time:.3f}s")
            
        except Exception as error:
            self.errors.append(str(error))
            ack.nack()
            self.logger.error(f"Error processing message {message.id}: {error}")


class EmulatorTester:
    """Main test class to orchestrate the testing."""
    
    def __init__(self):
        self.publisher = None
        self.subscriber = None
        self.topic_path = None
        self.subscription_path = None
        self.listener = None
        self.client = None
        
    def setup_pubsub_resources(self):
        """Create topic and subscription in emulator."""
        print("🔧 Setting up PubSub resources...")
        
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        
        self.topic_path = self.publisher.topic_path(PROJECT_ID, TOPIC_NAME)
        self.subscription_path = self.subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)
        
        # Create topic
        try:
            topic = self.publisher.create_topic(request={"name": self.topic_path})
            print(f"✅ Created topic: {topic.name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"ℹ️  Topic already exists: {self.topic_path}")
            else:
                print(f"❌ Error creating topic: {e}")
                return False
        
        # Create subscription
        try:
            sub = self.subscriber.create_subscription(
                request={"name": self.subscription_path, "topic": self.topic_path}
            )
            print(f"✅ Created subscription: {sub.name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"ℹ️  Subscription already exists: {self.subscription_path}")
            else:
                print(f"❌ Error creating subscription: {e}")
                return False
        
        return True
    
    def publish_test_messages(self, count: int = 5):
        """Publish test messages to the topic."""
        print(f"📤 Publishing {count} test messages...")
        
        published_messages = []
        
        for i in range(1, count + 1):
            test_message = Message(
                id=f"test-msg-{i:03d}",
                content=f"Test message content {i}",
                sequence=i
            )
            
            # Convert to JSON
            message_data = test_message.model_dump_json().encode('utf-8')
            
            try:
                future = self.publisher.publish(self.topic_path, message_data)
                message_id = future.result(timeout=10)
                published_messages.append((test_message, message_id))
                print(f"  ✅ Published message {i}: {message_id}")
                time.sleep(0.2)  # Small delay between messages
                
            except Exception as e:
                print(f"  ❌ Failed to publish message {i}: {e}")
                return []
        
        print(f"📤 Successfully published {len(published_messages)} messages")
        return published_messages
    
    def start_subscriber_in_thread(self):
        """Start the subscriber in a separate thread."""
        print("👂 Starting subscriber...")
        
        self.listener = MessageListener()
        self.client = create_pubsub_app(PROJECT_ID, max_workers=3, max_messages=10)
        
        def run_subscriber():
            try:
                self.client.start_listening(timeout=TEST_TIMEOUT)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
        
        subscriber_thread = threading.Thread(target=run_subscriber, daemon=True)
        subscriber_thread.start()
        
        # Give subscriber time to start
        time.sleep(2)
        return subscriber_thread
    
    def wait_for_messages(self, expected_count: int, timeout: int = TEST_TIMEOUT):
        """Wait for messages to be received."""
        print(f"⏳ Waiting up to {timeout}s for {expected_count} messages...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            received_count = len(self.listener.received_messages)
            print(f"  📨 Received {received_count}/{expected_count} messages")
            
            if received_count >= expected_count:
                print(f"✅ Received all {expected_count} messages!")
                return True
            
            time.sleep(1)
        
        print(f"⏰ Timeout reached. Received {len(self.listener.received_messages)}/{expected_count} messages")
        return False
    
    def verify_results(self, published_messages):
        """Verify that published messages were received correctly."""
        print("🔍 Verifying results...")
        
        received = self.listener.received_messages
        errors = self.listener.errors
        
        print(f"📊 Test Results:")
        print(f"  📤 Published: {len(published_messages)} messages")
        print(f"  📨 Received: {len(received)} messages")
        print(f"  ❌ Errors: {len(errors)}")
        
        if errors:
            print(f"  Error details: {errors}")
        
        if self.listener.processing_times:
            avg_time = sum(self.listener.processing_times) / len(self.listener.processing_times)
            print(f"  ⏱️  Average processing time: {avg_time:.3f}s")
        
        # Verify message content
        success = True
        if len(received) != len(published_messages):
            print(f"❌ Message count mismatch!")
            success = False
        
        # Check each received message
        for i, received_msg in enumerate(received):
            print(f"  📋 Message {i+1}: {received_msg.id} - {received_msg.content}")
            
            # Verify it's a valid Message with validation
            try:
                if received_msg.sequence < 1:
                    print(f"  ❌ Invalid sequence number: {received_msg.sequence}")
                    success = False
                if not received_msg.content.strip():
                    print(f"  ❌ Empty content")
                    success = False
            except Exception as e:
                print(f"  ❌ Validation error: {e}")
                success = False
        
        return success
    
    def cleanup(self):
        """Clean up resources."""
        print("🧹 Cleaning up...")
        if self.client:
            self.client.stop_listening()


def test_emulator_connectivity():
    """Test if emulator is responding."""
    print("🔍 Testing emulator connectivity...")
    try:
        client = pubsub_v1.PublisherClient()
        topic_path = client.topic_path("test-project", "connectivity-test")
        
        # Try to create a test topic
        try:
            client.create_topic(request={"name": topic_path})
            print("✅ Emulator is responding")
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                print("✅ Emulator is responding (topic exists)")
                return True
            else:
                print(f"❌ Emulator error: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Cannot connect to emulator: {e}")
        print("Make sure emulator is running: gcloud beta emulators pubsub start --host-port=localhost:8085")
        return False


def main():
    """Main test function."""
    print("🚀 Starting GCP PubSub Events Library Test")
    print(f"Using emulator: {os.environ.get('PUBSUB_EMULATOR_HOST', 'Not set')}")
    
    # Test emulator connectivity
    if not test_emulator_connectivity():
        return 1
    
    tester = EmulatorTester()
    
    try:
        # Setup resources
        if not tester.setup_pubsub_resources():
            print("❌ Failed to setup PubSub resources")
            return 1
        
        # Start subscriber
        subscriber_thread = tester.start_subscriber_in_thread()
        
        # Publish messages
        published_messages = tester.publish_test_messages(5)
        if not published_messages:
            print("❌ Failed to publish messages")
            return 1
        
        # Wait for messages
        success = tester.wait_for_messages(len(published_messages))
        
        # Stop subscriber
        tester.cleanup()
        
        # Verify results
        verification_success = tester.verify_results(published_messages)
        
        if success and verification_success:
            print("🎉 ALL TESTS PASSED! Library is working correctly with emulator!")
            return 0
        else:
            print("❌ TESTS FAILED! Check the output above for details.")
            return 1
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        tester.cleanup()


if __name__ == "__main__":
    sys.exit(main())