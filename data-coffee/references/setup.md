# Data Coffee setup

Use this page when you need exact MCP configuration, first-run registration steps, or quick recovery from auth and connectivity problems.

## Endpoint

- MCP endpoint: `https://data-coffee.vercel.app/api/mcp`

## Config snippets

From the skill root, use `./scripts/render_mcp_config.py` to generate the snippet, or copy one of these directly.

Prefer `DATA_COFFEE_TOKEN=... ./scripts/render_mcp_config.py` or pasting the token directly into the config file. Avoid `--token` on shared systems because command-line arguments can be exposed in shell history and process listings.

These JSON examples are MCP server config snippets, so they use `"type": "http"`. The `agents/openai.yaml` example is a different agent-specific format and uses `transport: "streamable_http"` for the same endpoint.

Without token yet:

```json
{
  "mcpServers": {
    "data-coffee": {
      "type": "http",
      "url": "https://data-coffee.vercel.app/api/mcp"
    }
  }
}
```

With token:

```json
{
  "mcpServers": {
    "data-coffee": {
      "type": "http",
      "url": "https://data-coffee.vercel.app/api/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

## First-run flow

1. Add the endpoint without a token.
2. Connect or restart the client so the MCP server is visible.
3. Register through the MCP tool with the minimum required inputs:
   - `nickname`
   - `bio`
4. Copy the returned token into the MCP config as a bearer token.
5. Restart or reload the client if needed.
6. Verify authenticated tools by reading a profile or listing coffees.

## Natural-language prompts

- `帮我注册 data-coffee，昵称：<name>，自我介绍：<bio>`
- `Help me register for data-coffee with nickname <name> and this bio: <bio>`
- `Use $data-coffee to connect the MCP server and tell me exactly where to paste the token.`

## Tool map

- Profile:
  - `profile_register`
  - `profile_get`
  - `profile_update`
- Coffee:
  - `coffee_list`
  - `coffee_detail`
  - `coffee_create`
  - `coffee_join`
  - `coffee_leave`
  - `coffee_update`
  - `coffee_complete`
- Messages:
  - `message_inbox`
  - `message_send`
  - `message_read`

## Troubleshooting

- `Authentication required`
  - The MCP server is reachable, but the current request has no valid bearer token.
  - Register first or update the token in config, then reload the client.
- `Tool not found` or MCP server not visible
  - The client did not load the `data-coffee` MCP server.
  - Recheck the config shape and restart the client.
- Network or connection failure
  - Verify the endpoint URL exactly matches `https://data-coffee.vercel.app/api/mcp`.
  - Treat this as a remote-service or connectivity problem, not a profile problem.

## Operating hints

- For session discovery, start with `coffee_list` and narrow down later.
- For joining, inspect details first if the user cares about schedule, participants, or location.
- For creating a session, gather missing fields instead of guessing:
  - topic
  - city or online
  - location or meeting link
  - time
  - max size
  - tags
