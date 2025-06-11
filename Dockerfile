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

# Install Python, git and other necessary tools including aria2 for fast downloads
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    # required for downloading models
    aria2 \
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

# Install ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui && \
    cd /comfyui && \
    # v0.3.40
    git checkout 866f6cd

# Change working directory to ComfyUI
WORKDIR /comfyui

# Install ComfyUI dependencies
RUN pip3 install torch torchvision torchaudio xformers --index-url https://download.pytorch.org/whl/cu126 \
    && pip3 install --upgrade -r requirements.txt

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Support for the network volume
ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Add scripts
ADD src/start.sh src/restore_snapshot.sh src/rp_handler.py test_input.json ./
ADD workflows/ src/workflows/
RUN chmod +x /start.sh /restore_snapshot.sh

# Restore the snapshot to install custom nodes
# ADD *snapshot*.json /
# RUN /restore_snapshot.sh

# Create necessary directories for downloaded models
RUN mkdir -p /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/hr16/Diffusion-Edge
RUN mkdir -p /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/TheMistoAI/MistoLine/Anyline
RUN mkdir -p /comfyui/models/depthanything
RUN mkdir -p /comfyui/models/FLUX-checkpoints
RUN mkdir -p /comfyui/models/clip
RUN mkdir -p /comfyui/models/FLUX.1-dev-Controlnet-Inpainting-Beta
RUN mkdir -p /comfyui/models/FLUX.1
RUN mkdir -p "/comfyui/models/loras/big melt"
RUN mkdir -p /comfyui/models/sams
RUN mkdir -p /comfyui/models/unet
RUN mkdir -p /comfyui/models/LLM
RUN mkdir -p /comfyui/models/upscale_models
RUN mkdir -p /comfyui/models/vae
RUN mkdir -p /comfyui/models/CLIP-GmP-ViT-L-14

# Copy and run custom nodes installation script in base stage
COPY src/install_custom_nodes.sh /install_custom_nodes.sh
COPY src/custom_nodes.txt /custom_nodes.txt
RUN chmod +x /install_custom_nodes.sh && /install_custom_nodes.sh

# Start container
CMD ["/start.sh"]

# Stage 2: Download models
FROM base as downloader

ARG HUGGINGFACE_ACCESS_TOKEN
ARG GH_ACCESS_TOKEN

# Fail if no HuggingFace token is provided
RUN if [ -z "$HUGGINGFACE_ACCESS_TOKEN" ]; then \
        echo "ERROR: HUGGINGFACE_ACCESS_TOKEN build argument is required but not provided."; \
        echo "Please provide it using: --build-arg HUGGINGFACE_ACCESS_TOKEN=your_token"; \
        exit 1; \
    fi

# Fail if no GitHub token is provided
RUN if [ -z "$GH_ACCESS_TOKEN" ]; then \
        echo "ERROR: GH_ACCESS_TOKEN build argument is required but not provided."; \
        echo "Please provide it using: --build-arg GH_ACCESS_TOKEN=your_token"; \
        echo "Create a token at: https://github.com/settings/tokens"; \
        exit 1; \
    fi

# Configure git to use the token for GitHub authentication
RUN git config --global url."https://${GH_ACCESS_TOKEN}@github.com/".insteadOf "https://github.com/"

# Change working directory to ComfyUI
WORKDIR /comfyui

# Create necessary directories with exact paths from workflow
# RUN mkdir -p models/FLUX-checkpoints \
#     models/vae \
#     models/unet \
#     models/clip \
#     models/FLUX.1-dev-Controlnet-Inpainting-Beta \
#     models/FLUX.1 \
#     "models/loras/big melt" \
#     models/sams \
#     models/LLM \
#     models/upscale_models \
#     models/depthanything \
#     models/CLIP-GmP-ViT-L-14

# Copy and run model download script
# COPY src/download_models.sh /download_models.sh
# RUN chmod +x /download_models.sh && /download_models.sh

# Stage 3: Final image
FROM base as final

# Copy models from downloader stage
# COPY --from=downloader /comfyui/models /comfyui/models

# Start container
CMD ["/start.sh"]