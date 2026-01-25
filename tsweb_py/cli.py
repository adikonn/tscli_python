"""Command-line interface for tsweb_py."""

import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .client import TestSysClient
from .config import LocalConfig
from .utils.terminal import choose_index, format_result_color


console = Console()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """tsweb_py - CLI client for TestSys online judge system."""
    pass


@cli.command()
def login():
    """Save TestSys credentials for future use."""
    client = TestSysClient()
    client.login()


@cli.group()
def local():
    """Manage local contest configuration."""
    pass


@local.command(name="show")
def local_show():
    """Display current local configuration."""
    config = LocalConfig.load()

    if config is None:
        console.print("[red]No local configuration found.[/red]")
        console.print("Run 'tsweb_py local set-contest' to create one.")
        return

    # Show current contest from session
    client = TestSysClient()
    if client.auto_login():
        user_info = client.get_user_info()
        if "contest" in user_info:
            console.print(
                f"\n[bold cyan]Current Contest:[/bold cyan] {user_info['contest']}"
            )

    if config.compilers:
        compiler = config.get_compiler()
        if compiler:
            console.print(
                f"[bold cyan]Default Compiler:[/bold cyan] {compiler.compiler_name}"
            )

    if config.problems:
        console.print(f"\n[bold cyan]Available Problems:[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")

        for problem in config.problems:
            table.add_row(problem.problem_id, problem.problem_name)

        console.print(table)

    if config.compilers:
        console.print(f"\n[bold cyan]Available Compilers:[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan")
        table.add_column("Language", style="yellow")
        table.add_column("Name", style="white")

        for idx, compiler in enumerate(config.compilers):
            marker = "*" if idx == config.default_lang else ""
            table.add_row(
                f"{idx}{marker}", compiler.compiler_lang, compiler.compiler_name
            )

        console.print(table)


@local.command(name="set-contest")
def local_set_contest():
    """Select and configure a contest."""
    client = TestSysClient()

    # Auto-login if credentials saved
    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    # Fetch available contests
    console.print("[cyan]Fetching available contests...[/cyan]")
    contests = client.get_available_contests()

    if not contests:
        console.print("[red]No contests found.[/red]")
        return

    # Display contests
    table = Table(
        title="Available Contests", show_header=True, header_style="bold cyan"
    )
    table.add_column("#", style="cyan")
    table.add_column("ID", style="yellow")
    table.add_column("Name", style="white")
    table.add_column("Status", style="magenta")

    for idx, contest in enumerate(contests):
        table.add_row(str(idx), contest.id, contest.name, contest.status)

    console.print(table)

    # Let user choose
    idx = choose_index("Select contest", contests)
    if idx is None:
        return

    selected = contests[idx]

    # Change to selected contest
    if not client.change_contest(selected.id):
        return

    # Create or update local config (without contest field - it's in cookies)
    config = LocalConfig.load()
    if config is None:
        config = LocalConfig()
    config.save()

    console.print(f"[green]Switched to contest: {selected.name}[/green]")
    console.print(
        "[yellow]Run 'tsweb_py local parse' to fetch problems and compilers.[/yellow]"
    )


@local.command(name="parse")
def local_parse():
    """Fetch problems and compilers for current contest."""
    config = LocalConfig.load()

    if config is None:
        console.print("[red]No local configuration found.[/red]")
        console.print("Run 'tsweb_py local set-contest' first.")
        return

    client = TestSysClient()

    # Auto-login
    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    # Fetch problems and compilers
    console.print("[cyan]Fetching problems and compilers...[/cyan]")

    config.problems = client.get_problems()
    config.compilers = client.get_compilers()

    if not config.problems:
        console.print(
            "[red]No problems found. Make sure you're in the right contest.[/red]"
        )
        return

    if not config.compilers:
        console.print("[red]No compilers found.[/red]")
        return

    config.save()

    console.print(
        f"[green]Found {len(config.problems)} problems and {len(config.compilers)} compilers.[/green]"
    )
    console.print("[yellow]Run 'tsweb_py local show' to view them.[/yellow]")


@local.command(name="set-compiler")
def local_set_compiler():
    """Choose default compiler/language."""
    config = LocalConfig.load()

    if config is None:
        console.print("[red]No local configuration found.[/red]")
        return

    if not config.compilers:
        console.print(
            "[red]No compilers found. Run 'tsweb_py local parse' first.[/red]"
        )
        return

    # Display compilers
    table = Table(
        title="Available Compilers", show_header=True, header_style="bold cyan"
    )
    table.add_column("#", style="cyan")
    table.add_column("Language", style="yellow")
    table.add_column("Name", style="white")

    for idx, compiler in enumerate(config.compilers):
        marker = "*" if idx == config.default_lang else ""
        table.add_row(f"{idx}{marker}", compiler.compiler_lang, compiler.compiler_name)

    console.print(table)

    # Let user choose
    idx = choose_index("Select default compiler", config.compilers)
    if idx is None:
        return

    config.default_lang = idx
    config.save()

    console.print(
        f"[green]Default compiler set to: {config.compilers[idx].compiler_name}[/green]"
    )


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("-p", "--problem", help="Problem ID (default: extracted from filename)")
@click.option("-l", "--lang", type=int, help="Compiler index (default: from config)")
@click.option(
    "-w",
    "--watch",
    is_flag=True,
    default=True,
    help="Watch submission results (default: true)",
)
def submit(file: Path, problem: Optional[str], lang: Optional[int], watch: bool):
    """Submit a solution file."""
    config = LocalConfig.load()

    if config is None:
        console.print("[red]No local configuration found.[/red]")
        console.print("Run 'tsweb_py local set-contest' first.")
        return

    # Determine problem ID
    if problem is None:
        # Extract from filename (e.g., "12A.cpp" -> "12A")
        problem = file.stem

    # Validate problem exists
    problem_exists = any(p.problem_id == problem for p in config.problems)
    if not problem_exists:
        console.print(
            f"[yellow]Warning: Problem '{problem}' not found in config[/yellow]"
        )

    # Determine compiler
    if lang is None:
        lang = config.default_lang

    if not (0 <= lang < len(config.compilers)):
        console.print(f"[red]Invalid compiler index: {lang}[/red]")
        return

    compiler = config.compilers[lang]

    # Submit
    client = TestSysClient()

    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    if not client.submit(problem, compiler.compiler_id, file):
        return

    # Watch results if requested
    if watch:
        watch_submission(client)


def watch_submission(client: TestSysClient):
    """Poll and display submission results in real-time."""
    console.print("\n[cyan]Watching submission...[/cyan]")

    # Get latest submission ID
    submissions = client.get_all_submissions()
    if not submissions:
        console.print("[red]No submissions found[/red]")
        return

    latest = submissions[0]
    submission_id = latest.id

    # Poll until judging complete
    with console.status("[bold green]Judging...") as status:
        while True:
            # Fetch current submissions
            submissions = client.get_all_submissions()
            current = next((s for s in submissions if s.id == submission_id), None)

            if current is None:
                console.print("[red]Submission not found[/red]")
                return

            # Check if judging is complete
            if current.result.upper() not in ["NO", "JUDGING", "PENDING", ""]:
                break

            time.sleep(0.5)

    # Display final result
    console.print(f"\n[bold]Result:[/bold] {format_result_color(current.result)}")
    console.print(f"[bold]Time:[/bold] {current.time}")

    # Fetch detailed feedback
    tests = client.get_feedback(submission_id)

    if tests:
        console.print("\n[bold cyan]Test Results:[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Test", style="cyan")
        table.add_column("Result", style="white")
        table.add_column("Time", style="yellow")
        table.add_column("Memory", style="yellow")
        table.add_column("Comment", style="white")

        for test in tests:
            table.add_row(
                test.test_id,
                format_result_color(test.result),
                test.time,
                test.memory,
                test.comment,
            )

        console.print(table)


@cli.command()
def info():
    """Show user information and current contest."""
    client = TestSysClient()

    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    user_info = client.get_user_info()

    console.print("\n[bold cyan]User Information:[/bold cyan]")
    if "name" in user_info:
        console.print(f"[bold]Name:[/bold] {user_info['name']}")
    if "contest" in user_info:
        console.print(f"[bold]Current Contest:[/bold] {user_info['contest']}")


@cli.command()
def submissions():
    """Show all submissions."""
    client = TestSysClient()

    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    console.print("[cyan]Fetching submissions...[/cyan]")
    subs = client.get_all_submissions()

    if not subs:
        console.print("[yellow]No submissions found.[/yellow]")
        return

    table = Table(title="Submissions", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Problem", style="yellow")
    table.add_column("Compiler", style="white")
    table.add_column("Result", style="white")
    table.add_column("Time", style="magenta")

    for sub in subs[:20]:  # Show last 20
        table.add_row(
            sub.id,
            sub.problem,
            sub.compiler,
            format_result_color(sub.result),
            sub.time,
        )

    console.print(table)


@cli.command()
def version():
    """Show version information."""
    console.print("[bold cyan]tsweb_py[/bold cyan] version [green]1.0.0[/green]")
    console.print("CLI client for TestSys online judge system")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
