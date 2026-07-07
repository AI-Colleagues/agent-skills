# Configure Orcheo CLI

## Purpose

Configure `orcheo` CLI through the `orcheo config` command so regular `orcheo` commands do not require repeated environment exports.
When needed, use `orcheo config --help` to see all available options.

## Required values

Ask the user for the following values:
- `--api-url` (always required)
- one of:
  - `--service-token`
  - `--auth-issuer` and `--auth-client-id` and `--auth-audience`

## Optional values

Ask if the user needs to provide the following values:
- `--auth-organization`
- `--auth-scopes`
- `--studio-url`
- `--env-file <path>` to read values from a `.env` file instead of flags

## Profiles

- `orcheo config list` shows all configured profiles.
- Pass `--profile <name>` to any `orcheo` command to use a non-default profile.
- `orcheo workspace use <slug>` sets the active workspace for the profile;
  `--workspace <slug>` overrides it per invocation.
