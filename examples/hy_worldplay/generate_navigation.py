"""
Batch navigation inference for HY-WorldPlay.

Loads the model once, then iterates over samples in a JSONL file.
Each sample provides navigation instructions, chunk lengths, a prompt,
and a reference image. The script converts navigation to poses, runs
inference, and saves the generated video.

Usage:
    torchrun --nproc_per_node=1 generate_navigation.py \
        --jsonl_path samples.jsonl \
        --output_dir ./outputs \
        --model_path models/HunyuanVideo-1.5 \
        --action_ckpt models/HY-WorldPlay/ar_distilled_action_model/model.safetensors
"""

import os
import sys
import json
import argparse
import traceback
from types import SimpleNamespace

if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
import einops
import imageio
import loguru

from hyvideo.pipelines.worldplay_video_pipeline import HunyuanVideo_1_5_Pipeline
from hyvideo.commons.parallel_states import initialize_parallel_state
from hyvideo.commons.infer_state import initialize_infer_state, InferState
from hyvideo.generate import pose_to_input, save_video

from navigation_to_poses import navigation_to_poses, navigation_to_poses_orbit

parallel_dims = initialize_parallel_state(sp=int(os.environ.get("WORLD_SIZE", "1")))
torch.cuda.set_device(int(os.environ.get("LOCAL_RANK", "0")))

RANK = int(os.environ.get("RANK", "0"))


def log(msg, level="INFO"):
    if RANK == 0:
        loguru.logger.log(level, msg)


def extract_prompt(prompt_dict):
    """Extract the first non-empty prompt from a prompt dict."""
    for key in sorted(prompt_dict.keys(), key=lambda x: int(x)):
        text = prompt_dict[key].strip()
        if text:
            return text
    return ""


def build_pipeline(args):
    """Build the HunyuanVideo pipeline (heavy — call once)."""
    transformer_dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float32

    pipe = HunyuanVideo_1_5_Pipeline.create_pipeline(
        pretrained_model_name_or_path=args.model_path,
        transformer_version="480p_i2v",
        enable_offloading=args.offloading,
        enable_group_offloading=args.group_offloading,
        create_sr_pipeline=args.sr,
        force_sparse_attn=False,
        transformer_dtype=transformer_dtype,
        action_ckpt=args.action_ckpt,
    )
    return pipe


def generate_single_sample(pipe, sample, output_dir, args):
    """Run inference for one navigation sample."""
    name = sample.get("name", "unnamed")
    log(f"Processing sample: {name}")

    navigation = sample["navigation"]
    chunk_length = sample["chunk_length"]
    prompt_dict = sample["prompt"]
    image_path = sample.get("image_path")
    rewrite = sample.get("rewrite", False)

    prompt = extract_prompt(prompt_dict)
    if not prompt:
        log(f"Skipping {name}: no prompt found", "WARNING")
        return

    if not image_path or not os.path.exists(image_path):
        log(f"Skipping {name}: image not found at {image_path}", "WARNING")
        return

    perspective = sample.get("perspective", "first_person")
    is_third_person = perspective == "third_person"

    if is_third_person:
        pose_json, video_length, latent_num = navigation_to_poses_orbit(navigation, chunk_length)
    else:
        pose_json, video_length, latent_num = navigation_to_poses(navigation, chunk_length)

    assert latent_num % 4 == 0, (
        f"latent_num={latent_num} not divisible by 4 for {name}"
    )

    viewmats, Ks, action = pose_to_input(pose_json, latent_num, tps=False)

    log(f"  prompt: {prompt[:80]}...")
    log(f"  image: {image_path}")
    log(f"  latent_num={latent_num}, video_length={video_length}")

    out = pipe(
        enable_sr=args.sr,
        prompt=prompt,
        aspect_ratio=args.aspect_ratio,
        num_inference_steps=args.num_inference_steps,
        sr_num_inference_steps=None,
        video_length=video_length,
        negative_prompt="",
        seed=args.seed,
        output_type="pt",
        prompt_rewrite=rewrite and args.rewrite,
        return_pre_sr_video=False,
        viewmats=viewmats.unsqueeze(0),
        Ks=Ks.unsqueeze(0),
        action=action.unsqueeze(0),
        few_step=args.few_step,
        chunk_latent_frames=4 if args.model_type == "ar" else 16,
        model_type=args.model_type,
        user_height=args.height,
        user_width=args.width,
        reference_image=image_path,
    )

    if RANK == 0:
        os.makedirs(output_dir, exist_ok=True)
        video_path = os.path.join(output_dir, f"{name}.mp4")

        if args.sr and hasattr(out, "sr_videos") and out.sr_videos is not None:
            save_video(out.sr_videos, video_path)
        else:
            save_video(out.videos, video_path)

        log(f"  Saved: {video_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch navigation inference for HY-WorldPlay"
    )
    parser.add_argument("--jsonl_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="./outputs/navigation")
    parser.add_argument("--model_path", type=str,
                        default="models/HunyuanVideo-1.5")
    parser.add_argument("--action_ckpt", type=str,
                        default="models/HY-WorldPlay/ar_distilled_action_model/model.safetensors")
    parser.add_argument("--model_type", type=str, default="ar", choices=["ar", "bi"])
    parser.add_argument("--few_step", action="store_true", default=True)
    parser.add_argument("--num_inference_steps", type=int, default=4)
    parser.add_argument("--aspect_ratio", type=str, default="16:9")
    parser.add_argument("--resolution", type=str, default="480p")
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--width", type=int, default=832)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--sr", action="store_true", default=False)
    parser.add_argument("--rewrite", action="store_true", default=False)
    parser.add_argument("--dtype", type=str, default="bf16", choices=["bf16", "fp32"])
    parser.add_argument("--offloading", action="store_true", default=True)
    parser.add_argument("--group_offloading", default=None)
    parser.add_argument("--names", nargs="*", default=None,
                        help="Only process these case names (default: all)")

    args = parser.parse_args()

    infer_args = SimpleNamespace(
        use_sageattn=False,
        sage_blocks_range="0-53",
        enable_torch_compile=False,
        use_fp8_gemm=False,
        quant_type="fp8-per-block",
        include_patterns="double_blocks",
        use_vae_parallel=False,
    )
    initialize_infer_state(infer_args)

    with open(args.jsonl_path, "r") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    if args.names:
        name_set = set(args.names)
        samples = [s for s in samples if s.get("name") in name_set]

    log(f"Loaded {len(samples)} samples from {args.jsonl_path}")
    log("Building pipeline (this takes a while)...")

    pipe = build_pipeline(args)

    log("Pipeline ready. Starting inference.")

    for i, sample in enumerate(samples):
        name = sample.get("name", "unnamed")
        log(f"[{i+1}/{len(samples)}] {name}")
        try:
            generate_single_sample(pipe, sample, args.output_dir, args)
        except Exception as e:
            log(f"Error processing {name}: {e}", "ERROR")
            traceback.print_exc()
            continue

    log("All samples done.")


if __name__ == "__main__":
    main()
