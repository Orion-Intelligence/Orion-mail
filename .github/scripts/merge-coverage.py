#!/usr/bin/env python3
"""Combine the client LCOV and backend Cobertura reports into a single summary."""

from __future__ import annotations

import json
import os
import pathlib
from defusedxml.ElementTree import parse as safe_parse

ROOT = pathlib.Path(".")
LCOV = ROOT / "client" / "coverage" / "lcov.info"
BACKEND_XML = ROOT / "backend" / "coverage.xml"
OUT_DIR = ROOT / "coverage-merged"


def lcov_totals(path: pathlib.Path) -> tuple[int, int]:
    total = 0
    covered = 0
    if not path.exists() or path.stat().st_size == 0:
        return covered, total
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.startswith("DA:"):
            continue
        parts = raw.split("DA:", 1)[1].split(",")
        if len(parts) != 2:
            continue
        total += 1
        if int(parts[1]) > 0:
            covered += 1
    return covered, total


def cobertura_totals(path: pathlib.Path) -> tuple[int, int]:
    if not path.exists() or path.stat().st_size == 0:
        return 0, 0
    cov = safe_parse(path).getroot()
    return int(cov.attrib.get("lines-covered", "0")), int(cov.attrib.get("lines-valid", "0"))


def percent(covered: int, total: int) -> float:
    return round((covered / total * 100.0) if total else 0.0, 2)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    client_covered, client_total = lcov_totals(LCOV)
    backend_covered, backend_total = cobertura_totals(BACKEND_XML)

    if (client_total + backend_total) == 0:
        raise SystemExit("No client or backend coverage files were produced")

    covered = client_covered + backend_covered
    total = client_total + backend_total

    summary = {
        "client": {"covered_lines": client_covered, "total_lines": client_total, "line_coverage_percent": percent(client_covered, client_total)},
        "backend": {"covered_lines": backend_covered, "total_lines": backend_total, "line_coverage_percent": percent(backend_covered, backend_total)},
        "combined": {"covered_lines": covered, "total_lines": total, "line_coverage_percent": percent(covered, total)},
    }

    markdown = "\n".join([
        "# Combined Coverage Summary",
        "",
        f"- Client (LCOV): {client_covered}/{client_total} ({summary['client']['line_coverage_percent']}%)",
        f"- Backend (Cobertura XML): {backend_covered}/{backend_total} ({summary['backend']['line_coverage_percent']}%)",
        f"- Combined: {covered}/{total} ({summary['combined']['line_coverage_percent']}%)",
        "",
    ])

    (OUT_DIR / "coverage-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "coverage-summary.md").write_text(markdown, encoding="utf-8")
    print(markdown)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fp:
            fp.write(markdown + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
