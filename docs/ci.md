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
      - run: pip install "ecp-runtime==0.9.0" "ecp-sdk==0.9.0"
      - run: ecp validate examples/customer_support_demo/manifest.yaml
      - run: |
          ecp run --manifest examples/customer_support_demo/manifest.yaml \
            --timeout 60 --max-duration 900 \
            --json-out ecp-report.json --audit-out ecp-audit.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ecp-report
          path: |
            ecp-report.json
            ecp-audit.json
```

`ecp run` exits with code `2` when checks fail. This makes it suitable for pull request gates.

## Bounding The Job

A looping or hung agent must not pin the runner. Two limits apply, and you want both:

```bash
ecp run --manifest evals/support.yaml --timeout 60 --max-duration 900
```

`--timeout` (`ECP_RPC_TIMEOUT`, default 30s) bounds a single RPC. `--max-duration` (`ECP_MAX_DURATION`, unset by default) bounds the whole run - an agent that answers just inside the per-RPC timeout on every step can still burn an hour of CI without ever tripping it.

When a limit is breached, the run degrades rather than aborting: the failing step is recorded, the rest of that scenario is skipped, the next scenario runs against a fresh agent, and you still get a complete report artifact. Steps that never produced a result count as failed checks, so a timed-out step cannot pass a gate.

## Auditing A Run

Upload `ecp-audit.json` alongside the report. It is the record of what actually happened:

```json
{
  "run_id": "3f1c...",
  "exit_reason": "timeout",
  "manifest": { "digest": "sha256:c8a39311...", "target": "python agent.py" },
  "agent": { "name": "SupportAgent" },
  "limits": { "rpc_timeout_s": 60.0, "max_duration_s": 900.0 },
  "totals": { "steps_planned": 4, "steps_executed": 2, "steps_failed": 1, "steps_skipped": 1 },
  "latency": { "max_ms": 812.4, "p95_ms": 790.1 },
  "usage": { "input_tokens": 4820, "output_tokens": 356, "total_tokens": 5176 }
}
```

Two fields matter most when reviewing a build:

- `exit_reason` - `ok` means every scenario ran to completion. Anything else means the run degraded.
- `steps_planned` vs `steps_executed` - a gap here means a high pass rate was measured over fewer steps than intended.

The manifest `digest` ties the result to the exact manifest contents, so a report can be traced back to its inputs. The schema is `schema/audit.schema.json`.

## Useful Flags

```bash
ecp run --manifest evals/support.yaml --json
ecp run --manifest evals/support.yaml --json-out report.json
ecp run --manifest evals/support.yaml --audit-out ecp-audit.json
ecp run --manifest evals/support.yaml --report report.html
ecp run --manifest evals/support.yaml --timeout 60 --max-duration 900
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
