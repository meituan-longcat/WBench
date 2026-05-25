"""
Download all model weights from HuggingFace to weights/ directory.

Usage:
    python download_weights.py          # Download all weights
    python download_weights.py --only clip raft  # Download specific models
"""
import argparse
import os
import sys

HF_REPO = "KainingYing/WBench-Weights"
WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")

WEIGHT_FILES = {
    "clip": [
        "clip/ViT-L-14.pt",
        "clip/ViT-B-32.pt",
    ],
    "clip-vit-base-patch16": [
        "clip-vit-base-patch16/config.json",
        "clip-vit-base-patch16/merges.txt",
        "clip-vit-base-patch16/model.safetensors",
        "clip-vit-base-patch16/preprocessor_config.json",
        "clip-vit-base-patch16/special_tokens_map.json",
        "clip-vit-base-patch16/tokenizer.json",
        "clip-vit-base-patch16/tokenizer_config.json",
        "clip-vit-base-patch16/vocab.json",
    ],
    "dinov2": [
        "torch_hub/checkpoints/dinov2_vitb14_pretrain.pth",
    ],
    "aesthetic": [
        "aesthetic/sa_0_4_vit_l_14_linear.pth",
    ],
    "pyiqa": [
        "pyiqa/musiq_koniq_ckpt-e95806b9.pth",
    ],
    "dreamsim": [
        "dreamsim/dino_vitb16_pretrain.pth",
        "dreamsim/open_clip_vitb16_pretrain.pth.tar",
        "dreamsim/clip_vitb16_pretrain.pth.tar",
        "dreamsim/ensemble_lora/adapter_config.json",
        "dreamsim/ensemble_lora/adapter_model.safetensors",
    ],
    "raft": [
        "raft/raft-things.pth",
    ],
    "amt": [
        "amt/amt-s.pth",
    ],
    "transnetv2": [
        "transnetv2/transnetv2-pytorch-weights.pth",
    ],
    "HPSv3": [
        "HPSv3/HPSv3.safetensors",
        "HPSv3/HPSv3_7B_local.yaml",
    ],
    "megasam": [
        "megasam/megasam_final.pth",
        "megasam/depth_anything_vitl14.pth",
        "megasam/torch_hub_checkpoints/dinov2_vitl14_pretrain.pth",
        "megasam/torch_hub_checkpoints/metric_depth_vit_large_800k.pth",
    ],
    "DA3": [
        "DA3-GIANT-1.1/config.json",
        "DA3-GIANT-1.1/model.safetensors",
    ],
    "sam2": [
        "sam2.1-hiera-base-plus/config.json",
        "sam2.1-hiera-base-plus/model.safetensors",
        "sam2.1-hiera-base-plus/processor_config.json",
    ],
}


def download_weights(models=None):
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Please install huggingface_hub: pip install huggingface_hub")
        sys.exit(1)

    os.makedirs(WEIGHTS_DIR, exist_ok=True)

    targets = models if models else list(WEIGHT_FILES.keys())
    total_files = sum(len(WEIGHT_FILES[m]) for m in targets if m in WEIGHT_FILES)
    downloaded = 0

    for model_name in targets:
        if model_name not in WEIGHT_FILES:
            print(f"[WARNING] Unknown model: {model_name}, skipping")
            continue

        files = WEIGHT_FILES[model_name]
        print(f"\n{'='*50}")
        print(f"  Downloading: {model_name} ({len(files)} files)")
        print(f"{'='*50}")

        for rel_path in files:
            local_path = os.path.join(WEIGHTS_DIR, rel_path)
            local_dir = os.path.dirname(local_path)
            os.makedirs(local_dir, exist_ok=True)

            if os.path.exists(local_path):
                print(f"  [SKIP] {rel_path} (already exists)")
                downloaded += 1
                continue

            try:
                hf_hub_download(
                    repo_id=HF_REPO,
                    filename=rel_path,
                    local_dir=WEIGHTS_DIR,
                    local_dir_use_symlinks=False,
                )
                downloaded += 1
                print(f"  [OK] {rel_path}")
            except Exception as e:
                print(f"  [FAIL] {rel_path}: {e}")

    print(f"\n{'='*50}")
    print(f"  Done: {downloaded}/{total_files} files downloaded")
    print(f"  Weights directory: {WEIGHTS_DIR}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Download WBench model weights from HuggingFace")
    parser.add_argument("--only", nargs="+", default=None,
                        choices=list(WEIGHT_FILES.keys()),
                        help="Download only specific model weights")
    parser.add_argument("--list", action="store_true",
                        help="List available weight groups")
    args = parser.parse_args()

    if args.list:
        print("Available weight groups:")
        for name, files in WEIGHT_FILES.items():
            print(f"  {name:25s} ({len(files)} files)")
        return

    download_weights(args.only)


if __name__ == "__main__":
    main()
