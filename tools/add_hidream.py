#!/usr/bin/env python3
"""Add HiDream-O1-World (camera-conditioned, HiDream.ai) to README + homepage.

Values come from the submission repo's report.json (self-reported, navi split,
158 cases — same case sets as Lyra/SANA/ABot). Also syncs the homepage to the
README's current state: refreshed navigation_trajectory column + AlayaWorld,
which had only landed in the README.

README  : 29 -> 30 models. homepage: 28 -> 30 models.
"""
import json
import re
from decimal import Decimal, ROUND_HALF_UP

README = "README.md"
HOMEPAGE = "homepage/index.html"
MEDALS = ["🥇", "🥈", "🥉"]
PAD = "&nbsp;&nbsp;"
NUM = re.compile(r'-?[\d.]+')

# README detail column order
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

HIDREAM = {"name": "HiDream-O1-World", "icon": "hidream.png", "type": "camera",
           "creator": "HiDream.ai",
           "det": dict(zip(RD, [65.6, 69.9, 93.7, 91.8, 88.6, 97.2, 78.1, 71.9, 91.9, 79.5,
                                84.8, 83.1, 83.6, 98.7, 88.9, 78.4, 92.6, 62.5, 81.7])),
           "dims": [80.7, 81.9, 81.9, 79.5, 88.0, 72.1]}
ALAYA = {"name": "AlayaWorld", "icon": "alayaworld.png", "type": "camera", "creator": "Alaya Lab · Open Source",
         "det": dict(zip(RD, [64.5, 67.3, 95.7, 96.1, 13.3, 98.6, 61.4, 52.0, 79.6, 73.9,
                              94.3, 63.0, 80.7, 99.4, 96.8, 87.7, None, 63.6, 76.7])),
         "dims": [73.0, 66.9, 65.8, 73.9, 88.2, 70.1]}


def hu(x): return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
def fmt(v): return f"{v:.1f}"
def key(c): return re.sub(r'<img[^>]*>', '', c).strip()
def cells(l): return [c.strip() for c in l.strip().strip("|").split("|")]
def num(c):
    m = NUM.search(c)
    return float(m.group()) if m else None


def medals(vals):
    order = sorted(range(len(vals)), key=lambda i: (-vals[i], i))
    return {i: MEDALS[r] for r, i in enumerate(order[:3])}


# ── README ────────────────────────────────────────────────────────────────────

def md_table(lines, needle):
    h = next(i for i, l in enumerate(lines) if needle in l)
    sep = next(i for i in range(h, len(lines)) if lines[i].lstrip().startswith("|:"))
    s = sep + 1
    e = s
    while e < len(lines) and lines[e].lstrip().startswith("|"):
        e += 1
    return sep - 1, s, e


def update_readme():
    lines = open(README, encoding="utf-8").read().split("\n")
    assert "HiDream" not in "\n".join(lines), "HiDream already in README"

    cell = f'<img src="assets/icon/{HIDREAM["icon"]}" height="18"> {HIDREAM["name"]}'

    # detail table: append row
    hi, s, e = md_table(lines, "Navigation Split (19 metrics)")
    cols = cells(lines[hi])[1:]
    assert cols == RD, f"README detail columns differ: {cols}"
    vals = [HIDREAM["det"][c] for c in RD]
    lines[s:e] = list(lines[s:e]) + [
        "| " + cell + " | " + " | ".join(("—" if v is None else fmt(v)) + f" {PAD}" for v in vals) + " |"]
    print(f"  README detail: {e - s + 1} rows")

    # 5-dim table: insert + re-sort + re-medal
    hi5, s5, e5 = md_table(lines, "Navigation Split (5 Dimensions")
    rows = []
    for l in lines[s5:e5]:
        c = cells(l)
        rows.append((c[1], [num(x) for x in c[2:8]]))
    rows.append((cell, HIDREAM["dims"]))
    old_rank = {key(m): i + 1 for i, (m, _) in enumerate(rows)}
    rows.sort(key=lambda r: -r[1][0])
    ct = list(zip(*[r[1] for r in rows]))
    cm = [medals(list(ct[j])) for j in range(6)]
    out = []
    for i, (m, v) in enumerate(rows):
        mm = [cm[j].get(i, "") for j in range(6)]
        a = f"**{fmt(v[0])} {mm[0]}**" if mm[0] else f"**{fmt(v[0])}** {PAD}"
        out.append(f"| {i+1} | {m} | " + " | ".join(
            [a] + [f"{fmt(v[j])} {mm[j]}" if mm[j] else f"{fmt(v[j])} {PAD}" for j in range(1, 6)]) + " |")
    lines[s5:e5] = out
    rank = next(i + 1 for i, (m, _) in enumerate(rows) if "HiDream" in m)
    print(f"  README 5dim: {len(out)} rows; HiDream at rank {rank}")

    text = "\n".join(lines)
    for a, b in [("29 video world models", "30 video world models"),
                 ("Systematic diagnosis of 29 models", "Systematic diagnosis of 30 models"),
                 ("**29 Models — Navigation Split (5 Dimensions, sorted by average)**",
                  "**30 Models — Navigation Split (5 Dimensions, sorted by average)**"),
                 ("<b>29 Models — Navigation Split (19 metrics)</b>",
                  "<b>30 Models — Navigation Split (19 metrics)</b>")]:
        assert a in text, f"README: not found {a!r}"
        text = text.replace(a, b)
    open(README, "w", encoding="utf-8").write(text)
    return {k: (old_rank.get(k), i + 1) for i, (m, _) in enumerate(rows) for k in [key(m)]}


# ── homepage ──────────────────────────────────────────────────────────────────

RANK_CELL = re.compile(r'<td[^>]*>(?:🥇|🥈|🥉|RANK|\d+)</td>')


def set_rank(row, i, plain):
    cell = ('<td class="rank-gold">🥇</td>' if i == 0 else
            '<td class="rank-silver">🥈</td>' if i == 1 else
            '<td class="rank-bronze">🥉</td>' if i == 2 else plain.format(i + 1))
    return RANK_CELL.sub(cell, row, count=1)


def tbody(html, tid):
    m = re.search(r'(<table id="' + re.escape(tid) + r'".*?<tbody>)(.*?)(</tbody>)', html, re.S)
    assert m, f"table {tid} not found"
    return m


def model_cell(mdl):
    icon = f'<img src="imgs/{mdl["icon"]}" class="model-icon">' if mdl["icon"] else ""
    return f'<td>{icon}{mdl["name"]}<br><span class="creator">{mdl["creator"]}</span></td>'


def row_name(r):
    """homepage renders "Name" + optional <span class="model-note">, the README
    writes them as "Name (note)" — rebuild the README form so the two match."""
    tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
    cell = tds[1]
    n = re.sub(r'<br>.*', '', cell, flags=re.S)
    n = re.sub(r'<[^>]+>', '', n).strip()
    note = re.search(r'model-note">(.*?)<', cell)
    return f"{n} ({note.group(1)})" if note else n


def update_homepage(readme_nav, readme_dims):
    html = open(HOMEPAGE, encoding="utf-8").read()
    assert "HiDream" not in html, "HiDream already in homepage"

    # detail: sync navigation column from README, then append the two new rows
    m = tbody(html, "table-detail")
    head, body, tail = m.group(1), m.group(2), m.group(3)
    rows = re.findall(r'<tr.*?</tr>', body, re.S)
    ni = HD.index("Navigation Trajectory")
    synced = 0
    out = []
    for r in rows:
        nm = row_name(r)
        nav = readme_nav.get(nm)
        assert nav is not None, f"homepage detail 行未匹配 README: {nm}"
        tds = re.findall(r'<td[^>]*>.*?</td>', r, re.S)
        old = num(re.sub(r'<[^>]+>', '', tds[2 + ni]))
        if old != nav:
            tds[2 + ni] = f"<td>{fmt(nav)}</td>"
            synced += 1
        out.append(re.match(r'<tr[^>]*>', r).group(0) + "".join(tds) + "</tr>")
    for mdl in (ALAYA, HIDREAM):
        vals = [mdl["det"][c] for c in HD]
        out.append(f'<tr data-model-type="{mdl["type"]}"><td class="">RANK</td>{model_cell(mdl)}'
                   + "".join(f"<td>{'—' if v is None else fmt(v)}</td>" for v in vals) + "</tr>")
    out = [set_rank(r, i, '<td class="">{}</td>') for i, r in enumerate(out)]
    nb = ("\n" + "\n".join(out) + "\n") if body.startswith("\n") else "".join(out)
    html = html[:m.start()] + head + nb + tail + html[m.end():]
    print(f"  homepage detail: {len(out)} rows ({synced} nav 值同步)")

    # navi 5-dim: rebuild every row's dims from the README, then insert the new two
    m = tbody(html, "table-navi")
    head, body, tail = m.group(1), m.group(2), m.group(3)
    rows = re.findall(r'<tr.*?</tr>', body, re.S)
    rebuilt, synced = [], 0
    for r in rows:
        nm = row_name(r)
        dims = readme_dims.get(nm)
        tds = re.findall(r'<td[^>]*>.*?</td>', r, re.S)
        assert dims is not None, f"homepage navi 行未匹配 README: {nm}"
        cur = [num(re.sub(r'<[^>]+>', '', t)) for t in tds[2:8]]
        if cur != dims:
            synced += 1
        new = (re.match(r'<tr[^>]*>', r).group(0) + tds[0] + tds[1]
               + f'<td class="col-avg">{fmt(dims[0])}</td>'
               + "".join(f"<td>{fmt(v)}</td>" for v in dims[1:]) + "</tr>")
        rebuilt.append((new, dims[0]))
    for mdl in (ALAYA, HIDREAM):
        d = mdl["dims"]
        rebuilt.append((f'<tr data-model-type="{mdl["type"]}"><td>RANK</td>{model_cell(mdl)}'
                        f'<td class="col-avg">{fmt(d[0])}</td>'
                        + "".join(f"<td>{fmt(v)}</td>" for v in d[1:]) + "</tr>", d[0]))
    rebuilt.sort(key=lambda x: -x[1])
    out = [set_rank(r, i, "<td>{}</td>") for i, (r, _) in enumerate(rebuilt)]
    nb = ("\n" + "\n".join(out) + "\n") if body.startswith("\n") else "".join(out)
    html = html[:m.start()] + head + nb + tail + html[m.end():]
    rank = next(i + 1 for i, r in enumerate(out) if "HiDream" in r)
    print(f"  homepage navi: {len(out)} rows ({synced} 行同步); HiDream at rank {rank}")

    before = html
    html = html.replace('<div class="stat-num">28</div><div class="stat-title">Models</div>',
                        '<div class="stat-num">30</div><div class="stat-title">Models</div>')
    html = html.replace("evaluating 28 models with 22 metrics",
                        "evaluating 30 models with 22 metrics")
    assert html != before, "homepage: count replacement failed"
    open(HOMEPAGE, "w", encoding="utf-8").write(html)


def main():
    import sys
    skip_readme = "--homepage-only" in sys.argv
    ranks = {}
    if skip_readme:
        print("README: 跳过（已完成）")
    else:
        print("README:")
        ranks = update_readme()

    # re-read the README as the single source of truth for the homepage
    lines = open(README, encoding="utf-8").read().split("\n")
    hi, s, e = md_table(lines, "Navigation Split (19 metrics)")
    ni = RD.index("Navigation Trajectory")
    nav = {}
    for l in lines[s:e]:
        c = cells(l)
        nav[key(c[0])] = num(c[1:][ni])
    hi5, s5, e5 = md_table(lines, "Navigation Split (5 Dimensions")
    dims = {}
    for l in lines[s5:e5]:
        c = cells(l)
        dims[key(c[1])] = [num(x) for x in c[2:8]]

    # one model is shortened differently on the homepage
    ALIAS = {"LingBot-World v2 (fast)": "LingBot-World (fast v2)"}
    for k, v in ALIAS.items():
        assert v in nav, f"alias target missing: {v}"
        nav[k], dims[k] = nav[v], dims[v]

    print("homepage:")
    update_homepage(nav, dims)

    print("\n名次变化 (README):")
    for k, (o, n) in sorted(ranks.items(), key=lambda x: x[1][1]):
        if o != n:
            print(f"  {k:32s} {o if o else '新':>3} -> {n}")


if __name__ == "__main__":
    main()
