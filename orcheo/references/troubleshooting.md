# Troubleshooting

## Workflow uploading or running issues

Validation depends on the server's workflow definition mode
(`ORCHEO_WORKFLOW_DEFINITION_MODE`) — see
[coding.md](./coding.md#definition-modes-and-validation).

### Failures in both modes

- `Compilation error: ...`: plain Python syntax error; fix the reported line.
- `LangGraph script exceeds the permitted size of N bytes`: remove dead code
  and trim large constants or embedded assets.
- Upload rejected at the API layer: managed deployments block client-supplied
  scripts entirely; the server must set
  `ORCHEO_WORKFLOW_TRUST_MODE=allow_client_uploads` (self-hosted only).

### Unrestricted mode (current default)

The script executes in-process with full Python builtins at build time:

- `LangGraph script execution exceeded the configured timeout`: module-level
  code and the entrypoint should only assemble the graph — move I/O and heavy
  computation into node execution.
- `Script did not produce a LangGraph StateGraph`: expose a top-level
  `StateGraph` or an `orcheo_workflow()` function returning one.
- `Multiple StateGraph candidates discovered; specify an entrypoint`: pass
  `--entrypoint <function>` (or set the `entrypoint` frontmatter key), or keep
  a single graph per file.

### Restricted mode (frozen IR)

The script never executes; an AST validator compiles it to a frozen IR and
rejects anything outside the declarative grammar:

- `imports must come from Orcheo; '<module>' is not allowed`: import only from
  `orcheo.*` (e.g. `from orcheo.graph import StateGraph`) and move other logic
  into `CodeNode` bodies.
- `relative imports are not allowed` / `star imports are not allowed`: use
  absolute `orcheo.*` imports.
- Rejections for lambdas, comprehensions, starred args, `await`/`yield`, or
  underscore/dunder access: keep the `orcheo_workflow` entrypoint declarative
  (node/edge construction and graph assembly only) and put computation in
  `CodeNode.run` bodies, which run in the MicroPython-WASM sandbox with a
  builtin allowlist.

### Templated custom-node fields

`ValidationError` during upload for a templated custom-node field, for
example `Input should be a valid list` with
`input_value='{{config.configurable.text_fields}}'`: node constructors are
validated before runtime template resolution, so custom node fields must
accept the unresolved template string. If the runtime value is expected to be
a list/dict/bool/etc., widen the field annotation to also include `str` (for
example `list[str] | str`). Orcheo runtime resolves the template before node
execution.
