# WBench Model Submission Format

How to get your model onto the
[leaderboard](https://meituan-longcat.github.io/WBench/#leaderboard).

**Submission is by email.** Build the package described below, upload the videos to
a cloud drive, and send us the link. There is no automated portal yet — a person
reviews each submission.

Email **kaining.ying.cv@gmail.com** and **rensiyu07@meituan.com** with:

- **Subject:** `[WBench Submission] <display_name>`
- **Body:** model name, type (text / camera / action), org, a one-line description,
  and whether you ran the evaluation yourself (path A) or want us to (path B).
- **Attach** `meta.json` (and `report.json` for path A — both are small).
- **Cloud-drive link** to the `videos/` folder (and `turns.json`). Supported:
  **Google Drive · Baidu Netdisk (百度网盘) · HuggingFace dataset · OneDrive**.
  Keep the link live until your row is published. A HuggingFace dataset holding the
  exact structure below is preferred — we can evaluate it directly.

There are two ways to submit. **Self-evaluation is the default** — you run the
public evaluation code yourself and submit the resulting scores (plus videos for
spot-checking). If you don't have the compute/environment, you can instead submit
videos only and we evaluate for you.

| | A. Self-evaluation (default) | B. We evaluate (fallback) |
|:---|:---|:---|
| You provide | scores (`report.json`) + videos | videos only |
| Who runs the 22 metrics | you (`python main.py ...`) | us |
| Needs GPU + VLM API | yes, on your side | no |
| Turnaround | fast (no queue) | batched |

> Either way we do **not** host or run your model — only videos and/or scores are
> submitted. Generate the clips yourself; the `src/models/{text,camera,action}`
> examples show how.

## A. Self-evaluation (recommended)

1. Generate videos and run the pipeline as in the README's
   [Evaluate Your Model](../README.md#-evaluate-your-model) section
   (`python main.py --model <model_name> ...`).
2. Package the outputs as in [What you submit](#1-what-you-submit) below, and
   **include your `report.json`** (the aggregated scores) alongside `meta.json`.
3. We re-run a small random subset to confirm reproducibility, then add your row
   to the leaderboard.

## B. We evaluate for you (fallback)

Submit the same package **without** `report.json`. We validate it, run the 22
metrics on our side, and return your scores. This path is batched.

## 1. What you submit

```
<model_name>/
├── meta.json                       # model metadata (required)
├── report.json                     # your scores (required for path A, omit for B)
├── turns.json                      # per-video turn boundaries (optional, recommended)
└── videos/
    └── case_<id>_combined.mp4      # one combined clip per case
```

- `<id>` is the case's JSON `id` field (string), e.g. `1`, `e_5`, `ps_3` — **not**
  the filename. Video name is always `case_<id>_combined.mp4`.
- Videos are the full multi-turn clip (all turns concatenated in order).
- Because videos are large, **share the `videos/` folder via a cloud drive and send
  the link** rather than emailing the raw files. Supported: **Google Drive · Baidu
  Netdisk (百度网盘) · HuggingFace dataset · OneDrive**. A HuggingFace dataset that
  holds this exact structure is preferred — we can evaluate it directly.

### Which cases to cover (by model type)

| Model type | Required cases | Count |
|:---|:---|:---:|
| **Text-conditioned** | all cases | 289 |
| **Camera-conditioned** | navigation cases only | 158 |
| **Action-conditioned** | navigation cases only | 158 |

The canonical id lists are derived from `data/cases/` (a case is "navigation" if
it has at least one W/A/S/D/arrow action). Camera/action models only get the Navi
leaderboard; text models get both Full (289) and Navi.

## 2. `meta.json`

```json
{
  "model_name": "mymodel",
  "type": "text",                 // text | camera | action
  "display_name": "My Model 1.0",
  "org": "My Lab",
  "contact": "you@example.com"
}
```

## 3. `turns.json` (optional but recommended)

Several metrics are computed **per turn** (e.g. navigation_trajectory scores each
turn's trajectory; some VLM metrics read the clip segment for a given turn). A
combined clip must therefore be split back into per-turn frame ranges. Different
models allot a **different, non-uniform** number of frames per turn, so we cannot
infer the boundaries reliably — you provide them:

```json
{
  "fps": 24,
  "cases": {
    "1":   { "turn_frames": [0, 57, 97, 137, 177] },
    "e_5": { "turn_frames": [0, 60, 120, 180] }
  }
}
```

- `turn_frames` lists the **start frame of each turn plus a final sentinel**, so
  turn *i* spans frames `[turn_frames[i], turn_frames[i+1])`.
- A case with **N turns** has **N+1** boundaries.
- Boundaries must be strictly increasing, start at `0`, and end at `≤` the video's
  actual frame count.

**If `turns.json` is omitted**, each clip is split **uniformly** by turn count
(`frames_per_turn = total_frames / num_turns`). This is fine if your model emits
equal-length turns, but if your turns are unequal (common for autoregressive
models with a longer first turn) uniform splitting misaligns the boundaries and
**per-turn metrics will be understated**. Whole-clip metrics (video quality,
segment continuity, geometric/photometric consistency, physical plausibility) are
unaffected either way.

> Tip: the `case_to_poses` / `case_to_actions` helpers in `src/models/{camera,action}`
> expose each turn's `chunk_length`; combined with your model's frames-per-turn you
> can generate `turns.json` programmatically instead of by hand.

## 4. Validation

Before evaluating we run `validate_submission.py`, which checks:

- `meta.json` present with a valid `type`.
- Video set covers exactly the required case ids for that type (missing / extra
  cases are reported).
- Each video decodes and has a sane frame count and resolution.
- If `turns.json` is present: every required case has an entry, boundary count
  equals `turns + 1`, boundaries are monotonic and within the video length, and
  `fps` matches the video.

A submission that fails validation is returned with the issues listed — we do not
spend evaluation compute on it.

## 5. What you get back

- **Path A:** confirmation that your `report.json` reproduces on our subset check,
  and a leaderboard row. If the subset disagrees beyond tolerance we flag it and
  fall back to a full re-evaluation.
- **Path B:** a `report.json` / `report.md` with per-metric scores, the 5 dimension
  scores, and the overall average, plus a note on how turns were split
  (`turn_split: provided` or `turn_split: uniform (no turns.json)`), and a
  leaderboard row.
