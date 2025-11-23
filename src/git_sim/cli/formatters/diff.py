"""Diff rendering for git-sim CLI."""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from git_sim.core.models import ChangeType, DiffHunk, FileChange


class DiffRenderer:
    """Renders file diffs with syntax highlighting using Rich."""

    # Style mappings for change types
    CHANGE_TYPE_STYLES = {
        ChangeType.ADD: ("green", "A", "added"),
        ChangeType.DELETE: ("red", "D", "deleted"),
        ChangeType.MODIFY: ("yellow", "M", "modified"),
        ChangeType.RENAME: ("blue", "R", "renamed"),
        ChangeType.COPY: ("cyan", "C", "copied"),
    }

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the diff renderer.

        Args:
            console: Rich Console instance. If None, creates a new one.
        """
        self.console = console or Console()

    def render_file_change(
        self,
        fc: FileChange,
        show_hunks: bool = True,
        max_hunk_lines: int = 50,
    ) -> None:
        """
        Render a single file change as a Rich panel.

        Args:
            fc: FileChange to render.
            show_hunks: If True, show the actual diff content.
            max_hunk_lines: Maximum lines to show per hunk.
        """
        color, prefix, verb = self.CHANGE_TYPE_STYLES.get(
            fc.change_type, ("white", "?", "changed")
        )

        # Build title
        if fc.old_path and fc.old_path != fc.path:
            title = f"[{color}]{prefix}[/{color}] {fc.old_path} → {fc.path}"
        else:
            title = f"[{color}]{prefix}[/{color}] {fc.path}"

        # Build content
        if show_hunks and fc.hunks:
            content = self._format_hunks(fc.hunks, max_hunk_lines)
            panel = Panel(
                content,
                title=title,
                subtitle=f"+{fc.additions} -{fc.deletions}",
                border_style=color,
            )
        else:
            # Summary only
            content = Text()
            content.append(f"File {verb}", style=color)
            if fc.additions or fc.deletions:
                content.append(f" (+{fc.additions} -{fc.deletions})")
            panel = Panel(content, title=title, border_style=color)

        self.console.print(panel)

    def _format_hunks(self, hunks: list[DiffHunk], max_lines: int) -> Syntax:
        """Format diff hunks as syntax-highlighted text."""
        lines: list[str] = []
        total_lines = 0

        for hunk in hunks:
            # Add hunk header
            header = f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
            if hunk.header:
                header += f" {hunk.header}"
            lines.append(header)
            total_lines += 1

            # Add hunk lines (with limit)
            for line in hunk.lines:
                if total_lines >= max_lines:
                    lines.append(f"... ({len(hunk.lines) - len(lines) + 1} more lines)")
                    break
                lines.append(line)
                total_lines += 1

        diff_text = "\n".join(lines)
        return Syntax(diff_text, "diff", theme="monokai", line_numbers=False)

    def render_file_changes_summary(
        self,
        changes: list[FileChange],
        title: str = "File Changes",
    ) -> None:
        """
        Render a summary table of file changes.

        Args:
            changes: List of FileChange objects.
            title: Title for the table.
        """
        if not changes:
            self.console.print("[dim]No file changes[/dim]")
            return

        table = Table(title=title, show_header=True, header_style="bold")
        table.add_column("Status", style="bold", width=6)
        table.add_column("File", style="white")
        table.add_column("+", style="green", justify="right", width=6)
        table.add_column("-", style="red", justify="right", width=6)

        for fc in changes:
            color, prefix, _ = self.CHANGE_TYPE_STYLES.get(
                fc.change_type, ("white", "?", "changed")
            )

            # Handle renames
            if fc.old_path and fc.old_path != fc.path:
                path_display = f"{fc.old_path} → {fc.path}"
            else:
                path_display = fc.path

            table.add_row(
                f"[{color}]{prefix}[/{color}]",
                path_display,
                str(fc.additions) if fc.additions else "",
                str(fc.deletions) if fc.deletions else "",
            )

        # Add totals row
        total_add = sum(fc.additions for fc in changes)
        total_del = sum(fc.deletions for fc in changes)
        table.add_row(
            "",
            f"[bold]{len(changes)} file(s)[/bold]",
            f"[bold green]+{total_add}[/bold green]",
            f"[bold red]-{total_del}[/bold red]",
            style="dim",
        )

        self.console.print(table)

    def render_diff_preview(
        self,
        changes: list[FileChange],
        max_files: int = 5,
        max_lines_per_file: int = 30,
    ) -> None:
        """
        Render a preview of diffs for multiple files.

        Args:
            changes: List of FileChange objects.
            max_files: Maximum number of files to show full diff.
            max_lines_per_file: Maximum lines per file diff.
        """
        shown = 0
        for fc in changes:
            if shown >= max_files:
                remaining = len(changes) - shown
                self.console.print(
                    f"\n[dim]... and {remaining} more file(s)[/dim]"
                )
                break

            if fc.hunks:
                self.render_file_change(fc, show_hunks=True, max_hunk_lines=max_lines_per_file)
                shown += 1
            else:
                # No hunks - just show summary line
                color, prefix, verb = self.CHANGE_TYPE_STYLES.get(
                    fc.change_type, ("white", "?", "changed")
                )
                self.console.print(
                    f"  [{color}]{prefix}[/{color}] {fc.path} ({verb})"
                )
