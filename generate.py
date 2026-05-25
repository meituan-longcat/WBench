"""
WBench Video Generation Script.

Generates multi-turn videos for all (or specified) cases using a registered model.

Usage:
    # Generate for all cases
    python generate.py --model example --data_dir data

    # Generate specific cases
    python generate.py --model example --cases data/cases/case_1.json data/cases/case_2.json

    # Limit number of cases
    python generate.py --model example --limit 10

    # Resume (skip existing)
    python generate.py --model example --resume
"""
import argparse
import glob
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models import get_model, list_models
from src.utils.case_loader import load_cases_raw

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def generate_case(model, case: dict, output_dir: str, data_root: str) -> dict:
    """Generate multi-turn video for a single case."""
    case_id = case["id"]
    output_path = os.path.join(output_dir, f"case_{case_id}_combined.mp4")

    result = model.generate_multi_turn(
        case=case,
        output_path=output_path,
        data_root=data_root,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="WBench video generation")
    parser.add_argument("--model", required=True, help=f"Model name. Available: {list_models()}")
    parser.add_argument("--data_dir", default="data", help="Path to data/ directory")
    parser.add_argument("--output_dir", default=None, help="Output dir (default: work_dirs/<model>/videos)")
    parser.add_argument("--cases", nargs="*", help="Specific case JSON files to process")
    parser.add_argument("--limit", type=int, default=None, help="Max cases to process")
    parser.add_argument("--resume", action="store_true", help="Skip cases with existing videos")
    args = parser.parse_args()

    model = get_model(args.model)
    logger.info(f"Using model: {model}")

    output_dir = args.output_dir or os.path.join("work_dirs", args.model, "videos")
    os.makedirs(output_dir, exist_ok=True)

    if args.cases:
        cases = []
        for f in args.cases:
            with open(f) as fp:
                cases.append(json.load(fp))
    else:
        cases = load_cases_raw(args.data_dir)

    if args.limit:
        cases = cases[:args.limit]

    logger.info(f"Processing {len(cases)} cases → {output_dir}")

    results = {"success": 0, "failed": 0, "skipped": 0}
    t0 = time.time()

    for i, case in enumerate(cases):
        case_id = case["id"]
        out_path = os.path.join(output_dir, f"case_{case_id}_combined.mp4")

        if args.resume and os.path.exists(out_path):
            logger.info(f"[{i+1}/{len(cases)}] case_{case_id}: SKIP (exists)")
            results["skipped"] += 1
            continue

        logger.info(f"[{i+1}/{len(cases)}] case_{case_id}: generating...")
        result = generate_case(model, case, output_dir, args.data_dir)

        if result.get("code") == 0:
            results["success"] += 1
            logger.info(f"  → OK: {result['video_path']}")
        else:
            results["failed"] += 1
            logger.error(f"  → FAIL: {result.get('error')}")

    elapsed = time.time() - t0
    logger.info(
        f"\nDone in {elapsed:.1f}s — "
        f"success={results['success']}, failed={results['failed']}, skipped={results['skipped']}"
    )


if __name__ == "__main__":
    main()
