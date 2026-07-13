# InfiniteWorld (infworld) integration example

Reference code for generating WBench videos with **InfiniteWorld**
(`infworld` in the WBench leaderboard), a navigation-controllable world model
that generates long videos **chunk-by-chunk** from a single first frame.

Unlike the API-based models (e.g. Kling), InfiniteWorld runs **locally from
released weights** and is driven by per-segment **navigation commands** plus a
text prompt. `json_inference.py` is the thin adapter that turns a structured
JSON case into the model's discrete move/view action indices and rolls out the
video one latent chunk at a time.

> The model itself (the `infworld` package and checkpoints) is **not** vendored
> here. Clone the official repository and download the weights separately —
> see *Prerequisites* below. Only the WBench adapter code lives in this folder.

## Files

| File | Role |
|:---|:---|
| `json_inference.py` | Inference entry point. Parses a JSON/JSONL case into a per-chunk generation schedule (`navigation -> move/view action ids`, `chunk_length -> number of model chunks`), loads VAE + T5 text encoder + DiT, and generates one MP4 per case. |

## Input format

Each case is a JSON object; `prompt` / `navigation` / `chunk_length` are dicts
keyed by segment index (`"0"`, `"1"`, ...).

```jsonc
{
  "name": "case_name",
  "image_path": "/path/to/first_frame.jpg",
  "perspective": "first_person" | "third_person" | "character_first_person",
  "prompt":       {"0": "...", "1": "..."},
  "navigation":   {"0": {"move": [fwd, right], "yaw": 0, "pitch": 0}, ...},
  "chunk_length": {"0": 2.7, "1": 5.3},   // seconds per segment
  "rewrite": false                          // reserved, ignored
}
```

- `move[0]` >0 forward / <0 back; `move[1]` >0 right / <0 left
- `yaw` >0 turn right / <0 turn left; `pitch` >0 turn up / <0 turn down
- Each segment's seconds are rounded to whole model chunks
  (`~2.667 s = 80 frames @ 30 FPS` per chunk).

## Prerequisites

1. Clone the official model repo and install its requirements so that the
   `infworld` package is importable, then download the weights (VAE, T5 text
   encoder, DiT checkpoint).
2. Copy `json_inference.py` into the cloned repo (it imports the `infworld`
   package and must run from there), or place this folder so that `infworld`
   is on `PYTHONPATH`.
3. Provide a model config YAML (default: `configs/infworld_config.yaml`),
   pointing `vae_cfg`, `text_encoder_cfg`, and `checkpoint_path` at your
   downloaded weights.

## Usage

```bash
# single case
python json_inference.py --json_path input.json

# batch (one JSON object per line)
python json_inference.py --jsonl_path inputs.jsonl

# multi-GPU (data-parallel over samples)
torchrun --nproc_per_node=4 json_inference.py --jsonl_path inputs.jsonl \
    --config configs/infworld_config.yaml \
    --output_dir ./outputs
```

Each output is named `infworld_<name>.mp4`. Symlink them back into
`work_dirs/<version>/infworld/videos/case_<id>_combined.mp4` to evaluate with
the WBench metrics pipeline.

## Notes

- **Chunk math** (`json_inference.py`): 30 FPS, temporal compression 4,
  21 latent frames/chunk -> 81 decoded frames -> 80 new frames per chunk
  (~2.667 s). Total frames `= 1 + Σ(model_chunks × 80)`.
- **Sampling defaults**: `NUM_SAMPLING_STEPS=30`, `SHIFT=7`,
  `TEXT_CFG_SCALE=5.0`, `BUCKET_CONFIG_NAME='ASPECT_RATIO_627_F64'`,
  `GLOBAL_SEED=42`. Adjust to match your weights/config.
- The prompt sent to the model is `base_prompt + navigation text +
  perspective suffix` (see `build_chunk_prompt`), so short segment prompts are
  fine — motion phrasing is added automatically per perspective.
