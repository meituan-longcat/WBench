# LingBot-World-v2 integration example

Reference code for generating WBench videos with **LingBot-World-v2**
(`lingbot` in the WBench leaderboard), a 14B camera-pose world model built on
**Wan I2V** and run in a distilled *causal-fast* (few-step, autoregressive
KV-cache) mode.

Unlike the API-based models (e.g. Kling), LingBot-World runs **locally from
released weights** and is driven by an explicit **camera-pose trajectory**
(c2w extrinsics + intrinsics per frame) rather than a plain text prompt. These
scripts are the thin adapter layer that turns a WBench case into the
pose-conditioned input the model expects.

> The model itself (the `wan` package and checkpoints under `model_zoo/`) is
> **not** vendored here. Clone the official LingBot-World-v2 repo and download
> the weights separately. Only the WBench adapter code lives in this folder.

## Pipeline

```
WBench case_*.json
      │  wbench_to_json.py             (action keys -> navigation dict + caption)
      ▼
  wbench_nav_158.jsonl
      │  run_wbench_fullseq_v2.py      (loads WanI2VCausal once, causal_fast mode)
      │    └─ generate_from_json_fast.py  (navigation -> per-frame poses/intrinsics + prompt)
      ▼
  outputs_v2/case_<id>.mp4
```

| File | Role |
|:---|:---|
| `wbench_to_json.py` | Convert a WBench dataset dir into a JSONL. Maps action tokens (`W/S/A/D`, `left/right/up/down`, `+` combos) to a per-turn navigation vector, and builds a single scene caption from `environment_prompt` + `character_prompt` + `perspective_prompt` (held in turn 0; later navigation turns stay empty). Standalone — no model dependency. |
| `generate_from_json_fast.py` | v1 (WanI2VFast) inference entry + the shared camera/prompt builders (`build_poses_from_json`, `build_intrinsics`, `build_prompt_with_perspective`). Imports the `wan` package. |
| `run_wbench_fullseq_v2.py` | v2 (WanI2VCausal, `infer_mode="causal_fast"`) driver. Reuses the v1 builders verbatim and feeds one CONTINUOUS accumulated trajectory per case to `generate()` in a single autoregressive rollout. Imports the `wan` package. |
| `run_rollout_v2.sh` | Resumable single-GPU driver over the full 158-case navigation split (auto-restart on transient failure, skips finished cases). |

## Prerequisites

1. Clone the official LingBot-World-v2 repo and install its requirements so the
   `wan` package is importable; download the `lingbot-world-v2-14b-causal-fast`
   weights into `model_zoo/`.
2. Copy `generate_from_json_fast.py` and `run_wbench_fullseq_v2.py` into the
   cloned repo root (they `import wan` and `from generate_from_json_fast import ...`,
   so they must run from there). `wbench_to_json.py` is standalone and can run
   anywhere.

## Usage

```bash
# 1) WBench cases -> JSONL (158 navigation cases)
python wbench_to_json.py \
    --wbench_dir /path/to/data/wbench_3.0_merged_v2 \
    --out wbench_trajectories/wbench_nav_158.jsonl

# 2) Run inference from inside the cloned LingBot-World-v2 repo
python run_wbench_fullseq_v2.py \
    --ckpt_dir model_zoo/lingbot-world-v2-14b-causal-fast \
    --jsonl_path wbench_trajectories/wbench_nav_158.jsonl \
    --output_dir wbench_trajectories/outputs_v2 \
    --size 480*832 --base_seed 42 \
    --local_attn_size 18 --sink_size 6

# or the resumable batch driver (set RUN to the repo root, GPU to a free card)
RUN=/path/to/lingbot-world-v2 GPU=0 bash run_rollout_v2.sh
```

Each output is named `case_<id>.mp4`. Symlink them back into
`work_dirs/<version>/lingbot/videos/case_<id>_combined.mp4` to evaluate with the
WBench metrics pipeline.

## Notes

- **v1 vs v2.** The two share the same input contract (poses.npy + intrinsics.npy,
  OpenCV c2w); the shipped `wasd_action.npy` is dead code in v2. The only
  functional change is `WanI2VFast` -> `WanI2VCausal(infer_mode="causal_fast")`
  plus v2 hyper-params (`chunk_size=4`, `sample_shift=10.0`,
  `local_attn_size=18`, `sink_size=6`). The camera/prompt builders are unchanged.
- **Action mapping** (verified against the WBench `navigation_trajectory`
  evaluator, NavScore ~0.99): `W=[1,0] S=[-1,0] A=[0,-1] D=[0,1]`;
  `left=yaw-1 right=yaw+1 up=pitch+1 down=pitch-1`; `+` combos sum component-wise.
- **Trajectory defaults** (`generate_from_json_fast.py`): 16 FPS,
  `TRANSLATION_SPEED_PER_FRAME=0.3`, per-turn seconds from `--secs_per_turn`
  (default 4). Adjust to match your weights/config.
- **Navigation-only.** `wbench_to_json.py` targets the 158-case navigation split;
  non-navigation interaction turns are not modeled (LingBot is camera-driven).
