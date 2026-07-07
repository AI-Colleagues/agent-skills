# Coding Orcheo workflows

Use `orcheo code` to generate workflow or node scaffolds.
When unsure of the available options, use the `--help` flag to see all available options.

## Install the Orcheo library

```bash
uv pip install -U orcheo
```

## Generate starter code

```bash
orcheo code template -o workflow.py            # minimal LangGraph workflow file
orcheo code template --name my_workflow        # set the workflow name
orcheo code scaffold <workflow_id>             # Python snippet that triggers an uploaded workflow via the SDK
```

## Workflow file contract

Orcheo loads any top-level `StateGraph` or an `orcheo_workflow` function (sync or
async) that returns one. A single graph-returning function with another name is
auto-discovered; `--entrypoint` (or the `entrypoint` frontmatter key) is only
needed to disambiguate when a file has several candidates. Prefer the name
`orcheo_workflow` — restricted definition mode (below) requires exactly that name.

```python
from orcheo.graph import END, START, StateGraph
from orcheo.graph.state import State


async def orcheo_workflow() -> StateGraph:
    """Build and return the workflow graph."""
    graph = StateGraph(State)
    # graph.add_node(...); graph.add_edge(...)
    return graph
```

Rules that matter when writing nodes:

- Build `StateGraph(State)`; `State` provides `inputs`, `node_results`,
  `messages`, `structured_response`, and `config`.
- Give every node instance a `name` equal to its `add_node` key — the node's
  output fields merge into state under `node_results.<node_name>`.
- Template node fields with `{{...}}` placeholders, resolved at runtime:
  - `{{inputs.foo}}` — run inputs.
  - `{{node_results.<node_name>.field}}` — upstream node outputs.
  - `{{config.configurable.key}}` — values from the runnable config
    (`config.json` / `--config`).
- Reference vault secrets with `[[credential_name]]` placeholders; never
  hardcode secret values.
- Keep each workflow file self-contained; do not import helpers from sibling
  workflow files.

## Definition modes and validation

The server's `ORCHEO_WORKFLOW_DEFINITION_MODE` selects how uploaded scripts are
validated. Script size limits apply in both modes.

- **unrestricted** (current default): the script executes in-process with full
  Python builtins at build time, under an execution timeout. There is no
  import allowlist. Client uploads are only accepted when the server sets
  `ORCHEO_WORKFLOW_TRUST_MODE=allow_client_uploads`.
- **restricted**: the script never executes — an AST validator compiles it to
  a frozen IR and accepts only a small declarative grammar:
  - Imports must be absolute `orcheo.*` imports (no `langgraph`, stdlib, or
    third-party imports; no relative or star imports).
  - A single zero-argument `orcheo_workflow` function is the required
    entrypoint.
  - Construction-time code is limited to node/edge instantiation and graph
    assembly (`add_node`, `add_edge`, `add_conditional_edges`,
    `set_entry_point`, `set_finish_point`, `compile`); lambdas,
    comprehensions, starred args, `await`/`yield`, and underscore/dunder
    access are rejected.
  - Custom logic goes in `CodeNode` subclass `run` bodies, which execute in a
    MicroPython-WASM sandbox with a builtin allowlist.

Write workflows that satisfy the restricted grammar (Orcheo-only imports, a
declarative `orcheo_workflow` entrypoint, computation inside `CodeNode`
bodies) so they ingest in either mode.

For rejection messages and fixes, see
[troubleshooting.md](./troubleshooting.md).

## Custom node fields that accept templates

Ingestion validates node constructors before templates are resolved. Any custom
node field that may receive a `{{...}}` placeholder must also accept `str`:

```python
text_fields: list[str] | str
```

## Workflow metadata frontmatter

Declare upload metadata in a PEP 723-style comment block at the top of the
file (parsed as TOML; CLI flags override frontmatter values):

```python
# /// orcheo
# name = "My Workflow"
# handle = "my-workflow"
# description = "Short human-readable summary."
# version = "1.0.0"
# entrypoint = "orcheo_workflow"
# config = "./config.json"
# avatar = "avatar-07"
# subtitle = "AI Assistant"
# ///
```

Allowed keys: `name`, `id`, `handle`, `description`, `config`, `entrypoint`,
`avatar`, `subtitle`, `notes`, `metadata`, `version`, and `[[updates]]`
entries (strict SemVer `version` with a `summary` and optional `migration`
note per release).

## Inspect schemas while coding

```bash
orcheo node list                     # full registry of built-in nodes
orcheo node show <node_name>
orcheo edge list
orcheo edge show <edge_name>
orcheo agent-tool list
orcheo agent-tool show <tool_name>
```

After coding, upload and run the workflow following
[operations.md](./operations.md).
