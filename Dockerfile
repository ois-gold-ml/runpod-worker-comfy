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
    # required for comfyui_controlnet_aux custom node
    libgl1-mesa-glx libglib2.0-0 -y \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Install git lfs for HF repo downloads
RUN git lfs install

# Clean up to reduce image size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install comfy-cli
RUN pip install comfy-cli

# Install ComfyUI
RUN /usr/bin/yes | comfy --workspace /comfyui install --cuda-version 11.8 --nvidia --version 0.3.26

# Change working directory to ComfyUI
WORKDIR /comfyui

# Install runpod
RUN pip install runpod requests

# Support for the network volume
ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Add scripts
ADD src/start.sh src/restore_snapshot.sh src/rp_handler.py test_input.json workflow.json ./
RUN chmod +x /start.sh /restore_snapshot.sh

# Optionally copy the snapshot file
ADD *snapshot*.json /

# Restore the snapshot to install custom nodes
RUN /restore_snapshot.sh

# Create necessary directories for downloaded models
RUN mkdir -p /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/hr16/Diffusion-Edge
RUN mkdir -p /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/TheMistoAI/MistoLine/Anyline
RUN mkdir -p /comfyui/models/depthanything

# Start container
CMD ["/start.sh"]

# Stage 2: Download models
FROM base as downloader

ARG HUGGINGFACE_ACCESS_TOKEN
ARG MODEL_TYPE

# Change working directory to ComfyUI
WORKDIR /comfyui

# Create necessary directories
RUN mkdir -p models/checkpoints models/vae models/unet models/clip
RUN wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/hr16/Diffusion-Edge/dsine.pt https://huggingface.co/hr16/Diffusion-Edge/resolve/main/dsine.pt
RUN wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/TheMistoAI/MistoLine/Anyline/MTEED.pth https://huggingface.co/TheMistoAI/MistoLine/resolve/main/Anyline/MTEED.pth
RUN wget -O /comfyui/models/depthanything/depth_anything_v2_vitl_fp32.safetensors https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vitl_fp32.safetensors
RUN git clone https://huggingface.co/microsoft/Florence-2-large-ft models/LLM/Florence-2-large-ft

# Stage 3: Final image
FROM base as final

# Copy models from stage 2 to the final image
COPY --from=downloader /comfyui/models /comfyui/models
COPY --from=downloader /comfyui/custom_nodes /comfyui/custom_nodes

# Start container
CMD ["/start.sh"]