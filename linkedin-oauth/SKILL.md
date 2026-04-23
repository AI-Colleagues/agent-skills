---
name: linkedin-oauth
description: Obtain LinkedIn OAuth tokens and store them directly into the Orcheo vault as credentials. Use this skill whenever the user wants to authenticate with LinkedIn, set up LinkedIn credentials for Orcheo, run the LinkedIn OAuth flow, or store linkedin_access_token / linkedin_refresh_token / linkedin_id_token. Also trigger when the user says "connect LinkedIn", "LinkedIn auth", "set up LinkedIn posting", or any variant of needing LinkedIn tokens ready for use.
license: MIT
metadata:
  author: AI Colleagues
  version: 0.1.0
---

# LinkedIn OAuth → Orcheo Vault

Runs a local OAuth 2.0 flow against LinkedIn, exchanges the authorization code for
tokens, and stores each token directly into the Orcheo vault via `orcheo credential create`.
Tokens are never printed to the terminal or returned to the agent.

## Invocation

The user may optionally specify a profile name:
- "set up LinkedIn auth" → no profile
- "set up LinkedIn auth for profile staging" → `--profile staging`

---

## Step 1 — Verify required environment variables

Check whether `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` are set:

```bash
echo "CLIENT_ID set: $([ -n "$LINKEDIN_CLIENT_ID" ] && echo yes || echo NO)"
echo "CLIENT_SECRET set: $([ -n "$LINKEDIN_CLIENT_SECRET" ] && echo yes || echo NO)"
```

If **both are set**, skip to Step 2.

If **either is missing**, walk the user through obtaining them — see [Getting LinkedIn credentials](#getting-linkedin-credentials) below. Do not ask the user to paste secrets into the conversation.

---

## Getting LinkedIn credentials

Guide the user through these steps (they do everything in their browser and terminal — you only check the result):

1. **Create or open a LinkedIn app**
   - Go to <https://www.linkedin.com/developers/apps>
   - Select an existing app or click **Create app**
   - Under the **Auth** tab, note the **Client ID** and **Client Secret**

2. **Add the redirect URI**
   - Still on the Auth tab, add `http://127.0.0.1:8765/callback` to **Authorized redirect URLs**

3. **Enable required products**
   - On the **Products** tab, request access to:
     - **Share on LinkedIn** (provides `w_member_social`)
     - **Sign In with LinkedIn using OpenID Connect** (provides `openid`, `profile`, `w_member_social`)
   - If posting to an organization page is needed, also request **Marketing Developer Platform** (`w_organization_social`)

4. **Set the environment variables** — tell the user to run these in their terminal (not paste here):
   ```bash
   export LINKEDIN_CLIENT_ID="<your-client-id>"
   export LINKEDIN_CLIENT_SECRET="<your-client-secret>"
   ```
   Then ask them to confirm they've set both, and re-run the check from Step 1.

---

## Step 2 — Run the OAuth flow

Once both env vars are confirmed present, run the script. It will open a browser window for the user to authorize the app, then silently store the tokens.

```bash
uv pip install -r "$CODEX_HOME/skills/linkedin-oauth/requirements.txt"
python "$CODEX_HOME/skills/linkedin-oauth/scripts/linkedin_oauth_store.py" [--profile <profile_name>]
```

If this skill is being run from a repository checkout instead of an installed path, use the equivalent local path to `linkedin-oauth/scripts/linkedin_oauth_store.py`.
Include `--profile <profile_name>` only if the user specified one.

The script:
- Launches a temporary local HTTP server on port 8765 to receive the callback
- Opens the LinkedIn authorization page in the user's default browser
- Waits up to 5 minutes for the user to authorize
- Exchanges the code for tokens
- Calls `orcheo credential create` for each token (access, refresh, id)
- Prints only credential names and a success count — never the token values

### What the user will see

Tell them: "Your browser should open the LinkedIn authorization page. Please sign in, approve the permissions, and return here once the browser says 'Authorization received.'"

---

## Step 3 — Report outcome

After the script exits:

- **Exit 0**: Tell the user which credentials were stored (the script prints the names). Remind them the credentials are now available as `linkedin_client_id`, `linkedin_client_secret`, `linkedin_access_token`, `linkedin_refresh_token`, and optionally `linkedin_id_token` in the Orcheo vault.
- **Non-zero exit / error output**: Show the error message from the script and help diagnose the issue (common causes: wrong redirect URI, missing product access on the LinkedIn app, env vars not exported to the current shell).

---

## Notes

- The script inherits `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` from the current shell environment. If the user set them in a different terminal session, they must re-export in the same session where the agent is running, or use `LINKEDIN_CLIENT_ID=xxx LINKEDIN_CLIENT_SECRET=yyy python ...` prefix.
- Port 8765 must be free when the script runs. If it is in use, ask the user to set `LINKEDIN_REDIRECT_URI` to a different port (e.g., `http://127.0.0.1:9876/callback`) and update the LinkedIn app's redirect URL to match.
- Scope override: the user can set `LINKEDIN_SCOPES` env var to customize requested scopes.
- By default, the script first requests `w_organization_social` in addition to member/OpenID scopes and automatically retries without it if the app lacks Marketing Developer Platform access.
