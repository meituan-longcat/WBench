---
name: wbench-evaluate
description: Run the WBench 22-metric evaluation pipeline on a model's videos. Use when the user asks to evaluate / score a model, run metrics, or produce a report (e.g. "evaluate kling3", "跑一下 hyworld1.5 的评测", "只算 video_quality"). Drives main.py (precompute → gpu → vlm → report) over work_dirs/<model>/videos.
---

# WBench Evaluation Pipeline

Score one model across 22 metrics / 5 dimensions. Reads
`work_dirs/<model>/videos/case_<id>_combined.mp4`, writes per-metric per-case JSON
to `work_dirs/<model>/evaluation/<metric>/case_<id>.json` and an aggregated
`work_dirs/<model>/evaluation/report.json`.

Entry point: `main.py` (repo root). `cd` into the checkout first.

## Three phases (run in order; `--phase all` does all four)

| Phase | What | Needs |
|:---|:---|:---|
| `precompute` | SAM2 masks + DA3 depth + MegaSAM poses | GPU |
| `gpu` | per-metric GPU compute (quality, consistency, navigation, spatial) | GPU |
| `vlm` | API metrics (scene/subject adherence, causal fidelity, interaction) | VLM API |
| `report` | merge per-metric JSON → `report.json` (Full + Navi splits) | CPU |

`precompute` must finish before `gpu`/`vlm` — the GPU metrics depend on the masks,
depth and poses it produces.

## Workflow

### 1. Confirm the videos are in place

```bash
ls work_dirs/<model>/videos/*.mp4 | wc -l
```
The pipeline auto-detects navi vs non-navi per case (`is_navi_case`) and only runs
navi-only metrics (navigation_trajectory, spatial_consistency, scene/subject
adherence) on applicable cases — a navi-only model (158 videos) is fine, missing
non-navi cases are simply skipped, not errored.

### 2. Pick free GPUs

```bash
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
```
Pass them with `--gpus 0,1,2,3` (default: all visible GPUs).

### 3. Precompute (background, slowest phase)

```bash
mkdir -p logs
nohup python main.py --model <model> --phase precompute --gpus 0,1,2,3 \
  > logs/eval_<model>_precompute.log 2>&1 &
```

### 4. GPU metrics

```bash
nohup python main.py --model <model> --phase gpu --gpus 0,1,2,3 \
  > logs/eval_<model>_gpu.log 2>&1 &
```
Scope with `--metrics`: dimension names (`quality`, `consistency`, `interaction`,
`setting`, `physical`) or individual metrics (`--metrics aesthetic_quality,segment_continuity`).
Re-running skips cases whose `case_<id>.json` already has a score (`--phase gpu`
is incremental). `visual_plausibility` runs separately via
`tools/run_visual_plausibility.py` (needs the `wbench-vp` env).

### 5. VLM metrics

```bash
nohup python main.py --model <model> --phase vlm --vlm_workers 8 \
  > logs/eval_<model>_vlm.log 2>&1 &
```

### 6. Report

```bash
python main.py --model <model> --phase report
```
Prints a Full/Navi table and writes `work_dirs/<model>/evaluation/report.json`.

## Single-video debug

```bash
python main.py --video work_dirs/<model>/videos/case_1_combined.mp4 \
  --case data/cases/case_1.json
```

## Gotchas

- **Conda env**: most metrics use the main env; `visual_plausibility` needs
  `wbench-vp` (vLLM). Use absolute python paths — `conda activate` doesn't persist
  in subshells. See `project-conda-envs` memory / repo CLAUDE.md.
- **Turn splitting is uniform**: per-turn VLM metrics split the clip by
  `total_frames // n_turns`; the pipeline does **not** read `turns.json`. For models
  with equal-length turns (e.g. kling) this is exact; for non-uniform turn lengths
  it misaligns per-turn metrics. Whole-clip metrics are unaffected.
- **CPU thrash**: GPU workers already cap threads (OMP/MKL/torch = 4). Don't launch
  multiple models in parallel — models are meant to run serially.
- Failed cases write `{"score": null, "error": ...}` and are counted in
  `report.json`'s `n_errors`; they don't abort the run.
