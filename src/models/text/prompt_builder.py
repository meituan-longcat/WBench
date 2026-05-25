"""
Prompt builder for text-conditioned video generation.

Converts case interactions into natural language prompts suitable for
text-to-video / image-to-video models.
"""
from typing import Dict, Any

# First-person navigation: camera movement descriptions
FIRST_PERSON_ACTIONS = {
    "W": "The camera pushes forward.",
    "S": "The camera pulls back.",
    "A": "The camera moves to the left.",
    "D": "The camera moves to the right.",
    "left": "The camera pans to the left.",
    "right": "The camera pans to the right.",
    "up": "The camera tilts up.",
    "down": "The camera tilts down.",
    "W+A": "The camera moves diagonally forward-left.",
    "W+D": "The camera moves diagonally forward-right.",
    "S+A": "The camera moves diagonally backward-left.",
    "S+D": "The camera moves diagonally backward-right.",
    "W+left": "The camera pushes forward while panning to the left.",
    "W+right": "The camera pushes forward while panning to the right.",
    "W+up": "The camera pushes forward while tilting up.",
    "W+down": "The camera pushes forward while tilting down.",
}

# Third-person navigation: subject moves, camera follows
THIRD_PERSON_ACTIONS = {
    "W": "The subject moves forward. The camera follows, maintaining distance and framing.",
    "S": "The subject moves backward. The camera follows, maintaining distance and framing.",
    "A": "The subject moves to the left. The camera tracks left, keeping the subject centered.",
    "D": "The subject moves to the right. The camera tracks right, keeping the subject centered.",
    "left": "The camera orbits counterclockwise around the subject. The subject stays still.",
    "right": "The camera orbits clockwise around the subject. The subject stays still.",
    "up": "The camera cranes upward while tilting down to keep the subject centered.",
    "down": "The camera cranes downward while tilting up to keep the subject centered.",
    "W+A": "The subject moves diagonally forward-left. The camera follows along the same diagonal.",
    "W+D": "The subject moves diagonally forward-right. The camera follows along the same diagonal.",
    "S+D": "The subject moves backward-right. The camera retreats along the same diagonal.",
    "W+left": "The subject moves forward. The camera arcs counterclockwise while following.",
    "W+right": "The subject moves forward. The camera arcs clockwise while following.",
    "W+up": "The subject moves forward. The camera cranes upward while following.",
    "W+down": "The subject moves forward. The camera cranes downward while following.",
}


def build_turn_prompt(
    case: Dict[str, Any],
    interaction: Dict[str, Any],
    perspective: str = "first_person",
    is_first_turn: bool = False,
) -> str:
    """
    Build a text prompt for a single generation turn.

    Args:
        case: Full case dict (contains environment_prompt, character_prompt, etc.)
        interaction: Single interaction dict {"type": ..., "action": ...}
        perspective: "first_person" or "third_person"
        is_first_turn: Whether this is the first turn (include scene description)

    Returns:
        Complete prompt string for the video generation model.
    """
    parts = []

    # Scene context (always include for consistency)
    env = case.get("environment_prompt", "")
    char = case.get("character_prompt", "")
    persp_prompt = case.get("perspective_prompt", "")

    if is_first_turn:
        if env:
            parts.append(env)
        if char:
            parts.append(char)
        if persp_prompt:
            parts.append(persp_prompt)

    itype = interaction.get("type", "")
    action = interaction.get("action", "")

    if itype == "navigation":
        action_map = THIRD_PERSON_ACTIONS if perspective == "third_person" else FIRST_PERSON_ACTIONS
        motion_desc = action_map.get(action, f"Camera moves: {action}")
        parts.append(motion_desc)

    elif itype == "event_edit":
        parts.append(action)

    elif itype == "subject_action":
        parts.append(action)

    elif itype == "perspective_switch":
        if action == "fp_to_tp":
            parts.append("The viewpoint transitions from first-person to third-person, revealing the subject from behind.")
        elif action == "tp_to_fp":
            parts.append("The viewpoint transitions from third-person to first-person, the camera enters the subject's eyes.")
        else:
            parts.append(action)

    return " ".join(parts)
