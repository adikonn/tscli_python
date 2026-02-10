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
def contest():
    """Manage contest information."""
    pass


@contest.command(name="show")
def contest_show():
    """Display current contest information, problems and compilers."""
    client = TestSysClient()
    
    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    # Show current contest and user info
    user_info = client.get_user_info()
    if "contest" in user_info:
        console.print(
            f"\n[bold cyan]Current Contest:[/bold cyan] {user_info['contest']}"
        )
    if "name" in user_info:
        console.print(f"[bold cyan]User:[/bold cyan] {user_info['name']}")

    # Fetch problems and compilers from site
    console.print("\n[cyan]Fetching problems and compilers...[/cyan]")
    problems = client.get_problems()
    compilers = client.get_compilers()

    # Load default compiler index from local config
    config = LocalConfig.load()
    default_lang = config.default_lang if config else 0

    # Show default compiler
    if compilers and 0 <= default_lang < len(compilers):
        console.print(
            f"[bold cyan]Default Compiler:[/bold cyan] {compilers[default_lang].compiler_name}"
        )

    # Show problems
    if problems:
        console.print(f"\n[bold cyan]Available Problems:[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")

        for problem in problems:
            table.add_row(problem.problem_id, problem.problem_name)

        console.print(table)
    else:
        console.print("[yellow]No problems found in this contest.[/yellow]")

    # Show compilers
    if compilers:
        console.print(f"\n[bold cyan]Available Compilers:[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan")
        table.add_column("Language", style="yellow")
        table.add_column("Name", style="white")

        for idx, compiler in enumerate(compilers):
            marker = "*" if idx == default_lang else ""
            table.add_row(
                f"{idx}{marker}", compiler.compiler_lang, compiler.compiler_name
            )

        console.print(table)
    else:
        console.print("[yellow]No compilers found in this contest.[/yellow]")


@cli.command(name="set-contest")
def set_contest():
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


@cli.command(name="set-compiler")
def set_compiler():
    """Choose default compiler/language."""
    client = TestSysClient()

    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    # Fetch compilers from site
    console.print("[cyan]Fetching compilers...[/cyan]")
    compilers = client.get_compilers()

    if not compilers:
        console.print("[red]No compilers found in this contest.[/red]")
        return

    # Load current default
    config = LocalConfig.load()
    if config is None:
        config = LocalConfig()

    # Display compilers
    table = Table(
        title="Available Compilers", show_header=True, header_style="bold cyan"
    )
    table.add_column("#", style="cyan")
    table.add_column("Language", style="yellow")
    table.add_column("Name", style="white")

    for idx, compiler in enumerate(compilers):
        marker = "*" if idx == config.default_lang else ""
        table.add_row(f"{idx}{marker}", compiler.compiler_lang, compiler.compiler_name)

    console.print(table)

    # Let user choose
    idx = choose_index("Select default compiler", compilers)
    if idx is None:
        return

    config.default_lang = idx
    config.save()

    console.print(
        f"[green]Default compiler set to: {compilers[idx].compiler_name}[/green]"
    )


@contest.command(name="statements")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file path")
def contest_statements(output: Optional[Path]):
    """Download contest statements PDF."""
    client = TestSysClient()

    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    console.print("[cyan]Fetching statements...[/cyan]")
    client.download_statements(output)


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
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug output",
)
def submit(file: Path, problem: Optional[str], lang: Optional[int], watch: bool, debug: bool):
    """Submit a solution file."""
    client = TestSysClient()

    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    # Determine problem ID
    if problem is None:
        # Extract from filename (e.g., "12A.cpp" -> "12A")
        problem = file.stem

    if debug:
        console.print(f"[cyan]DEBUG: Problem ID = {problem}[/cyan]")
        console.print(f"[cyan]DEBUG: File path = {file}[/cyan]")

    # Fetch compilers from site
    if debug:
        console.print("[cyan]DEBUG: Fetching compilers from site...[/cyan]")
    
    compilers = client.get_compilers()
    if not compilers:
        console.print("[red]No compilers found in this contest.[/red]")
        return

    if debug:
        console.print(f"[cyan]DEBUG: Found {len(compilers)} compilers[/cyan]")

    # Determine compiler
    if lang is None:
        # Load default from local config
        config = LocalConfig.load()
        lang = config.default_lang if config else 0
        if debug:
            console.print(f"[cyan]DEBUG: Using default compiler index: {lang}[/cyan]")

    if not (0 <= lang < len(compilers)):
        console.print(f"[red]Invalid compiler index: {lang}[/red]")
        console.print(f"[yellow]Available compilers: 0-{len(compilers)-1}[/yellow]")
        return

    compiler = compilers[lang]
    
    if debug:
        console.print(f"[cyan]DEBUG: Selected compiler: {compiler.compiler_lang}: {compiler.compiler_name} (ID: {compiler.compiler_id})[/cyan]")

    # Submit
    if not client.submit(problem, compiler.compiler_id, file):
        return

    # Watch results if requested
    if watch:
        watch_submission(client, debug)


def watch_submission(client: TestSysClient, debug: bool = False):
    """Poll and display submission results in real-time."""
    console.print("\n[cyan]Watching submission...[/cyan]")

    # Get latest submission ID
    if debug:
        console.print("[cyan]DEBUG: Fetching all submissions to get latest ID...[/cyan]")
    
    submissions = client.get_all_submissions(debug=debug)
    
    if debug:
        console.print(f"[cyan]DEBUG: Received {len(submissions) if submissions else 0} submissions[/cyan]")
        if submissions:
            console.print(f"[cyan]DEBUG: Latest submission ID: {submissions[0].id}[/cyan]")
            console.print(f"[cyan]DEBUG: Latest submission problem: {submissions[0].problem}[/cyan]")
            console.print(f"[cyan]DEBUG: Latest submission compiler: {submissions[0].compiler}[/cyan]")
            console.print(f"[cyan]DEBUG: Latest submission result: {submissions[0].result}[/cyan]")
    
    if not submissions:
        console.print("[red]No submissions found[/red]")
        if debug:
            console.print("[cyan]DEBUG: get_all_submissions() returned empty list[/cyan]")
        return

    latest = submissions[0]
    submission_id = latest.id
    
    if debug:
        console.print(f"[cyan]DEBUG: Tracking submission ID: {submission_id}[/cyan]")

    # Poll until judging complete
    poll_count = 0
    last_result = None
    no_change_count = 0
    MAX_NO_CHANGE = 20  # If result doesn't change for 10 seconds (20 * 0.5s), assume it's final
    
    # Don't use status spinner in debug mode - it can interfere with debug output and cause hangs
    if debug:
        console.print("[cyan]Starting polling loop (debug mode - no spinner)...[/cyan]")
        while True:
            poll_count += 1
            
            if poll_count % 10 == 0:
                console.print(f"[cyan]DEBUG: Poll #{poll_count}, still waiting...[/cyan]")
            
            # Fetch current submissions
            submissions = client.get_all_submissions(debug=debug)
            current = next((s for s in submissions if s.id == submission_id), None)

            if current is None:
                console.print("[red]Submission not found[/red]")
                console.print(f"[cyan]DEBUG: Submission {submission_id} not found in latest submissions[/cyan]")
                if submissions:
                    console.print(f"[cyan]DEBUG: Available submission IDs: {[s.id for s in submissions[:5]]}[/cyan]")
                return
            
            # Show debug info when result changes or first 3 polls
            if poll_count <= 3 or current.result != last_result:
                console.print(f"[cyan]DEBUG: Poll #{poll_count} - Result: '{current.result}' (upper: '{current.result.upper()}')[/cyan]")
                if current.result != last_result and last_result is not None:
                    console.print(f"[yellow]DEBUG: Result changed from '{last_result}' to '{current.result}'[/yellow]")
                    no_change_count = 0
                last_result = current.result
            
            # Track if result is stuck
            if current.result == last_result:
                no_change_count += 1
                if no_change_count == MAX_NO_CHANGE:
                    console.print(f"[yellow]DEBUG: Result hasn't changed for {MAX_NO_CHANGE} polls (~10 seconds)[/yellow]")
                    console.print(f"[yellow]DEBUG: Assuming '{current.result}' is the final result[/yellow]")

            # Check if judging is complete
            if current.result.upper() not in ["NO", "JUDGING", "PENDING", ""]:
                console.print(f"[cyan]DEBUG: Judging complete! Final result: {current.result}[/cyan]")
                break
            
            # If result is stuck on "NO" for too long, assume it's final
            # Some contests might not update the result field properly
            if current.result.upper() == "NO" and no_change_count >= MAX_NO_CHANGE:
                console.print(f"[yellow]DEBUG: Breaking out - result stuck on 'NO' for too long[/yellow]")
                console.print(f"[yellow]DEBUG: This might be a contest-specific behavior[/yellow]")
                break

            time.sleep(0.5)
    else:
        # Normal mode with status spinner
        with console.status("[bold green]Judging...") as status:
            while True:
                poll_count += 1
                
                # Fetch current submissions
                submissions = client.get_all_submissions(debug=False)
                current = next((s for s in submissions if s.id == submission_id), None)

                if current is None:
                    console.print("[red]Submission not found[/red]")
                    return
                
                # Track if result is stuck
                if current.result == last_result:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_result = current.result

                # Check if judging is complete
                if current.result.upper() not in ["NO", "JUDGING", "PENDING", ""]:
                    break
                
                # If result is stuck on "NO" for too long, assume it's final
                # Some contests might not update the result field properly
                if current.result.upper() == "NO" and no_change_count >= MAX_NO_CHANGE:
                    break

                time.sleep(0.5)

    # Display final result
    console.print(f"\n[bold]Result:[/bold] {format_result_color(current.result)}")
    console.print(f"[bold]Time:[/bold] {current.time}")

    # Fetch detailed feedback
    if debug:
        console.print(f"[cyan]DEBUG: Fetching feedback for submission {submission_id}...[/cyan]")
    
    tests = client.get_feedback(submission_id)
    
    if debug:
        console.print(f"[cyan]DEBUG: Received {len(tests) if tests else 0} test results[/cyan]")

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
    else:
        console.print("[yellow]No detailed test results available.[/yellow]")


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
@click.argument("submission_id", type=str)
def feedback(submission_id: str):
    """Show detailed test results for a specific submission."""
    client = TestSysClient()

    if not client.auto_login():
        console.print("[yellow]Not logged in. Please login first.[/yellow]")
        if not client.login():
            return

    console.print(f"[cyan]Fetching feedback for submission {submission_id}...[/cyan]")
    tests = client.get_feedback(submission_id)

    if tests:
        console.print(f"\n[bold cyan]Test Results for Submission {submission_id}:[/bold cyan]")
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
    else:
        console.print("[yellow]No test results found for this submission.[/yellow]")


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
