# Stage 1: Base image with common dependencies
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

# Environment variables for optimization
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    PYTHONUNBUFFERED=1 \
    CMAKE_BUILD_PARALLEL_LEVEL=8 \
    PIP_NO_CACHE_DIR=1

# Install Python, git and other necessary tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    aria2 \
    libgl1 \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Install Python packages in parallel
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -U pip && \
    pip install comfy-cli runpod requests

# Install ComfyUI
RUN --mount=type=cache,target=/root/.cache/pip \
    /usr/bin/yes | comfy --workspace /comfyui install --cuda-version 11.8 --nvidia --version 0.3.26

# Change working directory to ComfyUI
WORKDIR /comfyui

# Support for the network volume - rarely changes
ADD src/extra_model_paths.yaml ./

# Add executable scripts - rarely changes
ADD src/start.sh src/install_custom_nodes.sh ./
RUN chmod +x /start.sh /install_custom_nodes.sh

# Add configuration files - more likely to change
ADD src/custom_nodes.txt src/rp_handler.py test_input.json /

# Install custom nodes
RUN --mount=type=cache,target=/root/.cache/pip \
    /install_custom_nodes.sh

# Stage 2: Download models
FROM base as downloader

ARG HUGGINGFACE_ACCESS_TOKEN
ARG MODEL_TYPE

# Create necessary directories
RUN mkdir -p models/checkpoints models/vae models/unet models/clip

# Install controlnet aux separately to avoid conflicts
RUN --mount=type=cache,target=/root/.cache/pip \
    comfy node install comfyui_controlnet_aux

# Download checkpoints/vae/LoRA based on model type using aria2 for faster downloads
RUN if [ "$MODEL_TYPE" = "sdxl" ]; then \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors -d models/checkpoints -o sd_xl_base_1.0.safetensors && \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors -d models/vae -o sdxl_vae.safetensors && \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors -d models/vae -o sdxl-vae-fp16-fix.safetensors; \
    elif [ "$MODEL_TYPE" = "sd3" ]; then \
      aria2c -x 16 -s 16 -k 1M --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" https://huggingface.co/stabilityai/stable-diffusion-3-medium/resolve/main/sd3_medium_incl_clips_t5xxlfp8.safetensors -d models/checkpoints -o sd3_medium_incl_clips_t5xxlfp8.safetensors; \
    elif [ "$MODEL_TYPE" = "flux1-schnell" ]; then \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/flux1-schnell.safetensors -d models/unet -o flux1-schnell.safetensors && \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors -d models/clip -o clip_l.safetensors && \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors -d models/clip -o t5xxl_fp8_e4m3fn.safetensors && \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors -d models/vae -o ae.safetensors; \
    elif [ "$MODEL_TYPE" = "flux1-dev" ]; then \
      aria2c -x 16 -s 16 -k 1M --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors -d models/unet -o flux1-dev.safetensors && \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors -d models/clip -o clip_l.safetensors && \
      aria2c -x 16 -s 16 -k 1M https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors -d models/clip -o t5xxl_fp8_e4m3fn.safetensors && \
      aria2c -x 16 -s 16 -k 1M --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors -d models/vae -o ae.safetensors; \
    fi

# Stage 3: Final image
FROM base as final

# Copy models from stage 2 to the final image
COPY --from=downloader /comfyui/models /comfyui/models

# Start container
CMD ["/start.sh"]
