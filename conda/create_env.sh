#!/bin/bash
set -e

# GPU-Accelerated Sub-6 Spectrum Observatory - Environment Setup
# This script creates the rapids conda environment with RAPIDS + CUDA support

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "RAPIDS Environment Setup"
echo "=========================================="
echo ""

# Detect CUDA version
if command -v nvcc &> /dev/null; then
    CUDA_VERSION=$(nvcc --version | grep "release" | sed -n 's/.*release \([0-9]*\)\..*/\1/p')
    echo "✓ Detected CUDA version: $CUDA_VERSION"
else
    echo "✗ nvcc not found. Please install CUDA toolkit."
    exit 1
fi

# Select environment file
if [ "$CUDA_VERSION" -ge 13 ]; then
    ENV_FILE="$SCRIPT_DIR/environment_cuda13.yml"
    echo "→ Using CUDA 13 environment"
elif [ "$CUDA_VERSION" -ge 12 ]; then
    ENV_FILE="$SCRIPT_DIR/environment_cuda12.yml"
    echo "→ Using CUDA 12 environment"
else
    echo "✗ CUDA version $CUDA_VERSION is not supported. Need CUDA 12 or 13."
    exit 1
fi

echo ""
echo "Environment file: $ENV_FILE"
echo ""

# Check for mamba (faster solver)
if command -v mamba &> /dev/null; then
    CONDA_CMD="mamba"
    echo "✓ Using mamba (faster solver)"
else
    CONDA_CMD="conda"
    echo "✓ Using conda"
fi

echo ""
echo "Checking for existing 'rapids' environment..."
if conda env list | grep -q "^rapids "; then
    echo "⚠ Environment 'rapids' already exists."
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "→ Removing existing environment..."
        conda env remove -n rapids -y
    else
        echo "✗ Aborted. Activate existing environment with: conda activate rapids"
        exit 0
    fi
fi

echo ""
echo "Creating 'rapids' environment..."
echo "(This may take 5-15 minutes depending on your network and CPU)"
echo ""

$CONDA_CMD env create -f "$ENV_FILE"

echo ""
echo "=========================================="
echo "✓ Environment created successfully!"
echo "=========================================="
echo ""
echo "Activate with:"
echo "  conda activate rapids"
echo ""
echo "Verify installation with:"
echo "  python -c 'import cudf; print(f\"cuDF version: {cudf.__version__}\")'"
echo "  python -c 'import cupy; print(f\"CuPy version: {cupy.__version__}\")'"
echo "  python -c 'import cusignal; print(f\"cuSignal version: {cusignal.__version__}\")'"
echo "  python -c 'import streamlit; print(f\"Streamlit version: {streamlit.__version__}\")'"
echo ""
echo "Run the application:"
echo "  cd $PROJECT_ROOT"
echo "  streamlit run src/streamlit_app.py"
echo ""

