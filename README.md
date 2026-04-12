# Skills

> **Part of the [Orcheo](https://github.com/AI-Colleagues/orcheo) project** - A workflow orchestration platform built on LangGraph.

This directory contains AI agent skills used by this repository. Each skill
defines how an AI agent should help with a specific workflow.

## How to use a skill
- Use a slash command (e.g., `/orcheo`) to invoke the skill directly.
- Ask for a skill by name in your request (e.g., "use the orcheo skill").
- You can describe the task instead; an AI agent may pick a matching skill when
  it clearly applies.
- The AI agent will read the skill's `SKILL.md` and follow its instructions.

## What to expect
- Copy-pasteable commands and minimal, safe steps.
- Questions when details are missing (OS, versions, paths, credentials).
- A request for confirmation before installs, upgrades, or starting services.

## Where the details live
- Each skill lives in `<skill_name>/` (e.g., `orcheo/`).
- Read `<skill_name>/SKILL.md` for the full workflow and requirements.
- Supporting files (like templates or compose files) live in
  `<skill_name>/assets/`.

## Install in common agents

### Claude Code
Copy or symlink the skill to a Claude Code skills folder. Claude Code looks for
skills in `~/.claude/skills/` (user-level) or `./.claude/skills/`
(project-level).

**macOS / Linux:**
```bash
# User-level (available in all projects)
cp -R orcheo ~/.claude/skills/

# Or project-level (available only in that project)
cp -R orcheo .claude/skills/
```

**Windows (PowerShell):**
```powershell
# User-level
Copy-Item -Recurse orcheo "$env:USERPROFILE\.claude\skills\"

# Or project-level
Copy-Item -Recurse orcheo ".claude\skills\"
```

Ask for the skill by name in your prompt (e.g., "use the orcheo skill" or "use the orcheo-demos skill").

### Codex CLI
Copy or symlink the skill to your Codex skills folder.

**macOS / Linux:**
```bash
cp -R orcheo ~/.codex/skills/
```

**Windows (PowerShell):**
```powershell
Copy-Item -Recurse orcheo "$env:USERPROFILE\.codex\skills\"
```

Ask for it by name in your prompt (e.g., "use the orcheo skill").

### Cursor
- Cursor automatically detects skills in the project `.claude/skills/` and `.codex/skills/` folders, so add skills there as described above.

## Tips for skill users
- Share your OS, shell, and project path when it matters.
- If you want a specific command run, include it verbatim.
- For setup tasks, confirm whether you want global or project-local installs.
- `uv` is recommended for Python package management (faster and more reliable).

## Test Matrix

✅ = Tested and worked for at least one run
❌ = Have not tested or tested but did not work

### Orcheo Skill

#### macOS / Linux

| Agent       | No Orcheo | Orcheo w/o .env | Orcheo w/ .env |
|-------------|-----------|-----------------|----------------|
| Claude Code | ✅         | ✅               | ✅              |
| Codex CLI   | ✅         | ✅               | ✅              |
| Cursor      | ✅         | ✅               | ✅              |

#### Windows (Not yet tested)

| Agent       | No Orcheo | Orcheo w/o .env | Orcheo w/ .env |
|-------------|-----------|-----------------|----------------|
| Claude Code | ❌         | ❌               | ❌              |
| Codex CLI   | ❌         | ❌               | ❌              |
| Cursor      | ❌         | ❌               | ❌              |

### Orcheo-Demos Skill

#### macOS / Linux

| Agent       | Demo 1 | Demo 2 | Demo 3-5 |
|-------------|--------|--------|----------|
| Claude Code | ❌      | ❌      | ❌        |
| Codex CLI   | ❌      | ❌      | ❌        |
| Cursor      | ❌      | ❌      | ❌        |

#### Windows (Not yet tested)

| Agent       | Demo 1 | Demo 2 | Demo 3-5 |
|-------------|--------|--------|----------|
| Claude Code | ❌      | ❌      | ❌        |
| Codex CLI   | ❌      | ❌      | ❌        |
| Cursor      | ❌      | ❌      | ❌        |
