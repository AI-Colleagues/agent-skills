#!/usr/bin/env python3
"""Render Codex quota information from `codex /status` as a Markdown table."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import re
import select
import subprocess
import sys
import termios
import time
import struct
from datetime import datetime
from pathlib import Path

SAMPLE_OUTPUT = """\
╭────────────────────────────────────────────────────────────────────────╮
│  >_ OpenAI Codex (v0.120.0)                                            │
│                                                                        │
│ Visit https://chatgpt.com/codex/settings/usage for up-to-date          │
│ information on rate limits and credits                                 │
│                                                                        │
│  Model:                gpt-5.4 (reasoning high, summaries auto)        │
│  Directory:            ~                                               │
│  Permissions:          Custom (workspace-write, on-request)            │
│  Agents.md:            <none>                                          │
│  Account:              shaojie.jiang1@gmail.com (Plus)                 │
│  Collaboration mode:   Default                                         │
│  Session:              019d7bd3-b85d-7eb2-8189-04dad7b0e01e            │
│                                                                        │
│  5h limit:             [████████████████████] 100% left (resets 13:22) │
│  Weekly limit:         [████████████████░░░░] 79% left                 │
│                        (resets 22:40 on 16 Apr)                        │
╰────────────────────────────────────────────────────────────────────────╯
"""

ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
QUOTA_RE = re.compile(
    r"^\s*(5h limit|Weekly limit):\s*(?:\[[^\]]*\]\s*)?(\d+%)\s+left(?:\s*\(([^)]*)\))?\s*$"
)
WRAPPED_RESET_RE = re.compile(r"^\s*\(([^)]*resets[^)]*)\)\s*$", re.IGNORECASE)
REFRESH_RE = re.compile(r"Limits:\s+refresh requested; run /status again shortly\.", re.IGNORECASE)
SESSION_ROOT = Path.home() / ".codex" / "sessions"
MAX_SESSION_FILES = 20


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = ANSI_RE.sub("", text)
    return text


def iter_content_lines(text: str) -> list[str]:
    lines = []
    for raw_line in normalize_text(text).splitlines():
        line = raw_line
        if "│" in raw_line:
            start = raw_line.find("│")
            end = raw_line.rfind("│")
            if end > start:
                line = raw_line[start + 1 : end]
        lines.append(line.rstrip())
    return lines


def parse_quotas(text: str) -> dict[str, dict[str, str]]:
    quotas: dict[str, dict[str, str]] = {}
    pending_reset: str | None = None

    for line in iter_content_lines(text):
        match = QUOTA_RE.search(line)
        if match:
            name, left, reset = match.groups()
            quotas[name] = {"left": left, "reset": (reset or "").strip()}
            pending_reset = name if not reset else None
            continue

        if pending_reset:
            wrapped = WRAPPED_RESET_RE.search(line)
            if wrapped:
                quotas[pending_reset]["reset"] = wrapped.group(1).strip()
                pending_reset = None
                continue

            if line.strip():
                pending_reset = None

    missing = [name for name in ("5h limit", "Weekly limit") if name not in quotas]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"could not find quota lines for: {missing_text}")

    return quotas


def format_markdown_table(quotas: dict[str, dict[str, str]]) -> str:
    rows = [
        "| Quota | Left | Reset |",
        "| --- | --- | --- |",
    ]
    for name in ("5h limit", "Weekly limit"):
        quota = quotas[name]
        rows.append(f"| {name} | {quota['left']} | {quota['reset']} |")
    return "\n".join(rows)


def format_reset_time(reset_at: int | float, *, weekly: bool) -> str:
    when = datetime.fromtimestamp(float(reset_at)).astimezone()
    if weekly:
        return when.strftime("resets %H:%M on %d %b")
    return when.strftime("resets %H:%M")


def percent_left(used_percent: int | float) -> str:
    left = max(0.0, min(100.0, 100.0 - float(used_percent)))
    return f"{int(round(left))}%"


def parse_session_rate_limits(rate_limits: dict[str, object]) -> dict[str, dict[str, str]]:
    primary = rate_limits.get("primary")
    secondary = rate_limits.get("secondary")
    if not isinstance(primary, dict) or not isinstance(secondary, dict):
        raise RuntimeError("recent session data did not include primary and secondary limits")

    primary_used = primary.get("used_percent")
    primary_reset = primary.get("resets_at")
    secondary_used = secondary.get("used_percent")
    secondary_reset = secondary.get("resets_at")
    if primary_used is None or primary_reset is None or secondary_used is None or secondary_reset is None:
        raise RuntimeError("recent session data was missing usage percentages or reset timestamps")

    return {
        "5h limit": {
            "left": percent_left(primary_used),
            "reset": format_reset_time(primary_reset, weekly=False),
        },
        "Weekly limit": {
            "left": percent_left(secondary_used),
            "reset": format_reset_time(secondary_reset, weekly=True),
        },
    }


def iter_recent_session_files(limit: int = MAX_SESSION_FILES) -> list[Path]:
    if not SESSION_ROOT.exists():
        return []

    files: list[tuple[float, Path]] = []
    for path in SESSION_ROOT.rglob("*.jsonl"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        files.append((mtime, path))

    files.sort(reverse=True)
    return [path for _, path in files[:limit]]


def load_quotas_from_recent_sessions() -> dict[str, dict[str, str]]:
    for path in iter_recent_session_files():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for raw_line in reversed(lines):
            if '"token_count"' not in raw_line or '"rate_limits"' not in raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            payload = record.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            rate_limits = None
            if isinstance(info, dict):
                rate_limits = info.get("rate_limits")
            if rate_limits is None:
                rate_limits = payload.get("rate_limits")
            if isinstance(rate_limits, dict):
                return parse_session_rate_limits(rate_limits)

    raise RuntimeError("could not find recent Codex rate limit data in ~/.codex/sessions")


def buffer_contains_quotas(buffer: bytearray) -> bool:
    text = buffer.decode("utf-8", "replace")
    normalized = normalize_text(text)
    return "5h limit" in normalized and "Weekly limit" in normalized


def read_from_pty(fd: int, buffer: bytearray, duration_seconds: float) -> None:
    deadline = time.monotonic() + duration_seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if fd not in ready:
            continue
        try:
            chunk = os.read(fd, 8192)
        except OSError:
            return
        if not chunk:
            return
        buffer.extend(chunk)


def select_status_command(fd: int, buffer: bytearray) -> None:
    os.write(fd, b"/")
    read_from_pty(fd, buffer, 0.6)
    os.write(fd, b"status")
    read_from_pty(fd, buffer, 0.8)
    os.write(fd, b"\r")
    read_from_pty(fd, buffer, 2.2)


def capture_status_view(timeout_seconds: float) -> str:
    rows = 40
    cols = 140
    startup_delay_seconds = 7.0
    max_refresh_retries = 1
    master_fd: int | None = None
    process: subprocess.Popen[bytes] | None = None

    try:
        master_fd, slave_fd = pty.openpty()
        fcntl.ioctl(
            slave_fd,
            termios.TIOCSWINSZ,
            struct.pack("HHHH", rows, cols, 0, 0),
        )
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = str(cols)
        env["LINES"] = str(rows)

        process = subprocess.Popen(
            ["codex", "--no-alt-screen"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            text=False,
        )
        os.close(slave_fd)

        buffer = bytearray()
        read_from_pty(master_fd, buffer, min(startup_delay_seconds, timeout_seconds))
        select_status_command(master_fd, buffer)

        refresh_retries = 0
        while REFRESH_RE.search(normalize_text(buffer.decode("utf-8", "replace"))):
            if buffer_contains_quotas(buffer):
                return buffer.decode("utf-8", "replace")
            if refresh_retries >= max_refresh_retries:
                break
            refresh_retries += 1
            select_status_command(master_fd, buffer)

        if buffer_contains_quotas(buffer):
            return buffer.decode("utf-8", "replace")

        if not buffer.strip():
            raise RuntimeError("`codex` produced no output while requesting `/status`")
        raise RuntimeError("could not capture quota lines from the interactive status view")
    finally:
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass


def run_codex_status(timeout_seconds: float) -> str:
    attempt_timeout = max(timeout_seconds, 12.0)

    try:
        return capture_status_view(attempt_timeout)
    except FileNotFoundError as exc:
        raise RuntimeError("`codex` is not available on PATH") from exc
    except OSError as exc:
        raise RuntimeError(f"interactive Codex launch failed: {exc}") from exc


def load_live_or_session_quotas(timeout_seconds: float) -> dict[str, dict[str, str]]:
    failures: list[str] = []

    try:
        return parse_quotas(run_codex_status(timeout_seconds))
    except (RuntimeError, ValueError) as exc:
        failures.append(str(exc))

    try:
        return load_quotas_from_recent_sessions()
    except RuntimeError as exc:
        failures.append(str(exc))

    raise RuntimeError("; ".join(failures))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render Codex 5h and weekly quotas as a Markdown table."
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read raw `codex /status` output from stdin instead of invoking Codex.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Parse the bundled sample output.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Timeout in seconds when invoking `codex /status` directly.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.sample:
            quotas = parse_quotas(SAMPLE_OUTPUT)
        elif args.stdin:
            raw_output = sys.stdin.read()
            if not raw_output.strip():
                raise RuntimeError("stdin did not contain any status output to parse")
            quotas = parse_quotas(raw_output)
        elif not sys.stdin.isatty():
            piped_input = sys.stdin.read()
            if piped_input.strip():
                quotas = parse_quotas(piped_input)
            else:
                quotas = load_live_or_session_quotas(args.timeout)
        else:
            quotas = load_live_or_session_quotas(args.timeout)
    except (RuntimeError, ValueError) as exc:
        print(f"Failed to extract Codex quotas: {exc}", file=sys.stderr)
        print(
            "If live capture fails in this build, paste the visible `codex /status` block and rerun with `--stdin`.",
            file=sys.stderr,
        )
        return 1

    print(format_markdown_table(quotas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
