---
name: codex-quotas
description: Read Codex usage quotas and present the `5h limit` and `Weekly limit` rows as a Markdown table. Use when Codex needs to check current usage, remaining quota, reset times, or summarize the output of `codex /status`.
---

# Codex Quotas

Run `python3 /Users/shaojiejiang/.codex/skills/codex-quotas/scripts/report_quotas.py` first. The helper opens the Codex slash-command palette in a PTY, selects `status`, handles ANSI escapes, box drawing characters, wrapped reset lines, and retries once when Codex returns the `refresh requested` interstitial.

## Workflow

- Run `python3 /Users/shaojiejiang/.codex/skills/codex-quotas/scripts/report_quotas.py`.
- If the user already pasted raw `codex /status` output, run `python3 /Users/shaojiejiang/.codex/skills/codex-quotas/scripts/report_quotas.py --stdin` and feed the pasted block through stdin.
- If the live attempt still fails after the built-in refresh retry, ask the user to paste the visible `codex /status` block.
- Return only the Markdown table unless the helper reports a failure.

## Output

Emit this shape:

```markdown
| Quota | Left | Reset |
| --- | --- | --- |
| 5h limit | 100% | resets 13:22 |
| Weekly limit | 79% | resets 22:40 on 16 Apr |
```

Keep the original quota labels exactly as `5h limit` and `Weekly limit`.

## Parsing Rules

- Extract only the `5h limit` and `Weekly limit` rows.
- Preserve the `NN%` value exactly as shown.
- Capture reset text from the same line when present.
- If the weekly reset appears on the next wrapped line, attach that line to `Weekly limit`.
- Ignore progress bars, model metadata, and other status fields.

## Failure Handling

- If the helper cannot find a quota block, report that the interactive Codex status view did not emit parseable quota lines in the current environment.
- Ask the user for the raw status block only when the helper cannot parse live output and no pasted output is available.
