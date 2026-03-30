---
name: data-coffee
description: Connect to the Data Coffee MCP community, including first-time setup, token registration, profile maintenance, coffee session discovery and creation, and member messaging. Use when Codex needs to configure the Data Coffee MCP endpoint, help a user join the community, or operate Data Coffee tools such as profile_register, coffee_list, coffee_create, coffee_join, or message_inbox.
---

# Data Coffee

Connect to the Data Coffee MCP endpoint, complete first-run registration, and use the community tools without making the user manually reconstruct the workflow from the landing page.

Use this skill as an MCP onboarding and operating guide. Keep the main flow short, then open [setup.md](./references/setup.md) when you need exact config snippets, prompts, or failure handling.

## Quick start

1. Check whether a `data-coffee` MCP server is already configured.
2. If setup details are needed, open [setup.md](./references/setup.md).
3. If the user has no token yet, register with `profile_register` using the user's nickname and a concise bio.
4. Persist the returned token in the MCP config as `Authorization: Bearer <token>`.
5. Ask the user to restart or reload the client if the client does not hot-reload MCP auth changes.
6. After authentication works, use the Coffee and message tools for the user's actual goal.

## Workflow

### 1. Connect and verify

- Prefer reusing an existing `data-coffee` config block instead of overwriting unrelated MCP settings.
- Use `./scripts/render_mcp_config.py` when you need a clean JSON snippet with or without a token.
- If the user is registering for the first time, gather only the minimum inputs required by the live tool: `nickname` and `bio`.
- If registration succeeds, surface the token clearly and tell the user exactly where it must go.

### 2. Operate the community tools

- Profile:
  - Use `profile_get` to inspect an existing member profile.
  - Use `profile_update` only for fields the user actually wants to change.
- Coffee sessions:
  - Use `coffee_list` before recommending sessions.
  - Use `coffee_detail` before `coffee_join` when the user asks about one specific session.
  - Use `coffee_create` when the user wants to organize a meetup; gather topic, format, location, and time if missing.
  - Use `coffee_update` or `coffee_complete` only when the user is the creator or explicitly managing their own session.
- Messaging:
  - Use `message_inbox` to review direct messages, coffee messages, or system notifications.
  - Use `message_send` only after the user is clear about the recipient or target coffee.
  - Use `message_read` after reviewing messages when the user wants inbox cleanup.

### 3. Keep the interaction clean

- Do not invent profile details, cities, schedules, or tags.
- Do not claim registration is complete until the token is persisted and the client can use it.
- If the MCP server is unreachable, separate client-config issues from remote-service issues.
- If a tool requires authentication and returns an auth error, fall back to the setup flow instead of retrying blindly.

## Reference map

- Open [setup.md](./references/setup.md) for:
  - exact MCP config JSON
  - registration and token flow
  - suggested prompts
  - common troubleshooting

- Use [render_mcp_config.py](./scripts/render_mcp_config.py) to generate a config block quickly.

## Example requests

- "Use $data-coffee to help me connect the MCP endpoint and register with nickname `Alex`."
- "Use $data-coffee to check whether there are any Amsterdam coffee sessions this weekend."
- "Use $data-coffee to draft and create a coffee about MLOps hiring in Rotterdam next Wednesday evening."
- "Use $data-coffee to review my unread messages and mark them read after summarizing."
