"""
Quickstart example - the absolute simplest way to use gcp-pubsub-events.

This example shows how to listen to a PubSub subscription with just a few lines of code.
"""

import os

from gcp_pubsub_events import quick_listen

# Get project ID from environment or use default
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "demo-project")


def handle_message(data, ack):
    """Handle incoming messages."""
    print(f"Received message: {data}")
    ack.ack()


if __name__ == "__main__":
    print("Starting quickstart example...")
    print("This will listen to the 'quickstart-subscription' subscription")
    print("Press Ctrl+C to stop\n")

    # That's it! Just one function call
    quick_listen(
        project_id=PROJECT_ID,
        subscription_name="quickstart-subscription",
        handler=handle_message,
        auto_create_resources=True,  # Will create the subscription if it doesn't exist
    )
