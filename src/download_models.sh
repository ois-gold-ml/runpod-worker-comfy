#!/bin/bash

set -e

echo "Starting model downloads..."

# Change to ComfyUI directory
cd /workspace

# Download existing models (keeping original downloads) - small files first
# echo "Downloading small model files..."
# wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/hr16/Diffusion-Edge/dsine.pt https://huggingface.co/hr16/Diffusion-Edge/resolve/main/dsine.pt
# wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/TheMistoAI/MistoLine/Anyline/MTEED.pth https://huggingface.co/TheMistoAI/MistoLine/resolve/main/Anyline/MTEED.pth

# Download HEAVIEST models in parallel
echo "Downloading heavy models in parallel..."
# FLUX.1-dev GGUF (~12GB)
wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/unet" \
    "https://huggingface.co/lllyasviel/FLUX.1-dev-gguf/resolve/main/flux1-dev-F16.gguf" &

# FLUX schnell checkpoint (~23GB)
wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/checkpoints/FLUX-checkpoints" \
    "https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors" &

# VAE model (~335MB)
wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/vae" \
    "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors" &

# SAM model (~2.6GB)
wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/sams" \
    "https://huggingface.co/lkeab/hq-sam/resolve/main/sam_hq_vit_h.pth" &

# Wait for heavy downloads to complete
echo "Waiting for heavy model downloads to complete..."
wait

# Download CLIP models in parallel
echo "Downloading CLIP models in parallel..."
wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/clip" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" &

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/clip" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors" &

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/clip" \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" &

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/clip/CLIP-GmP-ViT-L-14" \
    "https://huggingface.co/zer0int/CLIP-GmP-ViT-L-14/resolve/main/ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors" &

echo "Waiting for CLIP model downloads to complete..."
wait

# Download ControlNet models in parallel
echo "Downloading ControlNet models"
# Clone Union Pro in background
wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/controlnet/FLUX.1/Shakker-Labs-ControlNet-Union-Pro" \
    "https://huggingface.co/Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro/resolve/main/diffusion_pytorch_model.safetensors"

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/controlnet/FLUX.1-dev-Controlnet-Inpainting-Beta" \
    "https://huggingface.co/alimama-creative/FLUX.1-dev-Controlnet-Inpainting-Beta/resolve/main/diffusion_pytorch_model.safetensors" &

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/controlnet/FLUX.1" \
    "https://huggingface.co/XLabs-AI/flux-controlnet-canny-v3/resolve/main/flux-canny-controlnet-v3.safetensors" &

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/controlnet/FLUX.1" \
    "https://huggingface.co/XLabs-AI/flux-controlnet-depth-v3/resolve/main/flux-depth-controlnet-v3.safetensors" &

# Wait for all ControlNet downloads
echo "Waiting for ControlNet downloads to complete..."
wait

# Download remaining models in parallel
echo "Downloading remaining models in parallel..."
wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/depthanything" \
    "https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vitl_fp32.safetensors" &

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/loras/big melt" \
    "https://huggingface.co/happyin/flux_melt/resolve/main/melt_LF_no_g_v1-000018.safetensors" &

wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/upscale_models" \
    "https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth" &

echo "Waiting for remaining model downloads to complete..."
wait

# Download LLM models in parallel (large repositories)
echo "Downloading LLM models in parallel..."
git clone https://huggingface.co/microsoft/Florence-2-large-ft models/LLM/Florence-2-large-ft &
git clone https://huggingface.co/MiaoshouAI/Florence-2-large-PromptGen-v2.0 models/LLM/Florence-2-large-PromptGen-v2.0 &

echo "Waiting for LLM model downloads to complete..."
wait

echo "All model downloads completed successfully!" 