import argparse
import gc
import logging
import os
import sys
import json
import shutil
import time
import traceback
import warnings

warnings.filterwarnings('ignore')

import random
import numpy as np
import torch
import torch.distributed as dist
from PIL import Image
from scipy.spatial.transform import Rotation as R

import wan
from wan.configs import MAX_AREA_CONFIGS, SIZE_CONFIGS, WAN_CONFIGS
from wan.distributed.util import init_distributed_group
from wan.utils.utils import save_video, str2bool


def torch_gc():
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


# ---- Constants ----
FPS = 16
# Calibrated from official examples (examples/00,01,02 pose statistics)
TRANSLATION_SPEED_PER_FRAME = 0.3     # ~0.2-0.6 in official data
YAW_SPEED_PER_FRAME = 0.6             # ~0.3-0.8 deg in official data
PITCH_SPEED_PER_FRAME = 0.3           # pitch is typically smaller than yaw

# Orbit camera for third-person: radius = translation_speed / angular_speed
ORBIT_RADIUS = TRANSLATION_SPEED_PER_FRAME / np.deg2rad(YAW_SPEED_PER_FRAME)
ORBIT_HEIGHT = ORBIT_RADIUS * 0.2     # slight elevation, proportional to radius

# perspective prompt suffix (appended to first frame prompt)
PERSPECTIVE_SUFFIX = {
    "first_person": "",
    "first_perspective": "",
    "character_first_person": (
        " The character moves in sync with the camera, performing natural actions "
        "that correspond to the camera's movement direction."
    ),
    "character_first_perspective": (
        " The character moves in sync with the camera, performing natural actions "
        "that correspond to the camera's movement direction."
    ),
    "third_person": (
        " The subject remains centered in the frame, moving and acting naturally "
        "in response to the camera's movement while staying in focus."
    ),
    "third_perspective": (
        " The subject remains centered in the frame, moving and acting naturally "
        "in response to the camera's movement while staying in focus."
    ),
}


# ---- Navigation -> Poses ----

def navigation_to_pose_params(nav: dict) -> tuple:
    """将navigation指令转换为 (forward, right, yaw, pitch)"""
    move = nav.get("move", [0, 0])
    yaw = nav.get("yaw", 0)
    pitch = nav.get("pitch", 0)
    forward = move[0] if len(move) > 0 else 0
    right = move[1] if len(move) > 1 else 0
    return forward, right, yaw, pitch


def generate_poses_for_chunk(num_frames: int, forward: float, right: float,
                             yaw: float, pitch: float, start_pose: np.ndarray) -> np.ndarray:
    """根据控制指令生成一个chunk的pose序列 (OpenCV: X右, Y下, Z前)"""
    poses = [start_pose.copy()]
    current_pose = start_pose.copy()

    for _ in range(1, num_frames):
        new_pose = current_pose.copy()
        # 平移 (local frame)
        trans_local = np.array([
            right * TRANSLATION_SPEED_PER_FRAME,
            0,
            forward * TRANSLATION_SPEED_PER_FRAME
        ])
        trans_world = current_pose[:3, :3] @ trans_local
        new_pose[:3, 3] += trans_world

        # 旋转 (yaw绕Y轴, pitch绕X轴)
        rot_delta = R.from_euler('yxz', [
            yaw * YAW_SPEED_PER_FRAME,
            pitch * PITCH_SPEED_PER_FRAME,
            0
        ], degrees=True)
        current_rot = R.from_matrix(current_pose[:3, :3])
        new_rot = current_rot * rot_delta
        new_pose[:3, :3] = new_rot.as_matrix()

        poses.append(new_pose)
        current_pose = new_pose

    return np.array(poses)


def generate_orbit_poses_for_chunk(num_frames: int, forward: float, right: float,
                                   yaw: float, pitch: float,
                                   azimuth: float, elevation: float,
                                   character_pos: np.ndarray,
                                   radius: float = ORBIT_RADIUS,
                                   height: float = ORBIT_HEIGHT) -> tuple:
    """Generate orbit camera poses around a character (OpenCV: X右, Y下, Z前).

    Character is at character_pos, camera orbits on a sphere looking at character.
    Returns (poses_array, final_azimuth, final_elevation, final_character_pos).
    """
    def _cam_pose(az, el, char_pos):
        # Camera position (OpenCV: Y is down, so height goes negative Y)
        cx = char_pos[0] + radius * np.cos(el) * np.sin(az)
        cy = char_pos[1] - height - radius * np.sin(el)  # Y-down
        cz = char_pos[2] + radius * np.cos(el) * np.cos(az)
        cam_pos = np.array([cx, cy, cz])

        # Look-at: Z axis from camera toward character
        target = char_pos.copy()
        target[1] -= height * 0.5  # look slightly above character center
        fwd = target - cam_pos
        fwd = fwd / (np.linalg.norm(fwd) + 1e-8)
        world_down = np.array([0.0, 1.0, 0.0])  # OpenCV Y-down
        right_vec = np.cross(fwd, world_down)
        right_vec = right_vec / (np.linalg.norm(right_vec) + 1e-8)
        down = np.cross(fwd, right_vec)

        T = np.eye(4, dtype=np.float32)
        T[:3, 0] = right_vec
        T[:3, 1] = down
        T[:3, 2] = fwd
        T[:3, 3] = cam_pos
        return T

    poses = [_cam_pose(azimuth, elevation, character_pos)]

    for _ in range(1, num_frames):
        # Orbit rotation: yaw<0 = left turn = azimuth increases (camera moves left)
        if yaw != 0:
            azimuth -= yaw * np.deg2rad(YAW_SPEED_PER_FRAME)
        if pitch != 0:
            elevation = np.clip(elevation - pitch * np.deg2rad(PITCH_SPEED_PER_FRAME),
                                np.deg2rad(-60), np.deg2rad(60))

        # Translation: character + camera move together
        if forward != 0 or right != 0:
            # Character facing direction (derived from current azimuth, opposite of camera)
            char_fwd = np.array([-np.sin(azimuth), 0, -np.cos(azimuth)])
            char_right = np.array([-np.cos(azimuth), 0, np.sin(azimuth)])
            character_pos = character_pos + char_fwd * forward * TRANSLATION_SPEED_PER_FRAME \
                                          + char_right * right * TRANSLATION_SPEED_PER_FRAME

        poses.append(_cam_pose(azimuth, elevation, character_pos))

    return np.array(poses), azimuth, elevation, character_pos


def build_poses_from_json(data: dict) -> np.ndarray:
    """根据JSON构建完整pose序列。
    first_person: rotate-in-place poses.
    third_person: orbit camera poses around character.
    """
    chunk_length = data.get("chunk_length", {})
    navigation = data.get("navigation", {})
    perspective = data.get("perspective", "first_person")
    sorted_keys = sorted(chunk_length.keys(), key=lambda x: int(x))
    is_third_person = perspective in ("third_person", "third_perspective")

    all_poses = []

    if is_third_person:
        # Orbit mode
        azimuth = np.pi  # start behind character
        elevation = 0.0
        character_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        for key in sorted_keys:
            length_sec = chunk_length[key]
            num_frames = max(1, int(length_sec * FPS))
            nav = navigation.get(key, {})
            forward, right, yaw, pitch = navigation_to_pose_params(nav)

            chunk_poses, azimuth, elevation, character_pos = \
                generate_orbit_poses_for_chunk(
                    num_frames, forward, right, yaw, pitch,
                    azimuth, elevation, character_pos)

            if len(all_poses) > 0:
                all_poses.append(chunk_poses[1:])
            else:
                all_poses.append(chunk_poses)
    else:
        # First-person: original rotate-in-place
        current_pose = np.eye(4, dtype=np.float32)

        for key in sorted_keys:
            length_sec = chunk_length[key]
            num_frames = max(1, int(length_sec * FPS))
            nav = navigation.get(key, {})
            forward, right, yaw, pitch = navigation_to_pose_params(nav)
            chunk_poses = generate_poses_for_chunk(num_frames, forward, right, yaw, pitch, current_pose)

            if len(all_poses) > 0:
                all_poses.append(chunk_poses[1:])
            else:
                all_poses.append(chunk_poses)
            current_pose = chunk_poses[-1].copy()

    return np.concatenate(all_poses, axis=0)


def build_intrinsics(num_frames: int) -> np.ndarray:
    default_intrinsic = np.array([502.9116, 503.10812, 415.77786, 239.77779], dtype=np.float32)
    return np.tile(default_intrinsic, (num_frames, 1))


def build_prompt_with_perspective(data: dict) -> str:
    """拼接所有段的 prompt，用 Then 连接，首帧末尾追加 perspective 提示"""
    prompts = data.get("prompt", {})
    chunk_length = data.get("chunk_length", {})
    perspective = data.get("perspective", "first_perspective")
    sorted_keys = sorted(chunk_length.keys(), key=lambda x: int(x))

    parts = []
    for i, key in enumerate(sorted_keys):
        text = prompts.get(key, "").strip()
        if i == 0:
            # 首帧: base prompt + perspective suffix
            suffix = PERSPECTIVE_SUFFIX.get(perspective, "")
            parts.append((text + suffix).strip() if text else suffix.strip())
        else:
            parts.append(text if text else "The scene continues with nothing particular happening.")

    return " Then, ".join(parts)


# ---- Arg parsing ----

def _parse_args():
    parser = argparse.ArgumentParser(description="Lingbot-Fast batch inference (single model load)")
    parser.add_argument("--task", type=str, default="i2v-A14B", choices=list(WAN_CONFIGS.keys()))
    parser.add_argument("--size", type=str, default="480*832", choices=list(SIZE_CONFIGS.keys()))
    parser.add_argument("--frame_num", type=int, default=None,
                        help="Max frames (4n+1). Default: derived from chunk_length per sample")
    parser.add_argument("--ckpt_dir", type=str, required=True)
    parser.add_argument("--json_path", type=str, default=None, help="Single JSON file")
    parser.add_argument("--jsonl_path", type=str, default=None, help="JSONL file with multiple samples")
    parser.add_argument("--output_dir", type=str, default="./outputs")
    parser.add_argument("--offload_model", type=str2bool, default=None)
    parser.add_argument("--ulysses_size", type=int, default=1)
    parser.add_argument("--t5_fsdp", action="store_true", default=False)
    parser.add_argument("--t5_cpu", action="store_true", default=False)
    parser.add_argument("--dit_fsdp", action="store_true", default=False)
    parser.add_argument("--sample_shift", type=float, default=None)
    parser.add_argument("--base_seed", type=int, default=42)
    parser.add_argument("--convert_model_dtype", action="store_true", default=False)
    parser.add_argument("--max_attention_size", type=int, default=None,
                        help="Max attention size for fast inference (None=auto)")

    args = parser.parse_args()

    if not args.json_path and not args.jsonl_path:
        parser.error("Either --json_path or --jsonl_path must be provided")

    cfg = WAN_CONFIGS[args.task]
    if args.sample_shift is None:
        args.sample_shift = cfg.sample_shift
    if args.frame_num is None:
        args.frame_num = 161
    args.base_seed = args.base_seed if args.base_seed >= 0 else random.randint(0, sys.maxsize)

    return args


def _init_logging(rank):
    if rank == 0:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            handlers=[logging.StreamHandler(stream=sys.stdout)])
    else:
        logging.basicConfig(level=logging.ERROR)


# ---- Per-chunk frame limit (fits in ~60GB VRAM with 2-card FSDP) ----
CHUNK_FRAME_NUM = 81  # 5s per chunk at 16fps, safe for most GPU configs


def _generate_one_chunk(wan_i2v, prompt, img, poses_chunk, intrinsics_chunk,
                        temp_dir, args, frame_num):
    """Run one I2V generation for a single chunk. Returns video tensor (C,F,H,W) on rank 0."""
    os.makedirs(temp_dir, exist_ok=True)
    np.save(os.path.join(temp_dir, "poses.npy"), poses_chunk.astype(np.float32))
    np.save(os.path.join(temp_dir, "intrinsics.npy"), intrinsics_chunk.astype(np.float32))

    video = wan_i2v.generate(
        prompt,
        img,
        action_path=temp_dir,
        max_area=MAX_AREA_CONFIGS[args.size],
        frame_num=frame_num,
        shift=args.sample_shift,
        seed=args.base_seed,
        offload_model=args.offload_model,
        max_attention_size=args.max_attention_size,
    )

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    return video


def _video_to_pil(video_tensor):
    """Convert last frame of video tensor (C,F,H,W) in [-1,1] to PIL Image."""
    last_frame = video_tensor[:, -1]  # (C, H, W)
    last_frame = (last_frame + 1) / 2  # [-1,1] -> [0,1]
    last_frame = last_frame.clamp(0, 1)
    last_frame = (last_frame * 255).byte().cpu()
    return Image.fromarray(last_frame.permute(1, 2, 0).numpy())


# ---- Single sample generation (chunk-by-chunk) ----

def generate_single(data: dict, wan_i2v, args, cfg, rank: int):
    """生成单个sample的视频，逐chunk生成再拼接。
    每个chunk独立做I2V，以上一chunk的最后一帧作为输入图，pose从identity重置。
    """
    name = data.get("name", "output")
    image_path = data.get("image_path", None)

    # skip if output already exists
    save_file = os.path.join(args.output_dir, f"lingbot_fast_{name}.mp4")
    if os.path.exists(save_file):
        logging.info(f"[{name}] output exists, skipping: {save_file}")
        return

    t_start = time.time()

    # image
    assert image_path is not None, "image_path is required"
    if not os.path.isabs(image_path):
        base_dir = os.path.dirname(os.path.abspath(
            args.jsonl_path if args.jsonl_path else args.json_path))
        image_path = os.path.join(base_dir, image_path)
    assert os.path.exists(image_path), f"Image not found: {image_path}"

    # Build per-chunk data
    chunk_length = data.get("chunk_length", {})
    navigation = data.get("navigation", {})
    prompts = data.get("prompt", {})
    perspective = data.get("perspective", "first_person")
    sorted_keys = sorted(chunk_length.keys(), key=lambda x: int(x))
    is_third_person = perspective in ("third_person", "third_perspective")

    # Build per-chunk prompts (first chunk gets full prompt + suffix, rest get their own)
    full_prompt = build_prompt_with_perspective(data)
    chunk_prompts = []
    for i, key in enumerate(sorted_keys):
        if i == 0:
            chunk_prompts.append(full_prompt)
        else:
            p = prompts.get(key, "").strip()
            if p:
                chunk_prompts.append(p)
            else:
                chunk_prompts.append(full_prompt)

    logging.info(f"[{name}] {len(sorted_keys)} chunks, perspective={perspective}")

    # Generate per-chunk poses (each starting from identity)
    chunk_pose_list = []
    if is_third_person:
        # Orbit: each chunk starts fresh from behind character
        for key in sorted_keys:
            length_sec = chunk_length[key]
            num_frames = max(1, int(length_sec * FPS))
            num_frames = ((num_frames - 1) // 4) * 4 + 1
            num_frames = min(num_frames, CHUNK_FRAME_NUM)
            nav = navigation.get(key, {})
            forward, right, yaw, pitch = navigation_to_pose_params(nav)
            azimuth = np.pi
            elevation = 0.0
            char_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            chunk_poses, _, _, _ = generate_orbit_poses_for_chunk(
                num_frames, forward, right, yaw, pitch,
                azimuth, elevation, char_pos)
            chunk_pose_list.append(chunk_poses)
    else:
        # First-person: each chunk starts from identity
        for key in sorted_keys:
            length_sec = chunk_length[key]
            num_frames = max(1, int(length_sec * FPS))
            num_frames = ((num_frames - 1) // 4) * 4 + 1
            num_frames = min(num_frames, CHUNK_FRAME_NUM)
            nav = navigation.get(key, {})
            forward, right, yaw, pitch = navigation_to_pose_params(nav)
            start_pose = np.eye(4, dtype=np.float32)
            chunk_poses = generate_poses_for_chunk(num_frames, forward, right, yaw, pitch, start_pose)
            chunk_pose_list.append(chunk_poses)

    # Generate chunk by chunk
    video_chunks = []
    current_img = Image.open(image_path).convert("RGB")

    for ci, key in enumerate(sorted_keys):
        chunk_poses = chunk_pose_list[ci]
        frame_num = len(chunk_poses)
        intrinsics = build_intrinsics(frame_num)
        prompt = chunk_prompts[ci]
        temp_dir = os.path.join(args.output_dir, f".temp_action_{name}_{rank}_chunk{ci}")

        logging.info(f"[{name}] chunk {ci+1}/{len(sorted_keys)}: "
                     f"{frame_num} frames, prompt: {prompt[:60]}...")

        video = _generate_one_chunk(
            wan_i2v, prompt, current_img, chunk_poses, intrinsics,
            temp_dir, args, frame_num)

        if rank == 0:
            # Save chunk video and extract last frame for next chunk
            video_chunks.append(video.cpu())
            current_img = _video_to_pil(video)
            # Broadcast last frame to all ranks so they have correct img for next chunk
            if dist.is_initialized():
                import io, torchvision.transforms.functional as TF_sync
                last_tensor = TF_sync.to_tensor(current_img)  # (C,H,W) [0,1]
                dist.broadcast(last_tensor.cuda(), src=0)
            logging.info(f"[{name}] chunk {ci+1} done, extracted last frame for next chunk")
        else:
            # Non-rank-0: receive broadcast last frame
            if dist.is_initialized():
                import torchvision.transforms.functional as TF_sync
                # Need shape info - use same shape as original img
                c, h_img, w_img = TF_sync.to_tensor(current_img).shape
                last_tensor = torch.zeros(c, h_img, w_img, device='cuda')
                dist.broadcast(last_tensor, src=0)
                last_tensor = last_tensor.cpu()
                last_np = (last_tensor.permute(1, 2, 0).numpy() * 255).astype(np.uint8)
                current_img = Image.fromarray(last_np)

        del video
        torch_gc()
        gc.collect()

    # Concatenate and save
    if rank == 0:
        # First chunk: all frames; subsequent chunks: skip frame 0 (overlap with prev last frame)
        parts = []
        for i, vc in enumerate(video_chunks):
            if i == 0:
                parts.append(vc)
            else:
                parts.append(vc[:, 1:])  # skip first frame (duplicate of prev last)

        full_video = torch.cat(parts, dim=1)
        logging.info(f"[{name}] saving {full_video.shape[1]} frames -> {save_file}")
        save_video(
            tensor=full_video[None],
            save_file=save_file,
            fps=cfg.sample_fps,
            nrow=1,
            normalize=True,
            value_range=(-1, 1)
        )
        del full_video, video_chunks

    torch_gc()
    gc.collect()

    elapsed = time.time() - t_start
    logging.info(f"[{name}] done in {elapsed:.1f}s")


# ---- Main ----

@torch.inference_mode()
def main():
    args = _parse_args()

    rank = int(os.getenv("RANK", 0))
    world_size = int(os.getenv("WORLD_SIZE", 1))
    local_rank = int(os.getenv("LOCAL_RANK", 0))
    device = local_rank
    _init_logging(rank)

    if args.offload_model is None:
        args.offload_model = False if world_size > 1 else True
        logging.info(f"offload_model auto set to {args.offload_model}")

    if world_size > 1:
        torch.cuda.set_device(local_rank)
        dist.init_process_group(backend="nccl", init_method="env://", rank=rank, world_size=world_size)
    else:
        assert not (args.t5_fsdp or args.dit_fsdp)
        assert not (args.ulysses_size > 1)

    if args.ulysses_size > 1:
        assert args.ulysses_size == world_size
        init_distributed_group()

    cfg = WAN_CONFIGS[args.task]
    if args.ulysses_size > 1:
        assert cfg.num_heads % args.ulysses_size == 0

    logging.info(f"args: {args}")

    # sync seed
    if dist.is_initialized():
        base_seed = [args.base_seed] if rank == 0 else [None]
        dist.broadcast_object_list(base_seed, src=0)
        args.base_seed = base_seed[0]

    # ---- Load model ONCE (Fast version with KV caching) ----
    logging.info("Creating WanI2VFast pipeline ...")
    wan_i2v = wan.WanI2VFast(
        config=cfg,
        checkpoint_dir=args.ckpt_dir,
        device_id=device,
        rank=rank,
        t5_fsdp=args.t5_fsdp,
        dit_fsdp=args.dit_fsdp,
        use_sp=(args.ulysses_size > 1),
        t5_cpu=args.t5_cpu,
        convert_model_dtype=args.convert_model_dtype,
    )
    logging.info("Fast model loaded!")

    os.makedirs(args.output_dir, exist_ok=True)

    # ---- Load samples ----
    samples = []
    if args.jsonl_path:
        logging.info(f"Loading JSONL: {args.jsonl_path}")
        with open(args.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
    elif args.json_path:
        logging.info(f"Loading JSON: {args.json_path}")
        with open(args.json_path, 'r', encoding='utf-8') as f:
            samples.append(json.load(f))

    logging.info(f"Total samples: {len(samples)}")

    # ---- Inference loop ----
    total_start = time.time()
    for idx, data in enumerate(samples):
        name = data.get("name", f"sample_{idx}")
        logging.info(f"{'='*50}")
        logging.info(f"[{idx+1}/{len(samples)}] {name}")
        logging.info(f"{'='*50}")
        try:
            generate_single(data, wan_i2v, args, cfg, rank)
        except Exception as e:
            logging.error(f"Error on {name}: {e}")
            traceback.print_exc()
            torch_gc()
            gc.collect()
            continue

    # cleanup
    torch.cuda.synchronize()
    if dist.is_initialized():
        dist.barrier()
        dist.destroy_process_group()
    total_elapsed = time.time() - total_start
    logging.info(f"All done! {len(samples)} samples in {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
