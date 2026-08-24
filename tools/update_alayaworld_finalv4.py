#!/usr/bin/env python3
"""Update AlayaWorld to the final-v4 navigation submission.

Scores are transcribed from Table 1 supplied with the final-v4 videos. The
script updates the README and homepage from one shared score definition, then
re-sorts the navigation leaderboard and recomputes medals.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.add_alaya_evoke import (  # noqa: E402
    HD,
    RD,
    build_dims_row,
    build_html_row,
    medals_for,
    parse_dims_row,
    parse_html_rows,
)


README = Path("README.md")
HOMEPAGE = Path("homepage/index.html")

ALAYAWORLD_DETAIL = dict(zip(RD, [
    62.8, 67.7, 94.1, 92.7, 91.1, 97.0, 64.3, 51.6, 87.7, 80.0,
    87.9, 81.9, 86.6, 98.1, 94.1, 80.3, 93.4, 61.1, 65.1,
]))
# Use the published averages: the per-metric values in the table are already
# rounded to one decimal and cannot reproduce the hidden-precision aggregates.
ALAYAWORLD_DIMS = [76.3, 79.3, 69.7, 80.0, 89.5, 63.1]


def is_alayaworld(value):
    return "AlayaWorld" in value and "Alaya-EVOKE" not in value


def model_name(name_cell):
    first_line = name_cell.split("<br>", 1)[0]
    name = re.sub(r"<[^>]+>", "", first_line).strip()
    note = re.search(r'class="model-note">(.*?)<', name_cell)
    return f"{name} ({note.group(1)})" if note else name


def update_readme():
    text = README.read_text(encoding="utf-8")

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
    assert len(models) == 31, f"expected 31 models, got {len(models)}"

    replaced = 0
    for index, (cell, _) in enumerate(models):
        if is_alayaworld(cell):
            models[index] = (cell, ALAYAWORLD_DIMS)
            replaced += 1
    assert replaced == 1, f"expected one AlayaWorld dimension row, got {replaced}"

    models.sort(key=lambda item: -item[1][0])
    medals = medals_for([values for _, values in models])
    rows = [build_dims_row(i + 1, cell, values, medals, i)
            for i, (cell, values) in enumerate(models)]
    text = (text[:table.start()] + head + header + "\n".join(rows) + tail
            + text[table.end():])

    detail_pattern = re.compile(
        r"^\| <img src=\"assets/icon/alayaworld\.png\" height=\"18\"> "
        r"AlayaWorld \|.*$",
        re.M,
    )
    detail_values = [ALAYAWORLD_DETAIL[key] for key in RD]
    detail_row = (
        '| <img src="assets/icon/alayaworld.png" height="18"> AlayaWorld | '
        + " | ".join(f"{value:.1f} &nbsp;&nbsp;" for value in detail_values)
        + " |"
    )
    text, count = detail_pattern.subn(detail_row, text)
    assert count == 1, f"expected one AlayaWorld detail row, got {count}"

    news = (
        "- **[2026/08/16]** 🔄 Updated [AlayaWorld]"
        "(https://github.com/AlayaLab/AlayaWorld) final-v4: **76.3**, #12 · "
        "thanks [@nevermorelch](https://github.com/nevermorelch).\n"
    )
    if news not in text:
        text = text.replace("## 📢 News\n\n", "## 📢 News\n\n" + news, 1)

    README.write_text(text, encoding="utf-8")


def update_homepage():
    html = HOMEPAGE.read_text(encoding="utf-8")

    table = re.search(
        r'(<table id="table-navi">.*?<tbody>)(.*?)(</tbody>)', html, re.S)
    assert table, "homepage navigation dimension table not found"
    models = parse_html_rows(table.group(2), True)
    assert len(models) == 31, f"expected 31 homepage models, got {len(models)}"

    replaced = 0
    for index, (model_type, name_cell, _) in enumerate(models):
        if is_alayaworld(model_name(name_cell)):
            models[index] = (model_type, name_cell, ALAYAWORLD_DIMS)
            replaced += 1
    assert replaced == 1, f"expected one homepage AlayaWorld row, got {replaced}"
    models.sort(key=lambda item: -item[2][0])
    rows = [build_html_row(model_type, name_cell, values, i, True)
            for i, (model_type, name_cell, values) in enumerate(models)]
    html = (html[:table.start()] + table.group(1) + "\n" + "\n".join(rows)
            + "\n" + table.group(3) + html[table.end():])

    detail = re.search(
        r'(<table id="table-detail">.*?<tbody>)(.*?)(</tbody>)', html, re.S)
    assert detail, "homepage navigation detail table not found"
    detail_models = parse_html_rows(detail.group(2), False)
    by_name = {model_name(name_cell): (model_type, name_cell, values)
               for model_type, name_cell, values in detail_models}
    assert len(by_name) == 31, f"expected 31 homepage detail models, got {len(by_name)}"

    alaya = by_name["AlayaWorld"]
    by_name["AlayaWorld"] = (
        alaya[0],
        alaya[1],
        [ALAYAWORLD_DETAIL[key] for key in HD],
    )
    ordered = [by_name[model_name(name_cell)] for _, name_cell, _ in models]
    detail_rows = [build_html_row(model_type, name_cell, values, i, False)
                   for i, (model_type, name_cell, values) in enumerate(ordered)]
    html = (html[:detail.start()] + detail.group(1) + "".join(detail_rows)
            + detail.group(3) + html[detail.end():])

    html = html.replace(
        '<div class="stat-num">30</div><div class="stat-title">Models</div>',
        '<div class="stat-num">31</div><div class="stat-title">Models</div>',
    )
    html = html.replace(
        '<span>📝 11 Text</span><span>📷 10 Camera</span>'
        '<span>🎮 6 Action</span>',
        '<span>📝 11 Text</span><span>📷 13 Camera</span>'
        '<span>🎮 7 Action</span>',
    )

    HOMEPAGE.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    update_readme()
    update_homepage()
    print("AlayaWorld final-v4 leaderboard updated")
