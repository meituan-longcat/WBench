#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════
# WBench One-Click Installation Script
# Creates a fully working environment with all 22 metrics + tools
# ═══════════════════════════════════════════════════════════════════

# ── Proxy setup (uncomment if behind a proxy) ──
# export http_proxy=http://your-proxy:port
# export https_proxy=http://your-proxy:port

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f ".gitmodules" ]; then
    echo ""
    echo "[0/7] Initializing git submodules ..."
    git submodule sync --recursive
    git submodule update --init --recursive
fi

ENV_NAME="${1:-wbench}"
PYTHON_VERSION="3.10"
TORCH_VERSION="2.4.0"

# Auto-detect CUDA version, or set manually: bash install.sh wbench cu121
if [ -n "$2" ]; then
    CUDA_VERSION="$2"
else
    NVCC_VER=$(nvcc --version 2>/dev/null | grep "release" | sed 's/.*release //' | sed 's/,.*//')
    if [ -n "$NVCC_VER" ]; then
        CUDA_MAJOR=$(echo $NVCC_VER | cut -d. -f1)
        CUDA_MINOR=$(echo $NVCC_VER | cut -d. -f2)
        if [ "$CUDA_MAJOR" -ge 12 ]; then
            CUDA_VERSION="cu124"
        else
            CUDA_VERSION="cu118"
        fi
        echo "[INFO] Detected CUDA $NVCC_VER → using $CUDA_VERSION"
    else
        CUDA_VERSION="cu118"
        echo "[INFO] nvcc not found, defaulting to $CUDA_VERSION"
    fi
fi

# Torch version mapping for different CUDA
if [ "$CUDA_VERSION" = "cu124" ]; then
    TORCH_VERSION="2.4.0"
    XFORMERS_VERSION="0.0.27.post2"
elif [ "$CUDA_VERSION" = "cu121" ]; then
    TORCH_VERSION="2.4.0"
    XFORMERS_VERSION="0.0.27.post2"
else
    TORCH_VERSION="2.4.0"
    XFORMERS_VERSION="0.0.27.post2"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           WBench Environment Installation                    ║"
echo "║  Env: $ENV_NAME | Python $PYTHON_VERSION | PyTorch $TORCH_VERSION+$CUDA_VERSION    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Create conda environment ─────────────────────────────────────
echo "[1/6] Creating conda environment: $ENV_NAME ..."
conda create -n "$ENV_NAME" python=$PYTHON_VERSION -y
CONDA_PREFIX=$(conda env list | grep "^$ENV_NAME " | awk '{print $NF}')
PY="$CONDA_PREFIX/bin/python"
PIP="$CONDA_PREFIX/bin/pip"

echo "       Python: $($PY --version)"
echo "       Path:   $CONDA_PREFIX"

# ── 2. Setup libstdc++ (fixes GLIBCXX_3.4.29 not found) ─────────────
echo ""
echo "[2/7] Linking system libstdc++ (GLIBCXX_3.4.29) ..."
# Copy conda's libstdc++ (has GLIBCXX_3.4.29) into the env instead of
# installing from conda-forge (which pulls in GraalPy and breaks CPython)
SYSTEM_LIBSTDCXX="/usr/local/conda/lib/libstdc++.so.6"
if [ -f "$SYSTEM_LIBSTDCXX" ]; then
    cp -f "$SYSTEM_LIBSTDCXX" "$CONDA_PREFIX/lib/libstdc++.so.6"
    echo "       Copied $SYSTEM_LIBSTDCXX → $CONDA_PREFIX/lib/"
else
    echo "       [WARN] $SYSTEM_LIBSTDCXX not found, may get GLIBCXX errors later"
fi

# ── 3. Install uv, torch, and Python packages ───────────────────────
echo ""
echo "[3/7] Installing uv + PyTorch ${TORCH_VERSION}+${CUDA_VERSION} ..."
$PIP install uv

UV="$CONDA_PREFIX/bin/uv"

# Install torch first (from PyTorch index for correct CUDA version)
$UV pip install --python "$PY" \
    "torch==${TORCH_VERSION}" "torchvision" \
    --extra-index-url "https://download.pytorch.org/whl/$CUDA_VERSION" \
    --index-strategy unsafe-best-match

echo ""
echo "[4/7] Installing remaining Python packages ..."
$UV pip install --python "$PY" \
    -r tools/requirements.txt \
    --index-strategy unsafe-best-match

# ── 5. Install extra packages ────────────────────────────────────────
echo ""
echo "[5/7] Installing xformers, torch-scatter, and tools deps ..."

# xformers (must match torch version exactly)
$UV pip install --python "$PY" \
    "xformers==$XFORMERS_VERSION" \
    --extra-index-url "https://download.pytorch.org/whl/$CUDA_VERSION" \
    --index-strategy unsafe-best-match \
    2>/dev/null || echo "       [WARN] xformers install failed (optional, will fallback to SDPA)"

# torch-scatter (pre-built wheel)
$UV pip install --python "$PY" \
    torch-scatter \
    -f "https://data.pyg.org/whl/torch-${TORCH_VERSION}+${CUDA_VERSION}.html" \
    --index-strategy unsafe-best-match \
    2>/dev/null || echo "       [WARN] torch-scatter install failed (needed for MegaSAM only)"

# Additional deps for tools
$UV pip install --python "$PY" \
    wandb iopath hydra-core fire "trl<1.0" \
    --index-strategy unsafe-best-match

# ── 6. Build MegaSAM CUDA extensions ────────────────────────────────
echo ""
echo "[6/7] Building MegaSAM CUDA extensions (lietorch + droid_backends) ..."
if [ -f "third_party/mega-sam/base/setup.py" ]; then
    cd third_party/mega-sam/base
    LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH" "$PY" setup.py install && \
        echo "       MegaSAM build: OK" || \
        echo "       [WARN] MegaSAM build failed (navigation metrics won't work)"
    cd ../../..
else
    echo "       [SKIP] third_party/mega-sam not found (run: git submodule update --init --recursive)"
fi

# ── 7. Download model weights ────────────────────────────────────────
echo ""
echo "[7/7] Downloading model weights ..."
if [ -f "tools/download_weights.py" ]; then
    "$PY" tools/download_weights.py || echo "       [WARN] Weight download failed. Run manually: python tools/download_weights.py"
else
    echo "       [SKIP] tools/download_weights.py not found"
fi

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Installation complete!                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Activate:  conda activate $ENV_NAME"
echo "  Run:       export LD_LIBRARY_PATH=\$CONDA_PREFIX/lib:\$LD_LIBRARY_PATH"
echo "             python src/evaluate.py --video <video> --case <case.json>"
echo ""
echo "  If you see 'GLIBCXX not found' errors, make sure LD_LIBRARY_PATH is set."
echo ""
