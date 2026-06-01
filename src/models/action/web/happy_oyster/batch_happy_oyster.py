#!/usr/bin/env python3
"""
Batch driver skeleton for Happy Oyster benchmark cases.

Wires the orchestration only — progress tracking, launching the keyboard layer
(auto_interact.py), and the download -> rename hand-off. The browser steps
(prompt injection, image upload, perspective flip, send click, download click)
still need a browser-automation host (Chrome DevTools / a browser MCP); see
../README.md and ../.claude/skills/happy/SKILL.md.

All paths are configurable via CLI flags; defaults assume you run from a
directory whose subtree contains the WBench `data/cases` + `data/images` tree
(the same directory the local server in ../serve.py exposes).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # tools/web_world_models/


def load_progress(progress_file):
    with open(progress_file) as f:
        return json.load(f)


def save_progress(progress_file, data):
    with open(progress_file, "w") as f:
        json.dump(data, f, indent=2)


def get_next_pending_case(progress_file):
    progress = load_progress(progress_file)
    for case_id, info in progress.items():
        if info["status"] == "pending":
            return case_id
    return None


def load_case_json(cases_dir, case_id):
    with open(Path(cases_dir) / f"{case_id}.json") as f:
        return json.load(f)


def wait_for_download(downloads_dir, timeout=150):
    """Wait for the newest non-Genie* mp4 to appear in the downloads dir."""
    downloads = Path(downloads_dir)
    start = time.time()
    while time.time() - start < timeout:
        non_genie = [f for f in downloads.glob("*.mp4") if not f.name.startswith("Genie")]
        if non_genie:
            return max(non_genie, key=lambda p: p.stat().st_mtime).name
        time.sleep(2)
    return None


def process_case(case_id, args):
    print(f"\n=== Processing {case_id} ===")
    case = load_case_json(args.cases_dir, case_id)
    perspective = case["settings"]["perspective"]
    print(f"  Perspective: {perspective} | Interactions: {len(case['interactions'])}")

    progress = load_progress(args.progress_file)
    progress[case_id]["status"] = "in_progress"
    save_progress(args.progress_file, progress)

    # Browser steps (prompt, upload, perspective, send) happen via your
    # automation host before this point — see SKILL.md steps 1-4.
    print("  [keyboard] launching auto_interact.py ...")
    subprocess.Popen(
        [args.python, "-u", str(BASE_DIR / "auto_interact.py"),
         str(Path(args.cases_dir) / f"{case_id}.json"),
         str(BASE_DIR / "happy_oyster" / "t2.png"), str(args.key_duration)],
        cwd=str(BASE_DIR),
    )

    print("  [download] waiting ...")
    filename = wait_for_download(args.downloads_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        (Path(args.downloads_dir) / filename).rename(out_dir / f"{case_id}.mp4")
        print(f"  Downloaded: {filename} -> {case_id}.mp4")
        progress = load_progress(args.progress_file)
        progress[case_id]["status"] = "done"
        save_progress(args.progress_file, progress)
        return True

    print("  ERROR: download timeout")
    progress = load_progress(args.progress_file)
    progress[case_id]["status"] = "pending"
    save_progress(args.progress_file, progress)
    return False


def parse_args():
    p = argparse.ArgumentParser(description="Happy Oyster batch driver (skeleton)")
    p.add_argument("--cases_dir", default="data/cases", help="Dir of case_<id>.json files")
    p.add_argument("--output_dir", default="happy_video", help="Where to place renamed videos")
    p.add_argument("--downloads_dir", default=str(Path.home() / "Downloads"),
                   help="Browser download directory to watch")
    p.add_argument("--progress_file", default="happy_progress.json",
                   help="JSON tracking per-case {status: pending|in_progress|done}")
    p.add_argument("--python", default=sys.executable, help="Python used to launch auto_interact.py")
    p.add_argument("--key_duration", default=3, type=float, help="Seconds per turn (Happy Oyster: 3)")
    return p.parse_args()


def main():
    args = parse_args()
    print("Happy Oyster batch processor")
    print(f"Progress file: {args.progress_file}")
    # NOTE: integrate your browser-automation host inside the loop before
    # calling process_case(); see SKILL.md. This skeleton only iterates pending.
    while True:
        case_id = get_next_pending_case(args.progress_file)
        if not case_id:
            print("\nAll cases completed!")
            break
        print(f"Next pending: {case_id}")
        # process_case(case_id, args)  # enable once browser steps are wired
        break  # remove once integrated, to avoid an infinite loop in the skeleton


if __name__ == "__main__":
    main()
