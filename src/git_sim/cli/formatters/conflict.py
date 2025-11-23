"""Conflict rendering for git-sim CLI."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from git_sim.core.models import ConflictSeverity, PotentialConflict, RebaseStep
from git_sim.simulation.conflict_detector import ConflictDetector


class ConflictRenderer:
    """Renders potential conflicts with detailed information."""

    SEVERITY_STYLES = {
        ConflictSeverity.LIKELY: ("yellow", "⚠️ ", "LIKELY"),
        ConflictSeverity.CERTAIN: ("red bold", "❌ ", "CERTAIN"),
        ConflictSeverity.NONE: ("green", "✓ ", "NONE"),
    }

    def __init__(self, console: Console | None = None):
        """
        Initialize the conflict renderer.

        Args:
            console: Rich Console instance. If None, creates a new one.
        """
        self.console = console or Console()
        self._conflict_detector = ConflictDetector()

    def render_conflict(self, conflict: PotentialConflict) -> None:
        """
        Render a single potential conflict.

        Args:
            conflict: PotentialConflict to render.
        """
        style, icon, label = self.SEVERITY_STYLES.get(conflict.severity, ("white", "? ", "UNKNOWN"))

        # Build content
        content = Text()
        content.append(f"{icon}{label}: ", style=style)
        content.append(conflict.description)

        # Add line range info if available
        if conflict.overlapping_ranges:
            content.append("\n\nAffected line ranges:\n", style="dim")
            for our_range, their_range in conflict.overlapping_ranges:
                content.append(
                    f"  • Ours: {our_range[0]}-{our_range[1]}, "
                    f"Theirs: {their_range[0]}-{their_range[1]}\n",
                    style="dim",
                )

        # Add difficulty estimate
        difficulty = self._conflict_detector.estimate_conflict_difficulty(conflict)
        content.append("\nResolution difficulty: ", style="dim")
        content.append(difficulty, style="italic")

        panel = Panel(
            content,
            title=f"[{style}]Conflict: {conflict.path}[/{style}]",
            border_style=style.split()[0],  # Use just the color, not "bold"
        )
        self.console.print(panel)

    def render_conflicts_summary(
        self,
        conflicts: list[PotentialConflict],
        title: str = "Potential Conflicts",
    ) -> None:
        """
        Render a summary table of all potential conflicts.

        Args:
            conflicts: List of PotentialConflict objects.
            title: Title for the summary.
        """
        if not conflicts:
            self.console.print(
                Panel(
                    "[green]No conflicts predicted![/green]",
                    title="Conflict Analysis",
                    border_style="green",
                )
            )
            return

        table = Table(title=title, show_header=True, header_style="bold")
        table.add_column("Severity", style="bold", width=10)
        table.add_column("File", style="white")
        table.add_column("Description")

        certain_count = 0
        likely_count = 0

        for conflict in conflicts:
            style, icon, label = self.SEVERITY_STYLES.get(
                conflict.severity, ("white", "?", "UNKNOWN")
            )

            # Truncate description if too long
            desc = conflict.description
            if len(desc) > 60:
                desc = desc[:57] + "..."

            table.add_row(
                f"[{style}]{label}[/{style}]",
                conflict.path,
                desc,
            )

            if conflict.severity == ConflictSeverity.CERTAIN:
                certain_count += 1
            elif conflict.severity == ConflictSeverity.LIKELY:
                likely_count += 1

        self.console.print(table)

        # Summary line
        summary_parts = []
        if certain_count:
            summary_parts.append(f"[red bold]{certain_count} certain[/red bold]")
        if likely_count:
            summary_parts.append(f"[yellow]{likely_count} likely[/yellow]")

        if summary_parts:
            self.console.print(f"\nTotal: {', '.join(summary_parts)} conflict(s) predicted")

    def render_step_conflicts(
        self,
        step: RebaseStep,
        step_number: int,
    ) -> None:
        """
        Render conflicts for a single rebase step.

        Args:
            step: RebaseStep containing conflicts.
            step_number: 1-indexed step number for display.
        """
        if not step.conflicts:
            return

        self.console.print(
            f"\n[bold]Step {step_number}: {step.commit_info.short_sha}[/bold] "
            f"[dim]{step.commit_info.first_line[:40]}[/dim]"
        )

        for conflict in step.conflicts:
            self.render_conflict(conflict)

    def render_rebase_conflicts(
        self,
        steps: list[RebaseStep],
        show_all: bool = False,
    ) -> None:
        """
        Render all conflicts from a rebase simulation.

        Args:
            steps: List of RebaseStep objects.
            show_all: If True, show details for all conflicts.
                     If False, show summary only.
        """
        # Collect all conflicts
        all_conflicts: list[tuple[int, RebaseStep, PotentialConflict]] = []
        for i, step in enumerate(steps):
            for conflict in step.conflicts:
                all_conflicts.append((i + 1, step, conflict))

        if not all_conflicts:
            self.console.print(
                Panel(
                    "[bold green]✓ No conflicts predicted![/bold green]\n\n"
                    "The rebase should complete cleanly.",
                    title="Conflict Analysis",
                    border_style="green",
                )
            )
            return

        # Count by severity
        certain = sum(1 for _, _, c in all_conflicts if c.severity == ConflictSeverity.CERTAIN)
        likely = sum(1 for _, _, c in all_conflicts if c.severity == ConflictSeverity.LIKELY)

        # Header
        header = Text()
        header.append("⚠️ ", style="yellow")
        header.append(f"Found {len(all_conflicts)} potential conflict(s)\n\n")

        if certain:
            header.append(f"  • {certain} ", style="red bold")
            header.append("CERTAIN", style="red bold")
            header.append(" - will require manual resolution\n")
        if likely:
            header.append(f"  • {likely} ", style="yellow")
            header.append("LIKELY", style="yellow")
            header.append(" - may auto-resolve or need minor fixes\n")

        self.console.print(
            Panel(header, title="[bold red]Conflict Analysis[/bold red]", border_style="red")
        )

        if show_all:
            # Show detailed view
            current_step = -1
            for step_num, step, conflict in all_conflicts:
                if step_num != current_step:
                    current_step = step_num
                    self.console.print(
                        f"\n[bold]Step {step_num}:[/bold] "
                        f"[yellow]{step.commit_info.short_sha}[/yellow] "
                        f"{step.commit_info.first_line[:50]}"
                    )
                self.render_conflict(conflict)
        else:
            # Show summary table
            self.console.print()
            conflicts_only = [c for _, _, c in all_conflicts]
            self.render_conflicts_summary(conflicts_only, title="Conflicts by File")

    def render_conflict_resolution_hints(
        self,
        conflicts: list[PotentialConflict],
    ) -> None:
        """
        Render hints for resolving conflicts.

        Args:
            conflicts: List of conflicts to provide hints for.
        """
        if not conflicts:
            return

        self.console.print("\n[bold]Resolution Hints:[/bold]")

        tips = []

        # Categorize conflicts
        delete_modify = [c for c in conflicts if "deleted" in c.description.lower()]
        rename_conflicts = [c for c in conflicts if "renamed" in c.description.lower()]
        content_conflicts = [
            c for c in conflicts if c not in delete_modify and c not in rename_conflicts
        ]

        if delete_modify:
            tips.append(
                "• [yellow]Delete/Modify conflicts:[/yellow] "
                "Decide whether to keep the file with modifications or accept deletion"
            )

        if rename_conflicts:
            tips.append(
                "• [blue]Rename conflicts:[/blue] "
                "Check if renames should be merged or if one rename should take precedence"
            )

        if content_conflicts:
            tips.append(
                "• [red]Content conflicts:[/red] "
                "Review both versions and manually merge the changes. "
                "Consider using `git mergetool` for complex conflicts"
            )

        tips.append(
            "\n[dim]After resolving each conflict, use `git add <file>` "
            "and then `git rebase --continue`[/dim]"
        )

        for tip in tips:
            self.console.print(f"  {tip}")
