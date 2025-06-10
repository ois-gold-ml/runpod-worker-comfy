#!/bin/bash

set -e

echo "Starting model downloads..."

# Change to ComfyUI directory
cd /comfyui

# Download existing models (keeping original downloads) - small files first
echo "Downloading small model files..."
wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/hr16/Diffusion-Edge/dsine.pt https://huggingface.co/hr16/Diffusion-Edge/resolve/main/dsine.pt
wget -O /comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/TheMistoAI/MistoLine/Anyline/MTEED.pth https://huggingface.co/TheMistoAI/MistoLine/resolve/main/Anyline/MTEED.pth

# Download HEAVIEST models with aria2 (parallel connections for max speed)
echo "Downloading heavy models in parallel..."
# FLUX.1-dev GGUF (~12GB) - heaviest file, max parallel connections
aria2c -x 16 -s 16 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/unet/flux1-dev-F16.gguf \
    https://huggingface.co/lllyasviel/FLUX.1-dev-gguf/resolve/main/flux1-dev-F16.gguf &

# FLUX schnell checkpoint (~23GB) - second heaviest
aria2c -x 12 -s 12 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/FLUX-checkpoints/flux1-schnell-fp8.safetensors \
    https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors &

# VAE model (~335MB) 
aria2c -x 8 -s 8 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/vae/ae.safetensors \
    "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors?download=true" &

# SAM model (~2.6GB)
aria2c -x 8 -s 8 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/sams/sam_hq_vit_h.pth \
    https://huggingface.co/lkeab/hq-sam/resolve/main/sam_hq_vit_h.pth &

# Wait for heavy downloads to complete
echo "Waiting for heavy model downloads to complete..."
wait

# Download CLIP models with aria2 (medium-sized files)
echo "Downloading CLIP models in parallel..."
aria2c -x 8 -s 8 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/clip/clip_l.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors?download=true" &

aria2c -x 8 -s 8 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/clip/t5xxl_fp16.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors?download=true" &

aria2c -x 8 -s 8 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/clip/t5xxl_fp8_e4m3fn.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors?download=true" &

aria2c -x 8 -s 8 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/CLIP-GmP-ViT-L-14/ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors \
    "https://huggingface.co/zer0int/CLIP-GmP-ViT-L-14/resolve/main/ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors?download=true" &

echo "Waiting for CLIP model downloads to complete..."
wait

# Download ControlNet models in parallel
echo "Downloading ControlNet models in parallel..."
# Clone Union Pro in background
git clone https://huggingface.co/Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro /tmp/controlnet-union &

# Download other ControlNet models with aria2
aria2c -x 6 -s 6 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/FLUX.1-dev-Controlnet-Inpainting-Beta/diffusion_pytorch_model.safetensors \
    https://huggingface.co/alimama-creative/FLUX.1-dev-Controlnet-Inpainting-Beta/resolve/main/diffusion_pytorch_model.safetensors &

aria2c -x 6 -s 6 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/FLUX.1/flux-canny-controlnet-v3.safetensors \
    https://huggingface.co/XLabs-AI/flux-controlnet-canny-v3/resolve/main/flux-canny-controlnet-v3.safetensors &

aria2c -x 6 -s 6 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/FLUX.1/flux-depth-controlnet-v3.safetensors \
    https://huggingface.co/XLabs-AI/flux-controlnet-depth-v3/resolve/main/flux-depth-controlnet-v3.safetensors &

# Wait for all ControlNet downloads
echo "Waiting for ControlNet downloads to complete..."
wait

# Process Union Pro after clone completes
echo "Processing Union Pro ControlNet..."
mkdir -p models/FLUX.1/Shakker-Labs-ControlNet-Union-Pro
cp /tmp/controlnet-union/diffusion_pytorch_model.safetensors models/FLUX.1/Shakker-Labs-ControlNet-Union-Pro/diffusion_pytorch_model.safetensors
rm -rf /tmp/controlnet-union

# Download remaining models with aria2 (smaller files)
echo "Downloading remaining models in parallel..."
aria2c -x 6 -s 6 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/depthanything/depth_anything_v2_vitl_fp32.safetensors \
    https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vitl_fp32.safetensors &

aria2c -x 6 -s 6 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    --header="Authorization: Bearer $GH_ACCESS_TOKEN" \
    -o "models/loras/big melt/melt_LF_no_g_v1-000018.safetensors" \
    https://huggingface.co/happyin/flux_melt/resolve/main/melt_LF_no_g_v1-000018.safetensors &

aria2c -x 6 -s 6 -j 1 --auto-file-renaming=false --allow-overwrite=true \
    -o models/upscale_models/4x-UltraSharp.pth \
    https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth &

echo "Waiting for remaining model downloads to complete..."
wait

# Download LLM models in parallel (large repositories)
echo "Downloading LLM models in parallel..."
git clone https://huggingface.co/microsoft/Florence-2-large-ft models/LLM/Florence-2-large-ft &
git clone https://huggingface.co/MiaoshouAI/Florence-2-large-PromptGen-v2.0 models/LLM/Florence-2-large-PromptGen-v2.0 &

echo "Waiting for LLM model downloads to complete..."
wait

echo "All model downloads completed successfully!" 