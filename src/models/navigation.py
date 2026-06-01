"""
Navigation intent layer (model-agnostic).

Converts a WBench case's discrete navigation actions (W/A/S/D + arrow keys)
into per-turn navigation signals: ``{"move": [forward, right], "yaw", "pitch"}``.

This layer encodes *intent only* — direction and which turns, not absolute
speed. It is the stable, model-independent contract that every
camera-conditioned (and action-conditioned) model should build on. The
mapping to concrete 6-DoF camera poses (with a specific speed/coordinate
convention) lives in ``poses.py`` and is meant to be adapted per model.

Sign conventions:
    move = [forward, right]   forward > 0 = ahead,  right > 0 = strafe right
    yaw                        > 0 = turn right,    < 0 = turn left
    pitch                      > 0 = look up,       < 0 = look down
"""
from typing import Dict, List, Optional, Any

# Single key -> navigation signal. Combination keys (e.g. "W+D") are summed.
SINGLE_KEY_NAV = {
    "W":     {"move": [1, 0],  "yaw": 0,  "pitch": 0},
    "S":     {"move": [-1, 0], "yaw": 0,  "pitch": 0},
    "A":     {"move": [0, -1], "yaw": 0,  "pitch": 0},
    "D":     {"move": [0, 1],  "yaw": 0,  "pitch": 0},
    "→":     {"move": [0, 0],  "yaw": 1,  "pitch": 0},
    "right": {"move": [0, 0],  "yaw": 1,  "pitch": 0},
    "←":     {"move": [0, 0],  "yaw": -1, "pitch": 0},
    "left":  {"move": [0, 0],  "yaw": -1, "pitch": 0},
    "↑":     {"move": [0, 0],  "yaw": 0,  "pitch": 1},
    "up":    {"move": [0, 0],  "yaw": 0,  "pitch": 1},
    "↓":     {"move": [0, 0],  "yaw": 0,  "pitch": -1},
    "down":  {"move": [0, 0],  "yaw": 0,  "pitch": -1},
    "stop":  {"move": [0, 0],  "yaw": 0,  "pitch": 0},
}

NAV_KEYS = set(SINGLE_KEY_NAV.keys())


def action_to_navigation(action: str) -> Optional[Dict[str, Any]]:
    """Convert an action string to a navigation signal.

    Supports single keys ("W") and combinations joined by "+" ("W+D").
    Returns ``None`` if the action is not a navigation action (e.g. a
    subject-action or event-edit instruction), so callers can skip it.
    """
    parts = [p.strip() for p in action.split("+")]
    if not all(p in NAV_KEYS for p in parts):
        return None

    fwd, right, yaw, pitch = 0, 0, 0, 0
    for p in parts:
        nav = SINGLE_KEY_NAV[p]
        fwd += nav["move"][0]
        right += nav["move"][1]
        yaw += nav["yaw"]
        pitch += nav["pitch"]
    return {"move": [fwd, right], "yaw": yaw, "pitch": pitch}


def is_navigation_action(action: str) -> bool:
    """True if the action maps to a navigation signal."""
    return action_to_navigation(action) is not None


def case_to_navigation(case: Dict[str, Any], duration: float = 4.0) -> Dict[str, Any]:
    """Convert a WBench case into per-turn navigation signals.

    Args:
        case: Raw case dict (from a case JSON).
        duration: Seconds per turn. WBench navigation turns are fixed-length;
            override only if your data carries an explicit per-turn duration.

    Returns:
        {
            "perspective": "third_person" | "first_person",
            "navigation":  {"0": {move, yaw, pitch}, "1": {...}, ...},
            "chunk_length":{"0": duration, "1": duration, ...},
        }

    Non-navigation interactions (subject_action / event_edit) get a zero
    signal so turn indices stay aligned with ``case["interactions"]``.
    """
    settings = case.get("settings", {})
    perspective = settings.get("perspective", "third_person")
    interactions = case.get("interactions", [])

    navigation: Dict[str, Dict[str, Any]] = {}
    chunk_length: Dict[str, float] = {}

    for i, interaction in enumerate(interactions):
        idx = str(i)
        action = interaction.get("action", interaction.get("action_key", "stop"))
        nav = action_to_navigation(action)
        navigation[idx] = nav if nav is not None else {"move": [0, 0], "yaw": 0, "pitch": 0}
        chunk_length[idx] = duration

    return {
        "perspective": perspective,
        "navigation": navigation,
        "chunk_length": chunk_length,
    }
