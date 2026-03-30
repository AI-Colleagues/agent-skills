#!/usr/bin/env python3
"""Render a minimal Data Coffee MCP config snippet."""

from __future__ import annotations

import argparse
import json


ENDPOINT = "https://data-coffee.vercel.app/api/mcp"


def build_config(token: str | None, server_name: str) -> dict:
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
        help="Optional bearer token returned by profile_register",
    )
    parser.add_argument(
        "--server-name",
        default="data-coffee",
        help="MCP server key to emit in the JSON snippet",
    )
    args = parser.parse_args()

    config = build_config(args.token, args.server_name)
    print(json.dumps(config, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
