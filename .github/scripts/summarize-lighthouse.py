#!/usr/bin/env python3
"""Render the Lighthouse category scores into the GitHub step summary."""

from __future__ import annotations

import json
import os
import pathlib

REPORT = pathlib.Path("lighthouse-results/lighthouse-report.report.json")


def main() -> int:
    if not REPORT.is_file():
        print("No Lighthouse report was produced")
        return 0

    data = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = ["| Category | Score |", "| --- | --- |"]
    for key, category in data.get("categories", {}).items():
        score = category.get("score")
        rows.append(f"| {category.get('title', key)} | {'n/a' if score is None else round(score * 100)} |")

    summary = "\n".join(["## Lighthouse", "", f"URL: {data.get('finalDisplayedUrl') or data.get('requestedUrl')}", "", *rows, ""])
    print(summary)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fp:
            fp.write(summary + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
