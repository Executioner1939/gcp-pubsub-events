"""
Simple example using the high-level API.

This demonstrates the easiest way to use gcp-pubsub-events.
"""

import os

from gcp_pubsub_events import pubsub_listener, run_pubsub_app, subscription

# Get project ID from environment or use default
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "demo-project")


@pubsub_listener
class SimpleEventHandler:
    """A simple event handler that processes messages."""

    def __init__(self):
        self.message_count = 0

    @subscription("simple-events")
    def handle_event(self, data: dict, ack):
        """Handle incoming events."""
        self.message_count += 1
        print(f"Message {self.message_count}: {data}")

        # Process the message
        if "error" in data:
            print("Error found in message, not acknowledging")
            ack.nack()
        else:
            print("Message processed successfully")
            ack.ack()


def main():
    """Run the simple example."""
    print(f"Starting simple PubSub app for project: {PROJECT_ID}")
    print("Make sure the PubSub emulator is running if in development!")
    print("Press Ctrl+C to stop\n")

    # Create the handler instance
    handler = SimpleEventHandler()

    # Run the app - it's that simple!
    run_pubsub_app(
        project_id=PROJECT_ID,
        auto_create_resources=True,  # Will create topics/subscriptions if missing
        clear_registry=True,  # Good for development to avoid duplicate registrations
        log_level="INFO",
    )


if __name__ == "__main__":
    main()
