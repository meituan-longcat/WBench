# Qwen3.8 Judge (beta)

WBench can score its VLM-judged metrics with a self-hosted **Qwen3.8-27B** instead of the
Doubao API. The prompts, rubrics, temperature and score formulas are the same for both
judges, but the two judges' scores are not interchangeable, so compare models only under
one judge. The default judge for the main leaderboard is unchanged.

## 1. Serve the model

Tested with SGLang 0.5.10, PyTorch 2.9.1 (CUDA 12.8) and Transformers 5.3.0 on one 80 GB GPU
per server.

```bash
python -m sglang.launch_server \
  --model-path <path-to>/Qwen3.8-27B --served-model-name Qwen/Qwen3.8-27B \
  --host 127.0.0.1 --port 18838 --dtype bfloat16 --context-length 65536 \
  --max-running-requests 2 --mem-fraction-static 0.82 --disable-cuda-graph \
  --attention-backend triton --mm-attention-backend sdpa \
  --reasoning-parser qwen3 --disable-radix-cache
```

The server holds about 66 GB of GPU memory. If another job takes memory on the same GPU, the
server can exit without an error in its log, so give it a dedicated GPU.

## 2. Point WBench at it

```bash
export VLM_MODEL_NAME="Qwen/Qwen3.8-27B"
export VLM_API_URL="http://127.0.0.1:18838/v1/chat/completions"
# No VLM_API_KEY is needed for a self-hosted endpoint.
python main.py --model my_model --phase vlm
```

## 3. What changes with this judge

Request settings (`src/metrics/vlm/vlm_evaluator.py`):

| Setting | Value |
|---|---|
| Thinking | disabled through the chat template (`enable_thinking: false`) |
| Temperature | 0.1, same as the API judges |
| Output budget | `max_completion_tokens` 2048, `min_tokens` 8 |

With the 300-token budget used for the API judges, Qwen sometimes returned empty or truncated
replies, so the budget is larger.

Score parsing:

- Causal Fidelity accepts only explicit scores: a `Score: N` marker, a JSON `score`
  field, an `Answer: N` label, or a reply whose first line is the digit. The former
  fallback, "first digit 0-3 anywhere in the text", was removed. It could pick up frame
  numbers or the rubric text. For replies that contain a `Score: N` marker, scores are
  identical to the old parser.
- Scene and Subject Adherence parse the JSON reply as before.

Constrained re-ask (Qwen only):

- A reply without a valid score is asked again once, with SGLang constrained decoding that
  enforces the output format the prompt already requests:
  - `Reason: ...\nScore: 0-3` for Causal Fidelity.
  - A JSON object with the required keys and value ranges for Scene and Subject.
- The prompt is not changed. Replies that were already valid are kept as they are.
- Every result records whether the re-ask was used:
  - `params.constrained_fallback` for Scene and Subject.
  - `track1/track2[].constrained_fallback` for Causal Fidelity.

## 4. Reference run (2026-10-21)

The ten top Navi models plus one new submission were re-judged; 3,102 / 3,102 judgments are
valid. The constrained re-ask was needed for 4.4% of results:

| Metric | Results that used the re-ask |
|---|---|
| Causal Fidelity | 16% |
| Scene Adherence | 2% |
| Subject Adherence | 2% |

On already-valid cases, constrained and plain replies agreed on 20/20 Scene and Subject
scores. Causal Fidelity varies noticeably between repeated runs with either decoding, so
differences of about 0.5 points in the overall average are within noise.

Known limitations:

- Subject Adherence scores cluster at 96–100, so it separates models poorly under this judge.
- Causal Fidelity has not yet been checked against human judgments.
