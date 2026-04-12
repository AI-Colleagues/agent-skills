#!/usr/bin/env python3
"""Helpers for loading configuration from nearby .env files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _candidate_env_files(search_roots: Iterable[Path | str | None]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    ordered_roots = [Path.cwd(), *[Path(root) for root in search_roots if root is not None]]

    for root in ordered_roots:
        resolved = root.expanduser().resolve()
        base = resolved.parent if resolved.is_file() else resolved
        for directory in (base, *base.parents):
            env_path = directory / ".env"
            if env_path in seen or not env_path.is_file():
                continue
            seen.add(env_path)
            candidates.append(env_path)
    return candidates


def find_env_value(name: str, *search_roots: Path | str | None) -> tuple[str | None, str | None]:
    """Return a variable from the first nearby .env, then fall back to the shell."""
    for env_path in _candidate_env_files(search_roots):
        value = _parse_dotenv(env_path).get(name)
        if value:
            return value, str(env_path)
    value = os.environ.get(name)
    return value, None
