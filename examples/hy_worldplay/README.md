# HY-WorldPlay (HunyuanVideo-1.5) integration example

Reference code for generating WBench videos with **HY-WorldPlay**, the
navigation-controllable world model built on **HunyuanVideo-1.5**
(referred to as `hunyuan` / `hy1.5` in the WBench leaderboard).

Unlike the API-based models (e.g. Kling), HY-WorldPlay runs **locally from
released weights** and is driven by an explicit **camera-pose trajectory**
rather than a plain text prompt. These scripts are the thin adapter layer that
turns a WBench case into the pose-conditioned input the model expects.

> The model itself (the `hyvideo` package and checkpoints) is **not** vendored
> here. Clone the official repository and download the weights separately —
> see *Prerequisites* below. Only the WBench adapter code lives in this folder.

## Pipeline

```
WBench case_*.json
      │  convert_cases_to_jsonl.py      (action keys -> navigation dict + prompt)
      ▼
  samples.jsonl
      │  generate_navigation.py         (loads HunyuanVideo-1.5 pipeline once)
      │    └─ navigation_to_poses.py    (navigation dict -> camera extrinsics/intrinsics)
      ▼
  outputs/case_<id>.mp4
```

| File | Role |
|:---|:---|
| `convert_cases_to_jsonl.py` | Convert a WBench `cases/` dir into `samples.jsonl`. Maps action keys (`W/S/A/D`, arrows, `+` combos) to a navigation vector and builds the per-segment prompt from the case `settings`. |
| `navigation_to_poses.py` | Pure-numpy conversion of a navigation dict into a per-latent camera-pose JSON. First-person uses a local trajectory; third-person uses an orbit trajectory. |
| `generate_navigation.py` | Batch inference entry point. Loads the `HunyuanVideo_1_5_Pipeline` once and iterates over the JSONL, saving one MP4 per case. |

## Prerequisites

1. Clone the official model repo and install its requirements:
   ```bash
   git clone https://github.com/Tencent-Hunyuan/HY-WorldPlay.git
   cd HY-WorldPlay && pip install -r requirements.txt
   ```
2. Download the weights (`HunyuanVideo-1.5` base + `HY-WorldPlay` action
   checkpoints) following that repo's instructions.
3. Copy `generate_navigation.py` and `navigation_to_poses.py` from this folder
   into the cloned `HY-WorldPlay/` directory (they import its `hyvideo`
   package and must run from there). `convert_cases_to_jsonl.py` is standalone
   and can run from anywhere.

## Usage

```bash
# 1) WBench cases -> JSONL (navigation cases only)
python convert_cases_to_jsonl.py /path/to/data/wbench_3.0_merged_v2 \
    --nav_only --output samples.jsonl

# 2) Run inference from inside the cloned HY-WorldPlay repo
torchrun --nproc_per_node=1 generate_navigation.py \
    --jsonl_path samples.jsonl \
    --output_dir ./outputs \
    --model_path models/HunyuanVideo-1.5 \
    --action_ckpt models/HY-WorldPlay/ar_distilled_action_model/model.safetensors
```

Each output is named `case_<id>.mp4`. Symlink them back into
`work_dirs/<version>/hunyuan/videos/case_<id>_combined.mp4` to evaluate with
the WBench metrics pipeline.

## Notes

- **Navigation-only.** Non-navigation interaction turns (event edits, subject
  actions) are dropped when `--nav_only` is set, since HY-WorldPlay is driven
  by camera trajectories. Drop the flag to keep all turns (non-nav turns get a
  stop action).
- **Defaults** (`navigation_to_poses.py`): 24 FPS, temporal compression 4 (6
  latents/sec), forward speed `0.08`, yaw/pitch `3°` per step. Adjust to match
  your weights/config.
- These scripts target HunyuanVideo-1.5 at 480p. See the official repo for
  resolution/model-type (`ar`/`bi`) options.
