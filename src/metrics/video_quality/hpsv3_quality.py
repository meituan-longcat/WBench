"""HPSv3 human preference score — Qwen2-VL-7B based preference model."""
import os
import sys
from typing import Dict, Any, List

import numpy as np
import torch
from PIL import Image

# Patch: ensure VideoInput is available in transformers.image_utils for HPSv3 compatibility
import transformers.image_utils as _img_utils
if not hasattr(_img_utils, "VideoInput"):
    _img_utils.VideoInput = List[np.ndarray]

from ..base import BaseMetric
from ..weight_utils import get_weights_dir

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_HPSV3_ROOT = os.path.join(_PROJECT_ROOT, "third_party", "HPSv3")

# Winsorized p1/p99 of all-sample raw HPSv3 rewards, used to map the unbounded raw
# reward onto [0,1] so this metric lines up with the other [0,1] metrics. These are
# a fixed global scale (same constants as leaderboard/plot_5dims_tables.py), not
# re-estimated per run.
_HPSV3_P1 = -5.21
_HPSV3_P99 = 8.61


class HPSv3QualityMetric(BaseMetric):
    def __init__(self, device="cuda"):
        super().__init__(device)
        # Clean up AMT's namespace pollution (datasets/, utils/) before importing HPSv3/trl
        _amt_path = os.path.join(_PROJECT_ROOT, "third_party", "amt")
        if _amt_path in sys.path:
            sys.path.remove(_amt_path)
        # Purge modules cached from AMT that shadow RAFT imports (datasets, utils)
        for _mod in [k for k in sys.modules if k in ("datasets", "utils") or k.startswith(("datasets.", "utils."))]:
            _file = getattr(sys.modules[_mod], "__file__", "") or ""
            if "amt" in _file:
                del sys.modules[_mod]

        if _HPSV3_ROOT not in sys.path:
            sys.path.insert(0, _HPSV3_ROOT)
        from hpsv3.inference import HPSv3RewardInferencer

        hpsv3_dir = get_weights_dir("HPSv3")
        checkpoint_path = os.path.join(hpsv3_dir, "HPSv3.safetensors")
        config_path = os.path.join(hpsv3_dir, "HPSv3_7B_local.yaml")

        # Use local Qwen2-VL weights if available
        local_qwen = os.path.join(get_weights_dir(), "Qwen2-VL-7B-Instruct")
        if os.path.isdir(local_qwen):
            os.environ["HF_HUB_OFFLINE"] = "1"
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            cfg["model_name_or_path"] = local_qwen
            tmp_cfg = os.path.join(hpsv3_dir, "_HPSv3_7B_resolved.yaml")
            with open(tmp_cfg, "w") as f:
                yaml.dump(cfg, f)
            config_path = tmp_cfg

        self.inferencer = HPSv3RewardInferencer(
            config_path=config_path,
            checkpoint_path=checkpoint_path,
            device=device,
        )

    @property
    def name(self):
        return "hpsv3_quality"

    def compute(self, frames: List[Image.Image], **kwargs) -> Dict[str, Any]:
        tmp_paths = []
        for i, frame in enumerate(frames):
            p = f"/tmp/_hpsv3_{os.getpid()}_{i}.png"
            frame.save(p)
            tmp_paths.append(p)
        try:
            prompts = [""] * len(tmp_paths)
            with torch.no_grad():
                rewards = self.inferencer.reward(prompts, tmp_paths)
            raw_scores = [rewards[i][0].item() for i in range(len(tmp_paths))]
        finally:
            for p in tmp_paths:
                if os.path.exists(p):
                    os.remove(p)
        raw_mean = float(np.mean(raw_scores))
        # Normalize the unbounded raw reward to [0,1] via the Winsorized p1/p99 scale,
        # so hpsv3_quality matches every other metric's [0,1] range. raw_mean is kept
        # for traceability.
        score = max(0.0, min(1.0, (raw_mean - _HPSV3_P1) / (_HPSV3_P99 - _HPSV3_P1)))
        return {
            f"{self.name}_score": score,
            f"{self.name}_raw_score": raw_mean,
            f"{self.name}_raw_scores": raw_scores,
        }
