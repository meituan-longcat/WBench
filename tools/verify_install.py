"""
Verify WBench installation — checks all dependencies, weights, and CUDA.

Usage:
    conda activate wbench
    export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
    python tools/verify_install.py
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "sam2"))
sys.path.insert(0, str(PROJECT_ROOT / "third_party" / "depth-anything-3" / "src"))

import src.compat  # noqa: F401

passed, failed, warned = 0, 0, 0


def check(name, func):
    global passed, failed, warned
    try:
        result = func()
        if result is None or result is True:
            print(f"  \033[32m✓\033[0m {name}")
        else:
            print(f"  \033[32m✓\033[0m {name} — {result}")
        passed += 1
    except Exception as e:
        print(f"  \033[31m✗\033[0m {name} — {e}")
        failed += 1


print()
print("=" * 60)
print("  WBench Installation Verification")
print("=" * 60)

# ── Core packages ────────────────────────────────────────────────────
print("\n[Core Packages]")
check("Python >= 3.10", lambda: f"{sys.version_info.major}.{sys.version_info.minor}" if sys.version_info >= (3, 10) else (_ for _ in ()).throw(RuntimeError("Python >= 3.10 required")))
check("torch", lambda: __import__("torch").__version__)
check("torchvision", lambda: __import__("torchvision").__version__)
check("numpy", lambda: __import__("numpy").__version__)
check("opencv-python", lambda: __import__("cv2").__version__)
check("transformers", lambda: __import__("transformers").__version__)
check("scipy", lambda: __import__("scipy").__version__)
check("PIL", lambda: __import__("PIL").__version__)
check("av (PyAV)", lambda: __import__("av").__version__)
check("requests", lambda: __import__("requests").__version__)
check("tqdm", lambda: __import__("tqdm").__version__)

# ── CUDA ─────────────────────────────────────────────────────────────
print("\n[CUDA]")
check("CUDA available", lambda: f"Yes ({__import__('torch').cuda.get_device_name(0)})" if __import__("torch").cuda.is_available() else (_ for _ in ()).throw(RuntimeError("No CUDA device")))

# ── Video Quality deps ───────────────────────────────────────────────
print("\n[Video Quality Metrics]")
check("clip (OpenAI)", lambda: __import__("clip") and "OK")
check("pyiqa", lambda: __import__("pyiqa").__version__)
check("dreamsim", lambda: __import__("dreamsim") and "OK")

# ── Third-party tools ────────────────────────────────────────────────
print("\n[Third-party Tools]")
check("SAM2 (native)", lambda: __import__("sam2.build_sam") and "OK")
check("hydra-core", lambda: __import__("hydra").__version__)
check("iopath", lambda: __import__("iopath") and "OK")
check("DA3 (depth-anything-3)", lambda: (
    __import__("depth_anything_3.api", fromlist=["DepthAnything3"]) and "OK"))

def check_xformers():
    import xformers
    return xformers.__version__
check("xformers", lambda: check_xformers() if True else "MISSING (optional)")

def check_wandb():
    import wandb
    return wandb.__version__
check("wandb", lambda: check_wandb())

# ── MegaSAM (CUDA extensions) ───────────────────────────────────────
print("\n[MegaSAM CUDA Extensions]")

def check_lietorch():
    import lietorch
    return "OK"
check("lietorch", lambda: check_lietorch())

def check_droid():
    import droid_backends
    return "OK"
check("droid_backends", lambda: check_droid())

def check_torch_scatter():
    from torch_scatter import scatter_sum
    return "OK"
check("torch-scatter", lambda: check_torch_scatter())

# ── WBench metrics (all 22) ──────────────────────────────────────────
print("\n[WBench Metrics — All 22]")
check("video_quality (6 sub)", lambda: __import__("src.metrics.video_quality.evaluator", fromlist=["VideoQualityEvaluator"]) and "OK")
check("background_consistency", lambda: __import__("src.metrics.consistency.background_consistency", fromlist=["BackgroundConsistencyMetric"]) and "OK")
check("segment_continuity", lambda: __import__("src.metrics.consistency.segment_continuity", fromlist=["compute_case"]) and "OK")
check("reconstruction_consistency", lambda: __import__("src.metrics.consistency.reconstruction_consistency", fromlist=["compute_case"]) and "OK")
check("spatial_consistency", lambda: __import__("src.metrics.consistency.spatial_consistency", fromlist=["evaluate_case"]) and "OK")
check("perspective_consistency", lambda: __import__("src.metrics.consistency.perspective_consistency", fromlist=["compute_case"]) and "OK")
check("subject_consistency", lambda: __import__("src.metrics.consistency.subject_consistency", fromlist=["SubjectConsistencyMetric"]) and "OK")
check("navigation_trajectory", lambda: __import__("src.metrics.interaction.navigation_trajectory", fromlist=["evaluate_navigation"]) and "OK")
check("vlm_interaction (3 sub)", lambda: __import__("src.metrics.interaction.vlm_interaction", fromlist=["EventEditAdherenceEvaluator"]) and "OK")
check("scene_adherence", lambda: __import__("src.metrics.setting_adherence.scene_adherence", fromlist=["evaluate_case"]) and "OK")
check("subject_adherence", lambda: __import__("src.metrics.setting_adherence.subject_adherence", fromlist=["evaluate_case"]) and "OK")
check("causal_fidelity", lambda: __import__("src.metrics.physical.causal_fidelity", fromlist=["evaluate_case"]) and "OK")
check("visual_plausibility", lambda: __import__("src.metrics.physical.visual_plausibility", fromlist=["compute_case"]) and "OK")
check("vlm_client", lambda: __import__("src.metrics.vlm.vlm_evaluator", fromlist=["VLMClient"]) and "OK")

# ── Weights ──────────────────────────────────────────────────────────
print("\n[Model Weights]")
WEIGHTS_DIR = os.environ.get("WBENCH_WEIGHTS_DIR") or str(PROJECT_ROOT / "weights")

weight_checks = {
    "CLIP ViT-L/14": "clip/ViT-L-14.pt",
    "Aesthetic": "aesthetic/sa_0_4_vit_l_14_linear.pth",
    "RAFT": "raft/raft-things.pth",
    "TransNetV2": "transnetv2/transnetv2-pytorch-weights.pth",
    "DreamSim": "dreamsim/dino_vitb16_pretrain.pth",
    "HPSv3": "HPSv3/HPSv3.safetensors",
    "SAM2 (native .pt)": "sam2.1-hiera-base-plus/sam2.1_hiera_base_plus.pt",
    "MegaSAM": "megasam/megasam_final.pth",
    "DA3-GIANT-1.1": "DA3-GIANT-1.1/config.json",
    "Qwen2-VL (HPSv3 base)": "Qwen2-VL-7B-Instruct/config.json",
}

for name, rel_path in weight_checks.items():
    full_path = os.path.join(WEIGHTS_DIR, rel_path)
    check(name, lambda p=full_path: "OK" if os.path.exists(p) else (_ for _ in ()).throw(FileNotFoundError(f"Not found: {p}")))

# ── Summary ──────────────────────────────────────────────────────────
print()
print("=" * 60)
total = passed + failed + warned
if failed == 0:
    print(f"  \033[32m ALL PASSED\033[0m ({passed}/{total} passed, {warned} warnings)")
    print("  Environment is ready for evaluation!")
else:
    print(f"  \033[31m {failed} FAILED\033[0m, {passed} passed, {warned} warnings")
    print("  Please fix the failed items above.")
print("=" * 60)
print()

sys.exit(0 if failed == 0 else 1)
