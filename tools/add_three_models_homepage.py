#!/usr/bin/env python3
"""Add Cosmos3-Nano, Cosmos3-Super (text) and LingBot-Fast-v2 (camera) to the
four homepage leaderboard tables, computing every value straight from each
model's evaluation/report.json with the CURRENT unified 5-dim recipe.

Recipe (verified by reproducing Kling's live rows + the 20260713 PDF's
LingBot-Fast-v2 column exactly):
  Quality      = mean(aesthetic, imaging, flickering, dynamic, smoothness, hpsv3)   [no bg]
  Setting      = mean(scene_adherence, subject_adherence)
  Interaction  = navi tables: mean(navigation_trajectory)
                 full tables: mean(navi, event_edit, subject_action, persp_switch)
  Consistency  = mean(bg, spatial, gated_spatial, perspective, segment, geometric,
                       photometric, subject_consistency)                            [with bg]
  Physical     = mean(visual_plausibility, causal_fidelity)
  Overall      = mean(5 dims)
All values = report[split][metric].mean * 100, rounded HALF-UP to 1 dp.

navi tables get all 3 models; full tables (text-only) get the 2 Cosmos3 models.
Sortable 5-dim tables are re-sorted by col-avg + re-medalled; detail tables are
non-sorted (rows inserted at an anchor, then renumbered sequentially).
"""
import json
import re
from decimal import Decimal, ROUND_HALF_UP

PATH = "homepage/index.html"

REPORTS = {
    "cosmos3_super": "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_super/evaluation/report.json",
    "cosmos3_nano":  "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_nano/evaluation/report.json",
    "lingbot_v2":    "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/lingbot_world_v2_fast/evaluation/report.json",
}

META = {
    "cosmos3_super": dict(disp="Cosmos3-Super", type="text",   icon="cosmos.png",  note=None,      creator="NVIDIA · Open Source"),
    "cosmos3_nano":  dict(disp="Cosmos3-Nano",  type="text",   icon="cosmos.png",  note=None,      creator="NVIDIA · Open Source"),
    "lingbot_v2":    dict(disp="LingBot-World", type="camera", icon="lingbot.png", note="fast v2", creator="Ant Group · Open Source"),
}

# report.json metric keys
Q  = ["aesthetic_quality", "imaging_quality", "temporal_flickering", "dynamic_degree", "motion_smoothness", "hpsv3_quality"]
SET = ["scene_adherence", "subject_adherence"]
CON = ["background_consistency", "spatial_consistency", "gated_spatial_consistency", "perspective_consistency",
       "segment_continuity", "geometric_consistency", "photometric_consistency", "subject_consistency"]
PHY = ["visual_plausibility", "causal_fidelity"]
INT_NAVI = ["navigation_trajectory"]
INT_FULL = ["navigation_trajectory", "event_edit_adherence", "subject_action_adherence", "perspective_switch_adherence"]

# homepage detail column orders
DET_NAVI = Q + SET + INT_NAVI + CON + PHY  # 19
DET_FULL = Q + SET + INT_FULL + CON + PHY  # 22


def hu(x):
    """half-up round to 1 dp, return float-ish string like 79.4 / 100.0"""
    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def pct(sec, key):
    return sec[key]["mean"] * 100.0


def dim(sec, keys):
    return hu(sum(sec[key]["mean"] for key in keys) / len(keys) * 100.0)


def five_dim(sec, split):
    int_keys = INT_NAVI if split == "navi" else INT_FULL
    q = dim(sec, Q); s = dim(sec, SET); i = dim(sec, int_keys); c = dim(sec, CON); p = dim(sec, PHY)
    avg = hu(sum([q, s, i, c, p]) / 5.0)
    return [avg, q, s, i, c, p]


def detail_vals(sec, order):
    return [hu(pct(sec, k)) for k in order]


def fmt(v):
    # 100.0 -> "100.0", 79.4 -> "79.4"
    return f"{v:.1f}"


def model_cell(m):
    note = f'<span class="model-note">{m["note"]}</span><br>' if m["note"] else ""
    return (f'<td><img src="imgs/{m["icon"]}" class="model-icon">{m["disp"]}<br>'
            f'{note}<span class="creator">{m["creator"]}</span></td>')


def make_5dim_row(m, vals):
    tds = "".join(f"<td>{fmt(v)}</td>" for v in vals[1:])
    return (f'<tr data-model-type="{m["type"]}"><td>RANK</td>{model_cell(m)}'
            f'<td class="col-avg">{fmt(vals[0])}</td>{tds}</tr>')


def make_detail_row(m, vals):
    tds = "".join(f"<td>{fmt(v)}</td>" for v in vals)
    return f'<tr data-model-type="{m["type"]}"><td class="">RANK</td>{model_cell(m)}{tds}</tr>'


RANK_CELL_RE = re.compile(r'<td[^>]*>(?:🥇|🥈|🥉|RANK|\d+)</td>')


def set_rank(row, i, plain_fmt):
    if i == 0:
        cell = '<td class="rank-gold">🥇</td>'
    elif i == 1:
        cell = '<td class="rank-silver">🥈</td>'
    elif i == 2:
        cell = '<td class="rank-bronze">🥉</td>'
    else:
        cell = plain_fmt.format(i + 1)
    return RANK_CELL_RE.sub(cell, row, count=1)


def get_tbody(html, tid):
    m = re.search(r'(<table id="' + re.escape(tid) + r'".*?<tbody>)(.*?)(</tbody>)', html, re.S)
    assert m, f"table {tid} not found"
    return m


AVG_RE = re.compile(r'<td class="col-avg">([\d.]+)</td>')


def sortable_table(html, tid, new_rows, plain_fmt):
    m = get_tbody(html, tid)
    head, body, tail = m.group(1), m.group(2), m.group(3)
    rows = re.findall(r'<tr.*?</tr>', body, re.S)
    n0 = len(rows)
    rows.extend(new_rows)
    rows.sort(key=lambda r: float(AVG_RE.search(r).group(1)), reverse=True)
    rows = [set_rank(r, i, plain_fmt) for i, r in enumerate(rows)]
    newbody = ("\n" + "\n".join(rows) + "\n") if body.startswith("\n") else "".join(rows)
    html = html[:m.start()] + head + newbody + tail + html[m.end():]
    top = re.search(r'class="model-icon">([^<]*)', rows[0]).group(1)
    print(f"  {tid}: {n0} -> {len(rows)} rows (sorted); #1 = {top}")
    return html


def detail_table(html, tid, inserts, plain_fmt):
    """inserts: list of (anchor_substr, row). Rows inserted right after the row
    matching anchor_substr, in the given order; then all rows renumbered."""
    m = get_tbody(html, tid)
    head, body, tail = m.group(1), m.group(2), m.group(3)
    rows = re.findall(r'<tr.*?</tr>', body, re.S)
    n0 = len(rows)
    for anchor, nr in inserts:
        idx = next(i for i, r in enumerate(rows) if anchor in r)
        rows.insert(idx + 1, nr)
    rows = [set_rank(r, i, plain_fmt) for i, r in enumerate(rows)]
    newbody = ("\n" + "\n".join(rows) + "\n") if body.startswith("\n") else "".join(rows)
    html = html[:m.start()] + head + newbody + tail + html[m.end():]
    print(f"  {tid}: {n0} -> {len(rows)} rows (anchor-insert)")
    return html


def main():
    secs = {k: json.load(open(v))["navi"] for k, v in REPORTS.items()}, \
           {k: json.load(open(v))["full"] for k, v in REPORTS.items()}
    navi_secs, full_secs = secs

    print("=== computed values ===")
    rows5_navi, detrows_navi = {}, {}
    for k in REPORTS:
        rows5_navi[k] = five_dim(navi_secs[k], "navi")
        detrows_navi[k] = detail_vals(navi_secs[k], DET_NAVI)
        print(f"{META[k]['disp']:15s} navi 5dim {rows5_navi[k]}")
    rows5_full, detrows_full = {}, {}
    for k in ("cosmos3_super", "cosmos3_nano"):
        rows5_full[k] = five_dim(full_secs[k], "full")
        detrows_full[k] = detail_vals(full_secs[k], DET_FULL)
        print(f"{META[k]['disp']:15s} full 5dim {rows5_full[k]}")

    html = open(PATH, encoding="utf-8").read()

    # ---- navi tables: all 3 models ----
    navi5 = [make_5dim_row(META[k], rows5_navi[k]) for k in REPORTS]
    html = sortable_table(html, "table-navi", navi5, "<td>{}</td>")
    html = detail_table(html, "table-detail", [
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_super"], detrows_navi["cosmos3_super"])),
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_nano"], detrows_navi["cosmos3_nano"])),
        ('model-note">fast<', make_detail_row(META["lingbot_v2"], detrows_navi["lingbot_v2"])),
    ], '<td class="">{}</td>')

    # ---- full tables: 2 Cosmos3 (text) ----
    full5 = [make_5dim_row(META[k], rows5_full[k]) for k in ("cosmos3_super", "cosmos3_nano")]
    html = sortable_table(html, "table-full", full5, '<td class="">{}</td>')
    html = detail_table(html, "table-detail-full", [
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_super"], detrows_full["cosmos3_super"])),
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_nano"], detrows_full["cosmos3_nano"])),
    ], '<td class="">{}</td>')

    # ---- filter counts: All 24->27, Text 9->11, Camera 9->10 ----
    for old, new in [(">All<br><small>(24)</small>", ">All<br><small>(27)</small>"),
                     (">Text<br><small>(9)</small>", ">Text<br><small>(11)</small>"),
                     (">Camera<br><small>(9)</small>", ">Camera<br><small>(10)</small>")]:
        assert old in html, f"count label not found: {old}"
        html = html.replace(old, new)
    print("  counts: All 24->27, Text 9->11, Camera 9->10")

    open(PATH, "w", encoding="utf-8").write(html)
    print("written", PATH)


if __name__ == "__main__":
    main()
