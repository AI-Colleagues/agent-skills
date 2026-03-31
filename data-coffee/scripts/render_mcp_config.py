#!/usr/bin/env python3
"""Render a minimal Data Coffee MCP config snippet."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


ENDPOINT = "https://data-coffee.vercel.app/api/mcp"


def build_config(token: str | None, server_name: str) -> dict[str, Any]:
    server = {
        "type": "http",
        "url": ENDPOINT,
    }
    if token:
        server["headers"] = {"Authorization": f"Bearer {token}"}
    return {"mcpServers": {server_name: server}}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a Data Coffee MCP config JSON snippet."
    )
    parser.add_argument(
        "--token",
        help="Optional bearer token returned by profile_register; falls back to DATA_COFFEE_TOKEN",
    )
    parser.add_argument(
        "--server-name",
        default="data-coffee",
        help="MCP server key to emit in the JSON snippet",
    )
    args = parser.parse_args()

    token = args.token or os.environ.get("DATA_COFFEE_TOKEN")

    config = build_config(token, args.server_name)
    print(json.dumps(config, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
