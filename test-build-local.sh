#!/usr/bin/env bash
set -e

# Build the Docker image for the file-operations-test stage
IMAGE_NAME="comfyui-file-test-local"
DOCKERFILE="Dockerfile"

# Optionally allow passing build args
EXTRA_ARGS="$@"

echo "[INFO] Building Docker image for file-operations-test stage..."
docker build --target file-operations-test -t "$IMAGE_NAME" -f "$DOCKERFILE" $EXTRA_ARGS .

if [ $? -eq 0 ]; then
  echo "[SUCCESS] Docker build for file-operations-test completed successfully."
  echo "You can run: docker run --rm $IMAGE_NAME"
else
  echo "[ERROR] Docker build failed!"
  exit 1
fi 