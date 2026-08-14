#!/usr/bin/env python3
"""Add Alaya-EVOKE (camera-conditioned, Alaya Lab) to README + homepage.

Scores from Alaya Lab's submission (self-reported, navi split, 158 cases —
same per-metric case sets as the other models). EVOKE enters at rank 1 with a
5-dimension average of 80.8, taking the Quality crown (82.8) and tying
Physical (72.1) with HiDream-O1-World (tie broken by table order).

README  : 30 -> 31 models. homepage: 30 -> 31 models.
"""
import re
from decimal import Decimal, ROUND_HALF_UP

README = "README.md"
HOMEPAGE = "homepage/index.html"
MEDALS = ["🥇", "🥈", "🥉"]

# README detail column order (BgCon sits before Flick)
RD = ["Aesthetic Quality", "Imaging Quality", "Background Consistency", "Temporal Flickering",
      "Dynamic Degree", "Motion Smoothness", "HPSv3 Quality", "Scene Adherence", "Subject Adherence",
      "Navigation Trajectory", "Spatial Consistency", "Gated Spatial Consistency",
      "Perspective Consistency", "Segment Continuity", "Geometric Consistency",
      "Photometric Consistency", "Subject Consistency Cross-Model", "Visual Plausibility",
      "Causal Fidelity"]
# homepage detail column order (BgCon sits after Navi)
HD = ["Aesthetic Quality", "Imaging Quality", "Temporal Flickering", "Dynamic Degree",
      "Motion Smoothness", "HPSv3 Quality", "Scene Adherence", "Subject Adherence",
      "Navigation Trajectory", "Background Consistency", "Spatial Consistency",
      "Gated Spatial Consistency", "Perspective Consistency", "Segment Continuity",
      "Geometric Consistency", "Photometric Consistency", "Subject Consistency Cross-Model",
      "Visual Plausibility", "Causal Fidelity"]

# 2-decimal source values from the submission report (navi split).
EVOKE = {"name": "Alaya-EVOKE", "icon": "alayaworld.png", "type": "camera",
         "creator": "Alaya Lab · Open Source",
         "det": dict(zip(RD, [66.12, 67.86, 92.27, 94.31, 96.84, 97.86, 73.75, 74.68, 92.84, 78.63,
                              84.26, 82.45, 69.74, 100.00, 92.68, 82.53, 91.03, 61.67, 82.44])),
         "dims": [80.821, 82.790, 83.760, 78.630, 86.870, 72.055]}  # avg + 5 dims


def hu(x):
    """Round half-up to 1 decimal (matches add_hidream.py)."""
    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def fmt(v):
    return f"{v:.1f}"


# ── README ────────────────────────────────────────────────────────────────────

NUM = re.compile(r"([\d.]+)")
VAL_CELL = re.compile(r"([\d.]+)(?:\s*(🥇|🥈|🥉))?\s*$")


def parse_dims_row(line):
    """README 5-dim row -> (model_cell, [avg, q, s, i, c, p])."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    model_cell = cells[1]
    vals = []
    for cell in cells[2:]:
        cell = cell.replace("**", "").replace("&nbsp;", "")
        m = VAL_CELL.search(cell)
        vals.append(float(m.group(1)) if m else None)
    return model_cell, vals


def build_dims_row(rank, model_cell, vals, medals, row_i):
    """Rebuild one README 5-dim row: rank, model, bold avg (+medal), 5 dims (+medal)."""
    avg_pos = medals[0].get(row_i)
    avg_cell = f"**{fmt(vals[0])} {MEDALS[avg_pos]}**" if avg_pos is not None else f"**{fmt(vals[0])}**"
    cells = []
    for c in range(1, 6):
        pos = medals[c].get(row_i)
        cells.append(f"{fmt(vals[c])} {MEDALS[pos]}" if pos is not None
                     else f"{fmt(vals[c])} &nbsp;&nbsp;")
    return f"| {rank} | {model_cell} | {avg_cell} | " + " | ".join(cells) + " |"


def medals_for(values):
    """Per-column top-3 medal positions (stable by row index on ties)."""
    n = len(values)
    cols = len(values[0])
    medals = [{} for _ in range(cols)]
    for c in range(cols):
        order = sorted(range(n), key=lambda i: (-values[i][c], i))
        for pos, i in enumerate(order[:3]):
            medals[c][i] = pos
    return medals


def update_readme():
    text = open(README, encoding="utf-8").read()
    assert "Alaya-EVOKE" not in text, "Alaya-EVOKE already in README"

    # ── 5-dim table: parse, insert, re-sort, re-medal ──
    m = re.search(r"(\*\*30 Models — Navigation Split \(5 Dimensions[^\n]*\n\n)"
                  r"(\| # \|[^\n]*\n\|[^\n]*\n)(.*?)(\n\n)", text, re.S)
    assert m, "5-dim table header not found"
    head, sep, body, tail = m.groups()
    rows = [l for l in body.split("\n") if l.startswith("| ")]
    assert len(rows) == 30, f"expected 30 rows, got {len(rows)}"

    models = [parse_dims_row(l) for l in rows]
    models.append((f'<img src="assets/icon/{EVOKE["icon"]}" height="18"> {EVOKE["name"]}',
                   [hu(v) for v in EVOKE["dims"]]))
    models.sort(key=lambda mc: -mc[1][0])  # stable by avg desc

    meds = medals_for([v for _, v in models])
    new_rows = [build_dims_row(i + 1, mc, v, meds, i) for i, (mc, v) in enumerate(models)]
    text = text[:m.start()] + head.replace("30 Models", "31 Models") + sep + "\n".join(new_rows) + tail + text[m.end():]

    # ── 19-metric detail table: append row ──
    detail_cell = f'<img src="assets/icon/{EVOKE["icon"]}" height="18"> {EVOKE["name"]}'
    det_vals = [hu(EVOKE["det"][k]) for k in RD]
    det_row = "| " + detail_cell + " | " + " | ".join(f"{v:.1f} &nbsp;&nbsp;" for v in det_vals) + " |"
    m2 = re.search(r"(<summary><b>30 Models — Navigation Split \(19 metrics\)</b></summary>\n\n"
                   r"(?:\|[^\n]*\n)+)", text)
    assert m2, "19-metric detail table not found"
    text = text[:m2.start()] + m2.group(1).replace("30 Models", "31 Models") + det_row + "\n" + text[m2.end():]

    # ── News ──
    news = ("- **[2026/08/14]** 🆕 Added [Alaya-EVOKE](https://evoke-world.github.io/Evoke) "
            "🥇 (Alaya Lab, camera-conditioned) to the leaderboard (now 31 models).\n")
    text = text.replace("## 📢 News\n\n", "## 📢 News\n\n" + news, 1)

    open(README, "w", encoding="utf-8").write(text)
    print("README updated")


# ── homepage ──────────────────────────────────────────────────────────────────

def parse_html_rows(body, dims_table):
    """tbody -> list of (type, name_cell, [values]) keeping original cell HTML."""
    rows = re.findall(r'<tr data-model-type="([^"]*)">(.*?)</tr>', body, re.S)
    out = []
    for mtype, inner in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', inner, re.S)
        # tds[0] = rank cell, tds[1] = name cell, rest = values
        name_cell = tds[1]
        vals = []
        for td in tds[2:]:
            mnum = NUM.search(td)
            vals.append(float(mnum.group(1)) if mnum else None)
        out.append((mtype, name_cell, vals))
    return out


def build_html_row(mtype, name_cell, vals, rank, dims_table):
    if rank == 0:
        rank_cell = '<td class="rank-gold">🥇</td>'
    elif rank == 1:
        rank_cell = '<td class="rank-silver">🥈</td>'
    elif rank == 2:
        rank_cell = '<td class="rank-bronze">🥉</td>'
    else:
        rank_cell = f'<td>{rank + 1}</td>' if dims_table else f'<td class="">{rank + 1}</td>'
    vcells = []
    for i, v in enumerate(vals):
        vcells.append(f'<td class="col-avg">{fmt(v)}</td>' if dims_table and i == 0
                      else f'<td>{"—" if v is None else fmt(v)}</td>')
    return (f'<tr data-model-type="{mtype}">{rank_cell}<td>{name_cell}</td>'
            + "".join(vcells) + "</tr>")


def update_homepage():
    html = open(HOMEPAGE, encoding="utf-8").read()
    assert "Alaya-EVOKE" not in html, "Alaya-EVOKE already in homepage"

    # ── table-navi (5 dims) ──
    m = re.search(r'(<table id="table-navi">.*?<tbody>)(.*?)(</tbody>)', html, re.S)
    head, body, tail = m.groups()
    models = parse_html_rows(body, True)
    assert len(models) == 30, f"table-navi expected 30 rows, got {len(models)}"
    evoke_name = f'<img src="imgs/{EVOKE["icon"]}" class="model-icon">{EVOKE["name"]}<br><span class="creator">{EVOKE["creator"]}</span>'
    models.append((EVOKE["type"], evoke_name, [hu(v) for v in EVOKE["dims"]]))
    models.sort(key=lambda mc: -mc[2][0])
    new_rows = [build_html_row(t, nc, v, i, True) for i, (t, nc, v) in enumerate(models)]
    html = html[:m.start()] + head + "\n" + "\n".join(new_rows) + "\n" + tail + html[m.end():]

    # ── table-detail (19 metrics) — same model order as table-navi ──
    m2 = re.search(r'(<table id="table-detail">.*?<tbody>)(.*?)(</tbody>)', html, re.S)
    head2, body2, tail2 = m2.groups()
    det_models = parse_html_rows(body2, False)
    assert len(det_models) == 30, f"table-detail expected 30 rows, got {len(det_models)}"
    by_name = {re.sub(r"<[^>]*>", "", nc).strip(): (t, nc, v) for t, nc, v in det_models}
    ordered = []
    for t, nc, v in models:  # models now sorted by avg
        key = re.sub(r"<[^>]*>", "", nc).strip()
        if EVOKE["name"] in key:
            det_vals = [hu(EVOKE["det"][k]) for k in HD]
            ordered.append((EVOKE["type"], nc, det_vals))
        else:
            assert key in by_name, f"model {key} missing from table-detail"
            ordered.append(by_name[key])
    new_det_rows = [build_html_row(t, nc, v, i, False) for i, (t, nc, v) in enumerate(ordered)]
    html = html[:m2.start()] + head2 + "".join(new_det_rows) + tail2 + html[m2.end():]

    # ── filter counts + TL;DR ──
    html = html.replace(">All<br><small>(27)</small>", ">All<br><small>(31)</small>")
    html = html.replace("Camera<br><small>(10)</small>", "Camera<br><small>(13)</small>")
    html = html.replace("Action<br><small>(6)</small>", "Action<br><small>(7)</small>")
    html = html.replace("evaluating 30 models", "evaluating 31 models")

    open(HOMEPAGE, "w", encoding="utf-8").write(html)
    print("homepage updated")


if __name__ == "__main__":
    update_readme()
    update_homepage()
