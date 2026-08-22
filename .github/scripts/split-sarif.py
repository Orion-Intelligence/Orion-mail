#!/usr/bin/env python3
"""Split a Codacy SARIF file into one run per tool with a unique code-scanning category.

GitHub rejects multiple SARIF runs that share a category, and it keeps stale alerts for
tools that stop reporting, so every known tool gets its own file -- empty when the tool
found nothing. Results located in .codacy.yml exclude_paths are dropped.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

SOURCE = Path("results.sarif")
BATCH_SIZE = 20
TOOLS = [
    "bandit",
    "eslint-8",
    "markdownlint",
    "opengrep",
    "prospector",
    "pylintpython3",
    "shellcheck",
    "stylelint",
    "trivy",
]


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value or "codacy").strip("-").lower()
    return value or "codacy"


def tool_key(run: dict) -> str:
    name = run.get("tool", {}).get("driver", {}).get("name") or ""
    return slug(name).removesuffix("-reported-by-codacy")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    out = ""
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out += "(?:.*/)?"
            index += 3
            continue
        if pattern.startswith("**", index):
            out += ".*"
            index += 2
            continue
        if char == "*":
            out += "[^/]*"
        elif char == "?":
            out += "[^/]"
        else:
            out += re.escape(char)
        index += 1
    return re.compile("^" + out + "$")


def excluded_paths() -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    config = Path(".codacy.yml")
    if not config.exists():
        return patterns
    inside = False
    for line in config.read_text().splitlines():
        if not line.startswith(" ") and line.strip():
            inside = line.strip() == "exclude_paths:"
            continue
        if inside and line.strip().startswith("- "):
            patterns.append(glob_to_regex(line.strip()[2:].strip().strip('"')))
    return patterns


def main() -> int:
    sarif = json.loads(SOURCE.read_text())
    runs = sarif.get("runs") or []
    excludes = excluded_paths()

    def keep_result(result: dict) -> bool:
        for location in result.get("locations") or []:
            uri = location.get("physicalLocation", {}).get("artifactLocation", {}).get("uri") or ""
            uri = uri.removeprefix("file://").removeprefix("./").removeprefix("/")
            if any(pattern.match(uri) for pattern in excludes):
                return False
        return True

    selected: dict[str, dict] = {}
    for run in runs:
        key = tool_key(run)
        if key in TOOLS and key not in selected:
            selected[key] = run
        elif key not in TOOLS:
            print(f"Skipping {key}: not part of the reported tool set")

    for key in TOOLS:
        if key not in selected:
            selected[key] = {"tool": {"driver": {"name": f"{key.capitalize()} (reported by Codacy)"}}, "results": []}
            print(f"No findings for {key}: registering an empty run")

    for index, key in enumerate(TOOLS, 1):
        output_dir = Path(f"sarif-results-{((index - 1) // BATCH_SIZE) + 1:02d}")
        output_dir.mkdir(exist_ok=True)
        run_sarif = copy.deepcopy(sarif)
        run_sarif["runs"] = [copy.deepcopy(selected[key])]
        run_output = run_sarif["runs"][0]

        dropped = [result for result in run_output.get("results") or [] if not keep_result(result)]
        if dropped:
            run_output["results"] = [result for result in run_output["results"] if keep_result(result)]
            print(f"Dropped {len(dropped)} {key} result(s) located in .codacy.yml exclude_paths")

        automation = run_output.setdefault("automationDetails", {})
        automation["id"] = f"codacy/{key}-reported-by-codacy/{index}"

        target = output_dir / f"{index:02d}-{key}.sarif"
        target.write_text(json.dumps(run_sarif), encoding="utf-8")
        print(f"Wrote {target} with category {automation['id']} ({len(run_output.get('results') or [])} results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
