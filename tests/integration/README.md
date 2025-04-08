# Integration Tests for RunPod Worker ComfyUI

This directory contains integration tests for the RunPod worker ComfyUI handler. These tests validate the "happy path" workflow without mocking any of the internal functions, only mocking the external services (ComfyUI, HTTP server for inputs, and TUS server for outputs).

## Prerequisites

- Python 3.8+
- pip
- Required packages: flask, requests, tusclient

## Test Files

- `mock_comfyui.py`: A mock implementation of the ComfyUI server APIs.
- `mock_http_server.py`: A simple HTTP server for serving test input images.
- `mock_tus_server.py`: A simple TUS protocol server for receiving output images.
- `test_integration.py`: The main test suite with integration tests.
- `data/`: Directory containing test input and output images.

## Running the Tests

### Locally

You can run the tests using the provided shell script:

```bash
./run_integration_tests.sh
```

Or manually:

```bash
pip install -r requirements.txt
python test_integration.py
```

### Using Docker

For a consistent testing environment, you can use Docker to run the tests:

```bash
./run_docker_tests.sh
```

This script will:
1. Build a Docker image based on the Dockerfile
2. Run the tests in a container
3. Clean up after completion

Alternatively, you can use Docker Compose directly:

```bash
docker-compose build
docker-compose run --rm integration-tests
docker-compose down
```

## Test Cases

The integration tests validate:

1. **Full workflow with input image**: Tests the complete path from providing a workflow and input image URL, to generating an output image and uploading it to a TUS server.

2. **Workflow without input image**: Tests the workflow when no input image is provided, only generating based on the workflow.

## How It Works

The integration tests:

1. Start a mock ComfyUI server that mimics the real ComfyUI API behavior.
2. Start a mock HTTP server to serve test input images.
3. Start a mock TUS server to receive uploaded output images.
4. Run the `handler` function directly, passing job data with realistic inputs.
5. Verify that the output is correctly processed and uploaded.
6. Stop all mock servers and clean up temporary files.

This approach tests the entire workflow with real HTTP requests and file operations, only mocking the external services.