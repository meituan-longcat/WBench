"""
Base class for video generation models.
All models must inherit BaseVideoModel and implement the generate() method.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class BaseVideoModel(ABC):
    """Abstract base class for I2V video generation models."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def generate(
        self,
        prompt: str,
        image: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a single video segment.

        Args:
            prompt: Text prompt describing the desired motion/content.
            image: Path to the conditioning image (first frame).
                   None means text-to-video mode.
            **kwargs: Model-specific parameters (num_frames, seed, etc.)

        Returns:
            {
                "code": 0,            # 0=success, -1=failure
                "video_path": "...",  # Local path to generated video segment
                "error": "..."        # Error message (only when code=-1)
            }
        """
        pass

    def generate_multi_turn(
        self,
        case: Dict[str, Any],
        output_path: str,
        data_root: str = "data",
    ) -> Dict[str, Any]:
        """
        Generate a multi-turn video from a case definition.

        Default implementation: iteratively generates one segment per turn,
        using the last frame of the previous segment as input for the next.
        Subclasses can override for models with native multi-turn support.

        Args:
            case: Parsed case dict (from case JSON)
            output_path: Where to save the combined video
            data_root: Root path for resolving relative image paths

        Returns:
            {"code": 0, "video_path": output_path} or {"code": -1, "error": ...}
        """
        import os
        import cv2
        import numpy as np

        interactions = case.get("interactions", [])
        if not interactions:
            return {"code": -1, "error": "No interactions in case"}

        initial_image = case.get("settings", {}).get("initial_image", "")
        if initial_image and not os.path.isabs(initial_image):
            initial_image = os.path.join(data_root, initial_image)

        segments = []
        current_image = initial_image

        for i, interaction in enumerate(interactions):
            prompt = self._build_turn_prompt(case, interaction)

            result = self.generate(
                prompt=prompt,
                image=current_image,
                turn=i + 1,
                action=interaction.get("action", ""),
                interaction_type=interaction.get("type", ""),
            )

            if result.get("code") != 0:
                return {
                    "code": -1,
                    "error": f"Turn {i+1} failed: {result.get('error', 'unknown')}"
                }

            seg_path = result["video_path"]
            segments.append(seg_path)

            current_image = self._extract_last_frame(seg_path)
            if current_image is None:
                return {"code": -1, "error": f"Failed to extract last frame from turn {i+1}"}

        combined = self._concat_segments(segments, output_path)
        if combined:
            return {"code": 0, "video_path": output_path}
        return {"code": -1, "error": "Failed to concatenate segments"}

    def _build_turn_prompt(self, case: Dict[str, Any], interaction: Dict[str, Any]) -> str:
        """Build prompt for a single turn. Override for custom prompt strategies."""
        parts = []
        env = case.get("environment_prompt", "")
        char = case.get("character_prompt", "")
        if env:
            parts.append(env)
        if char:
            parts.append(char)

        action = interaction.get("action", "")
        itype = interaction.get("type", "")
        prompt = interaction.get("prompt", "")

        if prompt:
            parts.append(prompt)
        elif itype == "navigation":
            parts.append(f"Camera moves: {action}")
        elif itype == "event_edit":
            parts.append(action)
        elif itype == "subject_action":
            parts.append(action)
        elif itype == "perspective_switch":
            parts.append(f"Perspective changes to: {action}")

        return ". ".join(parts)

    @staticmethod
    def _extract_last_frame(video_path: str) -> Optional[str]:
        """Extract last frame from video, save as temp image, return path."""
        import cv2
        import tempfile
        import os

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total - 1))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None

        tmp_dir = os.path.join(os.path.dirname(video_path), "_tmp_frames")
        os.makedirs(tmp_dir, exist_ok=True)
        out_path = os.path.join(tmp_dir, f"last_frame_{os.path.basename(video_path)}.jpg")
        cv2.imwrite(out_path, frame)
        return out_path

    @staticmethod
    def _concat_segments(segment_paths: List[str], output_path: str) -> bool:
        """Concatenate video segments into a single MP4."""
        import cv2
        import os

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        caps = [cv2.VideoCapture(p) for p in segment_paths]
        if not all(c.isOpened() for c in caps):
            for c in caps:
                c.release()
            return False

        fps = caps[0].get(cv2.CAP_PROP_FPS) or 24.0
        w = int(caps[0].get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(caps[0].get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

        for cap in caps:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                resized = cv2.resize(frame, (w, h)) if (frame.shape[1], frame.shape[0]) != (w, h) else frame
                writer.write(resized)
            cap.release()

        writer.release()
        return os.path.exists(output_path)

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {"model_name": self.model_name}

    def __repr__(self):
        return f"<{self.__class__.__name__}(model={self.model_name})>"
