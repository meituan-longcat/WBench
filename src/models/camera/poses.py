"""
Reference camera-pose layer.

Turns the model-agnostic navigation signals (see ``navigation.py``) into a
concrete 6-DoF camera trajectory. This is a *reference* implementation using
one specific convention (matching HY-WorldPlay). Other camera-conditioned
models are expected to copy and adapt this file to their own convention while
keeping the navigation *intent* (directions, relative magnitudes, per-turn
durations) unchanged — the WBench navigation metric normalises absolute scale,
so what matters is that the camera moves the way each action intends.

Conventions used here (adapt to your model as needed):
    - Pose = camera-to-world 4x4, OpenCV axes (x right, y down, z forward).
    - One pose per *latent* frame; latent rate = fps / temporal_compression.
    - Speeds are per latent step:
        FORWARD_SPEED = 0.08 world units   (used for both forward and strafe)
        YAW_SPEED     = 3 deg
        PITCH_SPEED   = 3 deg
      Magnitudes are direction-only: navigation move=[2,0] behaves like [1,0]
      (np.sign is applied), so combos like W+D produce a diagonal at ~1.41x.
    - Intrinsic K is fixed for 1920x1080; rescale if your frames differ.

First-person uses an egocentric trajectory (the camera is the mover).
Third-person uses an orbit trajectory (camera circles a character at origin).
"""
from typing import Dict, List, Any, Tuple

import numpy as np

FPS = 24
TEMPORAL_COMPRESSION = 4
LATENT_RATE = FPS // TEMPORAL_COMPRESSION  # 6 latents per second

FORWARD_SPEED = 0.08
YAW_SPEED = np.deg2rad(3)
PITCH_SPEED = np.deg2rad(3)

DEFAULT_INTRINSIC = [
    [969.6969696969696, 0.0, 960.0],
    [0.0, 969.6969696969696, 540.0],
    [0.0, 0.0, 1.0],
]

# Orbit radius derived from default speeds so the camera's tangential velocity
# matches the forward walking speed: radius = FORWARD_SPEED / YAW_SPEED (~1.53).
ORBIT_RADIUS = FORWARD_SPEED / YAW_SPEED
ORBIT_HEIGHT = 0.3


def _rot_x(theta: float) -> np.ndarray:
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_y(theta: float) -> np.ndarray:
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def navigation_to_motions(
    navigation: Dict[str, Dict[str, Any]],
    chunk_length: Dict[str, float],
    fps: int = FPS,
    temporal_compression: int = TEMPORAL_COMPRESSION,
) -> Tuple[List[Dict[str, float]], int]:
    """Expand per-turn navigation signals into a flat per-latent motion list.

    Returns (motions, total_latents). ``len(motions) == total_latents - 1``
    because the trajectory starts from an initial (identity/look-at) pose.
    The total latent count is padded up to a multiple of 4.
    """
    latent_rate = fps // temporal_compression
    chunk_keys = sorted(navigation.keys(), key=lambda x: int(x))

    chunk_latent_counts = [int(chunk_length[k] * latent_rate) for k in chunk_keys]
    total_latents = sum(chunk_latent_counts)

    remainder = total_latents % 4
    if remainder != 0:
        padding = 4 - remainder
        chunk_latent_counts[-1] += padding
        total_latents += padding

    motions: List[Dict[str, float]] = []
    for i, key in enumerate(chunk_keys):
        nav = navigation[key]
        move_fwd, move_right = nav["move"][0], nav["move"][1]
        yaw, pitch = nav["yaw"], nav["pitch"]

        # First chunk emits one fewer motion: the initial pose occupies slot 0.
        n_motions = chunk_latent_counts[i] - 1 if i == 0 else chunk_latent_counts[i]

        for _ in range(n_motions):
            motion: Dict[str, float] = {}
            if move_fwd != 0:
                motion["forward"] = FORWARD_SPEED * np.sign(move_fwd)
            if move_right != 0:
                motion["right"] = FORWARD_SPEED * np.sign(move_right)
            if yaw != 0:
                motion["yaw"] = YAW_SPEED * np.sign(yaw)
            if pitch != 0:
                motion["pitch"] = PITCH_SPEED * np.sign(pitch)
            motions.append(motion)

    return motions, total_latents


def generate_camera_trajectory_local(motions: List[Dict[str, float]]) -> List[np.ndarray]:
    """First-person: the camera itself moves through the world.

    Each step rotates the camera frame (yaw about local Y, pitch about local X)
    then translates along the (updated) local forward/right axes.
    """
    poses = []
    T = np.eye(4)
    poses.append(T.copy())

    for move in motions:
        if "yaw" in move:
            T[:3, :3] = T[:3, :3] @ _rot_y(move["yaw"])
        if "pitch" in move:
            T[:3, :3] = T[:3, :3] @ _rot_x(move["pitch"])

        forward = move.get("forward", 0.0)
        if forward != 0:
            T[:3, 3] += T[:3, :3] @ np.array([0, 0, forward])

        right = move.get("right", 0.0)
        if right != 0:
            T[:3, 3] += T[:3, :3] @ np.array([right, 0, 0])

        poses.append(T.copy())

    return poses


def generate_orbit_trajectory(
    motions: List[Dict[str, float]],
    radius: float = ORBIT_RADIUS,
    height: float = ORBIT_HEIGHT,
) -> List[np.ndarray]:
    """Third-person: the camera orbits a character at the origin, looking at it.

    yaw/pitch orbit the camera (azimuth/elevation); forward/right translate the
    character (and the camera with it). The character's heading is fixed, so
    forward is along world +Z — turning only re-frames the character, it does
    not steer the walk direction.
    """
    poses = []
    azimuth = np.pi  # start behind the character (+Z forward, camera at -Z)
    elevation = 0.0
    character_pos = np.array([0.0, 0.0, 0.0])
    character_yaw = 0.0

    def _cam_pose():
        cx = character_pos[0] + radius * np.cos(elevation) * np.sin(azimuth)
        cy = character_pos[1] + height + radius * np.sin(elevation)
        cz = character_pos[2] + radius * np.cos(elevation) * np.cos(azimuth)
        cam_pos = np.array([cx, cy, cz])

        forward = character_pos + np.array([0, height * 0.5, 0]) - cam_pos
        forward = forward / (np.linalg.norm(forward) + 1e-8)
        world_up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, world_up)
        right = right / (np.linalg.norm(right) + 1e-8)
        up = np.cross(right, forward)

        T = np.eye(4)
        T[:3, 0] = right
        T[:3, 1] = up
        T[:3, 2] = forward
        T[:3, 3] = cam_pos
        return T

    poses.append(_cam_pose())

    for move in motions:
        if "yaw" in move:
            azimuth -= move["yaw"]
        if "pitch" in move:
            elevation = np.clip(elevation - move["pitch"], np.deg2rad(-60), np.deg2rad(60))

        fwd = move.get("forward", 0.0)
        rgt = move.get("right", 0.0)
        if fwd != 0 or rgt != 0:
            char_forward = np.array([np.sin(character_yaw), 0, np.cos(character_yaw)])
            char_right = np.array([np.cos(character_yaw), 0, -np.sin(character_yaw)])
            character_pos += char_forward * fwd + char_right * rgt

        poses.append(_cam_pose())

    return poses


def _poses_to_json(poses: List[np.ndarray]) -> Dict[str, Any]:
    return {
        str(i): {"extrinsic": p.tolist(), "K": DEFAULT_INTRINSIC}
        for i, p in enumerate(poses)
    }


def _build(navigation, chunk_length, orbit, fps, temporal_compression, radius, height):
    motions, total_latents = navigation_to_motions(
        navigation, chunk_length, fps=fps, temporal_compression=temporal_compression
    )
    if orbit:
        poses = generate_orbit_trajectory(motions, radius=radius, height=height)
    else:
        poses = generate_camera_trajectory_local(motions)
    assert len(poses) == total_latents, f"{len(poses)} != {total_latents}"

    video_length = (total_latents - 1) * temporal_compression + 1
    return _poses_to_json(poses), video_length, total_latents, motions


def navigation_to_poses(navigation, chunk_length,
                        fps=FPS, temporal_compression=TEMPORAL_COMPRESSION):
    """First-person poses. Returns (pose_json, video_length, total_latents)."""
    pose_json, video_length, total_latents, _ = _build(
        navigation, chunk_length, orbit=False, fps=fps,
        temporal_compression=temporal_compression, radius=ORBIT_RADIUS, height=ORBIT_HEIGHT,
    )
    return pose_json, video_length, total_latents


def navigation_to_poses_orbit(navigation, chunk_length,
                              fps=FPS, temporal_compression=TEMPORAL_COMPRESSION,
                              radius=ORBIT_RADIUS, height=ORBIT_HEIGHT):
    """Third-person orbit poses. Returns (pose_json, video_length, total_latents)."""
    pose_json, video_length, total_latents, _ = _build(
        navigation, chunk_length, orbit=True, fps=fps,
        temporal_compression=temporal_compression, radius=radius, height=height,
    )
    return pose_json, video_length, total_latents


def case_to_poses(case: Dict[str, Any], duration: float = 4.0,
                  fps: int = FPS, temporal_compression: int = TEMPORAL_COMPRESSION) -> Dict[str, Any]:
    """End-to-end: WBench case -> camera trajectory, dispatched by perspective.

    Returns a dict:
        {
            "perspective":  "third_person" | "first_person",
            "poses":        {"0": {"extrinsic": 4x4, "K": 3x3}, ...},
            "video_length": int,   # number of RGB frames to generate
            "total_latents":int,
            "motions":      [{...}, ...],  # per-latent deltas (for preview/debug)
            "intrinsic":    DEFAULT_INTRINSIC,
        }
    """
    from ..navigation import case_to_navigation

    nav = case_to_navigation(case, duration=duration)
    orbit = nav["perspective"] != "first_person"
    pose_json, video_length, total_latents, motions = _build(
        nav["navigation"], nav["chunk_length"], orbit=orbit, fps=fps,
        temporal_compression=temporal_compression, radius=ORBIT_RADIUS, height=ORBIT_HEIGHT,
    )
    return {
        "perspective": nav["perspective"],
        "poses": pose_json,
        "video_length": video_length,
        "total_latents": total_latents,
        "motions": motions,
        "intrinsic": DEFAULT_INTRINSIC,
        "navigation": nav["navigation"],
        "chunk_length": nav["chunk_length"],
    }
