#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert WBench navigation cases -> the LingBot-World JSON sample format.

Output: one JSONL with 158 samples, each:
    {
      "name": "case_<id>",
      "image_path": ".../images/case_<id>.jpg",
      "perspective": "first_person" | "third_person",
      "prompt": {"0": <scene caption>, "1": "", ...},   # per-chunk; first holds full caption
      "navigation": {"0": {"move":[fwd,right], "yaw":..., "pitch":...}, ...},
      "chunk_length": {"0": 4, "1": 4, ...}              # seconds per turn
    }

The JSON is consumed by generate_from_json_fast.py's build_poses_from_json /
build_prompt_with_perspective. run_wbench_fullseq_fast.py reads each line, builds
the CONTINUOUS accumulated pose sequence, and feeds it to WanI2VFast.generate()
in one call (model-native autoregressive KV-cache). This converter only produces
the JSON; the camera trajectory itself is built at inference time.

Action mapping (WBench token -> move[fwd,right]/yaw/pitch), verified to match
the WBench navigation_trajectory evaluator (NavScore ~0.99):
    W=[1,0] S=[-1,0] A=[0,-1] D=[0,1]
    left=yaw-1  right=yaw+1  up=pitch+1  down=pitch-1
Combos like 'W+A', 'W+left' sum component-wise.

Prompt: a single scene caption (environment + character + perspective) held in
the first turn; later turns are empty (navigation scenes are static).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

# WBench action token -> (move[fwd,right], yaw, pitch)
ACT2NAV = {
    "W": ([1, 0], 0, 0), "S": ([-1, 0], 0, 0),
    "A": ([0, -1], 0, 0), "D": ([0, 1], 0, 0),
    "left": ([0, 0], -1, 0), "right": ([0, 0], 1, 0),
    "up": ([0, 0], 0, 1), "down": ([0, 0], 0, -1),
}

# Natural-language / non-navigation tokens that may appear in nav-prefix cases.
# These are NOT navigation; a case is truncated to its nav prefix, so any of
# these terminates the navigation sequence (we stop accumulating at the first).
NON_NAV_MARKERS = None  # any token not parseable by ACT2NAV is treated as non-nav


def parse_action(action: str):
    """Return (fwd, right, yaw, pitch) or None if the token is non-navigation."""
    fwd = right = yaw = pitch = 0
    toks = [t.strip() for t in action.replace(",", "+").split("+") if t.strip()]
    if not toks:
        return None
    for t in toks:
        if t not in ACT2NAV:
            return None  # non-navigation (natural language) -> signal caller to stop
        (mv, y, p) = ACT2NAV[t]
        fwd += mv[0]; right += mv[1]; yaw += y; pitch += p
    return fwd, right, yaw, pitch


def is_all_navigation(case: dict) -> bool:
    its = case.get("interactions", [])
    return bool(its) and all(it.get("type") == "navigation" for it in its)


def nav_prefix_len(case: dict) -> int:
    n = 0
    for it in case.get("interactions", []):
        if it.get("type") == "navigation":
            n += 1
        else:
            break
    return n


def case_perspective(case: dict) -> str:
    return case.get("settings", {}).get("perspective", "third_person")


def case_sort_key(f: Path):
    """Sort key that tolerates lettered ids (case_e_1, case_ps_1, case_1).

    Sorts by (prefix, trailing number) so 'case_e_2' < 'case_e_10' and lettered
    prefixes group together, instead of assuming a pure-numeric id (which crashes
    on e.g. int('e')).
    """
    cid = f.stem[len("case_"):] if f.stem.startswith("case_") else f.stem
    m = re.search(r"(\d+)$", cid)
    num = int(m.group(1)) if m else 0
    prefix = cid[:m.start()] if m else cid
    return (prefix, num)


def resolve_image_path(images_dir: str, cid, perspective: str) -> str | None:
    """Locate case image across flat and perspective-subdir layouts.

    Tries images/case_<id>.jpg (flat, preview dataset) first, then
    images/<perspective>/case_<id>.jpg (merged dataset). Returns the first
    existing path, or None if neither exists.
    """
    candidates = [
        os.path.join(images_dir, f"case_{cid}.jpg"),
        os.path.join(images_dir, perspective, f"case_{cid}.jpg"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def build_caption(case: dict) -> str:
    """Single scene caption: environment + character + perspective prompt."""
    parts = []
    env = case.get("environment_prompt", "").strip()
    if env:
        parts.append(env)
    char = case.get("character_prompt", "").strip()
    if char and "first-person viewer" not in char.lower():
        parts.append(char)
    persp = case.get("perspective_prompt", "").strip()
    if persp:
        parts.append(persp)
    if not parts:
        parts.append("A 3D scene.")
    return " ".join(parts)


def convert_case(case: dict, images_dir: str, secs_per_turn: int) -> dict | None:
    cid = case["id"]
    perspective = case_perspective(case)

    # Take the navigation prefix (pure-nav cases => all turns).
    plen = nav_prefix_len(case)
    nav_turns = case["interactions"][:plen]
    # Defensive: drop any trailing token that fails to parse as navigation.
    navigation = {}
    chunk_length = {}
    k = 0
    for it in nav_turns:
        parsed = parse_action(it["action"])
        if parsed is None:
            break
        fwd, right, yaw, pitch = parsed
        navigation[str(k)] = {"move": [fwd, right], "yaw": yaw, "pitch": pitch}
        chunk_length[str(k)] = secs_per_turn
        k += 1

    if k == 0:
        return None  # no usable navigation turn

    caption = build_caption(case)
    prompt = {str(i): (caption if i == 0 else "") for i in range(k)}

    img_path = resolve_image_path(images_dir, cid, perspective)
    if img_path is None:
        return None
    return {
        "name": f"case_{cid}",
        "image_path": img_path,
        "perspective": perspective,
        "prompt": prompt,
        "navigation": navigation,
        "chunk_length": chunk_length,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wbench_dir", required=True,
                    help="WBench dataset dir containing cases/ and images/ (e.g. data/wbench_3.0_merged_v2)")
    ap.add_argument("--out", default="./wbench_nav_158.jsonl")
    ap.add_argument("--secs_per_turn", type=int, default=4, help="Seconds per action turn")
    ap.add_argument("--include_prefix", action="store_true", default=True)
    args = ap.parse_args()

    cases_dir = os.path.join(args.wbench_dir, "cases")
    images_dir = os.path.join(args.wbench_dir, "images")

    case_files = sorted(Path(cases_dir).glob("case_*.json"), key=case_sort_key)
    selected = []
    for f in case_files:
        c = json.load(open(f, encoding="utf-8"))
        if is_all_navigation(c) or (args.include_prefix and nav_prefix_len(c) >= 1):
            selected.append(c)

    samples = []
    skipped = []
    fp = tp = 0
    for c in selected:
        if resolve_image_path(images_dir, c["id"], case_perspective(c)) is None:
            skipped.append(c["id"]); continue
        s = convert_case(c, images_dir, args.secs_per_turn)
        if s is None:
            skipped.append(c["id"]); continue
        samples.append(s)
        if s["perspective"].startswith("first"):
            fp += 1
        else:
            tp += 1

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"Wrote {len(samples)} samples -> {args.out}")
    print(f"  first_person: {fp}, third_person: {tp}")
    if skipped:
        print(f"  skipped {len(skipped)}: {skipped}")
    # show one example
    if samples:
        print("\nExample (first sample):")
        print(json.dumps(samples[0], ensure_ascii=False, indent=2)[:900])


if __name__ == "__main__":
    main()
