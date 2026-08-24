#!/usr/bin/env python3
"""Add JoyAI-Echo-1.5 (WM)'s 2026-08-24 Navi submission to the leaderboard.

The submission contains 158 navigation cases only. Source metric means are
embedded at their reported precision, then aggregated with the leaderboard's
current five-dimension formula and rounded half-up to one decimal for display.
"""

import re
import sys
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.add_alaya_evoke import (  # noqa: E402
    HD,
    RD,
    build_dims_row,
    build_html_row,
    medals_for,
    parse_dims_row,
    parse_html_rows,
)


README = ROOT / "README.md"
HOMEPAGE = ROOT / "homepage/index.html"
MODEL_NAME = "JoyAI-Echo-1.5 (WM)"
MODEL_TYPE = "action"
CREATOR = "JD Future Academy · JD"
ICON = "jd.png"

# Scores are percentages converted from report.json's Navi means.
DETAIL = {
    "Aesthetic Quality": 63.56,
    "Imaging Quality": 66.31,
    "Background Consistency": 93.89,
    "Temporal Flickering": 92.87,
    "Dynamic Degree": 98.73,
    "Motion Smoothness": 97.34,
    "HPSv3 Quality": 70.12,
    "Scene Adherence": 66.01,
    "Subject Adherence": 92.70,
    "Navigation Trajectory": 86.56,
    "Spatial Consistency": 90.65,
    "Gated Spatial Consistency": 83.81,
    "Perspective Consistency": 84.10,
    "Segment Continuity": 99.37,
    "Geometric Consistency": 93.60,
    "Photometric Consistency": 82.52,
    "Subject Consistency Cross-Model": 90.21,
    "Visual Plausibility": 60.81,
    "Causal Fidelity": 80.40,
}

DIMENSION_KEYS = {
    "quality": [
        "Aesthetic Quality",
        "Imaging Quality",
        "Temporal Flickering",
        "Dynamic Degree",
        "Motion Smoothness",
        "HPSv3 Quality",
    ],
    "setting": ["Scene Adherence", "Subject Adherence"],
    "interaction": ["Navigation Trajectory"],
    "consistency": [
        "Background Consistency",
        "Spatial Consistency",
        "Gated Spatial Consistency",
        "Perspective Consistency",
        "Segment Continuity",
        "Geometric Consistency",
        "Photometric Consistency",
        "Subject Consistency Cross-Model",
    ],
    "physical": ["Visual Plausibility", "Causal Fidelity"],
}


def mean(values):
    return sum(values) / len(values)


def round_half_up(value):
    return float(
        Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    )


def dimensions():
    dims = [mean([DETAIL[key] for key in DIMENSION_KEYS[name]])
            for name in (
                "quality", "setting", "interaction", "consistency", "physical"
            )]
    return [mean(dims), *dims]


def replace_once(text, old, new, label):
    count = text.count(old)
    assert count == 1, f"{label}: expected one occurrence, got {count}"
    return text.replace(old, new, 1)


def model_name(name_cell):
    first_line = name_cell.split("<br>", 1)[0]
    name = re.sub(r"<[^>]+>", "", first_line).strip()
    note = re.search(r'class="model-note">(.*?)<', name_cell)
    return f"{name} ({note.group(1)})" if note else name


def update_readme():
    text = README.read_text(encoding="utf-8")
    assert MODEL_NAME not in text, f"{MODEL_NAME} is already in README"

    table = re.search(
        r"(\*\*31 Models — Navigation Split \(5 Dimensions[^\n]*\n\n)"
        r"(\| # \|[^\n]*\n\|[^\n]*\n)(.*?)(\n\n)",
        text,
        re.S,
    )
    assert table, "README navigation dimension table not found"
    head, header, body, tail = table.groups()
    models = [parse_dims_row(line) for line in body.splitlines()
              if line.startswith("| ")]
    assert len(models) == 31, f"expected 31 README models, got {len(models)}"

    model_cell = f'<img src="assets/icon/{ICON}" height="18"> {MODEL_NAME}'
    models.append((model_cell, [round_half_up(value) for value in dimensions()]))
    models.sort(key=lambda item: -item[1][0])
    medals = medals_for([values for _, values in models])
    rows = [build_dims_row(index + 1, cell, values, medals, index)
            for index, (cell, values) in enumerate(models)]
    text = (text[:table.start()] + head.replace("31 Models", "32 Models")
            + header + "\n".join(rows) + tail + text[table.end():])

    detail = re.search(
        r"(<summary><b>31 Models — Navigation Split \(19 metrics\)</b>"
        r"</summary>\n\n(?:\|[^\n]*\n)+)",
        text,
    )
    assert detail, "README navigation detail table not found"
    detail_values = [round_half_up(DETAIL[key]) for key in RD]
    detail_row = (
        f'| <img src="assets/icon/{ICON}" height="18"> {MODEL_NAME} | '
        + " | ".join(f"{value:.1f} &nbsp;&nbsp;" for value in detail_values)
        + " |\n"
    )
    detail_block = detail.group(1).replace("31 Models", "32 Models") + detail_row
    text = text[:detail.start()] + detail_block + text[detail.end():]

    news = (
        "- **[2026/08/24]** 🆕 Added JoyAI-Echo-1.5 (WM): **81.6**, #1 · "
        "thanks [@franklinz233](https://github.com/franklinz233).\n"
    )
    text = replace_once(text, "## 📢 News\n\n", "## 📢 News\n\n" + news,
                        "README news")
    text = replace_once(text, "WBench evaluates 31 video world models",
                        "WBench evaluates 32 video world models", "README TL;DR")
    text = replace_once(text, "Systematic diagnosis of 31 models",
                        "Systematic diagnosis of 32 models", "README contribution")

    README.write_text(text, encoding="utf-8")


def update_homepage():
    html = HOMEPAGE.read_text(encoding="utf-8")
    assert MODEL_NAME not in html, f"{MODEL_NAME} is already in homepage"

    full_tables = {
        table_id: re.search(
            rf'<table id="{table_id}">.*?</table>', html, re.S
        ).group(0)
        for table_id in ("table-full", "table-detail-full")
    }

    table = re.search(
        r'(<table id="table-navi">.*?<tbody>)(.*?)(</tbody>)', html, re.S)
    assert table, "homepage navigation dimension table not found"
    models = parse_html_rows(table.group(2), True)
    assert len(models) == 31, f"expected 31 homepage models, got {len(models)}"

    name_cell = (
        f'<img src="imgs/{ICON}" class="model-icon">{MODEL_NAME}<br>'
        f'<span class="creator">{CREATOR}</span>'
    )
    models.append((MODEL_TYPE, name_cell,
                   [round_half_up(value) for value in dimensions()]))
    models.sort(key=lambda item: -item[2][0])
    rows = [build_html_row(model_type, cell, values, index, True)
            for index, (model_type, cell, values) in enumerate(models)]
    html = (html[:table.start()] + table.group(1) + "\n" + "\n".join(rows)
            + "\n" + table.group(3) + html[table.end():])

    detail = re.search(
        r'(<table id="table-detail">.*?<tbody>)(.*?)(</tbody>)', html, re.S)
    assert detail, "homepage navigation detail table not found"
    detail_models = parse_html_rows(detail.group(2), False)
    by_name = {model_name(cell): (model_type, cell, values)
               for model_type, cell, values in detail_models}
    assert len(by_name) == 31, f"expected 31 homepage detail models, got {len(by_name)}"
    by_name[MODEL_NAME] = (
        MODEL_TYPE,
        name_cell,
        [round_half_up(DETAIL[key]) for key in HD],
    )
    ordered = [by_name[model_name(cell)] for _, cell, _ in models]
    detail_rows = [build_html_row(model_type, cell, values, index, False)
                   for index, (model_type, cell, values) in enumerate(ordered)]
    html = (html[:detail.start()] + detail.group(1) + "".join(detail_rows)
            + detail.group(3) + html[detail.end():])

    replacements = [
        (
            '<div class="stat-num">31</div><div class="stat-title">Models</div>',
            '<div class="stat-num">32</div><div class="stat-title">Models</div>',
            "homepage model stat",
        ),
        (
            '<span>📝 11 Text</span><span>📷 13 Camera</span>'
            '<span>🎮 7 Action</span>',
            '<span>📝 11 Text</span><span>📷 13 Camera</span>'
            '<span>🎮 8 Action</span>',
            "homepage type stat",
        ),
        ("evaluating 31 models with 22 metrics",
         "evaluating 32 models with 22 metrics", "homepage TL;DR"),
        ("Among <b>31</b> evaluated models", "Among <b>32</b> evaluated models",
         "homepage finding count"),
        ("Kling 3.0 leads overall but lags in Consistency;",
         "JoyAI-Echo-1.5 (WM) leads overall but does not top any individual dimension;",
         "homepage finding leader"),
        (">All<br><small>(31)</small>", ">All<br><small>(32)</small>",
         "homepage all filter"),
        ("Action<br><small>(7)</small>", "Action<br><small>(8)</small>",
         "homepage action filter"),
    ]
    for old, new, label in replacements:
        html = replace_once(html, old, new, label)

    for table_id, old_table in full_tables.items():
        new_table = re.search(
            rf'<table id="{table_id}">.*?</table>', html, re.S
        ).group(0)
        assert new_table == old_table, f"{table_id} changed unexpectedly"

    type_counts = Counter(model_type for model_type, _, _ in models)
    assert type_counts == {"text": 11, "camera": 13, "action": 8}, type_counts

    HOMEPAGE.write_text(html, encoding="utf-8")


def main():
    dims = [round_half_up(value) for value in dimensions()]
    assert dims == [81.6, 81.5, 79.4, 86.6, 89.8, 70.6], dims
    update_readme()
    update_homepage()
    print(f"Added {MODEL_NAME}: overall {dims[0]:.1f}, 32 Navi models")


if __name__ == "__main__":
    main()
