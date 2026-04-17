#!/usr/bin/env python3
import time
import sys
from pathlib import Path
from rich.live import Live
from rich.table import Table
from rich.console import Console

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def get_last_line(file_path: Path) -> str:
    if not file_path.exists():
        return "Starting..."
    try:
        with open(file_path, "rb") as f:
            f.seek(0, 2)
            if f.tell() == 0:
                return "Initializing..."
            f.seek(max(0, f.tell() - 1024))
            lines = f.read().decode("utf-8", errors="ignore").splitlines()
            return lines[-1][:100] if lines else "..."
    except Exception:
        return "..."


def monitor(manifest_names: list[str]):
    console = Console()
    with Live(refresh_per_second=2, console=console) as live:
        while True:
            table = Table(title="[bold]runs[/bold]", box=None)
            table.add_column("Manifest", style="cyan", no_wrap=True)
            table.add_column("Status", style="green")
            table.add_column("Current / Last Output", style="dim", no_wrap=True)

            all_done = True
            for name in manifest_names:
                stem = Path(name).stem
                stdout_path = RESULTS_DIR / f"{name}.stdout"
                json_path = RESULTS_DIR / f"{stem}.json"

                is_done = json_path.exists()
                if not is_done:
                    all_done = False

                status = (
                    "[green]DONE[/green]" if is_done else "[yellow]RUNNING[/yellow]"
                )
                last_line = get_last_line(stdout_path) if not is_done else ""

                table.add_row(name, status, last_line)

            live.update(table)
            if all_done:
                break
            time.sleep(0.5)


if __name__ == "__main__":
    monitor(sys.argv[1:])
