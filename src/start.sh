#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    echo "runpod-worker-comfy: Starting ComfyUI"
    python3 /comfyui/main.py --disable-auto-launch --disable-metadata --listen &

    # Create a symlink to the workspace directory because `runpod-volume` is only mounted in serverless container
    ln -s /workspace /runpod-volume

    # Start Jupyter Lab only if token is provided
    if [ -n "$JUPYTER_TOKEN" ]; then
        echo "runpod-worker-comfy: Starting Jupyter Lab"
        echo "runpod-worker-comfy: Jupyter Lab will be available at http://localhost:8888 with token: $JUPYTER_TOKEN"
        jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token="$JUPYTER_TOKEN" --notebook-dir=/workspace &
    else
        echo "runpod-worker-comfy: Jupyter Lab not started (JUPYTER_TOKEN not provided)"
    fi

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    echo "runpod-worker-comfy: Starting ComfyUI"
    python3 /comfyui/main.py --disable-auto-launch --disable-metadata &

    echo "runpod-worker-comfy: Starting RunPod Handler"
    python3 -u /rp_handler.py
fi