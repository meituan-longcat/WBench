"""
MegaSAM pose inference — extract camera poses from a video.

Requires: MegaSAM conda environment (torch==2.1.0 + lietorch)

Usage:
    # Single video
    python tools/run_megasam.py --video work_dirs/hunyuan/videos/case_1_combined.mp4 \
        --output work_dirs/hunyuan/megasam/case_1_combined.npz

    # Batch: all videos in a directory
    python tools/run_megasam.py --video_dir work_dirs/hunyuan/videos \
        --output_dir work_dirs/hunyuan/megasam --gpus 0,1,2,3

Output:
    .npz with keys: cam_c2w (N,4,4), camera_centers (N,3), intrinsic, stride, fps
"""
import argparse
import cv2
import os
import subprocess
import sys
import tempfile
import time
import multiprocessing
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEGASAM_ROOT = PROJECT_ROOT / "third_party" / "mega-sam"
WEIGHTS_DIR = os.environ.get("WBENCH_WEIGHTS_DIR") or str(PROJECT_ROOT / "weights")
MEGASAM_WEIGHTS = Path(WEIGHTS_DIR) / "megasam"

DA_CKPT = MEGASAM_WEIGHTS / "depth_anything_vitl14.pth"
MEGASAM_CKPT = MEGASAM_WEIGHTS / "megasam_final.pth"


def compute_stride(video_path, target_fps=15):
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    cap.release()
    stride = max(1, int(fps / target_fps))
    return stride, fps, fps / stride


def extract_frames(video_path, frames_dir, stride=1):
    frames_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    idx, saved = 0, 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if idx % stride == 0:
            cv2.imwrite(str(frames_dir / f"{saved:05d}.jpg"), frame)
            saved += 1
        idx += 1
    cap.release()
    return saved


def setup_env(device=None):
    env = os.environ.copy()
    if device is not None and "CUDA_VISIBLE_DEVICES" not in env:
        env["CUDA_VISIBLE_DEVICES"] = str(device)
    env["PYTHONPATH"] = f"{MEGASAM_ROOT / 'UniDepth'}:{env.get('PYTHONPATH', '')}"

    torch_home = Path(WEIGHTS_DIR)
    hub_dir = torch_home / "hub"
    hub_dir.mkdir(parents=True, exist_ok=True)

    # torch.hub looks under $TORCH_HOME/hub/. Link torch_hub → hub/torchhub so that
    # hub/torchhub/facebookresearch_dinov2_main/ points at weights/torch_hub/facebookresearch_dinov2_main/.
    torchhub_link = hub_dir / "torchhub"
    torchhub_src = torch_home / "torch_hub"
    if torchhub_src.exists() and not torchhub_link.exists():
        os.symlink(str(torchhub_src), str(torchhub_link))

    # Depth-Anything's localhub mode calls torch.hub.load('torchhub/facebookresearch_dinov2_main',
    # source='local'); that relative path is resolved against the subprocess cwd=MEGASAM_ROOT
    # (it does NOT go through $TORCH_HOME), so MEGASAM_ROOT/torchhub must point at the vendored
    # dinov2 hub code.
    megasam_torchhub = MEGASAM_ROOT / "torchhub"
    if torchhub_src.exists() and not megasam_torchhub.exists() and not megasam_torchhub.is_symlink():
        os.symlink(str(torchhub_src), str(megasam_torchhub))

    ckpt_src = MEGASAM_WEIGHTS / "torch_hub_checkpoints"
    ckpt_dst = hub_dir / "checkpoints"
    if ckpt_src.exists() and not ckpt_dst.exists():
        os.symlink(str(ckpt_src), str(ckpt_dst))

    env["TORCH_HOME"] = str(torch_home)
    env["HF_HOME"] = str(MEGASAM_WEIGHTS / "huggingface")
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    return env


def run_single(video_path, output_path, device="0", target_fps=15.0,
               cpu_list=None, n_threads=4):
    import shutil

    video_path = Path(video_path).resolve()
    output_path = Path(output_path).resolve()
    scene_name = video_path.stem

    stride, orig_fps, eff_fps = compute_stride(video_path, target_fps)
    print(f"[INFO] {scene_name}: {orig_fps:.0f}fps → stride={stride} → {eff_fps:.1f}fps")

    env = setup_env(device)
    env["OMP_NUM_THREADS"] = str(n_threads)
    env["MKL_NUM_THREADS"] = str(n_threads)
    env["OPENBLAS_NUM_THREADS"] = str(n_threads)
    env["NUMEXPR_NUM_THREADS"] = str(n_threads)

    has_taskset = shutil.which("taskset") is not None
    t0 = time.time()

    tmp_base = PROJECT_ROOT / "_megasam_tmp"
    tmp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"megasam_{scene_name}_", dir=str(tmp_base)) as td:
        tp = Path(td)
        frames_dir = tp / "frames" / scene_name
        mono_root = tp / "mono"
        mono_dir = mono_root / scene_name
        metric_root = tp / "metric"

        n = extract_frames(video_path, frames_dir, stride)
        print(f"[TIME] extract: {time.time() - t0:.1f}s ({n} frames)")

        def run_cmd(cmd):
            if has_taskset and cpu_list:
                cmd = ["taskset", "-c", cpu_list] + cmd
            subprocess.run(cmd, cwd=str(MEGASAM_ROOT), env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        run_cmd([sys.executable, "Depth-Anything/run_videos.py",
                 "--encoder", "vitl", "--load-from", str(DA_CKPT),
                 "--img-path", str(frames_dir), "--outdir", str(mono_dir),
                 "--localhub"])

        run_cmd([sys.executable, "UniDepth/scripts/demo_mega-sam.py",
                 "--scene-name", scene_name, "--img-path", str(frames_dir),
                 "--outdir", str(metric_root)])

        run_cmd([sys.executable, "camera_tracking_scripts/test_demo.py",
                 "--datapath", str(frames_dir), "--weights", str(MEGASAM_CKPT),
                 "--scene_name", scene_name, "--mono_depth_path", str(mono_root),
                 "--metric_depth_path", str(metric_root), "--disable_vis"])

        npz_path = MEGASAM_ROOT / "outputs" / f"{scene_name}_droid.npz"
        if npz_path.exists():
            data = np.load(npz_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(output_path, cam_c2w=data["cam_c2w"],
                     camera_centers=data["cam_c2w"][:, :3, 3],
                     intrinsic=data["intrinsic"],
                     stride=stride, original_fps=orig_fps, effective_fps=eff_fps)
            npz_path.unlink()
            print(f"[DONE] {output_path} ({data['cam_c2w'].shape[0]} poses, {time.time()-t0:.1f}s)")
        else:
            print(f"[FAIL] output not found: {npz_path}")
            sys.exit(1)


def _gpu_worker_process(gpu_id, worker_idx, n_workers, task_list, target_fps):
    """Dedicated process per GPU. Processes its task list sequentially."""
    # CPU affinity
    try:
        available = sorted(os.sched_getaffinity(0))
    except AttributeError:
        available = list(range(os.cpu_count() or 64))
    total = len(available)
    n_cores = max(1, total // n_workers)
    n_threads = max(1, total // (2 * n_workers))
    start = worker_idx * n_cores
    cpu_ids = available[start:start + n_cores]
    cpu_list = ",".join(str(c) for c in cpu_ids)

    try:
        os.sched_setaffinity(0, cpu_ids)
    except (AttributeError, OSError):
        pass

    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    os.environ["OMP_NUM_THREADS"] = str(n_threads)
    os.environ["MKL_NUM_THREADS"] = str(n_threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(n_threads)

    tag = f"[GPU{gpu_id}]"
    print(f"  {tag} Worker started: {len(task_list)} videos, cpus={cpu_ids[0]}-{cpu_ids[-1]}, threads={n_threads}", flush=True)

    n_total = len(task_list)
    ok, fail = 0, 0
    for i, (video_path, output_path) in enumerate(task_list):
        print(f"  {tag} [{i+1}/{n_total}] {os.path.basename(video_path)}", flush=True)
        try:
            run_single(video_path, output_path, device="0",
                       target_fps=target_fps, cpu_list=cpu_list, n_threads=n_threads)
            ok += 1
        except subprocess.CalledProcessError as e:
            stderr_msg = e.stderr.decode()[-500:] if e.stderr else "no stderr"
            print(f"  {tag} FAIL {os.path.basename(video_path)}:\n    {stderr_msg}", flush=True)
            fail += 1
        except Exception as e:
            print(f"  {tag} FAIL {os.path.basename(video_path)}: {e}", flush=True)
            fail += 1

    print(f"  {tag} Done: {ok}/{n_total} ok, {fail} fail", flush=True)


def main():
    parser = argparse.ArgumentParser(description="MegaSAM pose inference")
    parser.add_argument("--video", type=str, help="Single video path")
    parser.add_argument("--video_dir", type=str, help="Batch: video directory")
    parser.add_argument("--output", type=str, help="Output .npz path (single mode)")
    parser.add_argument("--output_dir", type=str, help="Output directory (batch mode)")
    parser.add_argument("--gpus", type=str, default="0", help="GPU IDs (comma-separated)")
    parser.add_argument("--target_fps", type=float, default=15.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.video:
        output = args.output or args.video.replace(".mp4", ".npz")
        run_single(args.video, output, device=args.gpus.split(",")[0],
                   target_fps=args.target_fps)
        return

    if args.video_dir:
        gpu_ids = [int(g) for g in args.gpus.split(",")]
        output_dir = args.output_dir or os.path.join(os.path.dirname(args.video_dir), "megasam")
        os.makedirs(output_dir, exist_ok=True)

        n_gpus = len(gpu_ids)
        videos = sorted(Path(args.video_dir).glob("case_*_combined.mp4"))
        tasks = []
        for v in videos:
            out = Path(output_dir) / f"{v.stem}.npz"
            if out.exists() and not args.force:
                continue
            tasks.append((str(v), str(out)))

        print(f"Found {len(videos)} videos, {len(tasks)} to process, {len(gpu_ids)} GPUs")
        if tasks:
            n_workers = min(n_gpus, len(tasks))
            # Split tasks across GPUs
            worker_tasks = [[] for _ in range(n_workers)]
            for i, t in enumerate(tasks):
                worker_tasks[i % n_workers].append(t)

            ctx = multiprocessing.get_context("spawn")
            processes = []
            for w in range(n_workers):
                p = ctx.Process(
                    target=_gpu_worker_process,
                    args=(gpu_ids[w], w, n_workers, worker_tasks[w], args.target_fps),
                )
                p.start()
                processes.append(p)

            for p in processes:
                p.join()

            print("Done: all workers finished")


if __name__ == "__main__":
    main()
