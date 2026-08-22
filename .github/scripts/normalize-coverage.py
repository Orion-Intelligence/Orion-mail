#!/usr/bin/env python3
"""Rewrite client and backend coverage paths so they are relative to the repository root.

Cypress/nyc writes paths relative to the client workspace and pytest-cov writes them
relative to the backend package, which Codacy cannot map back onto the repository.
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(".").resolve()


def root_relative(raw: str, base: pathlib.Path) -> str:
    candidate = pathlib.Path(raw)
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    try:
        return candidate.relative_to(ROOT).as_posix()
    except ValueError:
        return raw


def normalize_lcov(path: pathlib.Path) -> int:
    lines: list[str] = []
    count = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("SF:"):
            line = "SF:" + root_relative(line[3:], ROOT / "client")
            count += 1
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def normalize_cobertura(path: pathlib.Path) -> int:
    tree = ET.parse(path)
    coverage = tree.getroot()
    base = ROOT / "backend"
    for source in coverage.iter("source"):
        text = (source.text or "").strip()
        if text and pathlib.Path(text).is_absolute():
            try:
                pathlib.Path(text).resolve().relative_to(ROOT)
                base = pathlib.Path(text).resolve()
                break
            except ValueError:
                continue

    count = 0
    for cls in coverage.iter("class"):
        cls.set("filename", root_relative(cls.get("filename", ""), base))
        count += 1

    sources = coverage.find("sources")
    if sources is not None:
        for child in list(sources):
            sources.remove(child)
        ET.SubElement(sources, "source").text = str(ROOT)

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return count


def main() -> int:
    client_files = normalize_lcov(ROOT / "client" / "coverage" / "lcov.info")
    backend_files = normalize_cobertura(ROOT / "backend" / "coverage.xml")
    print(f"Normalized {client_files} client file(s) and {backend_files} backend file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
