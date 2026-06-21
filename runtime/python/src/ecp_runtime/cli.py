import glob
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import typer
from pydantic import ValidationError

from .conformance import (
    build_conformance_report,
    conformance_check,
    validate_initialize_result,
    validate_reset_result,
    validate_step_result,
)
from .reporter import HTMLReporter
from .trend import RunTrendAnalyzer

# Import local modules (Using relative imports)
try:
    from .manifest import ECPManifest
    from .runner import ECPRunner
except ImportError:
    # Fallback for direct execution debugging
    sys.path.append(os.path.dirname(__file__))
    from manifest import ECPManifest
    from runner import ECPRunner

app = typer.Typer(
    name="ecp",
    help="Evaluation Context Protocol Runtime CLI",
    add_completion=False
)

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


@app.callback()
def main():
    """
    Official Runtime for the Evaluation Context Protocol (ECP).
    """
    pass


@app.command()
def run(
    manifest: Path = typer.Option(
        ...,
        "--manifest", "-m",
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Path to the test manifest YAML file"
    ),

    verbose: bool = False,
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Path to save an HTML report (e.g., output.html)",
        resolve_path=True,
    ),
    json_out: Optional[Path] = typer.Option(
        None,
        "--json-out",
        help="Path to save a JSON report (e.g., output.json)",
        resolve_path=True,
    ),
    print_json: bool = typer.Option(
        False,
        "--json",
        help="Print the JSON report to stdout",
    ),
    fail_on_error: bool = typer.Option(
        True,
        "--fail-on-error/--no-fail-on-error",
        help="Exit non-zero if any checks fail (useful for CI)",
    ),
):
    """
    Execute an evaluation run based on a manifest file.
    """
    _configure_logging(verbose)

    logger.info("ECP Runtime Initializing...")
    logger.info("Loading manifest: %s", manifest)

    try:
        # Load the YAML
        config = ECPManifest.from_yaml(str(manifest))

        # Run the Tests
        runner = ECPRunner(config)
        result_summary = runner.run_scenarios()
        total = int(result_summary.get("total", 0) or 0)
        passed = int(result_summary.get("passed", 0) or 0)
        failed = max(total - passed, 0)

        report_payload: Dict[str, Any] = {
            "manifest": str(manifest),
            "passed": passed,
            "total": total,
            "failed": failed,
            "scenarios": result_summary.get("scenarios", []),
        }

        if report:
            logger.info("Generating HTML report: %s", report)
            reporter = HTMLReporter()
            # Feed scenarios directly to reporter
            for scenario in result_summary.get("scenarios", []):
                reporter.add_scenario(scenario.get("name"), scenario.get("steps", []))
            reporter.save(str(report))
            logger.info("Report saved to %s", report)

        if json_out:
            json_out.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
            logger.info("JSON report saved to %s", json_out)

        if print_json:
            typer.echo(json.dumps(report_payload, indent=2))

        if fail_on_error and failed > 0:
            raise typer.Exit(code=2)

    except typer.Exit:
        raise
    except Exception as e:
        logger.error("CRITICAL ERROR: %s", e)
        if verbose:
            raise e
        sys.exit(1)


@app.command()
def validate(
    manifest: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the ECP manifest YAML file",
    ),
):
    """
    Validate a manifest without running the agent.
    """
    try:
        config = ECPManifest.from_yaml(str(manifest))
    except ValidationError as exc:
        typer.echo(f"Manifest invalid: {manifest}", err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Manifest invalid: {manifest}", err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    step_count = sum(len(scenario.steps) for scenario in config.scenarios)
    grader_count = sum(len(step.graders) for scenario in config.scenarios for step in scenario.steps)
    typer.echo(f"Manifest valid: {manifest}")
    typer.echo(f"Name: {config.name}")
    typer.echo(f"Scenarios: {len(config.scenarios)}")
    typer.echo(f"Steps: {step_count}")
    typer.echo(f"Graders: {grader_count}")


@app.command()
def doctor():
    """
    Check the local ECP runtime environment.
    """
    typer.echo("ECP doctor")
    typer.echo(f"Python: {sys.version.split()[0]}")
    typer.echo(f"Executable: {sys.executable}")
    typer.echo(f"Working directory: {Path.cwd()}")
    typer.echo(f"OpenAI key: {'set' if os.environ.get('OPENAI_API_KEY') else 'not set'}")
    typer.echo(f"Git: {'available' if shutil.which('git') else 'not found'}")


@app.command()
def init(
    directory: Path = typer.Argument(
        Path("ecp_eval"),
        help="Directory where a starter ECP agent and manifest should be created",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing starter files",
    ),
):
    """
    Create a minimal ECP evaluation project.
    """
    directory.mkdir(parents=True, exist_ok=True)
    agent_path = directory / "agent.py"
    manifest_path = directory / "manifest.yaml"

    if not force and (agent_path.exists() or manifest_path.exists()):
        typer.echo(f"Refusing to overwrite existing files in {directory}. Use --force to replace starters.", err=True)
        raise typer.Exit(code=1)

    agent_path.write_text(_starter_agent(), encoding="utf-8")
    manifest_path.write_text(_starter_manifest(agent_path.as_posix()), encoding="utf-8")

    typer.echo(f"Created {agent_path}")
    typer.echo(f"Created {manifest_path}")
    typer.echo(f"Try: ecp validate {manifest_path}")
    typer.echo(f"Then: ecp run --manifest {manifest_path}")


@app.command()
def conformance(
    target: str = typer.Option(
        ...,
        "--target",
        "-t",
        help="Agent command or ECP HTTP endpoint to check",
    ),
    step_input: str = typer.Option(
        "hello",
        "--input",
        help="Input text for the conformance step call",
    ),
    json_out: Optional[Path] = typer.Option(
        None,
        "--json-out",
        help="Path to save the machine-readable conformance report",
        resolve_path=True,
    ),
    print_json: bool = typer.Option(
        False,
        "--json",
        help="Print only the machine-readable conformance report",
    ),
):
    """
    Validate the core ECP protocol contract against an agent.
    """
    runner = ECPRunner(type("Manifest", (), {"target": target, "scenarios": []})())
    agent = runner._create_agent(target, rpc_timeout=float(os.environ.get("ECP_RPC_TIMEOUT", "30")))
    checks: List[Dict[str, Any]] = []
    started = False
    try:
        agent.start()
        started = True
        initialize = _run_conformance_call(
            agent,
            "initialize response",
            "agent/initialize",
            {"config": {}},
            result_validator=validate_initialize_result,
        )
        checks.append(initialize)
        if initialize["passed"]:
            checks.append(
                _run_conformance_call(
                    agent,
                    "step result contract",
                    "agent/step",
                    {"input": step_input},
                    result_validator=validate_step_result,
                )
            )
        else:
            checks.append(_skipped_conformance_check("step result contract", "agent/step"))
    except Exception as exc:
        checks.append(
            {
                "name": "initialize response",
                "method": "agent/initialize",
                "passed": False,
                "message": f"agent could not start: {exc}",
            }
        )
        checks.append(_skipped_conformance_check("step result contract", "agent/step"))
    finally:
        if started:
            checks.append(
                _run_conformance_call(
                    agent,
                    "reset response",
                    "agent/reset",
                    {},
                    result_validator=validate_reset_result,
                )
            )
            agent.stop()
        else:
            checks.append(_skipped_conformance_check("reset response", "agent/reset"))

    report = build_conformance_report(target, checks)
    rendered = json.dumps(report, indent=2)
    if json_out:
        json_out.write_text(rendered + "\n", encoding="utf-8")
    if print_json:
        typer.echo(rendered)
    else:
        for check in checks:
            marker = "PASS" if check["passed"] else "FAIL"
            typer.echo(f"{marker} | {check['name']} | {check['message']}")
        typer.echo(f"Conformance: {report['passed']}/{report['total']} checks passed")

    if not report["conformant"]:
        raise typer.Exit(code=1)


@app.command()
def trend(
    pattern: str = typer.Argument(
        ...,
        help="Glob pattern matching saved JSON report files (e.g. 'results/run-*.json')",
    ),
    window: int = typer.Option(
        20,
        "--window",
        "-w",
        help="Maximum number of recent runs to include in the analysis",
        min=1,
    ),
    exit_on_regression: bool = typer.Option(
        False,
        "--exit-on-regression",
        help="Exit with code 2 when a degrading trend is detected (for CI gates)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
):
    """
    Analyse pass-rate trends across a sequence of saved JSON report files.
    """
    _configure_logging(verbose)

    matched: List[Path] = sorted(Path(path) for path in glob.glob(pattern, recursive=True))

    if not matched:
        typer.echo(f"No files matched the pattern: {pattern}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(matched)} report(s). Analysing last {window}...")

    analyzer = RunTrendAnalyzer(matched, window=window)
    report = analyzer.analyze()

    typer.echo("")
    typer.echo(f"{'Run':<5}  {'Manifest':<45}  {'Passed':>6}  {'Total':>6}  {'Rate':>6}")
    typer.echo("-" * 74)
    for index, run in enumerate(report.runs, start=1):
        manifest_label = Path(run.manifest).name if len(run.manifest) > 45 else run.manifest
        rate_pct = f"{run.pass_rate * 100:.1f}%"
        typer.echo(f"{index:<5}  {manifest_label:<45}  {run.passed:>6}  {run.total:>6}  {rate_pct:>6}")

    typer.echo("")
    typer.echo(f"Trend Direction : {report.direction.upper()}")
    typer.echo(f"Slope (per run) : {report.pass_rate_slope:+.6f}")
    typer.echo(f"Window          : {len(report.runs)} run(s) analysed (max {report.window})")
    typer.echo(f"Regression flag : {'YES' if report.any_regression else 'No'}")
    typer.echo("")

    if report.any_regression and exit_on_regression:
        typer.echo("Regression detected. Exiting with code 2 (--exit-on-regression).", err=True)
        raise typer.Exit(code=2)


def _run_conformance_call(
    agent: Any,
    name: str,
    method: str,
    params: Dict[str, Any],
    *,
    result_validator: Optional[Callable[[Any], Any]] = None,
) -> Dict[str, Any]:
    try:
        response = agent.send_rpc(method, params)
    except Exception as exc:
        return {"name": name, "method": method, "passed": False, "message": str(exc)}
    return conformance_check(name, method, response, result_validator=result_validator)


def _skipped_conformance_check(name: str, method: str) -> Dict[str, Any]:
    return {
        "name": name,
        "method": method,
        "passed": False,
        "message": "skipped because a prerequisite failed",
    }


def _starter_agent() -> str:
    return '''from ecp import Result, agent, on_reset, on_step, serve


@agent(name="StarterAgent")
class StarterAgent:
    def __init__(self):
        self.seen = []

    @on_step
    def step(self, user_input: str):
        self.seen.append(user_input)
        return Result(
            public_output=f"Echo: {user_input}",
            evaluation_context="The starter agent echoed the user input.",
            tool_calls=[{"name": "echo", "arguments": {"text": user_input}}],
        )

    @on_reset
    def reset(self):
        self.seen.clear()


if __name__ == "__main__":
    serve(StarterAgent())
'''


def _starter_manifest(agent_filename: str) -> str:
    return f'''manifest_version: "v1"
name: "Starter ECP Evaluation"
target: 'python {agent_filename}'

scenarios:
  - name: "Echo contract"
    steps:
      - input: "hello ecp"
        graders:
          - type: text_match
            field: public_output
            condition: contains
            value: "hello ecp"
          - type: text_match
            field: evaluation_context
            condition: contains
            value: "echoed"
          - type: tool_usage
            tool_name: "echo"
            arguments:
              text: "hello ecp"
'''


if __name__ == "__main__":
    app()
