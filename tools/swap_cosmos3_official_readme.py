#!/usr/bin/env python3
"""Swap Cosmos3-Nano / Cosmos3-Super in the README leaderboard to the *_official
reports. Removes the two existing Cosmos3 rows from all four tables, recomputes
from *_official report.json (unified recipe, README column order), re-sorts the
5-dim tables and recomputes per-column medals. LingBot rows untouched; counts
unchanged.
"""
import json
import re
from decimal import Decimal, ROUND_HALF_UP

PATH = "README.md"
REPORTS = {
    "cosmos3_super": "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_super_official/evaluation/report.json",
    "cosmos3_nano":  "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_nano_official/evaluation/report.json",
}
CELL = {
    "cosmos3_super": '<img src="assets/icon/cosmos.png" height="18"> Cosmos3-Super',
    "cosmos3_nano":  '<img src="assets/icon/cosmos.png" height="18"> Cosmos3-Nano',
}
Q  = ["aesthetic_quality", "imaging_quality", "temporal_flickering", "dynamic_degree", "motion_smoothness", "hpsv3_quality"]
SET = ["scene_adherence", "subject_adherence"]
CON = ["background_consistency", "spatial_consistency", "gated_spatial_consistency", "perspective_consistency",
       "segment_continuity", "geometric_consistency", "photometric_consistency", "subject_consistency"]
PHY = ["visual_plausibility", "causal_fidelity"]
INT_NAVI = ["navigation_trajectory"]
INT_FULL = ["navigation_trajectory", "event_edit_adherence", "subject_action_adherence", "perspective_switch_adherence"]
DET_NAVI = ["aesthetic_quality", "imaging_quality", "background_consistency", "temporal_flickering",
            "dynamic_degree", "motion_smoothness", "hpsv3_quality", "scene_adherence", "subject_adherence",
            "navigation_trajectory", "spatial_consistency", "gated_spatial_consistency", "perspective_consistency",
            "segment_continuity", "geometric_consistency", "photometric_consistency", "subject_consistency",
            "visual_plausibility", "causal_fidelity"]
DET_FULL = ["aesthetic_quality", "imaging_quality", "background_consistency", "temporal_flickering",
            "dynamic_degree", "motion_smoothness", "hpsv3_quality", "scene_adherence", "subject_adherence",
            "navigation_trajectory", "event_edit_adherence", "subject_action_adherence", "perspective_switch_adherence",
            "spatial_consistency", "gated_spatial_consistency", "perspective_consistency", "segment_continuity",
            "geometric_consistency", "photometric_consistency", "subject_consistency", "visual_plausibility", "causal_fidelity"]
MEDALS = ["🥇", "🥈", "🥉"]
PAD = "&nbsp;&nbsp;"
NUM_RE = re.compile(r'[\d.]+')


def hu(x): return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
def dim(sec, keys): return hu(sum(sec[k]["mean"] for k in keys) / len(keys) * 100.0)


def five_dim(sec, split):
    ik = INT_NAVI if split == "navi" else INT_FULL
    q = dim(sec, Q); s = dim(sec, SET); i = dim(sec, ik); c = dim(sec, CON); p = dim(sec, PHY)
    return [hu(sum([q, s, i, c, p]) / 5.0), q, s, i, c, p]


def detail_vals(sec, order): return [hu(sec[k]["mean"] * 100.0) for k in order]
def fmt(v): return f"{v:.1f}"


def col_medals(values):
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))
    return {i: MEDALS[r] for r, i in enumerate(order[:3])}


def parse_5dim_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells[1], [float(NUM_RE.search(c).group()) for c in cells[2:8]]


def render_5dim_row(rank, model, vals, mm):
    avg = vals[0]
    avg_cell = f"**{fmt(avg)} {mm[0]}**" if mm[0] else f"**{fmt(avg)}** {PAD}"
    cells = [avg_cell]
    for j in range(1, 6):
        cells.append(f"{fmt(vals[j])} {mm[j]}" if mm[j] else f"{fmt(vals[j])} {PAD}")
    return f"| {rank} | {model} | " + " | ".join(cells) + " |"


def render_detail_row(model, vals):
    return f"| {model} | " + " | ".join(f"{fmt(v)} {PAD}" for v in vals) + " |"


def is_cosmos3(model_cell):
    return "Cosmos3-Super" in model_cell or "Cosmos3-Nano" in model_cell


def main():
    navi = {k: json.load(open(v))["navi"] for k, v in REPORTS.items()}
    full = {k: json.load(open(v))["full"] for k, v in REPORTS.items()}
    r5n = {k: five_dim(navi[k], "navi") for k in REPORTS}
    r5f = {k: five_dim(full[k], "full") for k in REPORTS}
    print("=== official 5-dim (README) ===")
    for k in REPORTS: print(f"  navi {k}: {r5n[k]}")
    for k in REPORTS: print(f"  full {k}: {r5f[k]}")

    lines = open(PATH, encoding="utf-8").read().split("\n")

    def find_table(needle):
        hdr = next(i for i, l in enumerate(lines) if needle in l)
        sep = next(i for i in range(hdr, len(lines)) if lines[i].lstrip().startswith("|:"))
        start = sep + 1
        end = start
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        return start, end

    def rebuild_5dim(block, new_rows, label):
        parsed = [parse_5dim_row(l) for l in block if not is_cosmos3(l)]
        rows = parsed + new_rows
        rows.sort(key=lambda r: -r[1][0])
        cols = list(zip(*[r[1] for r in rows]))
        colmed = [col_medals(list(cols[j])) for j in range(6)]
        out = [render_5dim_row(i + 1, m, v, [colmed[j].get(i, "") for j in range(6)])
               for i, (m, v) in enumerate(rows)]
        print(f"  {label}: -> {len(out)} rows; #1={rows[0][0].split('> ')[1]} {rows[0][1][0]}")
        return out

    # navi 5-dim
    s, e = find_table("Navigation Split (5 Dimensions")
    new = [(CELL[k], r5n[k]) for k in REPORTS]
    lines[s:e] = rebuild_5dim(lines[s:e], new, "navi-5dim")
    # full 5-dim
    s, e = find_table("Full Split (5 Dimensions")
    new = [(CELL[k], r5f[k]) for k in REPORTS]
    lines[s:e] = rebuild_5dim(lines[s:e], new, "full-5dim")

    # navi detail
    s, e = find_table("Navigation Split (19 metrics)")
    block = [l for l in lines[s:e] if not is_cosmos3(l)]
    ci = next(i for i, l in enumerate(block) if "Cosmos 2.5" in l)
    block.insert(ci + 1, render_detail_row(CELL["cosmos3_super"], detail_vals(navi["cosmos3_super"], DET_NAVI)))
    block.insert(ci + 2, render_detail_row(CELL["cosmos3_nano"], detail_vals(navi["cosmos3_nano"], DET_NAVI)))
    print(f"  navi-detail: -> {len(block)} rows")
    lines[s:e] = block
    # full detail
    s, e = find_table("Full Split (22 metrics)")
    block = [l for l in lines[s:e] if not is_cosmos3(l)]
    ci = next(i for i, l in enumerate(block) if "Cosmos 2.5" in l)
    block.insert(ci + 1, render_detail_row(CELL["cosmos3_super"], detail_vals(full["cosmos3_super"], DET_FULL)))
    block.insert(ci + 2, render_detail_row(CELL["cosmos3_nano"], detail_vals(full["cosmos3_nano"], DET_FULL)))
    print(f"  full-detail: -> {len(block)} rows")
    lines[s:e] = block

    open(PATH, "w", encoding="utf-8").write("\n".join(lines))
    print("written", PATH)


if __name__ == "__main__":
    main()
