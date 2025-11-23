"""Rebase command for git-sim CLI."""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from git_sim.cli.formatters.conflict import ConflictRenderer
from git_sim.cli.formatters.graph import CommitGraphRenderer
from git_sim.core.exceptions import GitSimError, RefNotFoundError
from git_sim.core.repository import Repository
from git_sim.simulation.rebase import RebaseSimulator

console = Console()


def rebase_command(
    onto: str = typer.Argument(
        ...,
        help="Branch or commit to rebase onto",
    ),
    source: str = typer.Option(
        "HEAD",
        "--source",
        "-s",
        help="Branch to rebase (default: current branch)",
    ),
    show_graph: bool = typer.Option(
        True,
        "--graph/--no-graph",
        "-g/-G",
        help="Show before/after commit graphs",
    ),
    show_conflicts: bool = typer.Option(
        True,
        "--conflicts/--no-conflicts",
        "-c/-C",
        help="Show detailed conflict analysis",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show verbose output including all conflict details",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        "-x",
        help="Actually execute the rebase after confirmation",
    ),
) -> None:
    """
    Simulate rebasing SOURCE onto ONTO.

    Analyzes the repository to predict what would happen if you ran
    `git rebase <onto>`. Shows potential conflicts, commit changes,
    and before/after commit graphs.

    Examples:

        git-sim rebase main

        git-sim rebase main --source feature-branch

        git-sim rebase HEAD~5 --no-graph
    """
    try:
        # Load repository
        repo = Repository(".")
        console.print(f"[dim]Repository: {repo.path}[/dim]\n")

        # Create simulator
        simulator = RebaseSimulator(repo, source=source, onto=onto)

        # Run simulation
        console.print(f"[bold]Simulating:[/bold] git rebase {onto}")
        if source != "HEAD":
            console.print(f"[bold]Source:[/bold] {source}")
        console.print()

        result = simulator.run()

        # Display warnings from validation
        for warning in simulator.warnings:
            console.print(f"[yellow]⚠️  {warning}[/yellow]")

        # Summary panel
        _render_summary(result, console)

        # Commit graph
        if show_graph:
            graph_renderer = CommitGraphRenderer(console)
            console.print()

            # Highlight commits being rebased
            rebased_shas = {step.original_sha for step in result.steps}
            new_shas = {step.new_sha for step in result.steps if step.new_sha}

            graph_renderer.render(
                result.before_graph,
                highlight_shas=rebased_shas,
                title="[bold]Before Rebase[/bold]",
            )
            console.print()
            graph_renderer.render(
                result.after_graph,
                highlight_shas=new_shas,
                title="[bold]After Rebase (Simulated)[/bold]",
            )

        # Conflict analysis
        if show_conflicts or result.has_conflicts:
            conflict_renderer = ConflictRenderer(console)
            console.print()
            conflict_renderer.render_rebase_conflicts(
                result.steps,
                show_all=verbose,
            )

            if result.has_conflicts:
                conflict_renderer.render_conflict_resolution_hints(
                    [c for step in result.steps for c in step.conflicts]
                )

        # Skipped commits
        if result.skipped_commits:
            console.print()
            console.print("[bold]Commits to be skipped[/bold] (already applied):")
            for commit in result.skipped_commits:
                console.print(
                    f"  [dim]○[/dim] [yellow]{commit.short_sha}[/yellow] "
                    f"[dim]{commit.first_line[:50]}[/dim]"
                )

        # Execute prompt
        if execute:
            _execute_rebase(result, console)

    except RefNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except GitSimError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _render_summary(result, console: Console) -> None:
    """Render a summary of the rebase simulation."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="bold")
    table.add_column("Value")

    table.add_row("Source branch", result.source_branch)
    table.add_row("Target branch", result.target_branch)
    table.add_row("Merge base", result.merge_base_sha[:7])
    table.add_row("Commits to replay", str(len(result.commits_to_replay)))

    if result.skipped_commits:
        table.add_row(
            "Commits to skip",
            f"[dim]{len(result.skipped_commits)} (duplicate patch-ids)[/dim]",
        )

    if result.has_conflicts:
        table.add_row(
            "Predicted conflicts",
            f"[red bold]{result.conflict_count}[/red bold]",
        )
    else:
        table.add_row(
            "Predicted conflicts",
            "[green]0[/green]",
        )

    console.print(Panel(table, title="[bold]Rebase Summary[/bold]", border_style="blue"))


def _execute_rebase(result, console: Console) -> None:
    """Prompt and execute the actual rebase."""
    console.print()

    if result.has_conflicts:
        console.print(
            "[yellow]⚠️  Warning: Conflicts are predicted. "
            "You may need to resolve them during rebase.[/yellow]"
        )

    if not Confirm.ask("\nProceed with actual rebase?"):
        console.print("[dim]Rebase cancelled.[/dim]")
        return

    console.print("\n[bold]Executing rebase...[/bold]")
    console.print("[dim]Running: git rebase {result.target_branch}[/dim]")

    import subprocess

    try:
        proc = subprocess.run(
            ["git", "rebase", result.target_branch],
            capture_output=True,
            text=True,
        )

        if proc.returncode == 0:
            console.print("[green]✓ Rebase completed successfully![/green]")
            console.print(proc.stdout)
        else:
            console.print("[red]Rebase encountered issues:[/red]")
            console.print(proc.stderr)
            console.print(
                "\n[dim]Use 'git rebase --continue' after resolving conflicts, "
                "or 'git rebase --abort' to cancel.[/dim]"
            )

    except FileNotFoundError:
        console.print("[red]Error: git command not found[/red]")
    except Exception as e:
        console.print(f"[red]Error executing rebase: {e}[/red]")
