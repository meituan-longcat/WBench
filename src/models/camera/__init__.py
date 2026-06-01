"""
Camera-conditioned model support for WBench.

Two layers:
  - navigation.py : WBench actions (W/A/S/D + arrows) -> {move, yaw, pitch}
                    intent signals. Model-agnostic; use as-is.
  - poses.py      : navigation intent -> 6-DoF camera trajectory. A *reference*
                    convention (HY-WorldPlay); adapt to your model.

To evaluate your own camera-conditioned model, subclass CameraConditionedModel
and implement generate_with_poses(). See example_model.py.
"""
from ..navigation import (
    SINGLE_KEY_NAV,
    action_to_navigation,
    is_navigation_action,
    case_to_navigation,
)
from .poses import (
    case_to_poses,
    navigation_to_motions,
    navigation_to_poses,
    navigation_to_poses_orbit,
    DEFAULT_INTRINSIC,
    FPS,
    TEMPORAL_COMPRESSION,
)
from .example_model import CameraConditionedModel, PreviewCameraModel

__all__ = [
    "SINGLE_KEY_NAV",
    "action_to_navigation",
    "is_navigation_action",
    "case_to_navigation",
    "case_to_poses",
    "navigation_to_motions",
    "navigation_to_poses",
    "navigation_to_poses_orbit",
    "DEFAULT_INTRINSIC",
    "FPS",
    "TEMPORAL_COMPRESSION",
    "CameraConditionedModel",
    "PreviewCameraModel",
]
