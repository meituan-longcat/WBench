"""
Demo: convert one WBench case into discrete actions and render a preview.

    python -m src.models.action.demo --case data/cases/case_1.json
    python -m src.models.action.demo --case data/cases/case_1.json --data_root data

Outputs:
    work_dirs/action_preview/videos/case_<id>_combined.mp4   (preview video)
    work_dirs/action_preview/actions/case_<id>.json          (per-turn actions)
"""
import argparse
import json
import os

from .actions import case_to_actions
from .example_model import PreviewActionModel


def main():
    parser = argparse.ArgumentParser(description="Action-conditioned conversion demo")
    parser.add_argument("--case", default="data/cases/case_1.json", help="Path to a case JSON")
    parser.add_argument("--data_root", default="data", help="Root for resolving initial_image")
    parser.add_argument("--out", default="work_dirs/action_preview/videos", help="Video output dir")
    args = parser.parse_args()

    with open(args.case) as fp:
        case = json.load(fp)
    cid = case["id"]

    print(f"=== case_{cid} ===")
    print(f"perspective: {case.get('settings', {}).get('perspective')}")

    conv = case_to_actions(case)
    print("\n--- per-turn actions ---")
    print(f"  {'turn':>4}  {'tokens':<12}  {'keyboard[W,S,A,D,_,_]':<22}  {'mouse[pitch,yaw]':<16}  dur")
    for a in conv["actions"]:
        tok = "+".join(a["tokens"]) or "(none)"
        print(f"  {a['turn']:>4}  {tok:<12}  {str(a['keyboard']):<22}  {str(a['mouse']):<16}  {a['duration']}s")
    print(f"\n  total_duration: {conv['total_duration']}s")

    out_path = os.path.join(args.out, f"case_{cid}_combined.mp4")
    print(f"\n--- rendering preview (PreviewActionModel) ---")
    model = PreviewActionModel()
    result = model.generate_multi_turn(case, out_path, data_root=args.data_root)
    if result.get("code") == 0:
        print(f"  OK -> {result['video_path']}")
        print(f"  actions -> work_dirs/action_preview/actions/case_{cid}.json")
    else:
        print(f"  FAILED -> {result.get('error')}")


if __name__ == "__main__":
    main()
