import typer
from pathlib import Path
from rich.console import Console
from .manifest import ECPManifest
from .runner import ECPRunner

app = typer.Typer()
console = Console()

@app.command()
def run(
    manifest: Path = typer.Option(..., help="Path to the test manifest YAML file"),
    verbose: bool = False
):
    """
    Execute an ECP Evaluation run.
    """
    if not manifest.exists():
        console.print(f"[red]Error: Manifest file {manifest} not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]ECP Runtime v0.1.0[/bold green]")
    console.print(f"Loading manifest: {manifest}")

    # 1. Parse Manifest
    try:
        config = ECPManifest.from_yaml(str(manifest))
    except Exception as e:
        console.print(f"[red]Invalid YAML Manifest:[/red] {e}")
        raise typer.Exit(code=1)

    # 2. Run Tests
    runner = ECPRunner(config)
    runner.run_scenarios()

    console.print("\n[bold blue]Run Complete.[/bold blue]")

if __name__ == "__main__":
    app()