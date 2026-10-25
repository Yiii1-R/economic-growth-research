#!/usr/bin/env python3
"""Build the first-wave 15-country results-variable pilot panel."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[2]
MPD_PATH = ROOT / "data/raw/SRC-001/2023/mpd2023_web.xlsx"
PWT_PATH = ROOT / "data/raw/SRC-002/11.0/pwt110.xlsx"
WDI_PATH = ROOT / "data/raw/SRC-003/2026-10-26/wdi_gdp_pc_constant_2015_usd.json"
OUTPUT_PATH = ROOT / "data/processed/pilot_results_country_year_v0.1.csv"
COVERAGE_REPORT = ROOT / "reports/pilot_coverage_v0.1.md"
COMPARISON_REPORT = ROOT / "reports/pilot_source_comparison_v0.1.md"

COUNTRIES = {
    "ARG": "阿根廷",
    "AUS": "澳大利亚",
    "BRA": "巴西",
    "CHN": "中国",
    "FRA": "法国",
    "GBR": "英国",
    "IND": "印度",
    "IDN": "印度尼西亚",
    "JPN": "日本",
    "KOR": "韩国",
    "MEX": "墨西哥",
    "NGA": "尼日利亚",
    "RUS": "俄罗斯",
    "USA": "美国",
    "ZAF": "南非",
}
ANCHOR_YEARS = [1820, 1870, 1913, 1950, 1980, 2000, 2019]


def as_number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_mpd_sheet(sheet_name: str) -> dict[tuple[str, int], float]:
    workbook = load_workbook(MPD_PATH, read_only=True, data_only=True)
    sheet = workbook[sheet_name]
    rows = sheet.iter_rows(values_only=True)
    next(rows)
    next(rows)
    code_row = next(rows)
    code_to_column = {
        str(code).strip(): index
        for index, code in enumerate(code_row)
        if str(code).strip() in COUNTRIES
    }
    values = {}
    for row in rows:
        year_value = as_number(row[0] if row else None)
        if year_value is None or year_value < 1820 or year_value > 2022:
            continue
        year = int(year_value)
        for code, index in code_to_column.items():
            value = as_number(row[index] if index < len(row) else None)
            if value is not None:
                values[(code, year)] = value
    workbook.close()
    return values


def read_pwt() -> dict[tuple[str, int], dict[str, float]]:
    workbook = load_workbook(PWT_PATH, read_only=True, data_only=True)
    sheet = workbook["Data"]
    rows = sheet.iter_rows(values_only=True)
    headers = list(next(rows))
    indices = {name: headers.index(name) for name in ["countrycode", "year", "rgdpo", "pop"]}
    values = {}
    for row in rows:
        code = str(row[indices["countrycode"]] or "").strip()
        year_value = as_number(row[indices["year"]])
        if code not in COUNTRIES or year_value is None:
            continue
        year = int(year_value)
        if year < 1950 or year > 2023:
            continue
        rgdpo = as_number(row[indices["rgdpo"]])
        population = as_number(row[indices["pop"]])
        gdp_pc = rgdpo / population if rgdpo is not None and population not in (None, 0) else None
        values[(code, year)] = {"gdp_pc": gdp_pc, "population": population}
    workbook.close()
    return values


def read_wdi() -> dict[tuple[str, int], float]:
    payload = json.loads(WDI_PATH.read_text(encoding="utf-8"))
    values = {}
    for row in payload[1]:
        code = str(row.get("countryiso3code") or "").strip()
        year_value = as_number(row.get("date"))
        if code not in COUNTRIES or year_value is None:
            continue
        value = as_number(row.get("value"))
        if value is not None:
            values[(code, int(year_value))] = value
    return values


def write_panel(maddison_gdp, maddison_population, pwt, wdi):
    keys = set(maddison_gdp) | set(maddison_population) | set(pwt) | set(wdi)
    rows = []
    for code, year in sorted(keys, key=lambda item: (item[0], item[1])):
        pwt_row = pwt.get((code, year), {})
        rows.append(
            {
                "country_id": code,
                "iso3": code,
                "country_name_zh": COUNTRIES[code],
                "year": year,
                "gdp_pc_maddison": maddison_gdp.get((code, year)),
                "population_maddison_raw": maddison_population.get((code, year)),
                "gdp_pc_pwt": pwt_row.get("gdp_pc"),
                "population_pwt_millions": pwt_row.get("population"),
                "gdp_pc_wdi": wdi.get((code, year)),
            }
        )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if value is None else value for key, value in row.items()})
    return rows


def count_available(rows: Iterable[dict], field: str, year: int | None = None) -> int:
    return sum(1 for row in rows if (year is None or row["year"] == year) and row[field] not in (None, ""))


def write_reports(rows, maddison_gdp, pwt, wdi):
    sources = [
        ("gdp_pc_maddison", "Maddison 2023", "1820—2022; 2011 prices"),
        ("gdp_pc_pwt", "PWT 11.0", "1950—2023; rgdpo / pop"),
        ("gdp_pc_wdi", "WDI NY.GDP.PCAP.KD", "1960—2023; constant 2015 US$"),
    ]
    lines = [
        "# 第一波结果变量覆盖率",
        "",
        "生成文件：`data/processed/pilot_results_country_year_v0.1.csv`。",
        "",
        "## 关键年份覆盖数",
        "",
        "| 年份 | Maddison | PWT | WDI |",
        "|---:|---:|---:|---:|",
    ]
    for year in ANCHOR_YEARS:
        counts = [count_available(rows, field, year) for field, _, _ in sources]
        lines.append(f"| {year} | {counts[0]} / 15 | {counts[1]} / 15 | {counts[2]} / 15 |")
    lines.extend(["", "## 各国可用年份", "", "| ISO3 | Maddison | PWT | WDI |", "|---|---:|---:|---:|"])
    for code in COUNTRIES:
        country_rows = [row for row in rows if row["iso3"] == code]
        counts = [count_available(country_rows, field) for field, _, _ in sources]
        lines.append(f"| {code} | {counts[0]} | {counts[1]} | {counts[2]} |")
    lines.extend(["", "## 解释", "", "- 覆盖数按 15 个试点国家中非缺失观测计数。", "- 空值保持为空，不将缺失解释为零。", "- 三个来源分别保留，未拼接为单一基线序列。", ""])
    COVERAGE_REPORT.write_text("\n".join(lines), encoding="utf-8")

    comparison_lines = [
        "# 第一波来源比较",
        "",
        "| 来源 | 变量构造 | 原始时间范围 | 试点非缺失观测数 |",
        "|---|---|---:|---:|",
    ]
    for field, name, definition in sources:
        available = count_available(rows, field)
        years = [row["year"] for row in rows if row[field] not in (None, "")]
        span = f"{min(years)}—{max(years)}" if years else "无"
        comparison_lines.append(f"| {name} | {definition} | {span} | {available} |")
    comparison_lines.extend(
        [
            "",
            "## 口径限制",
            "",
            "- Maddison 的 `gdp_pc_maddison` 保留原始 2011 价格口径。",
            "- PWT 的 `gdp_pc_pwt` 按 `rgdpo / pop` 构造，保留 PWT 的 2017 年链式 PPP 口径。",
            "- WDI 的 `gdp_pc_wdi` 仅用于外部核验，不替换历史基线。",
            "- 重叠期的水平差异不能直接解释为经济增长差异，后续需比较增长率和排名稳定性。",
            "",
        ]
    )
    COMPARISON_REPORT.write_text("\n".join(comparison_lines), encoding="utf-8")


def main():
    maddison_gdp = read_mpd_sheet("GDPpc")
    maddison_population = read_mpd_sheet("Population")
    pwt = read_pwt()
    wdi = read_wdi()
    rows = write_panel(maddison_gdp, maddison_population, pwt, wdi)
    write_reports(rows, maddison_gdp, pwt, wdi)
    print(f"wrote {len(rows)} country-year rows to {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"wrote reports to {COVERAGE_REPORT.relative_to(ROOT)} and {COMPARISON_REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
