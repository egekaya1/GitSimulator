"""Main Textual TUI application for git-sim."""

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from git_sim.core.models import CommitGraph, SimulationResult
from git_sim.core.repository import Repository
from git_sim.simulation.dispatcher import SimulationDispatcher


class CommitGraphWidget(Static):
    """Widget to display commit graph."""

    def __init__(self, content: str = "", **kwargs: Any) -> None:
        super().__init__(content, **kwargs)

    def update_graph(self, content: str) -> None:
        """Update the graph content."""
        self.update(content)


class ConflictListWidget(ListView):
    """Widget to display list of conflicts."""

    def update_conflicts(self, result: SimulationResult) -> None:
        """Update the conflict list."""
        self.clear()
        if not result.conflicts:
            self.append(ListItem(Label("[green]No conflicts predicted[/green]")))
            return

        for conflict in result.conflicts:
            severity_style = "red" if conflict.is_certain else "yellow"
            item = ListItem(
                Label(
                    f"[{severity_style}]{conflict.path}[/{severity_style}]: {conflict.description[:50]}"
                )
            )
            self.append(item)


class SimulationPanel(Static):
    """Panel showing simulation results."""

    def compose(self) -> ComposeResult:
        yield Static("Run a simulation to see results", id="sim-placeholder")


class GitSimApp(App[None]):  # Provide concrete generic parameter for mypy
    """Main TUI application for git-sim."""

    TITLE = "Git-Sim TUI"
    SUB_TITLE = "Simulate Git operations safely"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 3;
        grid-rows: 3 1fr 3;
    }

    #header-container {
        column-span: 2;
        height: 3;
    }

    #command-input {
        width: 100%;
        margin: 0 1;
    }

    #left-panel {
        height: 100%;
        border: solid green;
        padding: 1;
    }

    #right-panel {
        height: 100%;
        border: solid blue;
        padding: 1;
    }

    #footer-container {
        column-span: 2;
        height: 3;
    }

    .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #graph-before {
        height: 50%;
        border: solid gray;
    }

    #graph-after {
        height: 50%;
        border: solid gray;
    }

    #conflict-list {
        height: 100%;
    }

    #summary-panel {
        height: auto;
        max-height: 10;
        border: solid cyan;
        margin-bottom: 1;
    }

    .button-bar {
        height: 3;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "focus_input", "Run Command"),
        Binding("e", "explain", "Explain"),
        Binding("c", "clear", "Clear"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self, repo_path: str = ".") -> None:
        super().__init__()
        self.repo_path = repo_path
        self._dispatcher: SimulationDispatcher | None = None
        self._current_result: SimulationResult | None = None

    @property
    def dispatcher(self) -> SimulationDispatcher:
        """Get or create the simulation dispatcher."""
        if self._dispatcher is None:
            repo = Repository(self.repo_path)
            self._dispatcher = SimulationDispatcher(repo)
        return self._dispatcher

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="header-container"):
            yield Input(
                placeholder="Enter command (e.g., 'rebase main', 'merge feature', 'reset --hard HEAD~2')",
                id="command-input",
            )

        with Container(id="left-panel"):
            yield Static("Before", classes="panel-title")
            yield CommitGraphWidget(id="graph-before")
            yield Static("After (Simulated)", classes="panel-title")
            yield CommitGraphWidget(id="graph-after")

        with Container(id="right-panel"):
            yield Static("Simulation Results", classes="panel-title")
            yield Static("", id="summary-panel")
            yield Static("Conflicts", classes="panel-title")
            yield ConflictListWidget(id="conflict-list")
            with Horizontal(classes="button-bar"):
                yield Button("Simulate", id="btn-simulate", variant="primary")
                yield Button("Explain", id="btn-explain", variant="default")
                yield Button("Clear", id="btn-clear", variant="warning")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the command input on mount."""
        self.query_one("#command-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input submission."""
        if event.input.id == "command-input":
            self.run_simulation(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-simulate":
            command = self.query_one("#command-input", Input).value
            if command:
                self.run_simulation(command)
        elif event.button.id == "btn-explain":
            self.action_explain()
        elif event.button.id == "btn-clear":
            self.action_clear()

    def run_simulation(self, command: str) -> None:
        """Run a simulation and update the UI."""
        try:
            result = self.dispatcher.run_from_string(command)
            self._current_result = result
            self.update_display(result)
        except ValueError as e:
            self.notify(f"Error: {e}", severity="error")
        except Exception as e:
            self.notify(f"Simulation failed: {e}", severity="error")

    def update_display(self, result: SimulationResult) -> None:
        """Update all display panels with simulation result."""
        # Update summary
        summary_lines: list[str] = [
            f"[bold]Operation:[/bold] {result.operation_type.name}",
            f"[bold]Status:[/bold] {'[green]Clean[/green]' if result.success else '[red]Has conflicts[/red]'}",
        ]
        if result.commits_affected:
            summary_lines.append(f"[bold]Commits affected:[/bold] {len(result.commits_affected)}")
        if result.conflict_count:
            summary_lines.append(f"[bold]Conflicts:[/bold] [red]{result.conflict_count}[/red]")
        if result.safety_info:
            danger = result.safety_info.danger_level.name
            color = "green" if danger == "LOW" else ("yellow" if danger == "MEDIUM" else "red")
            summary_lines.append(f"[bold]Danger Level:[/bold] [{color}]{danger}[/{color}]")

        self.query_one("#summary-panel", Static).update("\n".join(summary_lines))

        # Update graphs
        before_text = (
            self._format_graph(result.before_graph) if result.before_graph.commits else "No commits"
        )
        after_text = (
            self._format_graph(result.after_graph) if result.after_graph.commits else "No commits"
        )

        self.query_one("#graph-before", CommitGraphWidget).update_graph(before_text)
        self.query_one("#graph-after", CommitGraphWidget).update_graph(after_text)

        # Update conflicts
        conflict_list = self.query_one("#conflict-list", ConflictListWidget)
        conflict_list.update_conflicts(result)

        # Notify
        if result.success:
            self.notify("Simulation completed successfully", severity="information")
        else:
            self.notify(f"Simulation found {result.conflict_count} conflict(s)", severity="warning")

    def _format_graph(self, graph: CommitGraph) -> str:
        """Format commit graph for display."""
        lines: list[str] = []
        # Simple topological display
        sorted_commits = sorted(graph.commits.values(), key=lambda c: c.timestamp, reverse=True)[
            :15
        ]

        # Track which commits have children (not detached)
        has_children: set[str] = set()
        for edge in graph.edges:
            has_children.add(edge[1])  # parent has a child

        for commit in sorted_commits:
            branch_labels: list[str] = [
                name for name, sha in graph.branch_tips.items() if sha == commit.sha
            ]

            # Check if commit is detached (no children and not a branch tip)
            is_detached = commit.sha not in has_children and not branch_labels

            label_str = f" ({', '.join(branch_labels)})" if branch_labels else ""
            head_marker = " <- HEAD" if commit.sha == graph.head_sha else ""
            detached_marker = " [dim](detached)[/dim]" if is_detached else ""

            marker = "*" if not is_detached else "○"
            lines.append(
                f"{marker} {commit.short_sha}{label_str}{head_marker}{detached_marker} {commit.first_line[:40]}"
            )

        return "\n".join(lines) if lines else "No commits to display"

    def action_focus_input(self) -> None:
        """Focus the command input."""
        self.query_one("#command-input", Input).focus()

    def action_explain(self) -> None:
        """Show explanation for current operation."""
        if self._current_result:
            op_name = self._current_result.operation_type.name.lower()
            self.notify(
                f"Use 'git-sim explain {op_name}' for detailed explanation", severity="information"
            )
        else:
            self.notify("Run a simulation first", severity="warning")

    def action_clear(self) -> None:
        """Clear the display."""
        self.query_one("#command-input", Input).value = ""
        self.query_one("#summary-panel", Static).update("")
        self.query_one("#graph-before", CommitGraphWidget).update_graph("")
        self.query_one("#graph-after", CommitGraphWidget).update_graph("")
        self.query_one("#conflict-list", ConflictListWidget).clear()
        self._current_result = None

    def action_help(self) -> None:
        """Show help."""
        self.notify(
            "Commands: rebase <branch>, merge <branch>, reset [--hard|--soft] <ref>, cherry-pick <commits>",
            severity="information",
        )

    # Headless helper for tests (avoids full Textual event loop)
    def headless_simulate(self, command: str) -> SimulationResult:
        """Run a simulation without relying on mounted widgets.

        Used in smoke tests to validate dispatcher integration.
        """
        return self.dispatcher.run_from_string(command)


def run_tui(repo_path: str = ".") -> None:
    """Run the TUI application."""
    app = GitSimApp(repo_path=repo_path)
    app.run()
