"""
Action-conditioned model interface + a runnable preview backend.

How to plug in your own action-conditioned world model:

    from src.models.action import ActionConditionedModel

    class MyActionModel(ActionConditionedModel):
        def generate_with_actions(self, image, actions, video_length, **kw):
            # image: path to the first frame
            # actions: [{"turn", "tokens", "keyboard", "mouse", "duration"}, ...]
            #          tokens   -> raw keys (keystroke/web products)
            #          keyboard -> 6-dim one-hot, mouse -> [pitch, yaw]  (MG3-style)
            # video_length: number of RGB frames to return
            # return: list of `video_length` BGR uint8 frames (np.ndarray HxWx3)
            return my_model.infer(image, actions, video_length)

    model = MyActionModel("mymodel")
    model.generate_multi_turn(case, "work_dirs/mymodel/videos/case_1_combined.mp4", "data")
    # then evaluate: python main.py --model mymodel

The per-turn action contract (raw tokens + keyboard/mouse) lives in
``actions.py``. Mapping turns to frames/iterations is model-specific.

``PreviewActionModel`` is NOT a generator: it warps the first frame in 2D to
visualise the navigation intent, for verifying the data plumbing.
"""
import os
from typing import Any, Dict, List

import numpy as np

from ..conditioning import DEFAULT_FPS, ConditionedVideoModel, preview_frames
from .actions import case_to_actions


class ActionConditionedModel(ConditionedVideoModel):
    """Base class for action-conditioned (discrete per-turn action) world models.

    Subclasses implement ``generate_with_actions``; case parsing, action
    conversion, and video writing are handled by the base.
    """

    def generate_with_actions(self, image: str, actions: List[Dict[str, Any]],
                              video_length: int, **kwargs) -> List[np.ndarray]:
        """Run the model. Override this.

        Args:
            image: path to the first-frame conditioning image.
            actions: per-turn list, each {turn, tokens, keyboard, mouse, duration}.
            video_length: number of RGB frames to return.
        Returns:
            list of `video_length` BGR uint8 frames (np.ndarray HxWx3).
        """
        raise NotImplementedError("Implement generate_with_actions() in your model subclass.")

    def generate_multi_turn(self, case: Dict[str, Any], output_path: str,
                            data_root: str = "data") -> Dict[str, Any]:
        image = self._resolve_image(case, data_root)
        if not image or not os.path.exists(image):
            return {"code": -1, "error": f"initial_image not found: {image}"}

        conv = case_to_actions(case, duration=self.duration)
        video_length = round(DEFAULT_FPS * conv["total_duration"])
        try:
            frames = self.generate_with_actions(
                image=image,
                actions=conv["actions"],
                video_length=video_length,
                perspective=conv["perspective"],
                navigation=conv["navigation"],
                chunk_length=conv["chunk_length"],
            )
        except NotImplementedError:
            raise
        except Exception as e:  # noqa: BLE001 - surface model errors as case failures
            return {"code": -1, "error": f"generate_with_actions failed: {e}"}

        if not frames:
            return {"code": -1, "error": "model returned no frames"}

        self._write_video(frames, output_path, fps=DEFAULT_FPS)
        if self.dump:
            self._dump(output_path, case["id"], "actions",
                       {"perspective": conv["perspective"], "actions": conv["actions"]})
        return {"code": 0, "video_path": output_path}


class PreviewActionModel(ActionConditionedModel):
    """Runnable stand-in: warps the first frame to preview navigation intent."""

    def __init__(self, model_name: str = "action_preview", **kwargs):
        super().__init__(model_name=model_name, **kwargs)

    def generate_with_actions(self, image, actions, video_length,
                              navigation=None, chunk_length=None, **kwargs) -> List[np.ndarray]:
        return preview_frames(image, navigation, chunk_length, video_length)
