# CI Usage

ECP is designed to fail builds when agent behavior regresses.

## GitHub Actions

```yaml
name: ECP evals

on:
  pull_request:
  push:
    branches: [main]

jobs:
  evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install "ecp-runtime==0.3.1" "ecp-sdk==0.3.1"
      - run: ecp validate examples/customer_support_demo/manifest.yaml
      - run: ecp run --manifest examples/customer_support_demo/manifest.yaml --json-out ecp-report.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ecp-report
          path: ecp-report.json
```

`ecp run` exits with code `2` when checks fail. This makes it suitable for pull request gates.

## Useful Flags

```bash
ecp run --manifest evals/support.yaml --json
ecp run --manifest evals/support.yaml --json-out report.json
ecp run --manifest evals/support.yaml --report report.html
ecp run --manifest evals/support.yaml --no-fail-on-error
```

## Local Preflight

```bash
ecp doctor
ecp validate evals/support.yaml
ecp conformance --target "python agent.py"
```

For CI systems, emit a stable machine-readable report:

```bash
ecp conformance --target "python agent.py" --json-out conformance.json
```

The command exits with code `1` when any initialize, step-result, or reset
contract check fails. Use `--json` to print only the JSON report to stdout.
