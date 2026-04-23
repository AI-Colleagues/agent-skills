---
name: claude-quotas
description: Check and report Claude usage quotas — current session and current week. Use this skill whenever the user asks about their Claude usage, quotas, rate limits, how much they've used, how much is left, when usage resets, or anything like "show my claude usage", "check my quotas", "how much have I used this week", "am I close to my limit", or "/claude-quotas". Always use this skill for quota-related queries — don't try to report usage without it.
license: MIT
metadata:
  author: AI Colleagues
  version: 0.1.0
---

# Claude Quotas

Report the user's current Claude usage quotas as a clean Markdown table.

## How to use this skill

Run the bundled script to capture and parse `claude /usage`, then display the results.

```bash
python3 ~/.claude/skills/claude-quotas/scripts/get_usage.py
```

The script outputs a Markdown table. Display it directly in your response.

If the script fails (e.g. `claude` not on PATH, pty capture timeout), fall back to:
1. Running `claude /usage` directly via Bash and parsing the raw output manually
2. Telling the user the command to run themselves

## Expected output format

After running the script, present the results like this:

```markdown
| Quota | Used | Resets |
|-------|------|--------|
| Current session | 1% | 1pm (Europe/Amsterdam) |
| Current week | 25% | Apr 13 at 8am (Europe/Amsterdam) |
```

Keep it brief — just the table, no preamble. If the user asks follow-up questions about what the numbers mean, answer them.
