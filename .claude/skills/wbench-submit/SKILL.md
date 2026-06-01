---
name: wbench-submit
description: Package and submit a model's results to WBench (leaderboard). Use when the user asks to prepare a submission, build the meta.json/turns.json package, or upload videos to the WBench-examples HF dataset (e.g. "package kling3 for submission", "生成 turns.json", "上传到 huggingface"). Produces the work_dirs/<model>/{meta.json,turns.json,videos/} bundle.
---

# WBench Submission Packaging

Assemble a submission bundle and (optionally) push it to a HuggingFace dataset.
Full spec: [`docs/SUBMISSION.md`](../../docs/SUBMISSION.md).

## Bundle layout

```
<model_name>/
├── meta.json                    # required
├── report.json                  # required for path A (self-eval), omit for path B
├── turns.json                   # optional but recommended (non-uniform turns)
└── videos/
    └── case_<id>_combined.mp4
```

`<id>` is the case's JSON `id` field (e.g. `1`, `e_5`, `ps_3`), never the filename.

## Two submission paths

- **A — self-evaluation (default):** include `report.json` (run the `wbench-evaluate`
  skill first). We re-run a random subset to confirm reproducibility.
- **B — we evaluate (fallback):** omit `report.json`, submit videos only; we run the
  22 metrics. Batched.

## Required case coverage

| Type | Cases | Count |
|:---|:---|:---:|
| text | all | 289 |
| camera / action | navigation only | 158 |

## 1. meta.json

```json
{
  "model_name": "mymodel",
  "type": "text",                 // text | camera | action
  "display_name": "My Model 1.0",
  "org": "My Lab",
  "sampled_by": "...",            // who generated the videos
  "contact": "you@example.com",
  "num_videos": 289,
  "split": "full"                 // full | navi
}
```

## 2. turns.json (recommended)

Per-turn metrics need per-turn frame ranges. Models allot a **non-uniform** number
of frames per turn, so provide the boundaries explicitly:

```json
{
  "fps": 24,
  "cases": {
    "1":   { "turn_frames": [0, 57, 97, 137, 177] },
    "e_5": { "turn_frames": [0, 60, 120, 180] }
  }
}
```

- `turn_frames` = start frame of each turn **plus a final sentinel**; turn *i* spans
  `[turn_frames[i], turn_frames[i+1])`.
- N turns → N+1 boundaries, strictly increasing, start at 0, end ≤ actual frame count.
- **Omitting it** → uniform split (`total_frames / n_turns`). Fine for equal-length
  turns (kling), but understates per-turn metrics for non-uniform turns (most
  autoregressive world models).

Generate programmatically from your model's frames-per-turn rule + the per-turn
`chunk_length` exposed by `case_to_poses` / `case_to_actions` in
`src/models/{camera,action}`. Validate before shipping:

```python
import cv2, json
turns = json.load(open("work_dirs/<model>/turns.json"))
for cid, t in turns["cases"].items():
    tf = t["turn_frames"]
    assert tf[0] == 0 and tf == sorted(tf) and len(set(tf)) == len(tf), cid
    nf = int(cv2.VideoCapture(f"work_dirs/<model>/videos/case_{cid}_combined.mp4").get(7))
    assert tf[-1] <= nf, f"{cid}: sentinel {tf[-1]} > {nf} frames"
print("turns.json OK")
```

## 3. Upload to HuggingFace (private dataset)

The reference bundles live under `meituan-longcat/WBench-examples` (folders
`hyworld1.5/`, `kling3/`). If your network needs a proxy to reach huggingface.co,
export `https_proxy` / `http_proxy` first.

```bash
# export https_proxy=http://<your-proxy>:<port> http_proxy=http://<your-proxy>:<port>
export HF_TOKEN=<write-scoped token>     # from https://huggingface.co/settings/tokens

REPO=meituan-longcat/WBench-examples

# create once (skip if it exists)
hf repo create "$REPO" --repo-type dataset --private

# upload a bundle (local dir → repo subfolder). Resumable: re-run to retry.
hf upload "$REPO" work_dirs/<model> <model> --repo-type dataset
```

Large bundles (multi-GB) — run in the background and watch the log:

```bash
mkdir -p logs
nohup bash -c 'export HF_TOKEN=<token>; \
  hf upload meituan-longcat/WBench-examples work_dirs/<model> <model> --repo-type dataset' \
  > logs/hf_upload_<model>.log 2>&1 &
```

## Gotchas

- `meta.json` `model_name` must match the bundle/repo folder name (e.g. `kling3`,
  `hyworld1.5`).
- mp4 files are auto-tracked as LFS by `hf upload` — no manual `git lfs track`.
- `hf upload` is resumable: an interrupted upload re-runs and skips files already
  pushed.
- A HuggingFace dataset link with this exact structure can be submitted **instead**
  of raw files (videos are large).
- `docs/SUBMISSION.md` mentions a `validate_submission.py` — it is not yet in the
  repo; validate `turns.json` with the snippet above for now.
