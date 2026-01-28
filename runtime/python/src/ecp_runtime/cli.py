import typer
import sys
import os
from pathlib import Path
from rich.console import Console

# Import local modules (Using relative imports)
try:
    from .manifest import ECPManifest
    from .runner import ECPRunner
except ImportError:
    # Fallback for direct execution debugging
    sys.path.append(os.path.dirname(__file__))
    from manifest import ECPManifest
    from runner import ECPRunner

# Initialize the Typer App
app = typer.Typer(
    name="ecp",
    help="Evaluation Context Protocol Runtime CLI",
    add_completion=False
)
console = Console()

# 1. Define the Root Callback (Helps Typer understand this is a CLI group)
@app.callback()
def main():
    """
    Official Runtime for the Evaluation Context Protocol (ECP).
    """
    pass

# 2. Define the Run Command
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
    verbose: bool = False
):
    """
    Execute an evaluation run based on a manifest file.
    """
    console.print(f"[bold green]ECP Runtime Initializing...[/bold green]")
    console.print(f"📂 Loading manifest: {manifest}")

    try:
        # Load the YAML
        config = ECPManifest.from_yaml(str(manifest))
        
        # Run the Tests
        runner = ECPRunner(config)
        runner.run_scenarios()

    except Exception as e:
        console.print(f"[bold red]CRITICAL ERROR:[/bold red] {e}")
        if verbose:
            raise e # Show full traceback
        sys.exit(1)

if __name__ == "__main__":
    app()