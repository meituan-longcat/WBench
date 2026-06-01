"""
Camera-conditioned model interface + a runnable preview backend.

How to plug in your own camera-conditioned world model:

    from src.models.camera import CameraConditionedModel

    class MyWorldModel(CameraConditionedModel):
        def generate_with_poses(self, image, poses, video_length, **kw):
            # image: path to the first frame
            # poses: {"0": {"extrinsic": 4x4, "K": 3x3}, ...} (one per latent frame)
            # video_length: number of RGB frames to return
            # return: list of `video_length` BGR uint8 frames (np.ndarray HxWx3)
            return my_model.infer(image, poses, video_length)

    model = MyWorldModel("mymodel")
    model.generate_multi_turn(case, "work_dirs/mymodel/videos/case_1_combined.mp4", "data")
    # then evaluate: python main.py --model mymodel

``generate_multi_turn`` (provided) does case -> poses -> your hook -> write mp4,
so you only implement ``generate_with_poses``. The pose convention (speeds,
axes, intrinsics) lives in ``poses.py`` — adapt it to your model.

``PreviewCameraModel`` is NOT a generator: it warps the first frame in 2D to
visualise the intended camera motion, for verifying the data plumbing.
"""
import os
from typing import Any, Dict, List

import numpy as np

from ..conditioning import ConditionedVideoModel, preview_frames
from .poses import FPS, case_to_poses


class CameraConditionedModel(ConditionedVideoModel):
    """Base class for camera-conditioned (6-DoF pose) world models.

    Subclasses implement ``generate_with_poses``; case parsing, action->pose
    conversion, and video writing are handled by the base.
    """

    def generate_with_poses(self, image: str, poses: Dict[str, Any],
                            video_length: int, **kwargs) -> List[np.ndarray]:
        """Run the model. Override this.

        Args:
            image: path to the first-frame conditioning image.
            poses: {"<latent_idx>": {"extrinsic": 4x4, "K": 3x3}, ...}.
            video_length: number of RGB frames to return.
        Returns:
            list of `video_length` BGR uint8 frames (np.ndarray HxWx3).
        """
        raise NotImplementedError("Implement generate_with_poses() in your model subclass.")

    def generate_multi_turn(self, case: Dict[str, Any], output_path: str,
                            data_root: str = "data") -> Dict[str, Any]:
        image = self._resolve_image(case, data_root)
        if not image or not os.path.exists(image):
            return {"code": -1, "error": f"initial_image not found: {image}"}

        conv = case_to_poses(case, duration=self.duration)
        try:
            frames = self.generate_with_poses(
                image=image,
                poses=conv["poses"],
                video_length=conv["video_length"],
                perspective=conv["perspective"],
                navigation=conv["navigation"],
                chunk_length=conv["chunk_length"],
                motions=conv["motions"],
            )
        except NotImplementedError:
            raise
        except Exception as e:  # noqa: BLE001 - surface model errors as case failures
            return {"code": -1, "error": f"generate_with_poses failed: {e}"}

        if not frames:
            return {"code": -1, "error": "model returned no frames"}

        self._write_video(frames, output_path, fps=FPS)
        if self.dump:
            self._dump(output_path, case["id"], "poses",
                       {"perspective": conv["perspective"],
                        "video_length": conv["video_length"],
                        "poses": conv["poses"]})
        return {"code": 0, "video_path": output_path}


class PreviewCameraModel(CameraConditionedModel):
    """Runnable stand-in: warps the first frame to preview camera intent."""

    def __init__(self, model_name: str = "camera_preview", **kwargs):
        super().__init__(model_name=model_name, **kwargs)

    def generate_with_poses(self, image, poses, video_length,
                            navigation=None, chunk_length=None, **kwargs) -> List[np.ndarray]:
        return preview_frames(image, navigation, chunk_length, video_length)
