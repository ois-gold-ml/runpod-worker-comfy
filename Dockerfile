# Stage 1: Base image with common dependencies
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    PYTHONUNBUFFERED=1 \
    CMAKE_BUILD_PARALLEL_LEVEL=8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Install Python, git and other necessary tools
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    aria2 \
    libgl1 \
    libglib2.0-0 \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && apt-get autoremove -y && apt-get clean -y

# Install pip packages with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install comfy-cli

# Install ComfyUI
RUN --mount=type=cache,target=/root/.cache/pip \
    /usr/bin/yes | comfy --workspace /comfyui install --cuda-version 11.8 --nvidia --version 0.3.26

# Change working directory to ComfyUI
WORKDIR /comfyui

# Install runpod
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install runpod requests

# Copy configuration files (less likely to change)
COPY src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Copy scripts
COPY src/start.sh src/install_custom_nodes.sh src/custom_nodes.txt src/rp_handler.py test_input.json ./
RUN chmod +x /start.sh /install_custom_nodes.sh

# Install custom nodes with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    comfy node install comfyui-tensorops save-image-extended-comfyui comfyui-florence2 \
    comfyui-depthanythingv2 comfyui_essentials comfy-easy-grids derfuu_comfyui_moddednodes \
    comfyui_controlnet_aux comfyui-manager ComfyUI-Custom-Scripts

# Stage 2: Download models
FROM base as downloader

ARG HUGGINGFACE_ACCESS_TOKEN
ARG MODEL_TYPE

# Change working directory to ComfyUI
WORKDIR /comfyui

# Create necessary directories
RUN mkdir -p models/checkpoints models/vae models/unet models/clip

# Download checkpoints/vae/LoRA to include in image based on model type
# Using aria2 for faster parallel downloads
RUN if [ "$MODEL_TYPE" = "sdxl" ]; then \
      aria2c -x 16 -s 16 -o models/checkpoints/sd_xl_base_1.0.safetensors https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors && \
      aria2c -x 16 -s 16 -o models/vae/sdxl_vae.safetensors https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors && \
      aria2c -x 16 -s 16 -o models/vae/sdxl-vae-fp16-fix.safetensors https://huggingface.co/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors; \
    elif [ "$MODEL_TYPE" = "sd3" ]; then \
      aria2c -x 16 -s 16 --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" -o models/checkpoints/sd3_medium_incl_clips_t5xxlfp8.safetensors https://huggingface.co/stabilityai/stable-diffusion-3-medium/resolve/main/sd3_medium_incl_clips_t5xxlfp8.safetensors; \
    elif [ "$MODEL_TYPE" = "flux1-schnell" ]; then \
      aria2c -x 16 -s 16 -o models/unet/flux1-schnell.safetensors https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/flux1-schnell.safetensors && \
      aria2c -x 16 -s 16 -o models/clip/clip_l.safetensors https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors && \
      aria2c -x 16 -s 16 -o models/clip/t5xxl_fp8_e4m3fn.safetensors https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors && \
      aria2c -x 16 -s 16 -o models/vae/ae.safetensors https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors; \
    elif [ "$MODEL_TYPE" = "flux1-dev" ]; then \
      aria2c -x 16 -s 16 --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" -o models/unet/flux1-dev.safetensors https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors && \
      aria2c -x 16 -s 16 -o models/clip/clip_l.safetensors https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors && \
      aria2c -x 16 -s 16 -o models/clip/t5xxl_fp8_e4m3fn.safetensors https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors && \
      aria2c -x 16 -s 16 --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" -o models/vae/ae.safetensors https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors; \
    fi

# Stage 3: Final image
FROM base as final

# Copy models from stage 2 to the final image
COPY --from=downloader /comfyui/models /comfyui/models

# Start container
CMD ["/start.sh"]
