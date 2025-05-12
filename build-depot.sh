#!/bin/bash

# Check if tag is provided
if [ -z "$1" ]; then
    echo "Error: Tag not provided"
    echo "Usage: $0 <tag>"
    exit 1
fi

TAG=$1
LATEST_COMMIT_SHA=$(git rev-parse HEAD)

# Change to root directory and use it as build context
cd /
depot build --push / -t fajyz/ois-gold-comfypack:${TAG} --platform linux/amd64 --target=final -f /workspace/runpod-worker-comfy/Dockerfile