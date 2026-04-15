import glob
import logging
import typer
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

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


if __name__ == "__main__":
    app()
