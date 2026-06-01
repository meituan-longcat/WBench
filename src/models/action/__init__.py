"""
Action-conditioned model support for WBench.

Two layers:
  - ../navigation.py : WBench actions (W/A/S/D + arrows) -> {move, yaw, pitch}
                       intent signals. Model-agnostic; shared with camera.
  - actions.py       : navigation intent -> discrete per-turn actions
                       (raw key tokens + MG3-style {keyboard, mouse}).

Action models come in two flavours:
  - Programmatic controllers (e.g. Matrix-Game-3): subclass ActionConditionedModel
    and implement generate_with_actions(). See example_model.py.
  - Web products (e.g. Project Genie, Happy Oyster): no weights/API, driven via
    browser automation + simulated keystrokes. See the web/ subdirectory.
"""
from ..navigation import (
    action_to_navigation,
    case_to_navigation,
    is_navigation_action,
)
from .actions import CAM_VALUE, case_to_actions, navigation_to_keyboard_mouse
from .example_model import ActionConditionedModel, PreviewActionModel

__all__ = [
    "action_to_navigation",
    "case_to_navigation",
    "is_navigation_action",
    "CAM_VALUE",
    "case_to_actions",
    "navigation_to_keyboard_mouse",
    "ActionConditionedModel",
    "PreviewActionModel",
]
