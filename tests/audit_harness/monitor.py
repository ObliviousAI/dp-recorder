#!/usr/bin/env python3
import time
import sys
from pathlib import Path

try:
    from rich.live import Live
    from rich.table import Table
    from rich.console import Console

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

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


def _monitor_rich(manifest_names: list[str]):
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


def _monitor_plain(manifest_names: list[str]):
    total = len(manifest_names)
    print(f"Monitoring {total} run(s). Install 'rich' for a live table view.")
    seen_done: set[str] = set()
    while True:
        done = []
        running = []
        for name in manifest_names:
            stem = Path(name).stem
            if (RESULTS_DIR / f"{stem}.json").exists():
                done.append(name)
            else:
                running.append(name)

        for name in done:
            if name not in seen_done:
                seen_done.add(name)
                print(f"  [{len(seen_done)}/{total}] DONE: {name}")

        if len(done) == total:
            break
        time.sleep(1.0)


def monitor(manifest_names: list[str]):
    if HAS_RICH:
        _monitor_rich(manifest_names)
    else:
        _monitor_plain(manifest_names)


if __name__ == "__main__":
    monitor(sys.argv[1:])
