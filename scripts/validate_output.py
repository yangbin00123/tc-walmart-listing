#!/usr/bin/env python3
"""Validate deterministic tc-walmart-listing output constraints."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from quality import final_check
from copy_checks import validate_copy, count_words


REQUIRED = [
    "01_product_profile.json",
    "02_kw_raw.json",
    "03_kw_removed.json",
    "03_kw_deferred.json",
    "03_keyword_decisions.json",
    "08_semantic_review.json",
    "03_kw_filtered.json",
    "04_kw_tagged.json",
    "05_keyword_plan.json",
    "06_competitor_context.json",
    "07_listing.json",
    "07_listing.md",
    "08_keyword_coverage.json",
]


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid JSON {path.name}: {exc}") from exc


def _validate(directory: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED:
        if not (directory / name).is_file():
            errors.append(f"missing required file: {name}")
    if errors:
        return errors

    try:
        for name in REQUIRED:
            if name.endswith(".json"):
                load_json(directory / name)
        raw = load_json(directory / "02_kw_raw.json")
        listing = load_json(directory / "07_listing.json")
        coverage = load_json(directory / "08_keyword_coverage.json")
    except ValueError as exc:
        return [str(exc)]

    ids = raw.get("product_ids")
    completed = raw.get("completed_product_ids")
    if raw.get("source") != "sorftime_mcp":
        errors.append("02_kw_raw.json source must be sorftime_mcp")
    if raw.get("tool") != "walmart_product_traffic_terms":
        errors.append("02_kw_raw.json tool must be walmart_product_traffic_terms")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or len(ids) != len(set(ids)):
        errors.append("product_ids must contain 1-20 unique values")
    if raw.get("complete") is not True or completed != ids:
        errors.append("keyword reverse lookup is not complete for every product ID")

    by_id = raw.get("raw", {}).get("by_product_id", {})
    if isinstance(ids, list):
        for product_id in ids:
            state = by_id.get(product_id)
            if not isinstance(state, dict):
                errors.append(f"missing raw pagination state for product ID {product_id}")
                continue
            if not state.get("pages"):
                errors.append(f"product ID {product_id} has no saved page response")
            if not state.get("stop_reason"):
                errors.append(f"product ID {product_id} has no stop_reason")
            if state.get("error") is not None:
                errors.append(f"product ID {product_id} contains an unresolved error")

    errors.extend(validate_copy(listing, load_json(directory / "01_product_profile.json")))

    if not errors:
        final_check(directory)
    return errors


def validate(directory: Path) -> list[str]:
    try:
        return _validate(directory)
    except (ValueError, TypeError, KeyError, OSError, AttributeError, IndexError) as exc:
        return ["invalid or inconsistent output: " + str(exc)]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_output.py <walmart_listing_directory>", file=sys.stderr)
        return 2
    directory = Path(sys.argv[1]).expanduser().resolve()
    if not directory.is_dir():
        print(f"ERROR: not a directory: {directory}", file=sys.stderr)
        return 2
    errors = validate(directory)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: Walmart listing output passed validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
