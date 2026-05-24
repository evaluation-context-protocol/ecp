# Contributing To ECP

Thanks for helping improve the Evaluation Context Protocol.

ECP is a vendor-neutral protocol and reference runtime for portable AI agent evaluations. The project is still experimental, so contributions that improve clarity, compatibility, tests, examples, and developer experience are especially valuable.

## Project Goals

ECP should make it easy to:

- run repeatable agent evals locally and in CI
- evaluate `public_output`, `tool_calls`, and `evaluation_context`
- keep eval contracts portable across frameworks and platforms
- implement the protocol in other languages or runtimes
- avoid coupling evaluation data to one hosted product

New protocol features should preserve that portability.

## Repo Layout

- `sdk/python/` - Python SDK for wrapping agents
- `runtime/python/` - reference runtime and `ecp` CLI
- `examples/` - runnable example agents and manifests
- `schema/` - JSON Schema contracts
- `spec/` - protocol specification source
- `docs/` - documentation site content
- `client/` and `server/` - local Inspector UI and proxy server

## Local Setup

```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e runtime/python
pip install -e sdk/python
pip install -r docs/requirements.txt
```

For framework-specific examples, install the relevant SDK extra:

```bash
pip install -e "sdk/python[langchain]"
pip install -e "sdk/python[crewai]"
pip install -e "sdk/python[pydanticai]"
pip install -e "sdk/python[llamaindex]"
```

## Running Tests

Runtime tests:

```bash
$env:PYTHONPATH="runtime/python/src"
python -m unittest discover runtime/python/tests
```

SDK tests:

```bash
$env:PYTHONPATH="sdk/python/src"
python -m unittest discover sdk/python/tests
```

Docs:

```bash
mkdocs build --strict
```

Flagship demo smoke test:

```bash
$env:PYTHONPATH="runtime/python/src;sdk/python/src"
python -m ecp_runtime.cli validate examples/customer_support_demo/manifest.yaml
python -m ecp_runtime.cli run --manifest examples/customer_support_demo/manifest.yaml --json
```

## Contribution Priorities

Good first contributions:

- clearer docs or examples
- better error messages
- additional manifest validation
- CI examples
- report readability improvements
- adapter normalization fixes
- JSON Schema improvements

Larger contributions:

- conformance test expansion
- additional language SDKs
- exporter integrations
- richer grader types
- Inspector improvements
- protocol versioning proposals

## Protocol Changes

Protocol changes should update all relevant surfaces:

- `spec/protocol.md`
- `docs/spec.md`
- JSON Schemas in `schema/`
- SDK result types
- runtime parsing/grading/reporting
- examples and tests

Prefer additive changes where possible. If a field must be renamed or deprecated, keep a compatibility path for at least one release line.

`evaluation_context` is the preferred field for evaluator-safe audit evidence. `private_thought` remains a deprecated compatibility alias and should not be used in new examples.

## Docs And Messaging

Keep the positioning consistent:

> ECP is a vendor-neutral protocol for portable AI agent evaluations.

Avoid describing ECP as just another eval platform. The stronger framing is that ECP is the contract layer that can run locally, in CI, or feed other tools.

When updating install instructions, keep these surfaces aligned:

- root `README.md`
- `docs/index.md`
- `docs/quickstart.md`
- `sdk/python/README.md`
- `runtime/python/README.md`
- package metadata in `pyproject.toml`

## Examples

Examples should be runnable and minimal. A good example demonstrates at least one of:

- output grading
- required tool use
- `evaluation_context`
- CI/report output
- framework adapter behavior

The flagship example is `examples/customer_support_demo`. Keep it stable and easy to explain.

## Pull Request Checklist

Before opening a PR:

- tests pass for changed packages
- docs build if docs changed
- examples still use `evaluation_context`
- README/docs/PyPI-facing text stay consistent
- protocol changes include schema and spec updates
- new behavior has focused tests

## Questions And Proposals

For larger ideas, open an issue first with:

- the problem you are solving
- why it belongs in the protocol or runtime
- proposed API/schema changes
- compatibility impact
- example manifest or agent output
