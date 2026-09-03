# frontend/cli.py
import json
import os
import sys
from typing import Optional

from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure project root is available on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

app = typer.Typer(
    help="SatQuery AI — Command-Line Interface for Earth Observation Intelligence",
    add_completion=False
)
console = Console()


@app.command(name="analyze")
def analyze(
    image1: str = typer.Option(..., "--image1", "-i1", help="Path to primary satellite/aerial image file"),
    query: str = typer.Option(..., "--query", "-q", help="Natural language query or instruction"),
    image2: Optional[str] = typer.Option(None, "--image2", "-i2", help="Optional secondary image path for bi-temporal/multi-modal tasks"),
    show_trace: bool = typer.Option(False, "--trace", "-t", help="Print the full JSON execution trace"),
):
    """Execute multi-modal satellite image analysis through the SatQuery orchestrator."""
    if not os.path.exists(image1):
        console.print(f"[bold red]Error:[/bold red] Image file not found at: {image1}")
        raise typer.Exit(code=1)

    paths = [image1]
    if image2:
        if not os.path.exists(image2):
            console.print(f"[bold red]Error:[/bold red] Secondary image file not found at: {image2}")
            raise typer.Exit(code=1)
        paths.append(image2)

    with console.status("[cyan]Extracting imagery metadata and orchestrating pipeline...", spinner="dots"):
        from orchestrator.metadata import extract_metadata
        from orchestrator.graph import orchestrator_app
        from orchestrator.graph_state import create_initial_state

        meta = [extract_metadata(p) for p in paths]
        state = create_initial_state(query=query, images_raw=paths, images_meta=meta)
        final_state = orchestrator_app.invoke(state)

    trace = final_state.get("trace") or {}
    result = final_state.get("result") or {}
    answer_text = result.get("text", "No result returned.")

    is_rejected = (
        not final_state.get("validation_ok", True)
        or final_state.get("task") == "reject"
    )

    # Header Panel
    console.print("\n[bold cyan]🛰️  SatQuery AI Execution Summary[/bold cyan]")

    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Property", style="dim", width=20)
    summary_table.add_column("Value")

    summary_table.add_row("Selected Task", f"[green]{trace.get('selected_task', 'reject')}[/green]")
    summary_table.add_row("Model Deployed", f"[blue]{trace.get('model_used', 'none')}[/blue]")
    summary_table.add_row("Task Mode", str(trace.get("parameters", {}).get("mode", "N/A")))
    summary_table.add_row("Validation Status", f"[yellow]{trace.get('validation', 'ok')}[/yellow]")

    conf = trace.get("output_confidence")
    conf_str = f"{conf:.0%}" if isinstance(conf, (int, float)) else "N/A"
    summary_table.add_row("Confidence", f"[bold green]{conf_str}[/bold green]")

    console.print(summary_table)

    # Result or Rejection Display
    if is_rejected:
        console.print(
            Panel(
                f"[bold red]Validation Failed / Request Rejected:[/bold red]\n{final_state.get('validation_msg', 'Incompatible request.')}",
                title="[red]Rejection Notice[/red]",
                border_style="red"
            )
        )
    else:
        console.print(
            Panel(
                f"[bold white]{answer_text}[/bold white]",
                title="[green]Analysis Answer[/green]",
                border_style="green"
            )
        )

    # Trace Details
    if show_trace:
        console.print("\n[bold cyan]Auditable Execution Trace (JSON):[/bold cyan]")
        console.print_json(data=trace)


if __name__ == "__main__":
    app()
