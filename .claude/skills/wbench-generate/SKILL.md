---
name: wbench-generate
description: Generate WBench videos for a model. Use when the user asks to generate / produce videos for a registered model (e.g. "generate kling videos", "用 wan 生成全部 case", "跑 camera_preview 的 navi case"). Drives generate.py over data/cases and writes work_dirs/<model>/videos/case_<id>_combined.mp4.
---

# WBench Video Generation

Run a registered model over the dataset cases and produce one combined multi-turn
clip per case at `work_dirs/<model>/videos/case_<id>_combined.mp4`.

Entry point: `generate.py` (repo root). Paths are relative to the repo root, so
`cd` into the checkout first.

## Registered models

`wan`, `kling`, `seedance` (text-conditioned), `camera_preview`, `action_preview`
(reference camera/action demos). List them anytime:

```bash
python -c "from src.models import list_models; print(list_models())"
```

To add your own, `register_model(name, cls)` in `src/models/__init__.py`; subclass
`ConditionedVideoModel` (camera/action) or `BaseVideoModel` (text). See
`src/models/{camera,action}/example_model.py`.

## Which cases to cover (by model type)

| Type | Cases | Count |
|:---|:---|:---:|
| text | all | 289 |
| camera / action | navigation only | 158 |

A case is "navigation" if it has ≥1 W/A/S/D/arrow action. Camera/action models
**must** be restricted to the 158 navi cases — passing all 289 wastes compute and
produces videos for cases the model can't be scored on.

## Workflow

### 1. Pick GPU (if the model needs one) and set API creds (text models)

Text models call a video API:
```bash
export VIDEO_API_URL="https://your-video-api.com"
export VIDEO_API_KEY="your-key"
```

### 2. Smoke test on one case first

```bash
python generate.py --model <model> --cases data/cases/case_1.json
```
Confirm `work_dirs/<model>/videos/case_1_combined.mp4` exists and plays before
launching the full run.

### 3. Full run (background for anything > a few minutes)

```bash
mkdir -p logs
nohup python generate.py --model <model> --resume \
  > logs/generate_<model>.log 2>&1 &
```

- `--resume` skips cases that already have a video — safe to re-run after an
  interruption.
- `--limit N` caps the number of cases (quick sanity passes).
- `--cases f1.json f2.json ...` restricts to specific cases.
- For **camera/action models, pass only the navi cases** via `--cases` (glob the
  navi id list from `data/cases/`).

### 4. Verify output

```bash
ls work_dirs/<model>/videos/ | wc -l          # expected count (289 or 158)
python -c "import cv2,glob; \
  [print(p, int(cv2.VideoCapture(p).get(7))) for p in glob.glob('work_dirs/<model>/videos/*.mp4')[:3]]"
```

## Gotchas

- The combined clip must contain **all turns concatenated in order** — the
  multi-turn logic (build prompt → infer → take last frame → next turn) is handled
  by `generate_multi_turn`; don't emit per-turn files.
- Video filename uses the JSON `id` field, not the source filename (e.g.
  `case_210_scratch.json` whose JSON id is `211` → `case_211_combined.mp4`).
- Frames-per-turn differ per model and matter for submission `turns.json` — see the
  `wbench-submit` skill.
