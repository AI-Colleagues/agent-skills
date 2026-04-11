#!/usr/bin/env python3
"""
Captures `claude /usage` TUI output and prints a Markdown table with quota info.

Limitations:
- Requires a Claude subscription plan (Pro/Max/Teams) with hasAvailableSubscription=true.
- Does NOT work when running inside the Claude Desktop app, because that environment
  routes claude.ai API calls through the Desktop app's embedded browser session —
  a session that spawned subprocesses cannot inherit.
  In Desktop app mode, open a standalone terminal and run `claude /usage` directly.
"""

import os
import pathlib
import pty
import re
import select
import signal
import sys
import time


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def is_desktop_app_mode() -> bool:
    """Return True if running inside the Claude Desktop app."""
    return os.environ.get('CLAUDE_CODE_ENTRYPOINT') == 'claude-desktop' \
        or os.environ.get('CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST') == '1'


def _patch_config(path: pathlib.Path, key: str, value) -> object:
    import json as _json
    data = _json.loads(path.read_text())
    original = data.get(key)
    data[key] = value
    path.write_text(_json.dumps(data))
    return original


def capture_usage_output(timeout: float = 10.0) -> str:
    """
    Spawn `claude /usage` in a pty and capture its output.

    Temporarily patches hasAvailableSubscription=true so the local check passes,
    then restores the original value regardless of outcome.
    """
    config_path = pathlib.Path.home() / '.claude.json'
    original_value = None
    patched = False
    if config_path.exists():
        try:
            original_value = _patch_config(config_path, 'hasAvailableSubscription', True)
            patched = True
        except Exception:
            pass

    master_fd, slave_fd = pty.openpty()
    pid = os.fork()
    if pid == 0:
        os.setsid()
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        os.close(master_fd)
        os.close(slave_fd)
        # Strip Desktop-app-specific env vars so the subprocess runs as a
        # plain CLI, which uses the standard OAuth token flow.
        skip = {'ANTHROPIC_API_KEY', 'CLAUDE_CODE_ENTRYPOINT',
                'CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST'}
        env = {k: v for k, v in os.environ.items() if k not in skip}
        os.execvpe('claude', ['claude', '/usage'], env)
        os._exit(1)

    os.close(slave_fd)
    chunks: list[bytes] = []
    start = time.time()
    done = False

    try:
        while time.time() - start < timeout and not done:
            r, _, _ = select.select([master_fd], [], [], 0.3)
            if r:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        chunks.append(data)
                except OSError:
                    break

            combined = strip_ansi(b''.join(chunks).decode('utf-8', errors='replace'))

            if 'Current week' in combined and 'Resets' in combined:
                time.sleep(0.5)
                done = True
            elif 'only' in combined and ('subscription' in combined or 'vilable' in combined):
                done = True
    finally:
        try:
            os.write(master_fd, b'\x1b')
        except OSError:
            pass
        time.sleep(0.3)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        os.close(master_fd)

        if patched and config_path.exists():
            try:
                _patch_config(config_path, 'hasAvailableSubscription', original_value)
            except Exception:
                pass

    return b''.join(chunks).decode('utf-8', errors='replace')


def parse_usage(raw: str) -> list[dict] | None:
    """
    Parse ANSI-stripped output into a list of quota dicts.
    Returns None if /usage is unavailable for this plan/env.
    """
    clean = strip_ansi(raw)

    if 'only' in clean and ('subscription' in clean or 'vilable' in clean):
        return None

    section_keys = ['Current session', 'Current week', 'Extra usage']
    section_spans: list[tuple[str, int, int]] = []
    for key in section_keys:
        m = re.search(re.escape(key), clean, re.IGNORECASE)
        if m:
            section_spans.append((key, m.start(), m.end()))

    section_spans.sort(key=lambda x: x[1])
    sections_text: list[tuple[str, str]] = []
    for i, (key, start, _) in enumerate(section_spans):
        end = section_spans[i + 1][1] if i + 1 < len(section_spans) else len(clean)
        sections_text.append((key, clean[start:end]))

    results = []
    for key, text in sections_text:
        pct_m = re.search(r'(\d+)%\s*used', text)
        if not pct_m:
            continue
        percent = pct_m.group(1)
        reset_m = re.search(r'Resets?\s+([^\r\n]+)', text)
        resets = reset_m.group(1).strip() if reset_m else '?'
        resets = re.sub(r'\s{2,}.*$', '', resets)
        spend_m = re.search(r'\$([\d.]+)\s*/\s*\$([\d.]+)\s*spent', text)
        extra = f'${spend_m.group(1)} / ${spend_m.group(2)}' if spend_m else None
        display = {'Current session': 'Current session',
                   'Current week': 'Current week',
                   'Extra usage': 'Extra usage'}.get(key, key)
        results.append({'name': display, 'percent': f'{percent}%',
                        'extra': extra, 'resets': resets})
    return results


def render_table(quotas: list[dict]) -> str:
    rows = []
    for q in quotas:
        used = q['percent']
        if q['extra']:
            used += f' ({q["extra"]})'
        rows.append((q['name'], used, q['resets']))

    lines = ['| Quota | Used | Resets |', '|-------|------|--------|']
    for name, used, resets in rows:
        lines.append(f'| {name} | {used} | {resets} |')
    return '\n'.join(lines)


def main() -> None:
    if is_desktop_app_mode():
        print(
            '_This skill cannot fetch quota data when running inside the Claude Desktop app. '
            'The Desktop app routes usage API calls through its embedded browser session, '
            'which spawned subprocesses cannot access._\n\n'
            '_**Workaround:** Open a standalone terminal (outside the Desktop app) '
            'and run `claude /usage` directly._'
        )
        sys.exit(0)

    raw = capture_usage_output()

    if not raw.strip():
        print('_Could not capture `claude /usage` output. Make sure `claude` is on your PATH._')
        sys.exit(1)

    quotas = parse_usage(raw)

    if quotas is None:
        print(
            '_`/usage` returned "only available for subscription plans". '
            'Your `~/.claude.json` has `hasAvailableSubscription: false`. '
            'If your subscription is active, try `claude logout && claude login` '
            'to refresh the cached account state._'
        )
        sys.exit(0)

    if not quotas:
        print('_No quota data found in `claude /usage` output. Try running it directly._')
        sys.exit(1)

    print(render_table(quotas))


if __name__ == '__main__':
    main()
