"""
Reference action layer for action-conditioned models.

Turns the model-agnostic navigation signals (see ``../navigation.py``) into
discrete per-turn actions. Action-conditioned world models come in two flavours,
and this layer serves both:

  - Keystroke / web products (e.g. Project Genie, Happy Oyster): consume the
    *raw key tokens* (W/A/S/D + arrows) directly, pressed into a game UI. Use the
    ``tokens`` field.
  - Programmatic controllers (e.g. Matrix-Game-3): consume a structured
    ``{keyboard, mouse}`` conditioning tensor. Use the ``keyboard`` / ``mouse``
    fields. This mapping follows the MG3 convention (the *reference*); adapt the
    representation to your model while keeping the per-turn intent unchanged.

Frame/iteration mapping (how many frames a turn spans, MG3's autoregressive
iteration math, etc.) is model-specific and intentionally left to the model.
"""
from typing import Any, Dict, List

from ..navigation import action_to_navigation, case_to_navigation

# MG3 mouse delta magnitude per step (reference convention).
CAM_VALUE = 0.1


def navigation_to_keyboard_mouse(nav: Dict[str, Any]) -> Dict[str, Any]:
    """Map a {move, yaw, pitch} signal to MG3-style {keyboard, mouse}.

    keyboard: 6-dim one-hot [W, S, A, D, _, _] (last two unused for navigation).
    mouse:    [pitch_axis, yaw_axis], each in {-CAM_VALUE, 0, +CAM_VALUE}.
    """
    move = nav.get("move", [0, 0])
    yaw = nav.get("yaw", 0)
    pitch = nav.get("pitch", 0)

    keyboard = [0, 0, 0, 0, 0, 0]
    if move[0] > 0:
        keyboard[0] = 1   # W forward
    elif move[0] < 0:
        keyboard[1] = 1   # S back
    if move[1] < 0:
        keyboard[2] = 1   # A left
    elif move[1] > 0:
        keyboard[3] = 1   # D right

    mouse = [0.0, 0.0]
    if pitch > 0:
        mouse[0] = CAM_VALUE
    elif pitch < 0:
        mouse[0] = -CAM_VALUE
    if yaw > 0:
        mouse[1] = CAM_VALUE
    elif yaw < 0:
        mouse[1] = -CAM_VALUE

    return {"keyboard": keyboard, "mouse": mouse}


def case_to_actions(case: Dict[str, Any], duration: float = 4.0) -> Dict[str, Any]:
    """Convert a WBench case into per-turn discrete actions.

    Returns:
        {
            "perspective": "third_person" | "first_person",
            "actions": [
                {
                    "turn": 1,
                    "tokens": ["W"],            # raw keys (keystroke/web models)
                    "keyboard": [1,0,0,0,0,0],  # MG3-style controller tensor
                    "mouse": [0.0, 0.0],
                    "duration": 4.0,            # seconds this action is held
                },
                ...
            ],
            "navigation":  {...},   # raw {move,yaw,pitch} per turn (for preview/debug)
            "chunk_length":{...},
            "total_duration": float,
        }

    Non-navigation interactions yield empty tokens and a zero action.
    """
    nav = case_to_navigation(case, duration=duration)
    interactions = case.get("interactions", [])

    actions: List[Dict[str, Any]] = []
    for i, interaction in enumerate(interactions):
        idx = str(i)
        raw = interaction.get("action", interaction.get("action_key", "stop"))
        tokens = [t.strip() for t in raw.split("+")] if action_to_navigation(raw) is not None else []
        km = navigation_to_keyboard_mouse(nav["navigation"][idx])
        actions.append({
            "turn": interaction.get("turn", i),
            "tokens": tokens,
            "keyboard": km["keyboard"],
            "mouse": km["mouse"],
            "duration": nav["chunk_length"][idx],
        })

    total_duration = sum(nav["chunk_length"][k] for k in nav["chunk_length"])
    return {
        "perspective": nav["perspective"],
        "actions": actions,
        "navigation": nav["navigation"],
        "chunk_length": nav["chunk_length"],
        "total_duration": total_duration,
    }
