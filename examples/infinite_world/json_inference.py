"""
Infinite World - JSON-based Inference with Per-Chunk Prompts and Navigation
===========================================================================
Accepts structured JSON input where each segment has its own prompt, navigation,
and duration (chunk_length in seconds). Converts navigation commands to discrete
move/view action indices and generates long videos chunk-by-chunk.

JSON input format:
{
  "name": "case_name",
  "image_path": "/path/to/first_frame.jpg",
  "perspective": "first_person" | "third_person" | "character_first_person",
  "prompt": {"0": "...", "1": "...", ...},
  "navigation": {"0": {"move": [fwd, right], "yaw": float, "pitch": float}, ...},
  "chunk_length": {"0": seconds, "1": seconds, ...},
  "rewrite": true/false  (ignored, reserved for pipeline)
}

Usage (run from inside the cloned InfiniteWorld repo, see README.md):
    python json_inference.py --json_path input.json
    python json_inference.py --jsonl_path inputs.jsonl
    torchrun --nproc_per_node=4 json_inference.py --json_path input.json
"""

import sys
import os
import cv2
import math
import torch
import random
import json
import datetime
import argparse
import numpy as np
from PIL import Image
from omegaconf import OmegaConf
import torch.distributed as dist
import torchvision.transforms as transforms
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from infworld.utils.prepare_dataloader import get_obj_from_str
from infworld.utils.data_utils import get_first_clip_from_video, save_silent_video
from infworld.utils.dataset_utils import is_vid, is_img

# ============================================================================
# Action Mapping Dictionaries
# ============================================================================
MOVE_ACTION_MAP = {
    'no-op': 0, 'go forward': 1, 'go back': 2, 'go left': 3, 'go right': 4,
    'go forward and go left': 5, 'go forward and go right': 6,
    'go back and go left': 7, 'go back and go right': 8, 'uncertain': 9,
}

VIEW_ACTION_MAP = {
    'no-op': 0, 'turn up': 1, 'turn down': 2, 'turn left': 3, 'turn right': 4,
    'turn up and turn left': 5, 'turn up and turn right': 6,
    'turn down and turn left': 7, 'turn down and turn right': 8, 'uncertain': 9,
}

# ============================================================================
# Generation Constants
# ============================================================================
LATENT_FRAMES_PER_CHUNK = 21
TEMPORAL_COMPRESSION = 4
DECODED_FRAMES_PER_CHUNK = (LATENT_FRAMES_PER_CHUNK - 1) * TEMPORAL_COMPRESSION + 1  # 81
NEW_FRAMES_PER_CHUNK = DECODED_FRAMES_PER_CHUNK - 1  # 80
SAVE_FPS = 30
SECONDS_PER_MODEL_CHUNK = NEW_FRAMES_PER_CHUNK / SAVE_FPS  # ~2.667

TEXT_CFG_SCALE = 5.0
NUM_SAMPLING_STEPS = 30
SHIFT = 7
GLOBAL_SEED = 42
BUCKET_CONFIG_NAME = 'ASPECT_RATIO_627_F64'

NEGATIVE_PROMPT = (
    "many cars, crowds, Vivid hues, overexposed, static, blurry details, "
    "subtitles, style, work, artwork, image, still, overall grayish, worst quality, "
    "low quality, JPEG compression artifacts, ugly, incomplete, extra fingers, "
    "poorly drawn hands, poorly drawn face, deformed, disfigured, deformed limbs, "
    "fused fingers, motionless image, cluttered background, three legs, "
    "crowded background, walking backwards."
)

# ============================================================================
# Perspective Suffixes
# ============================================================================
PERSPECTIVE_SUFFIXES = {
    "first_person": (
        "Smooth first-person camera perspective. "
        "The viewpoint moves through the scene as if the viewer is walking, "
        "with natural head-height framing and continuous motion."
    ),
    "third_person": (
        "Third-person perspective with the camera steadily following "
        "the main character from behind. The character remains centered in frame "
        "at all times, maintaining a consistent distance and height "
        "in a steady tracking shot."
    ),
    "character_first_person": (
        "First-person perspective from the character's own eyes. "
        "Held items, hands, or equipment are visible at the edges of the frame, "
        "bobbing naturally with the character's movement. "
        "The world is seen directly through the character's viewpoint."
    ),
}


# ============================================================================
# Navigation → Discrete Action Conversion
# ============================================================================
def navigation_to_move_view(nav):
    """Convert navigation dict to (move_str, view_str) matching MOVE/VIEW_ACTION_MAP keys.

    Args:
        nav: {"move": [fwd, right], "yaw": float, "pitch": float}
             move[0] >0 forward, <0 backward
             move[1] >0 right,   <0 left
             yaw     >0 turn right, <0 turn left
             pitch   >0 turn up,    <0 turn down
    """
    move = nav.get("move", [0, 0])
    fwd, right = move[0], move[1]
    yaw = nav.get("yaw", 0)
    pitch = nav.get("pitch", 0)

    if fwd > 0 and right > 0:
        move_str = "go forward and go right"
    elif fwd > 0 and right < 0:
        move_str = "go forward and go left"
    elif fwd < 0 and right > 0:
        move_str = "go back and go right"
    elif fwd < 0 and right < 0:
        move_str = "go back and go left"
    elif fwd > 0:
        move_str = "go forward"
    elif fwd < 0:
        move_str = "go back"
    elif right > 0:
        move_str = "go right"
    elif right < 0:
        move_str = "go left"
    else:
        move_str = "no-op"

    if yaw > 0 and pitch > 0:
        view_str = "turn up and turn right"
    elif yaw < 0 and pitch > 0:
        view_str = "turn up and turn left"
    elif yaw > 0 and pitch < 0:
        view_str = "turn down and turn right"
    elif yaw < 0 and pitch < 0:
        view_str = "turn down and turn left"
    elif yaw > 0:
        view_str = "turn right"
    elif yaw < 0:
        view_str = "turn left"
    elif pitch > 0:
        view_str = "turn up"
    elif pitch < 0:
        view_str = "turn down"
    else:
        view_str = "no-op"

    return move_str, view_str


# ============================================================================
# Perspective-Aware Navigation Text (ported from LongCat interactive_navigation.py)
# ============================================================================
def _nav_text_camera(move, yaw, pitch):
    """First-person camera-centric motion description."""
    parts = []
    if move[0] > 0:
        parts.append("pushes forward")
    elif move[0] < 0:
        parts.append("pulls backward")
    if move[1] > 0:
        parts.append("tracks right")
    elif move[1] < 0:
        parts.append("tracks left")
    translation = " while ".join(parts) if len(parts) == 2 else (parts[0] if parts else "")

    rotation = ""
    if yaw > 0:
        rotation = "pans right"
    elif yaw < 0:
        rotation = "pans left"

    tilt = ""
    if pitch > 0:
        tilt = "tilts up"
    elif pitch < 0:
        tilt = "tilts down"

    clauses = [c for c in [translation, rotation, tilt] if c]
    if not clauses:
        return ""
    if len(clauses) == 1:
        return f"The camera {clauses[0]} in a smooth continuous shot."
    return f"The camera {clauses[0]}, while simultaneously {', '.join(clauses[1:])}, in a smooth continuous shot."


def _nav_text_third_person(move, yaw, pitch):
    """Third-person: character moves, camera follows and orbits."""
    translation = ""
    if move[0] > 0 and move[1] > 0:
        translation = "walks forward and to the right"
    elif move[0] > 0 and move[1] < 0:
        translation = "walks forward and to the left"
    elif move[0] < 0 and move[1] > 0:
        translation = "steps backward and to the right"
    elif move[0] < 0 and move[1] < 0:
        translation = "steps backward and to the left"
    elif move[0] > 0:
        translation = "walks forward"
    elif move[0] < 0:
        translation = "steps backward"
    elif move[1] > 0:
        translation = "strafes right"
    elif move[1] < 0:
        translation = "strafes left"

    rotation = ""
    if yaw > 0:
        rotation = "turns right as the camera orbits around to stay behind the character"
    elif yaw < 0:
        rotation = "turns left as the camera orbits around to stay behind the character"

    tilt = ""
    if pitch > 0:
        tilt = "the camera tilts upward while following the character from behind"
    elif pitch < 0:
        tilt = "the camera tilts downward while following the character from behind"

    char_actions = [c for c in [translation, rotation] if c]
    if not char_actions and not tilt:
        return ""

    parts = []
    if char_actions:
        action_str = " and ".join(char_actions)
        if translation and not rotation:
            parts.append(f"The character {action_str} as the camera follows from behind in a steady tracking shot")
        else:
            parts.append(f"The character {action_str}")
    if tilt:
        parts.append(tilt)
    return ". ".join(parts) + "."


def _nav_text_character_fp(move, yaw, pitch):
    """Character first-person: movement described from character's own perspective."""
    parts = []
    if move[0] > 0:
        parts.append("moves forward")
    elif move[0] < 0:
        parts.append("steps backward")
    if move[1] > 0:
        parts.append("strafes right")
    elif move[1] < 0:
        parts.append("strafes left")
    translation = " and ".join(parts) if parts else ""

    rotation = ""
    if yaw > 0:
        rotation = "turns to face right"
    elif yaw < 0:
        rotation = "turns to face left"

    tilt = ""
    if pitch > 0:
        tilt = "looks upward"
    elif pitch < 0:
        tilt = "looks downward"

    clauses = [c for c in [translation, rotation, tilt] if c]
    if not clauses:
        return ""
    return f"The character {', '.join(clauses)} in a first-person perspective."


def navigation_to_text(nav, perspective):
    """Generate descriptive motion text based on navigation and perspective."""
    move = nav.get("move", [0, 0])
    yaw = nav.get("yaw", 0)
    pitch = nav.get("pitch", 0)

    if perspective == "third_person":
        return _nav_text_third_person(move, yaw, pitch)
    elif perspective == "character_first_person":
        return _nav_text_character_fp(move, yaw, pitch)
    else:
        return _nav_text_camera(move, yaw, pitch)


def build_chunk_prompt(base_prompt, nav, perspective):
    """Assemble final prompt = base_prompt + navigation text + perspective suffix."""
    nav_text = navigation_to_text(nav, perspective)
    suffix = PERSPECTIVE_SUFFIXES.get(perspective, "")

    parts = [p for p in [base_prompt, nav_text, suffix] if p]
    return " ".join(parts)


# ============================================================================
# Utility Functions (shared with infworld_inference.py)
# ============================================================================
def extract_ckpt_step(path):
    match = re.search(r'checkpoint-(\d+)\.ckpt', path)
    return int(match.group(1)) if match else 0


def resize_and_center_crop(image, target_size):
    orig_h, orig_w = image.shape[:2]
    target_h, target_w = target_size
    scale = max(target_h / orig_h, target_w / orig_w)
    final_h = math.ceil(scale * orig_h)
    final_w = math.ceil(scale * orig_w)
    resized = cv2.resize(image, (final_w, final_h), interpolation=cv2.INTER_AREA)
    tensor = torch.from_numpy(resized)[None, ...].permute(0, 3, 1, 2).contiguous()
    cropped = transforms.functional.center_crop(tensor, target_size)
    return cropped[:, :, None, :, :]


def setup_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True


def torch_gc():
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


def resolve_path(path, root=PROJECT_ROOT):
    if path is None:
        return path
    path = str(path).strip()
    if not os.path.isabs(path):
        path = os.path.join(root, path)
    return path


def load_condition_image(image_path, bucket_config):
    if is_vid(image_path):
        frames = get_first_clip_from_video(image_path, clip_len=1)
    elif is_img(image_path):
        image = cv2.imread(image_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        frames = [image]
    else:
        raise ValueError(f'Unsupported file format: {image_path}')

    processed_frames = []
    for frame in frames:
        ratio = frame.shape[0] / frame.shape[1]
        closest_bucket = sorted(bucket_config.keys(), key=lambda x: abs(float(x) - ratio))[0]
        target_h, target_w = bucket_config[closest_bucket][0]
        tensor = resize_and_center_crop(frame, (target_h, target_w))
        tensor = (tensor / 255 - 0.5) * 2
        processed_frames.append(tensor)
    return torch.cat(processed_frames, dim=2)


def load_dit_state_dict(checkpoint_path):
    checkpoint_path = resolve_path(checkpoint_path)
    if checkpoint_path.endswith(".safetensors"):
        from safetensors.torch import load_file
        state_dict = load_file(checkpoint_path)
    else:
        state_dict = torch.load(checkpoint_path, map_location="cpu")
    if "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]
    return state_dict


# ============================================================================
# Distributed Setup
# ============================================================================
def setup_distributed():
    if 'RANK' in os.environ:
        rank = int(os.environ['RANK'])
        local_rank = int(os.environ.get('LOCAL_RANK', rank % torch.cuda.device_count()))
        torch.cuda.set_device(local_rank)
        dist.init_process_group(backend="nccl", timeout=datetime.timedelta(seconds=3600 * 24))
        global_rank = dist.get_rank()
        num_processes = dist.get_world_size()
        return local_rank, global_rank, num_processes, True
    else:
        torch.cuda.set_device(0)
        return 0, 0, 1, False


# ============================================================================
# JSON Input Parsing → Generation Schedule
# ============================================================================
def parse_json_input(data):
    """Parse JSON input into a generation schedule.

    Returns:
        schedule: list of dicts, one per model chunk:
            {"prompt": str, "move_id": int, "view_id": int, "segment_idx": int}
        move_indices: list[int], frame-level move action IDs
        view_indices: list[int], frame-level view action IDs
        name: str
        image_path: str
    """
    chunk_length = data.get("chunk_length", {})
    prompts = data.get("prompt", {})
    navigation = data.get("navigation", {})
    perspective = data.get("perspective", "first_person")
    name = data.get("name", "output")
    image_path = data.get("image_path", None)

    sorted_keys = sorted(chunk_length.keys(), key=lambda x: int(x))

    schedule = []
    move_indices = []
    view_indices = []

    for seg_idx, key in enumerate(sorted_keys):
        seconds = chunk_length[key]
        num_model_chunks = max(1, round(seconds / SECONDS_PER_MODEL_CHUNK))

        base_prompt = prompts.get(key, "")
        nav = navigation.get(key, {"move": [0, 0], "yaw": 0, "pitch": 0})
        move_str, view_str = navigation_to_move_view(nav)
        move_id = MOVE_ACTION_MAP[move_str]
        view_id = VIEW_ACTION_MAP[view_str]
        full_prompt = build_chunk_prompt(base_prompt, nav, perspective)

        for _ in range(num_model_chunks):
            schedule.append({
                "prompt": full_prompt,
                "move_id": move_id,
                "view_id": view_id,
                "segment_idx": seg_idx,
            })

        n_frames = num_model_chunks * NEW_FRAMES_PER_CHUNK
        move_indices.extend([move_id] * n_frames)
        view_indices.extend([view_id] * n_frames)

    padding = DECODED_FRAMES_PER_CHUNK
    move_indices.extend([0] * padding)
    view_indices.extend([0] * padding)

    return schedule, move_indices, view_indices, name, image_path


# ============================================================================
# Single Sample Generation
# ============================================================================
def generate_sample(data, vae, text_encoder, scheduler, dit,
                    bucket_config, model_cfg, local_rank, output_dir):
    """Generate a video from one JSON sample."""
    schedule, move_indices, view_indices, name, image_path = parse_json_input(data)
    num_chunks = len(schedule)

    if not image_path or not os.path.exists(image_path):
        print(f"[InfWorld] Skipping {name}: image not found - {image_path}")
        return None

    print(f"[InfWorld] Sample '{name}': {num_chunks} model chunks, "
          f"~{1 + num_chunks * NEW_FRAMES_PER_CHUNK} frames, "
          f"~{(1 + num_chunks * NEW_FRAMES_PER_CHUNK) / SAVE_FPS:.1f}s")

    cond_video = load_condition_image(image_path, bucket_config).to(local_rank)
    with torch.no_grad():
        cond_latent = vae.encode(cond_video)

    video_buffer = cond_video.clone().cpu()

    latent_size = list(cond_latent.shape)
    latent_size[2] = LATENT_FRAMES_PER_CHUNK
    latent_size = torch.Size(latent_size)

    num_frames_cfg = model_cfg.validation_data.num_frames

    for chunk_idx in range(num_chunks):
        chunk_info = schedule[chunk_idx]
        prompt = chunk_info["prompt"]
        seg_idx = chunk_info["segment_idx"]

        print(f"[InfWorld] Chunk {chunk_idx + 1}/{num_chunks} "
              f"(segment {seg_idx}) prompt: {prompt[:60]}...")

        with torch.no_grad():
            current_cond = video_buffer.to(local_rank)
            current_latent = vae.encode(current_cond)

        curr_start = video_buffer.shape[2] - 1
        curr_end = curr_start + num_frames_cfg

        move = torch.tensor(
            move_indices[curr_start:curr_end],
            dtype=torch.long, device=local_rank,
        )
        view = torch.tensor(
            view_indices[curr_start:curr_end],
            dtype=torch.long, device=local_rank,
        )

        if move.shape[0] < num_frames_cfg:
            pad_len = num_frames_cfg - move.shape[0]
            move = torch.cat([move, torch.zeros(pad_len, dtype=torch.long, device=local_rank)])
            view = torch.cat([view, torch.zeros(pad_len, dtype=torch.long, device=local_rank)])

        additional_args = {
            "image_cond": current_latent,
            "move": move.unsqueeze(0),
            "view": view.unsqueeze(0),
        }

        torch_gc()

        with torch.no_grad():
            samples = scheduler.sample(
                model=dit,
                text_encoder=text_encoder,
                null_embedder=dit.y_embedder,
                z_size=latent_size,
                prompts=[prompt],
                guidance_scale=TEXT_CFG_SCALE,
                negative_prompts=[NEGATIVE_PROMPT],
                device=torch.device(local_rank),
                additional_args=additional_args,
            )

            decoded_chunk = vae.decode(samples).cpu()
            video_buffer = torch.cat([video_buffer, decoded_chunk[:, :, 1:]], dim=2)

            print(f"[InfWorld] Chunk {chunk_idx + 1} done. "
                  f"Total frames: {video_buffer.shape[2]}")
            torch_gc()

    save_path = os.path.join(output_dir, f"infworld_{name}")
    save_silent_video(video_buffer.to(local_rank), save_path, fps=SAVE_FPS, quality=10)
    print(f"[InfWorld] Saved: {save_path}.mp4 "
          f"({video_buffer.shape[2]} frames, "
          f"{video_buffer.shape[2] / SAVE_FPS:.1f}s)")

    del video_buffer, cond_video, cond_latent
    torch_gc()
    return save_path


# ============================================================================
# Model Loading
# ============================================================================
def load_models(config_path, local_rank, enable_context_parallel):
    """Load all model components from config."""
    args = OmegaConf.load(config_path)

    if hasattr(args, "vae_cfg") and "vae_pth" in args.vae_cfg:
        args.vae_cfg.vae_pth = resolve_path(args.vae_cfg.vae_pth)
    if hasattr(args, "text_encoder_cfg"):
        if "checkpoint_path" in args.text_encoder_cfg:
            args.text_encoder_cfg.checkpoint_path = resolve_path(args.text_encoder_cfg.checkpoint_path)
        if "tokenizer_path" in args.text_encoder_cfg:
            args.text_encoder_cfg.tokenizer_path = resolve_path(args.text_encoder_cfg.tokenizer_path)

    print("[InfWorld] Loading VAE...")
    vae = get_obj_from_str(args.vae_target)(**args.vae_cfg).to(local_rank)

    print("[InfWorld] Loading Text Encoder...")
    text_encoder = get_obj_from_str(args.text_encoder_target)(device=local_rank, **args.text_encoder_cfg)
    text_encoder.t5.model.to(local_rank)

    print("[InfWorld] Loading Scheduler...")
    scheduler = get_obj_from_str(args.scheduler_target)(**args.val_scheduler_cfg)
    scheduler.num_sampling_steps = NUM_SAMPLING_STEPS
    scheduler.shift = SHIFT

    print("[InfWorld] Loading DiT Model...")
    dtype = getattr(torch, args.amp_dtype)
    dit = get_obj_from_str(args.model_target)(
        out_channels=vae.out_channels,
        caption_channels=text_encoder.output_dim,
        model_max_length=text_encoder.model_max_length,
        enable_context_parallel=enable_context_parallel,
        **args.model_cfg
    ).to(dtype)
    dit.eval()

    state_dict = load_dit_state_dict(args.checkpoint_path)
    state_dict.pop("pos_embed_temporal", None)
    state_dict.pop("pos_embed", None)
    missing, unexpected = dit.load_state_dict(state_dict, strict=False)
    print(f"[InfWorld] Model loaded! Missing: {len(missing)}, Unexpected: {len(unexpected)}")
    dit.to(local_rank)

    from infworld.configs import bucket_config as bucket_config_module
    bucket_config = getattr(bucket_config_module, BUCKET_CONFIG_NAME)

    return vae, text_encoder, scheduler, dit, bucket_config, args


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Infinite World JSON-based inference")
    parser.add_argument("--json_path", type=str, default=None, help="Path to single JSON input")
    parser.add_argument("--jsonl_path", type=str, default=None, help="Path to JSONL with multiple samples")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory (default: outputs/json_inference)")
    parser.add_argument("--config", type=str, default=None, help="Model config YAML (default: configs/infworld_config.yaml)")
    parser.add_argument("--seed", type=int, default=GLOBAL_SEED, help="Random seed")
    cli_args = parser.parse_args()

    if not cli_args.json_path and not cli_args.jsonl_path:
        parser.error("Either --json_path or --jsonl_path must be provided")

    local_rank, global_rank, num_processes, use_dist = setup_distributed()
    print(f"[InfWorld] local_rank={local_rank} global_rank={global_rank} world_size={num_processes}")

    context_parallel_size = 1
    import infworld.context_parallel.context_parallel_util as cp_util
    if use_dist:
        from infworld.context_parallel.context_parallel_util import init_context_parallel, get_dp_size, get_dp_rank
        init_context_parallel(context_parallel_size=context_parallel_size,
                              global_rank=global_rank, world_size=num_processes)
        dp_rank = get_dp_rank()
        dp_size = get_dp_size()
    else:
        cp_util.dp_rank = 0
        cp_util.dp_size = 1
        cp_util.cp_rank = 0
        cp_util.cp_size = 1
        dp_rank = 0
        dp_size = 1
    enable_context_parallel = (context_parallel_size > 1)

    setup_seed(cli_args.seed + global_rank)
    torch_gc()

    config_path = cli_args.config or os.path.join(PROJECT_ROOT, 'configs', 'infworld_config.yaml')
    output_dir = cli_args.output_dir or os.path.join(PROJECT_ROOT, 'outputs', 'json_inference')
    os.makedirs(output_dir, exist_ok=True)

    vae, text_encoder, scheduler, dit, bucket_config, model_cfg = load_models(
        config_path, local_rank, enable_context_parallel
    )

    samples = []
    if cli_args.jsonl_path:
        with open(cli_args.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
        print(f"[InfWorld] Loaded {len(samples)} samples from JSONL")
    else:
        with open(cli_args.json_path, 'r', encoding='utf-8') as f:
            samples.append(json.load(f))
        print(f"[InfWorld] Loaded 1 sample from JSON")

    for idx, data in enumerate(samples):
        if idx % dp_size != dp_rank:
            continue

        name = data.get('name', f'sample_{idx}')
        print(f"\n{'=' * 60}")
        print(f"[InfWorld] Processing [{idx + 1}/{len(samples)}]: {name}")
        print(f"{'=' * 60}")

        try:
            generate_sample(data, vae, text_encoder, scheduler, dit,
                            bucket_config, model_cfg, local_rank, output_dir)
        except Exception as e:
            print(f"[InfWorld] Error processing {name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n[InfWorld] All done! Processed {len(samples)} samples.")


if __name__ == "__main__":
    main()
