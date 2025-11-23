"""Main CLI entry point for git-sim."""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from git_sim import __version__
from git_sim.cli.commands.rebase import rebase_command

# Create the main Typer app
app = typer.Typer(
    name="git-sim",
    help="Git simulation and visualization engine - dry run dangerous Git commands with visual feedback",
    no_args_is_help=True,
    add_completion=False,
)

# Create sub-apps for grouped commands
snapshot_app = typer.Typer(help="Manage repository state snapshots")
app.add_typer(snapshot_app, name="snapshot")

plugin_app = typer.Typer(help="Manage git-sim plugins")
app.add_typer(plugin_app, name="plugin")

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"git-sim version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """
    Git-Sim: Simulate Git operations before executing them.

    Run dangerous Git commands in a safe "dry run" mode with visual feedback.
    See predicted conflicts, commit graph changes, and file modifications
    before they happen.
    """
    pass


# Register commands
app.command(name="rebase", help="Simulate rebasing a branch onto another")(rebase_command)


@app.command()
def status() -> None:
    """
    Show the current repository status.

    Displays branch information and a summary of the commit graph.
    """
    from git_sim.cli.formatters.graph import CommitGraphRenderer
    from git_sim.core.exceptions import NotARepositoryError
    from git_sim.core.repository import Repository

    try:
        repo = Repository(".")
    except NotARepositoryError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Repository:[/bold] {repo.path}")
    console.print(f"[bold]Current branch:[/bold] {repo.head_branch or 'detached HEAD'}")
    console.print(f"[bold]HEAD:[/bold] {repo.head_sha[:7]}")

    console.print("\n[bold]Branches:[/bold]")
    for branch in repo.get_branches():
        prefix = "* " if branch.name == repo.head_branch else "  "
        style = "bold green" if branch.name == repo.head_branch else ""
        console.print(f"{prefix}[{style}]{branch.name}[/{style}] ({branch.head_sha[:7]})")

    console.print("\n[bold]Recent commits:[/bold]")
    graph_renderer = CommitGraphRenderer(console)
    graph = repo.build_graph([repo.head_sha], max_commits=10)
    graph_renderer.render(graph)


@app.command()
def log(
    ref: str = typer.Argument(
        "HEAD",
        help="Branch or commit to start from",
    ),
    max_count: int = typer.Option(
        20,
        "--max-count",
        "-n",
        help="Maximum number of commits to show",
    ),
) -> None:
    """
    Show commit log with graph visualization.

    Similar to `git log --graph` but with enhanced visualization.
    """
    from git_sim.cli.formatters.graph import CommitGraphRenderer
    from git_sim.core.exceptions import NotARepositoryError, RefNotFoundError
    from git_sim.core.repository import Repository

    try:
        repo = Repository(".")
        graph = repo.build_graph([ref], max_commits=max_count)
    except NotARepositoryError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except RefNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    graph_renderer = CommitGraphRenderer(console)
    graph_renderer.render(graph, max_commits=max_count)


@app.command()
def diff(
    commit: str = typer.Argument(
        "HEAD",
        help="Commit to show diff for",
    ),
) -> None:
    """
    Show the diff for a commit.

    Displays the changes introduced by the specified commit.
    """
    from git_sim.cli.formatters.diff import DiffRenderer
    from git_sim.core.exceptions import NotARepositoryError, RefNotFoundError
    from git_sim.core.repository import Repository

    try:
        repo = Repository(".")
        commit_info = repo.get_commit(commit)
        changes = repo.get_commit_changes(commit_info.sha)
    except NotARepositoryError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except RefNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(
        f"[bold]Commit:[/bold] [yellow]{commit_info.short_sha}[/yellow] "
        f"{commit_info.first_line}"
    )
    console.print(f"[bold]Author:[/bold] {commit_info.author}")
    console.print()

    diff_renderer = DiffRenderer(console)

    if changes:
        diff_renderer.render_file_changes_summary(changes)
        console.print()
        diff_renderer.render_diff_preview(changes)
    else:
        console.print("[dim]No changes in this commit[/dim]")


# ============== MERGE COMMAND ==============


@app.command()
def merge(
    branch: str = typer.Argument(..., help="Branch to merge"),
    no_ff: bool = typer.Option(
        False,
        "--no-ff",
        help="Create merge commit even if fast-forward is possible",
    ),
    show_graph: bool = typer.Option(
        True,
        "--graph/--no-graph",
        "-g/-G",
        help="Show before/after commit graphs",
    ),
) -> None:
    """
    Simulate merging a branch into the current branch.

    Analyzes what would happen if you ran `git merge <branch>`.
    """
    from git_sim.cli.formatters.conflict import ConflictRenderer
    from git_sim.cli.formatters.graph import CommitGraphRenderer
    from git_sim.core.exceptions import GitSimError
    from git_sim.core.repository import Repository
    from git_sim.simulation.merge import MergeSimulator

    try:
        repo = Repository(".")
        simulator = MergeSimulator(repo, source=branch, no_ff=no_ff)
        result = simulator.run()

        # Display warnings
        for warning in simulator.warnings:
            console.print(f"[yellow]⚠️  {warning}[/yellow]")

        # Summary
        table = Table(show_header=False, box=None)
        table.add_column("Label", style="bold")
        table.add_column("Value")

        table.add_row("Source branch", result.source_branch)
        table.add_row("Target branch", result.target_branch)
        table.add_row("Merge base", result.merge_base_sha[:7])
        table.add_row(
            "Merge type",
            "[green]Fast-forward[/green]" if result.is_fast_forward else "Merge commit",
        )
        table.add_row(
            "Files to merge",
            f"[green]{len(result.files_merged_cleanly)}[/green]",
        )
        table.add_row(
            "Conflicts",
            f"[red]{len(result.conflicts)}[/red]" if result.conflicts else "[green]0[/green]",
        )

        console.print(Panel(table, title="[bold]Merge Summary[/bold]", border_style="blue"))

        # Graph
        if show_graph:
            graph_renderer = CommitGraphRenderer(console)
            console.print()
            graph_renderer.render(result.before_graph, title="[bold]Before Merge[/bold]")
            console.print()
            graph_renderer.render(result.after_graph, title="[bold]After Merge (Simulated)[/bold]")

        # Conflicts
        if result.has_conflicts:
            conflict_renderer = ConflictRenderer(console)
            console.print()
            conflict_renderer.render_conflicts_summary(result.conflicts)

    except GitSimError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# ============== RESET COMMAND ==============


@app.command()
def reset(
    target: str = typer.Argument(..., help="Target commit/ref"),
    hard: bool = typer.Option(False, "--hard", help="Hard reset (discard all changes)"),
    soft: bool = typer.Option(False, "--soft", help="Soft reset (keep changes staged)"),
    show_graph: bool = typer.Option(True, "--graph/--no-graph", "-g/-G"),
) -> None:
    """
    Simulate git reset operation.

    Shows which commits will become unreachable and what files will be affected.
    """
    from git_sim.cli.formatters.graph import CommitGraphRenderer
    from git_sim.core.exceptions import GitSimError
    from git_sim.core.models import ResetMode
    from git_sim.core.repository import Repository
    from git_sim.simulation.explain import ExplainRenderer
    from git_sim.simulation.reset import ResetSimulator

    # Determine mode
    if hard:
        mode = ResetMode.HARD
    elif soft:
        mode = ResetMode.SOFT
    else:
        mode = ResetMode.MIXED

    try:
        repo = Repository(".")
        simulator = ResetSimulator(repo, target=target, mode=mode)
        result = simulator.run()

        # Display warnings
        for warning in simulator.warnings:
            console.print(f"[yellow]⚠️  {warning}[/yellow]")

        # Summary
        table = Table(show_header=False, box=None)
        table.add_column("Label", style="bold")
        table.add_column("Value")

        table.add_row("Current HEAD", result.current_sha[:7])
        table.add_row("Target", result.target_sha[:7])
        table.add_row("Mode", f"[bold]{mode.name}[/bold]")
        table.add_row(
            "Commits to detach",
            f"[red]{len(result.commits_detached)}[/red]" if result.commits_detached else "0",
        )

        if result.files_unstaged:
            table.add_row("Files to unstage", str(len(result.files_unstaged)))
        if result.files_discarded:
            table.add_row(
                "Files with changes discarded",
                f"[red]{len(result.files_discarded)}[/red]",
            )

        console.print(Panel(table, title="[bold]Reset Summary[/bold]", border_style="blue"))

        # Show detached commits
        if result.commits_detached:
            console.print("\n[bold red]Commits that will become unreachable:[/bold red]")
            for commit in result.commits_detached[:10]:
                console.print(f"  [dim]○[/dim] [yellow]{commit.short_sha}[/yellow] {commit.first_line[:50]}")
            if len(result.commits_detached) > 10:
                console.print(f"  [dim]... and {len(result.commits_detached) - 10} more[/dim]")

        # Safety info
        sim_result = result.to_simulation_result()
        if sim_result.safety_info:
            console.print()
            ExplainRenderer(console).render_safety_report(sim_result.safety_info)

        # Graph
        if show_graph:
            graph_renderer = CommitGraphRenderer(console)
            console.print()
            graph_renderer.render(result.before_graph, title="[bold]Before Reset[/bold]")
            console.print()
            graph_renderer.render(
                result.after_graph,
                highlight_shas={c.sha for c in result.commits_detached},
                title="[bold]After Reset (Simulated)[/bold]",
            )

    except GitSimError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# ============== CHERRY-PICK COMMAND ==============


@app.command(name="cherry-pick")
def cherry_pick(
    commits: list[str] = typer.Argument(..., help="Commits to cherry-pick"),
    show_graph: bool = typer.Option(True, "--graph/--no-graph", "-g/-G"),
) -> None:
    """
    Simulate cherry-picking commits onto the current branch.

    Shows which commits will be applied and predicts conflicts.
    """
    from git_sim.cli.formatters.conflict import ConflictRenderer
    from git_sim.cli.formatters.graph import CommitGraphRenderer
    from git_sim.core.exceptions import GitSimError
    from git_sim.core.repository import Repository
    from git_sim.simulation.cherry_pick import CherryPickSimulator

    try:
        repo = Repository(".")
        simulator = CherryPickSimulator(repo, commits=commits)
        result = simulator.run()

        # Display warnings
        for warning in simulator.warnings:
            console.print(f"[yellow]⚠️  {warning}[/yellow]")

        # Summary
        table = Table(show_header=False, box=None)
        table.add_column("Label", style="bold")
        table.add_column("Value")

        table.add_row("Commits to pick", str(len(result.commits_to_pick)))
        table.add_row("Target branch", result.target_branch)
        table.add_row(
            "Predicted conflicts",
            f"[red]{len(result.conflicts)}[/red]" if result.conflicts else "[green]0[/green]",
        )

        console.print(Panel(table, title="[bold]Cherry-Pick Summary[/bold]", border_style="blue"))

        # Show steps
        console.print("\n[bold]Commits to be picked:[/bold]")
        for step in result.steps:
            if step.commit_info:
                conflict_marker = " [red]⚠️ conflicts[/red]" if step.has_conflicts else ""
                console.print(
                    f"  {step.step_number}. [yellow]{step.commit_info.short_sha}[/yellow] "
                    f"{step.commit_info.first_line[:50]}{conflict_marker}"
                )

        # Conflicts
        if result.has_conflicts:
            conflict_renderer = ConflictRenderer(console)
            console.print()
            conflict_renderer.render_conflicts_summary(result.conflicts)

        # Graph
        if show_graph:
            graph_renderer = CommitGraphRenderer(console)
            console.print()
            graph_renderer.render(
                result.before_graph,
                highlight_shas={c.sha for c in result.commits_to_pick},
                title="[bold]Before Cherry-Pick[/bold]",
            )
            console.print()
            graph_renderer.render(
                result.after_graph,
                highlight_shas={s.new_sha for s in result.steps if s.new_sha},
                title="[bold]After Cherry-Pick (Simulated)[/bold]",
            )

    except GitSimError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# ============== EXPLAIN COMMAND ==============


@app.command()
def explain(
    command: str = typer.Argument(..., help="Command to explain (rebase, merge, reset, cherry-pick)"),
) -> None:
    """
    Get a detailed explanation of how a Git command works.

    Learn about the internals, risks, and best practices for Git operations.
    """
    from git_sim.simulation.explain import explain_command

    explain_command(command, console)


# ============== SNAPSHOT COMMANDS ==============


@snapshot_app.command("create")
def snapshot_create(
    name: str = typer.Argument(..., help="Name for the snapshot"),
    description: str = typer.Option("", "--desc", "-d", help="Description"),
) -> None:
    """Create a snapshot of the current repository state."""
    from git_sim.snapshot import SnapshotManager

    try:
        manager = SnapshotManager(".")
        snapshot = manager.create(name=name, description=description)

        console.print(f"[green]✓[/green] Created snapshot: [bold]{snapshot.name}[/bold]")
        console.print(f"  ID: {snapshot.id}")
        console.print(f"  HEAD: {snapshot.head_sha[:7]}")
        if snapshot.head_branch:
            console.print(f"  Branch: {snapshot.head_branch}")

    except Exception as e:
        console.print(f"[red]Error creating snapshot: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command("list")
def snapshot_list() -> None:
    """List all snapshots."""
    from git_sim.snapshot import SnapshotManager

    try:
        manager = SnapshotManager(".")
        snapshots = manager.list()

        if not snapshots:
            console.print("[dim]No snapshots found[/dim]")
            return

        table = Table(title="Snapshots")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Created", style="dim")
        table.add_column("HEAD", style="yellow")
        table.add_column("Branch")

        for s in snapshots:
            created = s.created_at[:19].replace("T", " ")
            table.add_row(
                s.id[:8],
                s.name,
                created,
                s.head_sha[:7],
                s.head_branch or "[dim]detached[/dim]",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing snapshots: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command("restore")
def snapshot_restore(
    snapshot_id: str = typer.Argument(..., help="Snapshot ID or name"),
    hard: bool = typer.Option(False, "--hard", help="Hard restore (discard changes)"),
) -> None:
    """Restore repository to a snapshot state."""
    from git_sim.snapshot import SnapshotManager

    try:
        manager = SnapshotManager(".")
        mode = "hard" if hard else "soft"
        success, message = manager.restore(snapshot_id, mode=mode)

        if success:
            console.print(f"[green]✓[/green] {message}")
        else:
            console.print(f"[red]✗[/red] {message}")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error restoring snapshot: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command("delete")
def snapshot_delete(
    snapshot_id: str = typer.Argument(..., help="Snapshot ID or name"),
) -> None:
    """Delete a snapshot."""
    from git_sim.snapshot import SnapshotManager

    try:
        manager = SnapshotManager(".")
        if manager.delete(snapshot_id):
            console.print(f"[green]✓[/green] Deleted snapshot: {snapshot_id}")
        else:
            console.print(f"[red]Snapshot not found: {snapshot_id}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error deleting snapshot: {e}[/red]")
        raise typer.Exit(1)


# ============== SIMULATE COMMAND (UNIFIED) ==============


@app.command()
def sim(
    command_string: str = typer.Argument(..., help="Git command to simulate (e.g., 'rebase main')"),
) -> None:
    """
    Simulate any Git command using unified syntax.

    Examples:
        git-sim sim "rebase main"
        git-sim sim "merge feature"
        git-sim sim "reset --hard HEAD~2"
        git-sim sim "cherry-pick abc123"
    """
    from git_sim.cli.formatters.graph import CommitGraphRenderer
    from git_sim.simulation.dispatcher import SimulationDispatcher
    from git_sim.simulation.explain import ExplainRenderer

    try:
        dispatcher = SimulationDispatcher()
        result = dispatcher.run_from_string(command_string)

        # Summary
        console.print(f"\n[bold]Simulating:[/bold] git {command_string}\n")

        table = Table(show_header=False, box=None)
        table.add_column("Label", style="bold")
        table.add_column("Value")

        table.add_row("Operation", result.operation_type.name)
        table.add_row(
            "Status",
            "[green]Clean[/green]" if result.success else "[red]Has conflicts[/red]",
        )
        if result.commits_affected:
            table.add_row("Commits affected", str(len(result.commits_affected)))
        if result.conflict_count:
            table.add_row("Conflicts", f"[red]{result.conflict_count}[/red]")

        console.print(Panel(table, title="[bold]Simulation Result[/bold]"))

        # Warnings
        for warning in result.warnings:
            console.print(f"[yellow]⚠️  {warning}[/yellow]")

        # Safety info
        if result.safety_info:
            console.print()
            ExplainRenderer(console).render_safety_report(result.safety_info)

        # Graph
        if result.before_graph.commits:
            graph_renderer = CommitGraphRenderer(console)
            console.print()
            graph_renderer.render_comparison(
                result.before_graph,
                result.after_graph,
                highlight_after={c.sha for c in result.commits_created} if result.commits_created else None,
            )

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# ============== PLUGIN COMMANDS ==============


@plugin_app.command("list")
def plugin_list() -> None:
    """List all available and loaded plugins."""
    from git_sim.plugins import PluginType, discover_plugins
    from git_sim.plugins.base import get_plugin_manager

    # Show discovered plugins
    discovered = discover_plugins()
    manager = get_plugin_manager()
    loaded = manager.list_plugins()

    if not discovered and not loaded:
        console.print("[dim]No plugins found.[/dim]")
        console.print("\nTo create a plugin, use: [bold]git-sim plugin new <name>[/bold]")
        return

    if discovered:
        console.print("[bold]Available plugins:[/bold]")
        table = Table()
        table.add_column("Name", style="cyan")
        table.add_column("Module")
        table.add_column("Status")

        loaded_names = {p.name for p in loaded}
        for name, module in discovered:
            status = "[green]loaded[/green]" if name in loaded_names else "[dim]available[/dim]"
            table.add_row(name, module, status)

        console.print(table)

    if loaded:
        console.print("\n[bold]Loaded plugins:[/bold]")
        for meta in loaded:
            console.print(
                f"  [cyan]{meta.name}[/cyan] v{meta.version} "
                f"[dim]({meta.plugin_type.name.lower()})[/dim]"
            )
            if meta.description:
                console.print(f"    {meta.description}")


@plugin_app.command("new")
def plugin_new(
    name: str = typer.Argument(..., help="Name for the new plugin"),
    plugin_type: str = typer.Option(
        "simulator",
        "--type",
        "-t",
        help="Plugin type: simulator, formatter, or hook",
    ),
    output: str = typer.Option(".", "--output", "-o", help="Output directory"),
) -> None:
    """Generate a new plugin template."""
    from git_sim.plugins.loader import create_plugin_template

    try:
        path = create_plugin_template(name, plugin_type, output)
        console.print(f"[green]✓[/green] Created plugin template: [bold]{path}[/bold]")
        console.print("\nNext steps:")
        console.print("  1. Implement your plugin logic")
        console.print("  2. Add entry point to pyproject.toml:")
        console.print(f'     [project.entry-points."git_sim.plugins"]')
        console.print(f'     {name} = "your_package:{name.title().replace("-", "")}Plugin"')
        console.print("  3. Install your package: pip install -e .")
    except Exception as e:
        console.print(f"[red]Error creating plugin: {e}[/red]")
        raise typer.Exit(1)


@plugin_app.command("load")
def plugin_load(
    name: str = typer.Argument(..., help="Plugin name to load"),
) -> None:
    """Load a plugin by name."""
    from git_sim.plugins import load_plugin

    plugin = load_plugin(name)
    if plugin:
        console.print(
            f"[green]✓[/green] Loaded: [bold]{plugin.metadata.name}[/bold] "
            f"v{plugin.metadata.version}"
        )
    else:
        console.print(f"[red]Failed to load plugin: {name}[/red]")
        raise typer.Exit(1)


# ============== TUI COMMAND ==============


@app.command()
def tui() -> None:
    """
    Launch the interactive TUI (Terminal User Interface).

    A full-screen interactive interface for exploring git simulations.
    Requires: pip install git-sim[tui]
    """
    try:
        from git_sim.tui import run_tui

        run_tui()
    except ImportError:
        console.print(
            "[red]TUI dependencies not installed.[/red]\n"
            "Install with: [bold]pip install git-sim[tui][/bold]"
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
