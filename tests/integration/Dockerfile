FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt /app/requirements.txt
COPY tests/integration/requirements.txt /app/tests/integration/requirements.txt

# Install both project and test dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir -r /app/tests/integration/requirements.txt

# Copy project files
COPY src /app/src
COPY tests /app/tests

# Set environment variables
ENV PYTHONPATH=/app
ENV COMFY_OUTPUT_PATH=/tmp/comfyui_output
ENV COMFY_HOST=127.0.0.1:8188
ENV COMFY_POLLING_INTERVAL_MS=100
ENV COMFY_POLLING_MAX_RETRIES=20
ENV PYTHONUNBUFFERED=1
ENV FLASK_DEBUG=1

# Create necessary directories
RUN mkdir -p /tmp/comfyui_output /app/tests/integration/uploads

# Set working directory for tests
WORKDIR /app/tests/integration

# Command to run tests
CMD ["python", "-u", "test_integration.py"]