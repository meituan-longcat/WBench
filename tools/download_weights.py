"""
Download all WBench model weights from HuggingFace to the weights/ directory.

Pulls the entire meituan-longcat/WBench-weights repo in one shot — every metric
needs the full set, so there is no per-model selection list to keep in sync.

Usage:
    python tools/download_weights.py                       # download everything
    python tools/download_weights.py --weights-dir /path   # custom destination
"""
import argparse
import os
import sys
from pathlib import Path

HF_REPO = "meituan-longcat/WBench-weights"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS_DIR = os.environ.get("WBENCH_WEIGHTS_DIR") or str(PROJECT_ROOT / "weights")


def download_weights(weights_dir):
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Please install huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    os.makedirs(weights_dir, exist_ok=True)
    print(f"\nDownloading entire repo {HF_REPO} to {weights_dir} ...")
    snapshot_download(
        repo_id=HF_REPO,
        local_dir=weights_dir,
        local_dir_use_symlinks=False,
        ignore_patterns=[".cache/*"],
    )
    print("\nDone! All weights downloaded.")
    print(f"  Weights directory: {weights_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Download all WBench model weights from HuggingFace"
    )
    parser.add_argument(
        "--weights-dir", default=DEFAULT_WEIGHTS_DIR,
        help="Destination directory (default: $WBENCH_WEIGHTS_DIR or <repo>/weights)",
    )
    args = parser.parse_args()
    download_weights(args.weights_dir)


if __name__ == "__main__":
    main()
