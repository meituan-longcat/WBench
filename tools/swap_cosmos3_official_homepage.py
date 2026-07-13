#!/usr/bin/env python3
"""Swap Cosmos3-Nano / Cosmos3-Super on the homepage to the *_official reports.

Strategy: strip the two existing Cosmos3 rows from all four tables, then re-add
them with values recomputed from the *_official report.json using the SAME
unified recipe / insertion logic as add_three_models_homepage.py. The 5-dim
tables are re-sorted + rank re-medalled; detail tables are anchor-inserted and
renumbered. LingBot-World v2 is untouched. Counts are unchanged (27/11/10).
"""
import json
import re
from decimal import Decimal, ROUND_HALF_UP

PATH = "homepage/index.html"

REPORTS = {
    "cosmos3_super": "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_super_official/evaluation/report.json",
    "cosmos3_nano":  "/mnt/dolphinfs/ssd_pool/docker/user/hadoop-hldy-nlp/EVA/rensiyu07/sana_wm/WBench/work_dirs/cosmos3_nano_official/evaluation/report.json",
}
META = {
    "cosmos3_super": dict(disp="Cosmos3-Super", type="text", icon="cosmos.png", note=None, creator="NVIDIA · Open Source"),
    "cosmos3_nano":  dict(disp="Cosmos3-Nano",  type="text", icon="cosmos.png", note=None, creator="NVIDIA · Open Source"),
}

Q  = ["aesthetic_quality", "imaging_quality", "temporal_flickering", "dynamic_degree", "motion_smoothness", "hpsv3_quality"]
SET = ["scene_adherence", "subject_adherence"]
CON = ["background_consistency", "spatial_consistency", "gated_spatial_consistency", "perspective_consistency",
       "segment_continuity", "geometric_consistency", "photometric_consistency", "subject_consistency"]
PHY = ["visual_plausibility", "causal_fidelity"]
INT_NAVI = ["navigation_trajectory"]
INT_FULL = ["navigation_trajectory", "event_edit_adherence", "subject_action_adherence", "perspective_switch_adherence"]
DET_NAVI = Q + SET + INT_NAVI + CON + PHY  # 19
DET_FULL = Q + SET + INT_FULL + CON + PHY  # 22


def hu(x): return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
def pct(sec, key): return sec[key]["mean"] * 100.0
def dim(sec, keys): return hu(sum(sec[k]["mean"] for k in keys) / len(keys) * 100.0)


def five_dim(sec, split):
    ik = INT_NAVI if split == "navi" else INT_FULL
    q = dim(sec, Q); s = dim(sec, SET); i = dim(sec, ik); c = dim(sec, CON); p = dim(sec, PHY)
    return [hu(sum([q, s, i, c, p]) / 5.0), q, s, i, c, p]


def detail_vals(sec, order): return [hu(pct(sec, k)) for k in order]
def fmt(v): return f"{v:.1f}"


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
    if i == 0: cell = '<td class="rank-gold">🥇</td>'
    elif i == 1: cell = '<td class="rank-silver">🥈</td>'
    elif i == 2: cell = '<td class="rank-bronze">🥉</td>'
    else: cell = plain_fmt.format(i + 1)
    return RANK_CELL_RE.sub(cell, row, count=1)


def get_tbody(html, tid):
    m = re.search(r'(<table id="' + re.escape(tid) + r'".*?<tbody>)(.*?)(</tbody>)', html, re.S)
    assert m, f"table {tid} not found"
    return m


AVG_RE = re.compile(r'<td class="col-avg">([\d.]+)</td>')


def strip_rows(rows, names):
    """drop <tr> whose model-icon display name is in names."""
    keep = []
    for r in rows:
        nm = re.search(r'model-icon">([^<]*)', r)
        if nm and nm.group(1).strip() in names:
            continue
        keep.append(r)
    return keep


def sortable_table(html, tid, new_rows, plain_fmt, drop):
    m = get_tbody(html, tid)
    head, body, tail = m.group(1), m.group(2), m.group(3)
    rows = re.findall(r'<tr.*?</tr>', body, re.S)
    rows = strip_rows(rows, drop)
    rows.extend(new_rows)
    rows.sort(key=lambda r: float(AVG_RE.search(r).group(1)), reverse=True)
    rows = [set_rank(r, i, plain_fmt) for i, r in enumerate(rows)]
    newbody = ("\n" + "\n".join(rows) + "\n") if body.startswith("\n") else "".join(rows)
    html = html[:m.start()] + head + newbody + tail + html[m.end():]
    top = re.search(r'class="model-icon">([^<]*)', rows[0]).group(1)
    print(f"  {tid}: {len(rows)} rows (sorted); #1 = {top}")
    return html


def detail_table(html, tid, inserts, plain_fmt, drop):
    m = get_tbody(html, tid)
    head, body, tail = m.group(1), m.group(2), m.group(3)
    rows = re.findall(r'<tr.*?</tr>', body, re.S)
    rows = strip_rows(rows, drop)
    for anchor, nr in inserts:
        idx = next(i for i, r in enumerate(rows) if anchor in r)
        rows.insert(idx + 1, nr)
    rows = [set_rank(r, i, plain_fmt) for i, r in enumerate(rows)]
    newbody = ("\n" + "\n".join(rows) + "\n") if body.startswith("\n") else "".join(rows)
    html = html[:m.start()] + head + newbody + tail + html[m.end():]
    print(f"  {tid}: {len(rows)} rows (anchor-insert)")
    return html


def main():
    navi = {k: json.load(open(v))["navi"] for k, v in REPORTS.items()}
    full = {k: json.load(open(v))["full"] for k, v in REPORTS.items()}
    DROP = {"Cosmos3-Super", "Cosmos3-Nano"}

    r5n = {k: five_dim(navi[k], "navi") for k in REPORTS}
    r5f = {k: five_dim(full[k], "full") for k in REPORTS}
    dvn = {k: detail_vals(navi[k], DET_NAVI) for k in REPORTS}
    dvf = {k: detail_vals(full[k], DET_FULL) for k in REPORTS}
    print("=== official 5-dim ===")
    for k in REPORTS: print(f"  navi {META[k]['disp']:14s} {r5n[k]}")
    for k in REPORTS: print(f"  full {META[k]['disp']:14s} {r5f[k]}")

    html = open(PATH, encoding="utf-8").read()

    # navi 5-dim
    navi5 = [make_5dim_row(META[k], r5n[k]) for k in REPORTS]
    html = sortable_table(html, "table-navi", navi5, "<td>{}</td>", DROP)
    # navi detail
    html = detail_table(html, "table-detail", [
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_super"], dvn["cosmos3_super"])),
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_nano"], dvn["cosmos3_nano"])),
    ], '<td class="">{}</td>', DROP)
    # full 5-dim
    full5 = [make_5dim_row(META[k], r5f[k]) for k in REPORTS]
    html = sortable_table(html, "table-full", full5, '<td class="">{}</td>', DROP)
    # full detail
    html = detail_table(html, "table-detail-full", [
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_super"], dvf["cosmos3_super"])),
        ("Cosmos 2.5<br>", make_detail_row(META["cosmos3_nano"], dvf["cosmos3_nano"])),
    ], '<td class="">{}</td>', DROP)

    open(PATH, "w", encoding="utf-8").write(html)
    print("written", PATH)


if __name__ == "__main__":
    main()
