import logging
import typer
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

from .reporter import HTMLReporter

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


if __name__ == "__main__":
    app()
