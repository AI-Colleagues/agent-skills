# Repository Guidelines

## Project Structure & Module Organization

This repository is a collection of reusable agent skills, not a single packaged application. Each skill lives in a top-level kebab-case directory such as `orcheo/`, `data-coffee/`, or `video-speech-cleanup/`. The required entry point is `SKILL.md`. Supporting material stays beside it:

- `references/` for deeper workflow docs
- `scripts/` for Python helpers and CLIs
- `agents/openai.yaml` for agent-specific config when needed
- `.github/workflows/claude.yml` for repository automation

Keep new assets inside the skill they belong to; avoid cross-skill dependencies unless they are clearly documented.

Every `SKILL.md` must include the following frontmatter fields. Reviewers should reject PRs that are missing any of them:

```yaml
name:
description:
license:
metadata:
  author:
  version:
```

## Build, Test, and Development Commands

There is no repo-wide build target or shared test runner. Validate the skill you changed:

```bash
python3 <skill>/scripts/<tool>.py --help
python3 -m py_compile <skill>/scripts/*.py
git diff --check
```

Examples:

```bash
python3 data-coffee/scripts/render_mcp_config.py --server-name data-coffee
python3 video-speech-cleanup/scripts/process_video.py --help
cp -R orcheo ~/.codex/skills/
```

Use `uv` for Python package management when you need an isolated environment, but keep commands copy-pasteable from `SKILL.md`.

## Coding Style & Naming Conventions

Use concise, instructional Markdown with short sections, fenced commands, and repository-relative links. Skill folders use kebab-case; helper scripts use snake_case, for example `linkedin_oauth_store.py`.

Python in this repo follows the existing pattern: 4-space indentation, `#!/usr/bin/env python3`, `from __future__ import annotations`, explicit type hints, and small focused functions. Match surrounding style before introducing new structure.

## Testing Guidelines

Because there is no central coverage gate, contributors are expected to run targeted checks. For docs, verify links, commands, and file paths. For Python helpers, at minimum run `--help`, `py_compile`, and one realistic smoke test when the script touches external tools or APIs. Record manual verification steps in the PR.

## Commit & Pull Request Guidelines

Recent commits use short imperative, sentence-case subjects with issue references, for example `Add LinkedIn OAuth credential storage workflow (#17)`. Follow that format.

PRs should describe the affected skill(s), user-visible behavior, and manual validation performed. Link the related issue when available. Include screenshots only when changing rendered artifacts or UI-like outputs. Never commit secrets, tokens, or copied credential values.
