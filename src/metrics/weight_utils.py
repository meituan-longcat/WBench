"""
Model weight management.

All weights are stored under the project root weights/ directory.
Directory structure:
    weights/
    ├── clip/               # CLIP models (ViT-L/14, ViT-B/32)
    ├── clip-vit-base-patch16/  # HuggingFace CLIP (for subject_consistency)
    ├── torch_hub/          # DINOv2 (torch.hub cache)
    ├── aesthetic/          # LAION aesthetic scoring head
    ├── pyiqa/              # MUSIQ via pyiqa
    ├── dreamsim/           # DreamSim perceptual model
    ├── raft/               # RAFT optical flow (raft-things.pth)
    ├── amt/                # AMT-S frame interpolation (amt-s.pth)
    ├── transnetv2/         # TransNetV2 (transnetv2-pytorch-weights.pth)
    └── HPSv3/              # HPSv3 (HPSv3.safetensors + config)
"""
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WEIGHTS_DIR = os.environ.get("WBENCH_WEIGHTS_DIR") or os.path.join(_PROJECT_ROOT, "weights")


def get_weights_dir(subdir: str = "") -> str:
    """Get weight subdirectory path (auto-creates)."""
    path = os.path.join(WEIGHTS_DIR, subdir) if subdir else WEIGHTS_DIR
    os.makedirs(path, exist_ok=True)
    return path


def setup_torch_hub_dir():
    """Set torch.hub cache to project-local weights/torch_hub/."""
    import torch
    hub_dir = get_weights_dir("torch_hub")
    torch.hub.set_dir(hub_dir)
    return hub_dir
