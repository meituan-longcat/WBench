#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════
# WBench Visual Plausibility Environment Installation
# Separate environment for the visual_plausibility metric (vLLM + Qwen3-VL)
# ═══════════════════════════════════════════════════════════════════

ENV_NAME="${1:-wbench-vp}"
PYTHON_VERSION="3.10"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     WBench Visual Plausibility Environment Setup             ║"
echo "║  Env: $ENV_NAME | Python $PYTHON_VERSION | vLLM + Qwen3-VL          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Create conda environment ─────────────────────────────────────
if conda env list | grep -q "^$ENV_NAME "; then
    echo "[1/3] Environment '$ENV_NAME' already exists, skipping creation."
else
    echo "[1/3] Creating conda environment: $ENV_NAME ..."
    conda create -n "$ENV_NAME" python=$PYTHON_VERSION -y
fi

CONDA_PREFIX=$(conda env list | grep "^$ENV_NAME " | awk '{print $NF}')
PY="$CONDA_PREFIX/bin/python"
PIP="$CONDA_PREFIX/bin/pip"

echo "       Python: $($PY --version)"
echo "       Path:   $CONDA_PREFIX"

# ── 2. Install vLLM ─────────────────────────────────────────────────
# ── Proxy setup (uncomment if behind a proxy) ──
# export http_proxy=http://your-proxy:port
# export https_proxy=http://your-proxy:port

echo ""
echo "[2/3] Installing vLLM==0.11.0 ..."
$PIP install "vllm==0.11.0" \
    --extra-index-url https://pypi.nvidia.com \
    --extra-index-url https://download.pytorch.org/whl/cu124

echo ""
echo "[3/3] Installing qwen-vl-utils and remaining dependencies ..."
$PIP install qwen-vl-utils==0.0.14
$PIP install transformers accelerate opencv-python-headless numpy

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Installation complete!                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Activate:  conda activate $ENV_NAME"
echo "  Run:       python main.py --model <model> --metrics visual_plausibility"
echo ""
echo "  Note: Set PAVRM_MODEL_PATH to your local qwen3vl-a3b weights directory."
echo ""
