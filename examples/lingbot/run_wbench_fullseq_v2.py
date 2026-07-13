#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LingBot-World-v2 (14B causal-fast) full-sequence inference over WBench navigation.

v2 is a camera-pose world model with the SAME input contract as v1 (LingBot-World-Fast):
`_generate_causal_fast` in wan/image2video.py consumes ONLY poses.npy (F,4,4 c2w,
OpenCV) + intrinsics.npy (F,4 = fx,fy,cx,cy); the shipped wasd_action.npy is dead
code there (`wasd_action = None`). So the validated v1 WBench camera/prompt builders
(generate_from_json_fast.py, NavScore ~0.99) transfer verbatim.

The ONLY functional difference from v1's run_wbench_fullseq_fast.py:
    wan.WanI2VFast(...)  ->  wan.WanI2VCausal(..., infer_mode="causal_fast")
and matching v2's official causal-fast hyper-parameters:
    chunk_size=4 (v2 default; v1 used 3), timesteps_index=[0,250,500,750]
    (the generate() default; _generate_causal_fast internally uses [0,179,358,679]
    for the distilled few-step schedule), shift from config (sample_shift=10.0).

One CONTINUOUS accumulated camera trajectory per case is fed to generate() in a
single autoregressive rollout; turn transitions ride the model-native KV cache
(sliding window + attention sink). Single-GPU, no FSDP/SP.

Run (lyra2 env active, from the v2 repo root so `import wan` resolves):
    python run_wbench_fullseq_v2.py \
        --ckpt_dir model_zoo/lingbot-world-v2-14b-causal-fast \
        --jsonl_path wbench_trajectories/wbench_nav_158.jsonl \
        --output_dir wbench_trajectories/outputs_v2 \
        --size 480*832 --base_seed 42 \
        --local_attn_size 18 --sink_size 6
"""

import argparse
import gc
import json
import logging
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import torch
from PIL import Image

# Import the VERBATIM v1 camera + prompt builders (validated against the WBench
# navigation_trajectory evaluator). This file lives in the WBench adapter dir;
# make that dir importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wan
from wan.configs import MAX_AREA_CONFIGS, WAN_CONFIGS

from generate_from_json_fast import (
    FPS,
    build_poses_from_json,
    build_intrinsics,
    build_prompt_with_perspective,
)
from wan.utils.utils import save_video


def _parse_args():
    p = argparse.ArgumentParser(description="LingBot-World-v2 causal-fast full-sequence over WBench navigation")
    p.add_argument("--task", default="i2v-A14B", choices=list(WAN_CONFIGS.keys()))
    p.add_argument("--size", default="480*832")
    p.add_argument("--ckpt_dir", required=True)
    p.add_argument("--jsonl_path", required=True)
    p.add_argument("--output_dir", default="wbench_trajectories/outputs_v2")
    p.add_argument("--chunk_size", type=int, default=4,
                   help="Causal latent chunk size (v2 official default = 4)")
    p.add_argument("--base_seed", type=int, default=42)
    p.add_argument("--sample_shift", type=float, default=None,
                   help="Flow-matching shift; default = cfg.sample_shift (10.0)")
    p.add_argument("--local_attn_size", type=int, default=18,
                   help="Sliding-window KV-cache size in LATENT frames (-1=full seq). "
                        "v2 official causal-fast default = 18. Finite value caps VRAM "
                        "for long sequences (model-native streaming).")
    p.add_argument("--sink_size", type=int, default=6,
                   help="Attention-sink: keep first N latent frames un-evicted "
                        "(anchors initial scene). v2 official default = 6.")
    p.add_argument("--only", default=None, help="Comma-separated case names to run")
    p.add_argument("--min_mp4_bytes", type=int, default=50_000)
    p.add_argument("--max_attention_size", type=int, default=None)
    return p.parse_args()


def main():
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        handlers=[logging.StreamHandler(stream=sys.stdout)],
    )
    cfg = WAN_CONFIGS[args.task]
    if args.sample_shift is None:
        args.sample_shift = cfg.sample_shift
    max_area = MAX_AREA_CONFIGS[args.size]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load samples
    samples = []
    with open(args.jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        samples = [s for s in samples if s.get("name") in want]
    logging.info(f"Loaded {len(samples)} samples from {args.jsonl_path}")

    # ── Build WanI2VCausal (causal_fast) ONCE (single-GPU, no FSDP/SP) ──
    t0 = time.perf_counter()
    wan_i2v = wan.WanI2VCausal(
        config=cfg,
        checkpoint_dir=args.ckpt_dir,
        device_id=0,
        rank=0,
        t5_fsdp=False,
        dit_fsdp=False,
        use_sp=False,
        t5_cpu=False,
        local_attn_size=args.local_attn_size,
        sink_size=args.sink_size,
        infer_mode="causal_fast",
    )
    logging.info(f"WanI2VCausal(causal_fast) loaded in {time.perf_counter()-t0:.1f}s "
                 f"(local_attn_size={args.local_attn_size}, sink_size={args.sink_size}, "
                 f"chunk_size={args.chunk_size}, shift={args.sample_shift})")

    done, skipped, failed = [], [], []
    t_batch = time.perf_counter()

    for k, data in enumerate(samples, 1):
        name = data.get("name", f"sample_{k}")
        save_file = out_dir / f"{name}.mp4"
        if save_file.exists() and save_file.stat().st_size >= args.min_mp4_bytes:
            skipped.append(name)
            logging.info(f"[{k}/{len(samples)}] {name}: skip (exists)")
            continue

        image_path = data["image_path"]
        if not os.path.isfile(image_path):
            failed.append((name, "missing image"))
            logging.warning(f"[{k}/{len(samples)}] {name}: MISSING image {image_path}")
            continue

        try:
            # ── Continuous accumulated pose sequence (verbatim v1 builders) ──
            poses = build_poses_from_json(data)
            frame_num = len(poses)
            frame_num = ((frame_num - 1) // 4) * 4 + 1  # 4n+1
            poses = poses[:frame_num]
            intrinsics = build_intrinsics(frame_num)
            prompt = build_prompt_with_perspective(data)
            img = Image.open(image_path).convert("RGB")

            # action_path dir for this case (poses + intrinsics)
            tmp = out_dir / f".action_{name}"
            tmp.mkdir(exist_ok=True)
            np.save(tmp / "poses.npy", poses.astype(np.float32))
            np.save(tmp / "intrinsics.npy", intrinsics.astype(np.float32))

            t_case = time.perf_counter()
            video = wan_i2v.generate(
                prompt,
                img,
                action_path=str(tmp),
                chunk_size=args.chunk_size,
                max_area=max_area,
                frame_num=frame_num,
                shift=args.sample_shift,
                seed=args.base_seed,
                offload_model=False,
                max_attention_size=args.max_attention_size,
            )
            save_video(
                tensor=video[None],
                save_file=str(save_file),
                fps=cfg.sample_fps,
                nrow=1,
                normalize=True,
                value_range=(-1, 1),
            )
            dt = time.perf_counter() - t_case
            n_turns = len(data.get("chunk_length", {}))
            done.append(name)
            logging.info(
                f"[{k}/{len(samples)}] {name}: OK  {data.get('perspective','?')}  "
                f"{n_turns} turns  req_frames={frame_num}  {dt:.1f}s -> {save_file.name}")

            del video, img
            shutil.rmtree(tmp, ignore_errors=True)
            torch.cuda.empty_cache(); gc.collect()
        except Exception as e:
            torch.cuda.empty_cache(); gc.collect()
            failed.append((name, str(e)[:200]))
            logging.error(f"[{k}/{len(samples)}] {name}: FAILED {e}")
            traceback.print_exc()

    elapsed = time.perf_counter() - t_batch
    logging.info("=" * 60)
    logging.info(f"BATCH DONE in {elapsed/60:.1f} min  "
                 f"generated={len(done)} skipped={len(skipped)} failed={len(failed)}")
    if failed:
        logging.info(f"failed: {failed}")
    with open(out_dir / "_fullseq_manifest.json", "w") as f:
        json.dump({"done": done, "skipped": skipped,
                   "failed": [{"name": n, "err": e} for n, e in failed]}, f, indent=2)


if __name__ == "__main__":
    main()
