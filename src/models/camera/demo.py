"""
Demo: convert one WBench case into a camera trajectory and render a preview.

    python -m src.models.camera.demo --case data/cases/case_1.json
    python -m src.models.camera.demo --case data/cases/case_1.json --data_root data

Outputs:
    work_dirs/camera_preview/videos/case_<id>_combined.mp4   (preview video)
    work_dirs/camera_preview/poses/case_<id>.json            (camera poses)
"""
import argparse
import json
import os

from ..navigation import case_to_navigation, action_to_navigation
from .poses import case_to_poses
from .example_model import PreviewCameraModel


def main():
    parser = argparse.ArgumentParser(description="Camera-conditioned conversion demo")
    parser.add_argument("--case", default="data/cases/case_1.json", help="Path to a case JSON")
    parser.add_argument("--data_root", default="data", help="Root for resolving initial_image")
    parser.add_argument("--out", default="work_dirs/camera_preview/videos", help="Video output dir")
    args = parser.parse_args()

    with open(args.case) as fp:
        case = json.load(fp)
    cid = case["id"]

    print(f"=== case_{cid} ===")
    print(f"perspective: {case.get('settings', {}).get('perspective')}")

    nav = case_to_navigation(case)
    print("\n--- per-turn navigation intent ---")
    for i, inter in enumerate(case.get("interactions", [])):
        action = inter.get("action", inter.get("action_key", ""))
        sig = nav["navigation"][str(i)]
        tag = "" if action_to_navigation(action) is not None else "  (non-nav -> zero)"
        print(f"  turn {i}: {action!r:>10} -> move={sig['move']} yaw={sig['yaw']} pitch={sig['pitch']}{tag}")

    conv = case_to_poses(case)
    print("\n--- pose conversion ---")
    print(f"  total_latents: {conv['total_latents']}")
    print(f"  video_length : {conv['video_length']} frames @ 24fps "
          f"(~{conv['video_length'] / 24:.1f}s)")
    print(f"  poses        : {len(conv['poses'])} (one per latent)")
    print(f"  pose[0].extrinsic[:3]:")
    for row in conv["poses"]["0"]["extrinsic"][:3]:
        print(f"      {[round(x, 3) for x in row]}")

    out_path = os.path.join(args.out, f"case_{cid}_combined.mp4")
    print(f"\n--- rendering preview (PreviewCameraModel) ---")
    model = PreviewCameraModel()
    result = model.generate_multi_turn(case, out_path, data_root=args.data_root)
    if result.get("code") == 0:
        print(f"  OK -> {result['video_path']}")
        print(f"  poses -> work_dirs/camera_preview/poses/case_{cid}.json")
    else:
        print(f"  FAILED -> {result.get('error')}")


if __name__ == "__main__":
    main()
