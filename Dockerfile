# Stage 1: Test base (for testing file operations only)
FROM ubuntu:22.04 as test-base

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive

# Install minimal dependencies for testing file operations
RUN apt-get update && apt-get install -y \
    python3 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

# Create a mock ComfyUI directory structure
RUN mkdir -p /comfyui
WORKDIR /comfyui

# Stage 2: Production base with CUDA dependencies
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04 as prod-base

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive
# Prefer binary wheels over source distributions for faster pip installations
ENV PIP_PREFER_BINARY=1
# Ensures output from python is printed immediately to the terminal without buffering
ENV PYTHONUNBUFFERED=1 
# Speed up some cmake builds
ENV CMAKE_BUILD_PARALLEL_LEVEL=8

ARG HUGGINGFACE_ACCESS_TOKEN
RUN if [ -z "$HUGGINGFACE_ACCESS_TOKEN" ]; then \
        echo "ERROR: HUGGINGFACE_ACCESS_TOKEN build argument is required but not provided."; \
        echo "Please provide it using: --build-arg HUGGINGFACE_ACCESS_TOKEN=your_token"; \
        exit 1; \
    fi

# Set the environment variable (ARG/ENV as needed)
ARG GH_ACCESS_TOKEN
RUN if [ -z "$GH_ACCESS_TOKEN" ]; then \
        echo "ERROR: GH_ACCESS_TOKEN build argument is required but not provided."; \
        echo "Please provide it using: --build-arg GH_ACCESS_TOKEN=your_token"; \
        exit 1; \
    fi

# Install Python, git and other necessary tools including aria2 for fast downloads
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    git \
    wget \
    gettext \
    libgl1 \
    libgl1-mesa-glx libglib2.0-0 -y \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/python3.10 /usr/bin/python3 \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Clean up to reduce image size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Install ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui && \
    cd /comfyui && \
    # v0.3.40
    git checkout 866f6cd

# Change working directory to ComfyUI
WORKDIR /comfyui

# Stage 3: File operations (shared between test and production)
FROM test-base as file-operations-test

# Support for the network volume
COPY src/extra_model_paths.yaml ./

# Create workflows directory
RUN mkdir -p /workflows

# Copy workflow files with directory structure preserved
COPY workflows/ /workflows/

# Add scripts
COPY src/start.sh src/restore_snapshot.sh src/rp_handler.py src/install_custom_nodes.sh src/custom_nodes.txt.template test_input.json /
RUN chmod +x /start.sh /restore_snapshot.sh /install_custom_nodes.sh

# Test validation command - will fail if any of the expected files/directories don't exist
RUN echo "Running file structure validation tests..." && \
    test -f /comfyui/extra_model_paths.yaml && \
    test -d /workflows && \
    test -f /workflows/2_0.4/workflow.json && \
    test -f /workflows/2_0.6/workflow.json && \
    test -f /workflows/3_0.4/workflow.json && \
    test -f /workflows/3_0.6/workflow.json && \
    test -f /workflows/4_0.4/workflow.json && \
    test -f /workflows/4_0.6/workflow.json && \
    test -f /workflows/5_0.4/workflow.json && \
    test -f /workflows/5_0.6/workflow.json && \
    test -f /start.sh && test -x /start.sh && \
    test -f /restore_snapshot.sh && test -x /restore_snapshot.sh && \
    test -f /rp_handler.py && \
    test -f /test_input.json && \
    test -f /custom_nodes.txt.template && \
    echo "All file structure tests passed!"

# Stage 4: Production build with dependencies
FROM prod-base as production

# Install ComfyUI dependencies
RUN pip3 install torch torchvision torchaudio xformers --index-url https://download.pytorch.org/whl/cu126 \
    && pip3 install --upgrade -r requirements.txt

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy happyin requirements and install them in a virtual environment
COPY happyin/requirements.txt requirements-happyin.txt
RUN python3 -m venv /comfyui/venv && \
    /comfyui/venv/bin/pip install --upgrade pip && \
    /comfyui/venv/bin/pip install -r requirements-happyin.txt

# required for ComfyUI-Apt_Preset
RUN pip3 install --upgrade pip setuptools wheel watchdog

# required for happyin image describer
RUN pip3 install ollama

# Install Jupyter Lab for local development when SERVE_API_LOCALLY=true
RUN pip3 install jupyterlab

# Copy file structure from test stage
COPY --from=file-operations-test /comfyui/ /comfyui/
COPY --from=file-operations-test /workflows/ /workflows/
COPY --from=file-operations-test /start.sh /restore_snapshot.sh /install_custom_nodes.sh /rp_handler.py /test_input.json /
COPY --from=file-operations-test /custom_nodes.txt.template /custom_nodes.txt.template

# Copy and extract custom_nodes.tar.gz
COPY happyin/custom_nodes.tar.gz /tmp/custom_nodes.tar.gz
COPY happyin/custom_nodes.md5.txt /tmp/custom_nodes.md5.txt
RUN cd /tmp && \
    echo "Verifying custom_nodes.tar.gz integrity..." && \
    echo "$(cat custom_nodes.md5.txt)  custom_nodes.tar.gz" | md5sum -c - && \
    echo "MD5 verification passed!" && \
    tar -xzf custom_nodes.tar.gz && \
    cp -r ComfyUI/custom_nodes/* /comfyui/custom_nodes/ && \
    rm -rf /tmp/custom_nodes.tar.gz /tmp/ComfyUI /tmp/custom_nodes.md5.txt

# Generate custom_nodes.txt with envsubst
# RUN envsubst < /custom_nodes.txt.template > /custom_nodes.txt

# ARG GH_ACCESS_TOKEN
# RUN /install_custom_nodes.sh && rm -f /custom_nodes.txt

# Stage 5: Download models (optional)
# FROM production as downloader

ARG HUGGINGFACE_ACCESS_TOKEN
RUN wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/depthanything" \
    "https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vitl_fp32.safetensors"


# RUN wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/LLM/Florence-2-large-PromptGen-v2.0" \
#     "https://huggingface.co/MiaoshouAI/Florence-2-large-PromptGen-v2.0/resolve/main/model.safetensors"

RUN wget --header="Authorization: Bearer ${HUGGINGFACE_ACCESS_TOKEN}" --directory-prefix="models/sams" \
    "https://huggingface.co/lkeab/hq-sam/resolve/main/sam_hq_vit_h.pth"

# Download Florence-2 models
RUN pip3 install huggingface_hub
RUN python3 -c "import os; from huggingface_hub import snapshot_download; os.environ['HF_TOKEN'] = '${HUGGINGFACE_ACCESS_TOKEN}'; snapshot_download(repo_id='microsoft/Florence-2-base', local_dir='/comfyui/models/LLM/Florence-2-base', local_dir_use_symlinks=False)"
RUN python3 -c "import os; from huggingface_hub import snapshot_download; os.environ['HF_TOKEN'] = '${HUGGINGFACE_ACCESS_TOKEN}'; snapshot_download(repo_id='MiaoshouAI/Florence-2-large-PromptGen-v2.0', local_dir='/comfyui/models/LLM/Florence-2-large-PromptGen-v2.0', local_dir_use_symlinks=False)"

# Fail if no HuggingFace token is provided

# Final stage
FROM production as final
CMD ["/start.sh"]
