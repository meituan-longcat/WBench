<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/longcat-combine-dark.svg">
    <img src="assets/longcat-combine.svg" width="250">
  </picture>
</div>

<div align="center">
  <h1>WBench: A Comprehensive Multi-turn Benchmark for<br>Interactive Video World Model Evaluation</h1>
</div>

<div align="center">

**Kaining Ying**<sup><img src="assets/icon/fudan.svg" height="10">&ast;</sup>, **Hengrui Hu**<sup><img src="assets/icon/fudan.svg" height="10">&ast;</sup>, **Siyu Ren**<sup><img src="assets/icon/longcat-color.png" height="10"></sup>, Jiamu Li<sup><img src="assets/icon/longcat-color.png" height="10"></sup>, Fengjiao Chen<sup><img src="assets/icon/longcat-color.png" height="10"></sup>,<br>Ziwen Wang<sup><img src="assets/icon/longcat-color.png" height="10"></sup>, Xuezhi Cao<sup><img src="assets/icon/longcat-color.png" height="10"></sup>, Xunliang Cai<sup><img src="assets/icon/longcat-color.png" height="10"></sup>, Henghui Ding<sup><img src="assets/icon/fudan.svg" height="10"></sup> <sup>[✉️](mailto:hhding@fudan.edu.cn)</sup>
<br>
<sup><img src="assets/icon/fudan.svg" height="12"></sup> Fudan University &nbsp;&nbsp; <sup><img src="assets/icon/longcat-color.png" height="12"></sup> Meituan LongCat Team

</div>

<div align="center">

[![Homepage](https://img.shields.io/badge/Homepage-blue?style=for-the-badge&logo=google-chrome&logoColor=white)](https://meituan-longcat.github.io/WBench/)
[![Paper](https://img.shields.io/badge/Paper-red?style=for-the-badge&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2605.25874)
[![HF Daily Paper](https://img.shields.io/badge/Daily_Paper_%232-FFD21E?style=for-the-badge&logo=huggingface&logoColor=white&color=FF9D00)](https://huggingface.co/papers/2605.25874)
[![Leaderboard](https://img.shields.io/badge/Leaderboard-32CD32?style=for-the-badge&logo=google-chrome&logoColor=white)](https://meituan-longcat.github.io/WBench/#leaderboard)
[![Datasets](https://img.shields.io/badge/Datasets-4285F4?style=for-the-badge&logo=huggingface&logoColor=white)](https://huggingface.co/datasets/meituan-longcat/WBench)
[![Weights](https://img.shields.io/badge/Weights-FF9D00?style=for-the-badge&logo=huggingface&logoColor=white)](https://huggingface.co/meituan-longcat/WBench-weights)
[![Examples](https://img.shields.io/badge/Examples-FF9D00?style=for-the-badge&logo=huggingface&logoColor=white)](https://huggingface.co/datasets/meituan-longcat/WBench-examples)
[![Examples (Open)](https://img.shields.io/badge/Examples_2_(Open)-1BC47D?style=for-the-badge&logo=huggingface&logoColor=white)](https://huggingface.co/datasets/Kaining/WBench-examples-open)
[![ModelScope](https://img.shields.io/badge/ModelScope-6B4EFF?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyBmaWxsPSJ3aGl0ZSIgZmlsbC1ydWxlPSJldmVub2RkIiBoZWlnaHQ9IjFlbSIgc3R5bGU9ImZsZXg6bm9uZTtsaW5lLWhlaWdodDoxIiB2aWV3Qm94PSIwIDAgMjQgMjQiIHdpZHRoPSIxZW0iIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHRpdGxlPk1vZGVsU2NvcGU8L3RpdGxlPjxwYXRoIGQ9Ik0yLjY2NyA1LjNIOHYyLjY2N0g1LjMzM3YyLjY2NkgyLjY2N1Y4LjQ2N0guNXYyLjE2NmgyLjE2N1YxMy4zSDBWNy45NjdoMi42NjdWNS4zek0yLjY2NyAxMy4zaDIuNjY2djIuNjY3SDh2Mi42NjZIMi42NjdWMTMuM3pNOCAxMC42MzNoMi42NjdWMTMuM0g4di0yLjY2N3pNMTMuMzMzIDEzLjN2Mi42NjdoLTIuNjY2VjEzLjNoMi42NjZ6TTEzLjMzMyAxMy4zdi0yLjY2N0gxNlYxMy4zaC0yLjY2N3oiPjwvcGF0aD48cGF0aCBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGQ9Ik0yMS4zMzMgMTMuM3YtMi42NjdoLTIuNjY2VjcuOTY3SDE2VjUuM2g1LjMzM3YyLjY2N0gyNFYxMy4zaC0yLjY2N3ptMC0yLjY2N0gyMy41VjguNDY3aC0yLjE2N3YyLjE2NnoiPjwvcGF0aD48cGF0aCBkPSJNMjEuMzMzIDEzLjN2NS4zMzNIMTZ2LTIuNjY2aDIuNjY3VjEzLjNoMi42NjZ6Ij48L3BhdGg+PC9zdmc+&logoColor=white)](https://modelscope.cn/datasets/meituan-longcat/WBench)
[![中文解读](https://img.shields.io/badge/中文解读-07C160?style=for-the-badge&logo=wechat&logoColor=white)](https://mp.weixin.qq.com/s/br3RlOBGtReolLZc5YW2HA)
[![WeChat Live](https://img.shields.io/badge/WeChat_Live-07C160?style=for-the-badge&logo=wechat&logoColor=white)](https://weixin.qq.com/sph/Aue3nWCWCx)
[![TWITTER POST](https://img.shields.io/badge/TWITTER_POST-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/Meituan_LongCat/status/2059658634829996047)
[![WeChat Group](https://img.shields.io/badge/WeChat_Group-07C160?style=for-the-badge&logo=wechat&logoColor=white)](assets/wx_qr.png)

</div>

<div align="center">
  <i>Is Your World Model an All-Round Player?</i>
</div>

---

<div align="center">
  <img src="assets/teaser.png" width="90%">
</div>

<p align="center" style="color: grey;">
<b>TL;DR</b> — WBench evaluates 35 video world models across 5 dimensions and 22 metrics.
</p>

<div align="center">
  <img src="assets/qr_code.png" width="300">
</div>

## 📢 News

- **[2026/08/28]** 🆕 [JoyAI-Echo-1.5 (WM)](https://echo-team-joy-future-academy-jd.github.io/Echo-1.5-Page/wm/) (`flash`, `4-step`): Navi **81.0**, #2 · thanks [@franklinz233](https://github.com/franklinz233).
- **[2026/08/27]** 🆕 [Helios](https://pku-yuangroup.github.io/Helios-Page) ([Distilled](https://huggingface.co/BestWishYsh/Helios-Distilled)): Full **69.7**, #9; Navi **74.3**, #22 · thanks [@SHYuanBest](https://github.com/SHYuanBest).
- **[2026/08/26]** 🆕 [Zing-0.5](https://zing.loopit.me/): Navi **81.0**, #3 · thanks [@seedleap](https://github.com/seedleap).
- **[2026/08/24]** 🆕 Added [JoyAI-Echo-1.5 (WM)](https://echo-team-joy-future-academy-jd.github.io/Echo-1.5-Page/wm/): **81.6**, #1 · thanks [@franklinz233](https://github.com/franklinz233).
- **[2026/08/16]** 🔄 Updated [AlayaWorld](https://github.com/AlayaLab/AlayaWorld) final-v4: **76.3**, #12 · thanks [@nevermorelch](https://github.com/nevermorelch).
- **[2026/08/16]** 🔄 Updated [HiDream-O1-World](https://hidream.ai/) 08/14: **80.9**, #1 · thanks [@Spark001](https://github.com/Spark001).
- **[2026/08/14]** 🆕 Added [Alaya-EVOKE](https://evoke-world.github.io/Evoke) · thanks [@SII-YuanyangYin](https://github.com/SII-YuanyangYin).
- **[2026/07/29]** 🆕 Added [HiDream-O1-World](https://hidream.org/zh) (camera-conditioned).
- **[2026/07/29]** 🆕 Added [AlayaWorld](https://github.com/AlayaLab/AlayaWorld) (Alaya Lab, camera-conditioned) to the leaderboard (now 29 models).
- **[2026/07/14]** 🆕 Added [ABot-World](https://github.com/amap-cvlab/ABot-World) (Amap, action-conditioned) to the leaderboard (now 28 models).
- **[2026/07/12]** 🆕 Added [LingBot-World (fast v2)](https://github.com/Robbyant/lingbot-world-v2) (camera) to the leaderboard (now 27 models).
- **[2026/07/12]** 🆕 Added [Cosmos3-Super & Cosmos3-Nano](https://github.com/nvidia-cosmos) (text) to the leaderboard (now 26 models).
- **[2026/06/18]** 🆕 Added [DreamX-World (5B AR)](https://github.com/AMAP-ML/DreamX-World) to the leaderboard (now 24 models).
- **[2026/06/17]** 🆕 Added [LingBot-World (fast)](https://github.com/robbyant/lingbot-world) to the leaderboard (now 23 models).
- **[2026/06/16]** 🔌 Open-sourced the [HY-World 1.5 integration example](examples/hy_worldplay).
- **[2026/06/16]** 🆕 Added 2 camera-controlled world models — [Lyra 2.0](https://research.nvidia.com/labs/sil/projects/lyra2/) & [SANA-WM](https://nvlabs.github.io/Sana/WM/) (4-step AR).
- **[2026/06/10]** 🧭 Added [HY-World 1.5 pose exports](https://huggingface.co/datasets/meituan-longcat/WBench-examples/tree/main/hyworld1.5/poses) to [WBench-examples](https://huggingface.co/datasets/meituan-longcat/WBench-examples).
- **[2026/06/01]** WBench is now an official benchmark on [Hugging Face](https://huggingface.co/datasets/meituan-longcat/WBench) 🤗 (navi & full tasks)!
- **[2026/06/01]** 📦 Released [WBench-examples](https://huggingface.co/datasets/meituan-longcat/WBench-examples): ready-to-eval videos from HY-World 1.5 & Kling 3.0.
- **[2026/06/01]** 🎮 Added [camera- & action-conditioned examples](#-implement-your-model) + web automation (Genie3, Happy Oyster).
- **[2026/06/01]** Added [Claude Code skills](#-claude-code-skills) 🤖 for generation, evaluation & submission.
- **[2026/05/29]** Paper ranked **#2** 🏅 on [Hugging Face Daily Papers](https://huggingface.co/papers/2605.25874)!
- **[2026/05/28]** Paper now available on [arXiv](https://arxiv.org/abs/2605.25874) 📄!
- **[2026/05/28]** [Homepage](https://meituan-longcat.github.io/WBench/) with interactive [leaderboard](https://meituan-longcat.github.io/WBench/#leaderboard) & [dataset gallery](https://meituan-longcat.github.io/WBench/#gallery) is live! 🌐
- **[2026/05/28]** 🚀 Released the full [WBench dataset](https://huggingface.co/datasets/meituan-longcat/WBench), [evaluation code](https://github.com/meituan-longcat/WBench) & [model weights](https://huggingface.co/meituan-longcat/WBench-weights).

## ✨ Contributions

- A **comprehensive evaluation framework** with 289 cases, 1,058 interaction turns, covering 4 interaction types (navigation, subject action, event editing, perspective switching) across diverse scenes and perspectives.
- A **unified navigation protocol** that bridges text, 6-DoF camera pose, and discrete-action interfaces, enabling fair comparison across model families.
- **22 automatic metrics** spanning 5 complementary dimensions, validated against human judgments, ensuring reliable automatic evaluation at scale.
- **Systematic diagnosis of 35 models** revealing that current world models have not yet unified high-fidelity rendering with reliable controllability, consistency, and physics compliance.

## 🏆 Leaderboard

The live leaderboard is maintained on the [WBench homepage](https://meituan-longcat.github.io/WBench/#leaderboard), with current scores, detailed metrics, model metadata, and filters.

The leaderboard marks **Open Source** entries when both the inference code and the evaluated checkpoint are publicly available. API, web-only, and unreleased entries remain identified by their access type.

## 🚀 Quick Start

```bash
# Install
git clone --recursive https://github.com/meituan-longcat/WBench.git
cd WBench

# If you already cloned without submodules
git submodule update --init --recursive

# Download data and weights
pip install huggingface_hub
hf download meituan-longcat/WBench --repo-type dataset --local-dir data/ --exclude "splits/*"
hf download meituan-longcat/WBench-weights --local-dir weights/

# Environment 1: wbench-main (all metrics except visual_plausibility)
# 2nd arg = PyTorch's CUDA build — match it to YOUR system (check via `nvcc --version`):
#   cu124 → CUDA 12.x    cu121 → CUDA 12.1    cu118 → CUDA 11.8
# Always pass it explicitly: if omitted, auto-detection falls back to cu118 when nvcc
# isn't on PATH, which makes the MegaSAM CUDA extensions fail to build on CUDA-12 machines.
bash tools/install.sh wbench-main cu124
conda activate wbench-main
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH



# Verify
conda activate wbench-main
python tools/verify_install.py

# Run evaluation (auto multi-GPU)
python main.py --model your_model
```

See [docs/installation.md](docs/installation.md) for detailed setup instructions.

## 🎮 Evaluate Your Model

Set environment variables for VLM metrics first (we use [Doubao-Seed-2.0-lite](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-2-0-lite) via [Volcengine ARK](https://www.volcengine.com/docs/82379/1099475)):
```bash
export VLM_API_KEY="<your-ark-api-key>"
# Optional (defaults shown):
# export VLM_API_URL="https://ark.cn-beijing.volces.com/api/v3"
# export VLM_MODEL_NAME="doubao-seed-2-0-lite-260215"
```

1. Generate multi-turn videos → place in `work_dirs/<model>/videos/case_{id}_combined.mp4`
2. Run the 3-phase pipeline:

```bash
# Full pipeline (precompute → GPU metrics → VLM metrics → report)
python main.py --model my_model --gpus 0,1,2,3,4,5,6,7

# Or run phases independently:
python main.py --model my_model --phase precompute    # SAM2 + DA3 + MegaSAM
python main.py --model my_model --phase gpu           # GPU metrics (per-metric)
python main.py --model my_model --phase vlm           # VLM metrics (API)
python main.py --model my_model --phase report        # Aggregate report
```

**Note:** the pipeline above covers 21 of the 22 metrics. `visual_plausibility` is the exception — it runs in the **separate `wbench-vp` environment** (set up in [Quick Start](#-quick-start)):
```bash
conda activate wbench-vp
python tools/run_visual_plausibility.py --model my_model  # uses all available GPUs
```

3. Results: `work_dirs/<model>/evaluation/{metric}/case_{id}.json` + `report.json`

```bash
# Run specific metrics (by name or dimension)
python main.py --model my_model --phase gpu --metrics hpsv3_quality
python main.py --model my_model --phase gpu --metrics quality         # all 6 video quality
python main.py --model my_model --phase gpu --metrics consistency     # all consistency metrics

# Skip pre-computation if already done
python main.py --model my_model --phase gpu --skip_megasam --skip_sam2 --skip_da3

# Single video evaluation
python main.py --video video.mp4 --case data/cases/case_1.json
```

**Dimensions** (`--metrics` supports these as shorthand):
| Dimension | Metrics |
|:---|:---|
| `quality` | aesthetic_quality, imaging_quality, temporal_flickering, dynamic_degree, motion_smoothness, hpsv3_quality |
| `consistency` | background_consistency, segment_continuity, perspective_consistency, subject_consistency, geometric_consistency, photometric_consistency, spatial_consistency, gated_spatial_consistency |
| `interaction` | navigation_trajectory, event_edit_adherence, subject_action_adherence, perspective_switch_adherence |
| `setting` | scene_adherence, subject_adherence |
| `physical` | visual_plausibility, causal_fidelity |


## 🔌 Implement Your Model

WBench supports 3 model types with different control interfaces:

| Type | Input | Cases | Status |
|:---|:---|:---:|:---:|
| **Text-conditioned** | Text prompt + first-frame image | 289 (all) | ✅ Implemented |
| **Camera-conditioned** | First-frame image + 6-DoF camera pose | 158 (navi) | ✅ Implemented |
| **Action-conditioned** | First-frame image + discrete action | 158 (navi) | ✅ Implemented |

### Text-conditioned models

```python
from src.models import get_model

# Available: wan, kling, seedance (or register your own)
model = get_model("wan")

# Generate multi-turn video from a case
result = model.generate_multi_turn(
    case=case_dict,
    output_path="work_dirs/wan/videos/case_1_combined.mp4",
    data_root="data/",
)
```

Each turn: build prompt from interaction → call I2V API → extract last frame → next turn.

Set API credentials:
```bash
export VIDEO_API_URL="https://your-video-api.com"
export VIDEO_API_KEY="your-key"
```

### Camera-conditioned models

The benchmark's navigation actions (W/A/S/D + arrows) are converted to per-turn
`{move, yaw, pitch}` intent and then to a 6-DoF camera trajectory. Subclass
`CameraConditionedModel` and implement one hook — case parsing, action→pose
conversion, and video writing are handled for you:

```python
from src.models.camera import CameraConditionedModel

class MyWorldModel(CameraConditionedModel):
    def generate_with_poses(self, image, poses, video_length, **kw):
        # image: first-frame path; poses: {"<latent_idx>": {"extrinsic": 4x4, "K": 3x3}, ...}
        # return: list of `video_length` BGR uint8 frames
        return my_model.infer(image, poses, video_length)

MyWorldModel("mymodel").generate_multi_turn(case_dict,
    "work_dirs/mymodel/videos/case_1_combined.mp4", data_root="data/")
```

The pose convention (axes, speeds, intrinsics) lives in `src/models/camera/poses.py`
— copy and adapt it to your model; the navigation metric normalises scale, so what
matters is matching the per-action *intent*. Quick look at one case:

```bash
python -m src.models.camera.demo --case data/cases/case_1.json   # prints poses + renders a preview
```

> **Note:** Camera/action models only cover the **158 navigation cases** (cases
> containing at least one W/A/S/D/arrow action). When generating at scale, pass
> only those cases — e.g. via `generate.py --model your_model --cases <navi_list>`.

### Action-conditioned models

Two flavours, both fed from the same per-turn navigation plan:

**Programmatic controllers** (e.g. Matrix-Game-3). Subclass `ActionConditionedModel`
and implement `generate_with_actions`. Each action carries both raw key `tokens`
and an MG3-style `{keyboard, mouse}` tensor:

```python
from src.models.action import ActionConditionedModel

class MyActionModel(ActionConditionedModel):
    def generate_with_actions(self, image, actions, video_length, **kw):
        # actions: [{"turn", "tokens", "keyboard", "mouse", "duration"}, ...]
        return my_model.infer(image, actions, video_length)

MyActionModel("mymodel").generate_multi_turn(case_dict,
    "work_dirs/mymodel/videos/case_1_combined.mp4", data_root="data/")
```

```bash
python -m src.models.action.demo --case data/cases/case_1.json   # prints actions + renders a preview
```

**Web products** (e.g. Project Genie, Happy Oyster) — no weights/API; driven by
browser automation + simulated keystrokes. See
[`src/models/action/web/`](src/models/action/web/README.md).

## 🤖 Claude Code Skills

If you use [Claude Code](https://claude.com/claude-code), this repo ships
skills that drive the full workflow — just ask in natural language and Claude
runs the right commands:

| Skill | Triggers on | What it does |
|:---|:---|:---|
| `wbench-generate` | "generate kling videos" | Runs `generate.py` over the dataset → `work_dirs/<model>/videos/` |
| `wbench-evaluate` | "evaluate kling3" | Runs the 4-phase `main.py` pipeline (precompute → gpu → vlm → report) |
| `wbench-submit` | "package my model for submission" | Builds the `meta.json` / `turns.json` bundle and uploads to HuggingFace |
| `genie3` / `happy` | "run case_5 on genie3" | Browser automation for the web products ([details](src/models/action/web/README.md)) |

Skills live in `.claude/skills/` (and `src/models/action/web/.claude/skills/`) and
are auto-discovered when you open the repo in Claude Code.

## 📋 TODO

- [x] Text-conditioned model generation (Wan, Kling, Seedance)
- [x] Homepage with interactive leaderboard
- [x] Dataset and weights release on HuggingFace
- [x] Camera-conditioned model generation example
- [x] Action-conditioned model generation example
- [x] Hosted submission & evaluation service (submit videos, get scores)
- [x] ArXiv paper release

## 📝 Citation

If you find our work useful, please consider citing:

```bibtex
@article{ying2026wbenchcomprehensivemultiturnbenchmark,
  title={WBench: A Comprehensive Multi-turn Benchmark for Interactive Video World Model Evaluation},
  author={Ying, Kaining and Hu, Hengrui and Ren, Siyu and Li, Jiamu and Chen, Fengjiao and Wang, Ziwen and Cao, Xuezhi and Cai, Xunliang and Ding, Henghui},
  journal={arXiv preprint arXiv:2605.25874},
  year={2026}
}
```

## 🙏 Acknowledgement

This project builds upon the following excellent works:

- [WorldScore](https://github.com/haoyi-duan/WorldScore) — World model evaluation framework
- [VBench](https://github.com/Vchitect/VBench) — Video quality metrics
- [SAM2](https://github.com/facebookresearch/sam2) — Segment Anything Model 2 for mask tracking
- [Depth-Anything-V3](https://github.com/DepthAnything/Depth-Anything-V3) — Monocular depth estimation
- [MegaSAM](https://github.com/mega-sam/mega-sam) — Camera pose estimation
- [DreamSim](https://github.com/ssundaram21/dreamsim) — Perceptual similarity metric
- [HPSv3](https://github.com/tgxs002/HPSv2) — Human Preference Score
- [AMT](https://github.com/MCG-NKU/AMT) — Frame interpolation for motion smoothness
- [RAFT](https://github.com/princeton-vl/RAFT) — Optical flow estimation
- [TransNetV2](https://github.com/soCzech/TransNetV2) — Scene boundary detection
- ... and many other excellent open-source projects

## 📧 Contact

Feel free to open an [Issue](https://github.com/meituan-longcat/WBench/issues) or [Pull Request](https://github.com/meituan-longcat/WBench/pulls). You can also reach us directly:

- **Kaining Ying**: `kaining.ying.cv@gmail.com`
- **Siyu Ren**: `rensiyu07@meituan.com`
- **Henghui Ding**: `hhding@fudan.edu.cn`

## 📄 License

Code and data: [MIT License](LICENSE). Model weights retain their [original licenses](https://huggingface.co/meituan-longcat/WBench-weights/blob/main/LICENSE_NOTICE.md).
