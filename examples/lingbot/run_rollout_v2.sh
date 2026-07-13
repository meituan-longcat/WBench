#!/usr/bin/env bash
set -uo pipefail
# ─────────────────────────────────────────────────────────────────────────────
# LingBot-World-v2 (14B causal-fast) — full 158-case WBench navigation rollout.
# Single-GPU, model-native sliding-window KV cache (v2 official causal-fast:
# local_attn_size=18, sink_size=6). Resumable + auto-restart on transient death.
# ─────────────────────────────────────────────────────────────────────────────
# RUN must point at the cloned LingBot-World-v2 repo (where `wan/` and this
# script live after you copy the adapter files in). Override with env vars.
RUN=${RUN:-$(cd "$(dirname "$0")" && pwd)}
GPU=${GPU:-0}
OUT=${OUT:-$RUN/wbench_trajectories/outputs_v2}
LOG=${LOG:-$RUN/wbench_trajectories/rollout_v2.log}

# Activate the model's python env before running (edit to match your setup).
# source /path/to/activate_lyra2.sh >/dev/null 2>&1
export PYTHONNOUSERSITE=1; unset PYTHONPATH
export CUDA_VISIBLE_DEVICES=$GPU
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd "$RUN"

mkdir -p "$OUT"
stamp(){ echo "[$(date '+%F %T')] $*"; }

attempt=0
while true; do
  attempt=$((attempt+1))
  done_n=$(ls "$OUT"/case_*.mp4 2>/dev/null | wc -l)
  stamp "=== attempt $attempt — $done_n/158 mp4s present — launching driver ===" | tee -a "$LOG"
  if [ "$done_n" -ge 158 ]; then stamp "ALL 158 DONE." | tee -a "$LOG"; break; fi

  python run_wbench_fullseq_v2.py \
      --ckpt_dir model_zoo/lingbot-world-v2-14b-causal-fast \
      --jsonl_path wbench_trajectories/wbench_nav_158.jsonl \
      --output_dir "$OUT" \
      --size 480*832 --base_seed 42 \
      --local_attn_size 18 --sink_size 6 \
      >> "$LOG" 2>&1
  rc=$?
  done_n=$(ls "$OUT"/case_*.mp4 2>/dev/null | wc -l)
  stamp "driver exited rc=$rc — $done_n/158 mp4s present" | tee -a "$LOG"
  if [ "$done_n" -ge 158 ]; then stamp "ALL 158 DONE." | tee -a "$LOG"; break; fi
  if [ "$attempt" -ge 20 ]; then stamp "GIVING UP after $attempt attempts." | tee -a "$LOG"; break; fi
  stamp "restarting in 15s (resume skips finished cases)..." | tee -a "$LOG"; sleep 15
done
