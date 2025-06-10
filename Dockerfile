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

# Start container
CMD ["/start.sh"]

# Stage 2: Download models
FROM base as downloader

ARG HUGGINGFACE_ACCESS_TOKEN

# Fail if no HuggingFace token is provided
RUN if [ -z "$HUGGINGFACE_ACCESS_TOKEN" ]; then \
        echo "ERROR: HUGGINGFACE_ACCESS_TOKEN build argument is required but not provided."; \
        echo "Please provide it using: --build-arg HUGGINGFACE_ACCESS_TOKEN=your_token"; \
        exit 1; \
    fi

# Change working directory to ComfyUI
WORKDIR /comfyui

# Create necessary directories with exact paths from workflow
RUN mkdir -p models/FLUX-checkpoints \
    models/vae \
    models/unet \
    models/clip \
    models/FLUX.1-dev-Controlnet-Inpainting-Beta \
    models/FLUX.1 \
    "models/loras/big melt" \
    models/sams \
    models/LLM \
    models/upscale_models \
    models/depthanything \
    models/CLIP-GmP-ViT-L-14

# Download existing models (keeping original downloads)
RUN wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/hr16/Diffusion-Edge/dsine.pt https://huggingface.co/hr16/Diffusion-Edge/resolve/main/dsine.pt
RUN wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/TheMistoAI/MistoLine/Anyline/MTEED.pth https://huggingface.co/TheMistoAI/MistoLine/resolve/main/Anyline/MTEED.pth

# Download checkpoints with workflow-expected paths
RUN wget -O models/FLUX-checkpoints/flux1-schnell-fp8.safetensors https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors

# Download CLIP models with workflow-expected paths
RUN wget -O models/clip/clip_l.safetensors "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors?download=true"
RUN wget -O models/CLIP-GmP-ViT-L-14/ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors "https://huggingface.co/zer0int/CLIP-GmP-ViT-L-14/resolve/main/ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors?download=true"
RUN wget -O models/clip/t5xxl_fp16.safetensors "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors?download=true"
RUN wget -O models/clip/t5xxl_fp8_e4m3fn.safetensors "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors?download=true"

# Download ControlNet models with workflow-expected paths
RUN git clone https://huggingface.co/Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro /tmp/controlnet-union && \
    mkdir -p models/FLUX.1/Shakker-Labs-ControlNet-Union-Pro && \
    cp /tmp/controlnet-union/diffusion_pytorch_model.safetensors models/FLUX.1/Shakker-Labs-ControlNet-Union-Pro/diffusion_pytorch_model.safetensors && \
    rm -rf /tmp/controlnet-union

# Download additional ControlNet models referenced in workflow
# Note: Using XLabs-AI models as they are more reliable
RUN wget -O models/FLUX.1-dev-Controlnet-Inpainting-Beta/diffusion_pytorch_model.safetensors https://huggingface.co/alimama-creative/FLUX.1-dev-Controlnet-Inpainting-Beta/resolve/main/diffusion_pytorch_model.safetensors
RUN wget -O models/FLUX.1/flux-canny-controlnet-v3.safetensors https://huggingface.co/XLabs-AI/flux-controlnet-canny-v3/resolve/main/flux-canny-controlnet-v3.safetensors
RUN wget -O models/FLUX.1/flux-depth-controlnet-v3.safetensors https://huggingface.co/XLabs-AI/flux-controlnet-depth-v3/resolve/main/flux-depth-controlnet-v3.safetensors

# Download DepthAnything models
RUN wget -O models/depthanything/depth_anything_v2_vitl_fp32.safetensors https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vitl_fp32.safetensors

# Download LoRA models from private HuggingFace repository (requires token)
RUN wget --header="Authorization: Bearer $HUGGINGFACE_ACCESS_TOKEN" -O "models/loras/big melt/melt_LF_no_g_v1-000018.safetensors" https://huggingface.co/happyin/flux_melt/resolve/main/melt_LF_no_g_v1-000018.safetensors

# Download SAMs models
RUN wget -O models/sams/sam_hq_vit_h.pth https://huggingface.co/lkeab/hq-sam/resolve/main/sam_hq_vit_h.pth

# Download UNET models
RUN wget -O models/unet/flux1-dev-F16.gguf https://huggingface.co/lllyasviel/FLUX.1-dev-gguf/resolve/main/flux1-dev-F16.gguf

# Download LLM models (via git clone for repositories with multiple files)
RUN git clone https://huggingface.co/microsoft/Florence-2-large-ft models/LLM/Florence-2-large-ft
RUN git clone https://huggingface.co/MiaoshouAI/Florence-2-large-PromptGen-v2.0 models/LLM/Florence-2-large-PromptGen-v2.0

# Download upscale models
RUN wget -O models/upscale_models/4x-UltraSharp.pth https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth

# Download VAE models
RUN wget -O models/vae/ae.safetensors "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors?download=true"

# Clone custom nodes
RUN cd custom_nodes && \
    git clone https://github.com/AnastasiyaW/stable_contusion && \
    git clone https://github.com/AnastasiyaW/happyin && \
    git clone https://github.com/AnastasiyaW/happyin_canny && \
    git clone https://github.com/WASasquatch/was-node-suite-comfyui && \
    git clone https://github.com/Derfuu/Derfuu_ComfyUI_ModdedNodes && \
    git clone https://github.com/city96/ComfyUI-GGUF && \
    git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts && \
    git clone https://github.com/TinyTerra/ComfyUI_tinyterraNodes && \
    git clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale && \
    git clone https://github.com/rgthree/rgthree-comfy && \
    git clone https://github.com/cubiq/ComfyUI_essentials && \
    git clone https://github.com/kijai/ComfyUI-DepthAnythingV2 && \
    git clone https://github.com/kijai/ComfyUI-Florence2 && \
    git clone https://github.com/storyicon/comfyui_segment_anything && \
    git clone https://github.com/yolain/ComfyUI-Easy-Use && \
    git clone https://github.com/crystian/ComfyUI-Crystools && \
    git clone https://github.com/un-seen/comfyui-tensorops && \
    git clone https://github.com/cardenluo/ComfyUI-Apt_Preset && \
    git clone https://github.com/AlekPet/ComfyUI_Custom_Nodes_AlekPet

# Stage 3: Final image
FROM base as final

# Copy models from stage 2 to the final image
COPY --from=downloader /comfyui/models /comfyui/models
COPY --from=downloader /comfyui/custom_nodes /comfyui/custom_nodes

# Start container
CMD ["/start.sh"]