# Stage 1: Base image with common dependencies
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

# Set environment variables in a single layer
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    PYTHONUNBUFFERED=1 \
    CMAKE_BUILD_PARALLEL_LEVEL=8

# Install Python, git and other necessary tools including aria2 for fast downloads
# Combine apt operations to reduce layers and cleanup in the same step
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    aria2 \
    libgl1 \
    git-lfs \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && git lfs install \
    && apt-get autoremove -y && apt-get clean -y

# Install ComfyUI - this rarely changes so put it early in the build
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui && \
    cd /comfyui && \
    git checkout 866f6cd

# Change working directory to ComfyUI
WORKDIR /comfyui

# Copy requirements files first to leverage caching
COPY requirements.txt ./
COPY src/extra_model_paths.yaml ./
COPY src/custom_nodes.txt /custom_nodes.txt

# Install all Python dependencies in a single layer
# This includes ComfyUI requirements and your custom requirements
RUN pip3 install torch torchvision torchaudio xformers --index-url https://download.pytorch.org/whl/cu126 \
    && pip3 install --upgrade -r requirements.txt

# Create all necessary directories in a single layer
RUN mkdir -p \
    /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/hr16/Diffusion-Edge \
    /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/TheMistoAI/MistoLine/Anyline \
    /comfyui/models/depthanything \
    /comfyui/models/FLUX-checkpoints \
    /comfyui/models/clip \
    /comfyui/models/FLUX.1-dev-Controlnet-Inpainting-Beta \
    /comfyui/models/FLUX.1 \
    "/comfyui/models/loras/big melt" \
    /comfyui/models/sams \
    /comfyui/models/unet \
    /comfyui/models/LLM \
    /comfyui/models/upscale_models \
    /comfyui/models/vae \
    /comfyui/models/CLIP-GmP-ViT-L-14

# Copy scripts and workflows
COPY src/install_custom_nodes.sh /install_custom_nodes.sh
COPY src/start.sh src/restore_snapshot.sh src/rp_handler.py test_input.json /
COPY workflows/ /src/workflows/

# Make scripts executable and install custom nodes
RUN chmod +x /start.sh /restore_snapshot.sh /install_custom_nodes.sh && \
    /install_custom_nodes.sh

# Start container
CMD ["/start.sh"]

# Stage 2: Final image (simplified from original)
FROM base as final

# Copy models from downloader stage
# COPY --from=downloader /comfyui/models /comfyui/models

CMD ["/start.sh"]
