FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install Google Cloud SDK and PubSub emulator
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update && apt-get install -y google-cloud-cli google-cloud-cli-pubsub-emulator && \
    rm -rf /var/lib/apt/lists/*

# Set Java environment (default-jdk location)
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Set working directory
WORKDIR /workspace

# Copy requirements and install Python dependencies
COPY requirements.txt setup.py README.md ./
COPY gcp_pubsub_events/ ./gcp_pubsub_events/

# Install the library
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir pytest pytest-asyncio pytest-timeout

# Copy test files
COPY tests/ ./tests/
COPY test_library_emulator.py ./

# Set environment for emulator
ENV PUBSUB_EMULATOR_HOST=localhost:8085

# Default command
CMD ["pytest", "tests/", "-v"]