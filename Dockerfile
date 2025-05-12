# Stage 1: Base image with common dependencies
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive
# Prefer binary wheels over source distributions for faster pip installations
ENV PIP_PREFER_BINARY=1
# Ensures output from python is printed immediately to the terminal without buffering
ENV PYTHONUNBUFFERED=1 
# Speed up some cmake builds
ENV CMAKE_BUILD_PARALLEL_LEVEL=8

# Install Python, git and other necessary tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    libgl1 \
    # required for cloning HF repos (florence-2-large-ft)
    git-lfs \
    libgl1-mesa-glx libglib2.0-0 -y \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && git lfs install

# Clean up to reduce image size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Copy the pre-configured ComfyUI directory
COPY /ComfyUI /comfyui

# Copy all Python packages from the host system
COPY /usr/local/lib/python* /usr/local/lib/
COPY /usr/lib/python* /usr/lib/

# Install runpod
RUN pip install runpod requests

# Support for the network volume
ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Add scripts
ADD src/start.sh src/rp_handler.py test_input.json workflow.json ./
RUN chmod +x /start.sh

# Start container
CMD ["/start.sh"]

# Stage 2: Download models
FROM base as downloader

# Change working directory to ComfyUI
WORKDIR /comfyui

# Stage 3: Final image
FROM base as final

# Start container
CMD ["/start.sh"]