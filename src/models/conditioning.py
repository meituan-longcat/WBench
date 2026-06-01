"""
Shared base + helpers for non-text (camera / action) conditioned models.

Text models drive generation turn-by-turn via prompts (see base.py). Camera and
action models instead consume the whole per-turn navigation plan up front and
render a full clip. ``ConditionedVideoModel`` factors out the common plumbing
(resolve first frame, write mp4, dump the conditioning), leaving each subclass
to implement only its conversion + model hook.

``preview_frames`` is a model-free visualiser: it warps the first frame in 2D to
show the navigation intent (pan on yaw/strafe, tilt on pitch, zoom on forward).
Both PreviewCameraModel and PreviewActionModel use it so the examples run
end-to-end without a real model.
"""
import json
import os
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from .base import BaseVideoModel

DEFAULT_FPS = 24


class ConditionedVideoModel(BaseVideoModel):
    """Base class for navigation-driven (camera/action) world models."""

    def __init__(self, model_name: str, duration: float = 4.0, dump: bool = True):
        super().__init__(model_name=model_name)
        self.duration = duration
        self.dump = dump

    def generate(self, prompt: str, image: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError(
            "Camera/action models are navigation-driven, not text-driven. "
            "Implement the model hook (generate_with_poses / generate_with_actions) "
            "and call generate_multi_turn()."
        )

    @staticmethod
    def _resolve_image(case: Dict[str, Any], data_root: str) -> str:
        img = case.get("settings", {}).get("initial_image", "")
        if img and not os.path.isabs(img):
            img = os.path.join(data_root, img)
        return img

    def _write_video(self, frames: List[np.ndarray], output_path: str, fps: int = DEFAULT_FPS) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        h, w = frames[0].shape[:2]
        writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for f in frames:
            writer.write(f if (f.shape[1], f.shape[0]) == (w, h) else cv2.resize(f, (w, h)))
        writer.release()

    def _dump(self, output_path: str, case_id: Any, subdir: str, payload: Dict[str, Any]) -> None:
        d = os.path.join(os.path.dirname(os.path.dirname(output_path)), subdir)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"case_{case_id}.json"), "w") as fp:
            json.dump(payload, fp)


# Preview warp gains (per-frame, visualisation only — not physically meaningful).
_PAN_PER_FRAME_YAW = 0.0035    # horizontal pan (frac of width) per frame held in yaw
_PAN_PER_FRAME_RIGHT = 0.0035  # horizontal pan per frame held strafing
_TILT_PER_FRAME_PITCH = 0.0035 # vertical pan per frame held in pitch
_ZOOM_PER_FRAME_FWD = 0.0012   # zoom-in per frame held moving forward


def preview_frames(image_path: str, navigation: Dict[str, Dict[str, Any]],
                   chunk_length: Dict[str, float], video_length: int) -> List[np.ndarray]:
    """Warp the first frame in 2D to preview the navigation intent.

    Driven purely by the shared navigation signals (direction per turn), so it
    works the same for camera and action examples. NOT a real generator.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"could not read image: {image_path}")
    h, w = img.shape[:2]

    keys = sorted(navigation.keys(), key=lambda x: int(x))
    total_sec = sum(float(chunk_length[k]) for k in keys) or 1.0

    # Per-frame direction (sign only), allotting frames to turns by duration.
    per_frame = []
    for k in keys:
        n = max(1, round(video_length * float(chunk_length[k]) / total_sec))
        nav = navigation[k]
        per_frame.extend([(
            int(np.sign(nav["move"][0])),
            int(np.sign(nav["move"][1])),
            int(np.sign(nav["yaw"])),
            int(np.sign(nav["pitch"])),
        )] * n)
    per_frame = per_frame[:video_length]
    per_frame += [(0, 0, 0, 0)] * (video_length - len(per_frame))

    cf = cr = cy = cp = 0.0
    frames = []
    for fwd, rgt, yaw, pit in per_frame:
        cf += fwd; cr += rgt; cy += yaw; cp += pit
        dx = -(cy * _PAN_PER_FRAME_YAW + cr * _PAN_PER_FRAME_RIGHT) * w
        dy = (cp * _TILT_PER_FRAME_PITCH) * h
        scale = 1.0 + cf * _ZOOM_PER_FRAME_FWD
        M = cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale)
        M[0, 2] += dx
        M[1, 2] += dy
        frames.append(cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT))
    return frames
