"""Utility functions for terminal UI and user input."""

from typing import Optional
from rich.console import Console
from rich.table import Table

console = Console()


def scanline(prompt: str = "") -> str:
    """Read a line of input from user."""
    if prompt:
        return input(prompt)
    return input()


def scanline_trim(prompt: str = "") -> str:
    """Read and trim a line of input from user."""
    return scanline(prompt).strip()


def choose_index(prompt: str, options: list, max_attempts: int = 3) -> Optional[int]:
    """
    Let user choose an index from a list of options.
    Returns the selected index or None if invalid.
    """
    for _ in range(max_attempts):
        try:
            choice = input(f"{prompt} (0-{len(options) - 1}): ")
            idx = int(choice)
            if 0 <= idx < len(options):
                return idx
            console.print(
                f"[red]Please enter a number between 0 and {len(options) - 1}[/red]"
            )
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled[/yellow]")
            return None

    console.print("[red]Too many invalid attempts[/red]")
    return None


def create_table(title: str, headers: list) -> Table:
    """Create a formatted table for display."""
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for header in headers:
        table.add_column(header)
    return table


def clear_screen():
    """Clear the terminal screen."""
    console.clear()


def format_result_color(result: str) -> str:
    """Format a test result with appropriate color."""
    result_upper = result.upper()

    if result_upper == "OK" or result_upper == "AC":
        return f"[green]{result}[/green]"
    elif result_upper in ["WA", "RT", "RE"]:
        return f"[red]{result}[/red]"
    elif result_upper in ["TL", "ML", "TLE", "MLE"]:
        return f"[magenta]{result}[/magenta]"
    elif result_upper in ["NO", "JUDGING", "PENDING"]:
        return f"[yellow]{result}[/yellow]"
    else:
        return result
