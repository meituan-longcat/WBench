"""
Convert navigation instructions (data_pipeline format) to HY-WorldPlay pose JSON.

Standalone module with no torch dependency — only numpy.
"""

import numpy as np
import json

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


def _rot_x(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_y(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def generate_camera_trajectory_local(motions):
    """Reproduce HY-WorldPlay's generate_camera_trajectory_local (numpy only)."""
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


# Orbit radius derived from default speeds: radius = FORWARD_SPEED / YAW_SPEED
# so that the camera's tangential velocity matches the forward walking speed.
ORBIT_RADIUS = FORWARD_SPEED / YAW_SPEED  # ~1.53
ORBIT_HEIGHT = 0.3  # slight elevation above character, proportional to radius


def generate_orbit_trajectory(motions, radius=ORBIT_RADIUS, height=ORBIT_HEIGHT):
    """Generate orbit camera poses around a character at the origin.

    The character is assumed to be at world origin, walking forward along +Z.
    The camera orbits on a sphere of *radius* at *height* above the character,
    always looking at the character position.

    Each motion dict may contain:
      - "yaw":     azimuth delta (radians, positive = orbit right)
      - "pitch":   elevation delta (radians, positive = orbit up)
      - "forward": character moves forward; camera + character translate together
      - "right":   character strafes right; camera + character translate together
    """
    poses = []
    azimuth = np.pi  # start behind the character (+Z forward, camera at -Z)
    elevation = 0.0
    character_pos = np.array([0.0, 0.0, 0.0])
    character_yaw = 0.0  # character facing direction in world

    def _cam_pose():
        # Camera position on sphere around character
        cx = character_pos[0] + radius * np.cos(elevation) * np.sin(azimuth)
        cy = character_pos[1] + height + radius * np.sin(elevation)
        cz = character_pos[2] + radius * np.cos(elevation) * np.cos(azimuth)
        cam_pos = np.array([cx, cy, cz])

        # Look-at: camera Z axis points from camera toward character
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
        # Orbit rotation (camera moves, character stays)
        # yaw<0 = "turn left" = character faces left = camera orbits clockwise (azimuth increases)
        if "yaw" in move:
            azimuth -= move["yaw"]
        if "pitch" in move:
            elevation = np.clip(elevation - move["pitch"],
                                np.deg2rad(-60), np.deg2rad(60))

        # Translation (character + camera move together)
        fwd = move.get("forward", 0.0)
        rgt = move.get("right", 0.0)
        if fwd != 0 or rgt != 0:
            # Character moves in its own facing direction
            char_forward = np.array([np.sin(character_yaw), 0, np.cos(character_yaw)])
            char_right = np.array([np.cos(character_yaw), 0, -np.sin(character_yaw)])
            character_pos += char_forward * fwd + char_right * rgt

        poses.append(_cam_pose())

    return poses


def navigation_to_poses_orbit(navigation, chunk_length,
                              fps=FPS, temporal_compression=TEMPORAL_COMPRESSION,
                              radius=ORBIT_RADIUS, height=ORBIT_HEIGHT):
    """Convert navigation to orbit-camera poses for third-person view.

    Same interface as navigation_to_poses, but generates orbit trajectories
    where left/right rotations orbit the camera around the character.
    """
    latent_rate = fps // temporal_compression
    chunk_keys = sorted(navigation.keys(), key=lambda x: int(x))

    chunk_latent_counts = []
    for key in chunk_keys:
        chunk_latent_counts.append(int(chunk_length[key] * latent_rate))

    total_latents = sum(chunk_latent_counts)

    remainder = total_latents % 4
    if remainder != 0:
        padding = 4 - remainder
        chunk_latent_counts[-1] += padding
        total_latents += padding

    motions = []
    for i, key in enumerate(chunk_keys):
        nav = navigation[key]
        move_fwd = nav["move"][0]
        move_right = nav["move"][1]
        yaw = nav["yaw"]
        pitch = nav["pitch"]

        n_motions = chunk_latent_counts[i] - 1 if i == 0 else chunk_latent_counts[i]

        for _ in range(n_motions):
            motion = {}
            if move_fwd != 0:
                motion["forward"] = FORWARD_SPEED * np.sign(move_fwd)
            if move_right != 0:
                motion["right"] = FORWARD_SPEED * np.sign(move_right)
            if yaw != 0:
                motion["yaw"] = YAW_SPEED * np.sign(yaw)
            if pitch != 0:
                motion["pitch"] = PITCH_SPEED * np.sign(pitch)
            motions.append(motion)

    poses = generate_orbit_trajectory(motions, radius=radius, height=height)
    assert len(poses) == total_latents

    pose_json = {}
    for i, p in enumerate(poses):
        pose_json[str(i)] = {"extrinsic": p.tolist(), "K": DEFAULT_INTRINSIC}

    video_length = (total_latents - 1) * temporal_compression + 1

    return pose_json, video_length, total_latents


def navigation_to_poses(navigation, chunk_length,
                        fps=FPS, temporal_compression=TEMPORAL_COMPRESSION):
    """
    Convert navigation dict + chunk_length dict to HY-WorldPlay pose JSON.

    Args:
        navigation: dict keyed by chunk index string.
            Each value: {"move": [fwd, right], "yaw": float, "pitch": float}
            Values indicate direction only; actual magnitudes use default speeds.
        chunk_length: dict keyed by chunk index string.
            Each value: int, duration in seconds for that chunk.

    Returns:
        (pose_json, video_length, latent_num)
    """
    latent_rate = fps // temporal_compression
    chunk_keys = sorted(navigation.keys(), key=lambda x: int(x))

    chunk_latent_counts = []
    for key in chunk_keys:
        chunk_latent_counts.append(int(chunk_length[key] * latent_rate))

    total_latents = sum(chunk_latent_counts)

    remainder = total_latents % 4
    if remainder != 0:
        padding = 4 - remainder
        chunk_latent_counts[-1] += padding
        total_latents += padding

    motions = []
    for i, key in enumerate(chunk_keys):
        nav = navigation[key]
        move_fwd = nav["move"][0]
        move_right = nav["move"][1]
        yaw = nav["yaw"]
        pitch = nav["pitch"]

        n_motions = chunk_latent_counts[i] - 1 if i == 0 else chunk_latent_counts[i]

        for _ in range(n_motions):
            motion = {}
            if move_fwd != 0:
                motion["forward"] = FORWARD_SPEED * np.sign(move_fwd)
            if move_right != 0:
                motion["right"] = FORWARD_SPEED * np.sign(move_right)
            if yaw != 0:
                motion["yaw"] = YAW_SPEED * np.sign(yaw)
            if pitch != 0:
                motion["pitch"] = PITCH_SPEED * np.sign(pitch)
            motions.append(motion)

    poses = generate_camera_trajectory_local(motions)
    assert len(poses) == total_latents

    pose_json = {}
    for i, p in enumerate(poses):
        pose_json[str(i)] = {"extrinsic": p.tolist(), "K": DEFAULT_INTRINSIC}

    video_length = (total_latents - 1) * temporal_compression + 1

    return pose_json, video_length, total_latents
