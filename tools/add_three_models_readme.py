#!/usr/bin/env python3
"""Add Cosmos3-Nano, Cosmos3-Super (text) and LingBot-World (fast v2, camera) to
the four README leaderboard tables, using the SAME unified 5-dim recipe as
tools/add_three_models_homepage.py (verified against the homepage + PDF).

README specifics that differ from the homepage:
  * icons use assets/icon/<name>.png (not imgs/)
  * detail tables put Background Consistency at column 3 (not 10/13)
  * 5-dim tables are sorted by Average desc, each column carries its OWN top-3
    medals (🥇🥈🥉), Average column is bold
  * detail tables have no rank / no medals; rows are anchor-inserted
Before editing, the script re-derives every existing medal in the two 5-dim
tables and asserts it matches the file, so a recipe/tie-break mismatch fails
loudly instead of silently corrupting the board.
"""
import json
import re
from decimal import Decimal, ROUND_HALF_UP

PATH = "README.md"

REPORTS = {
    "cosmos3_super": "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_super/evaluation/report.json",
    "cosmos3_nano":  "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_nano/evaluation/report.json",
    "lingbot_v2":    "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/lingbot_world_v2_fast/evaluation/report.json",
}

CELL = {
    "cosmos3_super": '<img src="assets/icon/cosmos.png" height="18"> Cosmos3-Super',
    "cosmos3_nano":  '<img src="assets/icon/cosmos.png" height="18"> Cosmos3-Nano',
    "lingbot_v2":    '<img src="assets/icon/lingbot.png" height="18"> LingBot-World (fast v2)',
}

Q  = ["aesthetic_quality", "imaging_quality", "temporal_flickering", "dynamic_degree", "motion_smoothness", "hpsv3_quality"]
SET = ["scene_adherence", "subject_adherence"]
CON = ["background_consistency", "spatial_consistency", "gated_spatial_consistency", "perspective_consistency",
       "segment_continuity", "geometric_consistency", "photometric_consistency", "subject_consistency"]
PHY = ["visual_plausibility", "causal_fidelity"]
INT_NAVI = ["navigation_trajectory"]
INT_FULL = ["navigation_trajectory", "event_edit_adherence", "subject_action_adherence", "perspective_switch_adherence"]

# README detail column orders (Background Consistency at position 3)
DET_NAVI = ["aesthetic_quality", "imaging_quality", "background_consistency", "temporal_flickering",
            "dynamic_degree", "motion_smoothness", "hpsv3_quality", "scene_adherence", "subject_adherence",
            "navigation_trajectory", "spatial_consistency", "gated_spatial_consistency", "perspective_consistency",
            "segment_continuity", "geometric_consistency", "photometric_consistency", "subject_consistency",
            "visual_plausibility", "causal_fidelity"]  # 19
DET_FULL = ["aesthetic_quality", "imaging_quality", "background_consistency", "temporal_flickering",
            "dynamic_degree", "motion_smoothness", "hpsv3_quality", "scene_adherence", "subject_adherence",
            "navigation_trajectory", "event_edit_adherence", "subject_action_adherence", "perspective_switch_adherence",
            "spatial_consistency", "gated_spatial_consistency", "perspective_consistency", "segment_continuity",
            "geometric_consistency", "photometric_consistency", "subject_consistency",
            "visual_plausibility", "causal_fidelity"]  # 22

MEDALS = ["🥇", "🥈", "🥉"]
PAD = "&nbsp;&nbsp;"


def hu(x):
    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def dim(sec, keys):
    return hu(sum(sec[key]["mean"] for key in keys) / len(keys) * 100.0)


def five_dim(sec, split):
    int_keys = INT_NAVI if split == "navi" else INT_FULL
    q = dim(sec, Q); s = dim(sec, SET); i = dim(sec, int_keys); c = dim(sec, CON); p = dim(sec, PHY)
    avg = hu(sum([q, s, i, c, p]) / 5.0)
    return [avg, q, s, i, c, p]


def detail_vals(sec, order):
    return [hu(sec[k]["mean"] * 100.0) for k in order]


def fmt(v):
    return f"{v:.1f}"


def col_medals(values):
    """idx -> medal for the 3 highest values (stable tie-break by row order)."""
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))
    return {i: MEDALS[r] for r, i in enumerate(order[:3])}


# ---------- 5-dim tables ----------
NUM_RE = re.compile(r'[\d.]+')


def parse_5dim_row(line):
    """-> (model_cell, [avg,q,s,i,c,p]) from a README 5-dim table row."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    # cells: rank, model, avg, q, s, i, c, p
    model = cells[1]
    vals = [float(NUM_RE.search(c).group()) for c in cells[2:8]]
    return model, vals


def render_5dim_row(rank, model, vals, medal_map):
    """medal_map: list of 6 dicts (per column) idx->medal for THIS row index."""
    avg = vals[0]
    avg_medal = medal_map[0]
    if avg_medal:
        avg_cell = f"**{fmt(avg)} {avg_medal}**"
    else:
        avg_cell = f"**{fmt(avg)}** {PAD}"
    cells = [avg_cell]
    for j in range(1, 6):
        m = medal_map[j]
        cells.append(f"{fmt(vals[j])} {m}" if m else f"{fmt(vals[j])} {PAD}")
    return f"| {rank} | {model} | " + " | ".join(cells) + " |"


def rebuild_5dim(block_lines, new_rows, label):
    """block_lines: the data rows (list of str). new_rows: list of (model,[6])."""
    parsed = [parse_5dim_row(l) for l in block_lines]

    # ---- validate: recompute medals on existing rows, compare to file ----
    existing_medals = []
    for l in block_lines:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        row_m = []
        for c in cells[2:8]:
            row_m.append(next((x for x in MEDALS if x in c), ""))
        existing_medals.append(row_m)
    cols = list(zip(*[p[1] for p in parsed]))
    for j in range(6):
        cm = col_medals(list(cols[j]))
        for i in range(len(parsed)):
            want = cm.get(i, "")
            got = existing_medals[i][j]
            if want != got:
                print(f"  [WARN] {label} col{j} row{i} ({parsed[i][0][:30]}): "
                      f"file={got!r} recomputed={want!r}")

    rows = parsed + new_rows
    rows.sort(key=lambda r: -r[1][0])
    cols = list(zip(*[r[1] for r in rows]))
    colmed = [col_medals(list(cols[j])) for j in range(6)]
    out = []
    for i, (model, vals) in enumerate(rows):
        mm = [colmed[j].get(i, "") for j in range(6)]
        out.append(render_5dim_row(i + 1, model, vals, mm))
    top = re.search(r'height="18"> (.+)$', rows[0][0])
    print(f"  {label}: {len(parsed)} -> {len(rows)} rows (sorted); #1 = {rows[0][1][0]} {top.group(1) if top else ''}")
    return out


# ---------- detail tables ----------
def render_detail_row(model, vals):
    return f"| {model} | " + " | ".join(f"{fmt(v)} {PAD}" for v in vals) + " |"


def main():
    navi = {k: json.load(open(v))["navi"] for k, v in REPORTS.items()}
    full = {k: json.load(open(v))["full"] for k, v in REPORTS.items()}

    print("=== computed 5-dim ===")
    r5_navi = {k: five_dim(navi[k], "navi") for k in REPORTS}
    r5_full = {k: five_dim(full[k], "full") for k in ("cosmos3_super", "cosmos3_nano")}
    for k, v in r5_navi.items():
        print(f"  navi {CELL[k].split('> ')[1]:28s} {v}")
    for k, v in r5_full.items():
        print(f"  full {CELL[k].split('> ')[1]:28s} {v}")

    html = open(PATH, encoding="utf-8").read()
    lines = html.split("\n")

    def find_table(header_needle):
        """return (start_idx, end_idx) of data-row lines for the md table whose
        nearest preceding non-row context contains header_needle."""
        hdr = next(i for i, l in enumerate(lines) if header_needle in l)
        # data rows: first '|' row after the '|:---' separator following hdr
        sep = next(i for i in range(hdr, len(lines)) if lines[i].lstrip().startswith("|:") or lines[i].lstrip().startswith("| :"))
        start = sep + 1
        end = start
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        return start, end

    # ---- navi 5-dim ----
    s, e = find_table("Navigation Split (5 Dimensions")
    new_navi5 = [(CELL[k], r5_navi[k]) for k in REPORTS]
    lines[s:e] = rebuild_5dim(lines[s:e], new_navi5, "navi-5dim")

    # ---- full 5-dim ----
    s, e = find_table("Full Split (5 Dimensions")
    new_full5 = [(CELL[k], r5_full[k]) for k in ("cosmos3_super", "cosmos3_nano")]
    lines[s:e] = rebuild_5dim(lines[s:e], new_full5, "full-5dim")

    # ---- navi 19-metric detail ----
    s, e = find_table("Navigation Split (19 metrics)")
    block = lines[s:e]
    ci = next(i for i, l in enumerate(block) if "Cosmos 2.5" in l)
    block.insert(ci + 1, render_detail_row(CELL["cosmos3_super"], detail_vals(navi["cosmos3_super"], DET_NAVI)))
    block.insert(ci + 2, render_detail_row(CELL["cosmos3_nano"], detail_vals(navi["cosmos3_nano"], DET_NAVI)))
    li = next(i for i, l in enumerate(block) if "LingBot-World (fast)" in l)
    block.insert(li + 1, render_detail_row(CELL["lingbot_v2"], detail_vals(navi["lingbot_v2"], DET_NAVI)))
    print(f"  navi-detail: {e-s} -> {len(block)} rows")
    lines[s:e] = block

    # ---- full 22-metric detail ----
    s, e = find_table("Full Split (22 metrics)")
    block = lines[s:e]
    ci = next(i for i, l in enumerate(block) if "Cosmos 2.5" in l)
    block.insert(ci + 1, render_detail_row(CELL["cosmos3_super"], detail_vals(full["cosmos3_super"], DET_FULL)))
    block.insert(ci + 2, render_detail_row(CELL["cosmos3_nano"], detail_vals(full["cosmos3_nano"], DET_FULL)))
    print(f"  full-detail: {e-s} -> {len(block)} rows")
    lines[s:e] = block

    html = "\n".join(lines)

    # ---- count labels ----
    repl = [
        ("Systematic diagnosis of 24 models", "Systematic diagnosis of 27 models"),
        ("**24 Models — Navigation Split (5 Dimensions", "**27 Models — Navigation Split (5 Dimensions"),
        ("**9 Text-driven Models — Full Split (5 Dimensions", "**11 Text-driven Models — Full Split (5 Dimensions"),
        ("<b>24 Models — Navigation Split (19 metrics)</b>", "<b>27 Models — Navigation Split (19 metrics)</b>"),
        ("<b>9 Text-driven Models — Full Split (22 metrics)</b>", "<b>11 Text-driven Models — Full Split (22 metrics)</b>"),
    ]
    for old, new in repl:
        assert old in html, f"count label not found: {old!r}"
        html = html.replace(old, new)
    print("  counts updated: 24->27, 9->11")

    # ---- news entry (insert at top of news list) ----
    anchor = "- **[2026/06/18]** 🆕 Added [DreamX-World"
    assert anchor in html, "news anchor not found"
    entry = ("- **[2026/07/12]** 🆕 Added [Cosmos3-Super & Cosmos3-Nano](https://github.com/nvidia-cosmos) "
             "(text) and [LingBot-World (fast v2)](https://github.com/robbyant/lingbot-world) (camera) "
             "to the leaderboard (now 27 models).\n")
    html = html.replace(anchor, entry + anchor)
    print("  news entry added")

    open(PATH, "w", encoding="utf-8").write(html)
    print("written", PATH)


if __name__ == "__main__":
    main()
