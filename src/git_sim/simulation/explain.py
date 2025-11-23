"""Educational explanations for Git operations."""

from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from git_sim.core.models import DangerLevel, OperationType, SafetyInfo


@dataclass
class OperationExplanation:
    """Detailed explanation of a Git operation."""

    operation: OperationType
    summary: str
    how_it_works: list[str]
    what_changes: list[str]
    risks: list[str]
    safety_tips: list[str]
    alternatives: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


# Pre-built explanations for each operation
EXPLANATIONS = {
    OperationType.REBASE: OperationExplanation(
        operation=OperationType.REBASE,
        summary="Rebase re-applies commits from one branch onto another, creating new commits with different SHAs.",
        how_it_works=[
            "1. Find the merge base (common ancestor) between source and target branches",
            "2. Save the commits from merge-base to source tip",
            "3. Reset the source branch to the target branch",
            "4. Re-apply each saved commit one by one onto the new base",
            "5. Each re-applied commit gets a new SHA (it's technically a new commit)",
        ],
        what_changes=[
            "• Commit SHAs will change for all rebased commits",
            "• Commit timestamps may be updated",
            "• Branch history becomes linear (no merge commits)",
            "• Parent references are rewritten",
        ],
        risks=[
            "⚠️ HISTORY REWRITE: All rebased commits get new SHAs",
            "⚠️ FORCE PUSH REQUIRED: If branch was already pushed",
            "⚠️ CONFLICTS: May need to resolve same conflict multiple times",
            "⚠️ COLLABORATION RISK: Others' work may be invalidated",
        ],
        safety_tips=[
            "✓ Never rebase public/shared branches",
            "✓ Create a backup branch before rebasing: git branch backup-<branch>",
            "✓ Use git reflog to recover if something goes wrong",
            "✓ Communicate with team before force-pushing",
        ],
        alternatives=[
            "git merge: Preserves history, creates merge commit",
            "git cherry-pick: Pick specific commits without rewriting others",
            "git rebase -i: Interactive mode for more control",
        ],
        see_also=[
            "git reflog - View history of HEAD movements",
            "git reset --hard ORIG_HEAD - Undo a rebase",
        ],
    ),
    OperationType.MERGE: OperationExplanation(
        operation=OperationType.MERGE,
        summary="Merge combines changes from one branch into another, creating a merge commit.",
        how_it_works=[
            "1. Find the merge base (common ancestor) between branches",
            "2. Calculate three-way diff: base vs ours vs theirs",
            "3. Apply non-conflicting changes automatically",
            "4. Mark conflicting regions for manual resolution",
            "5. Create a merge commit with two parents",
        ],
        what_changes=[
            "• Creates a new merge commit (unless fast-forward)",
            "• Merge commit has two parent references",
            "• Branch history shows the merge point",
            "• Original commits remain unchanged",
        ],
        risks=[
            "⚠️ CONFLICTS: May need manual resolution",
            "⚠️ HISTORY: Creates non-linear history (merge bubbles)",
            "⚠️ COMPLEXITY: Large merges can be hard to review",
        ],
        safety_tips=[
            "✓ Pull/fetch before merging to get latest changes",
            "✓ Merge frequently to reduce conflict size",
            "✓ Use git merge --no-commit to review before committing",
            "✓ Use git merge --abort if something goes wrong",
        ],
        alternatives=[
            "git rebase: Creates linear history (rewrites commits)",
            "git merge --squash: Combine all changes into one commit",
            "git cherry-pick: Pick specific commits",
        ],
        see_also=[
            "git log --graph - Visualize merge history",
            "git merge-base - Find common ancestor",
        ],
    ),
    OperationType.RESET: OperationExplanation(
        operation=OperationType.RESET,
        summary="Reset moves HEAD and optionally modifies the index and working tree.",
        how_it_works=[
            "1. Move HEAD to the specified commit",
            "2. Based on mode, update index and/or working tree:",
            "   --soft: Only move HEAD (staged changes preserved)",
            "   --mixed: Move HEAD + reset index (changes unstaged)",
            "   --hard: Move HEAD + reset index + reset working tree",
        ],
        what_changes=[
            "• HEAD pointer moves to target commit",
            "• --soft: Nothing else changes",
            "• --mixed: Index reset, working directory unchanged",
            "• --hard: Both index and working directory reset",
        ],
        risks=[
            "⚠️ --hard: DESTROYS uncommitted changes permanently",
            "⚠️ Commits become unreachable (orphaned)",
            "⚠️ Force push required if resetting pushed commits",
        ],
        safety_tips=[
            "✓ Commit or stash changes before --hard reset",
            "✓ Use git stash before experimenting",
            "✓ Use git reflog to recover orphaned commits",
            "✓ Prefer git revert for shared branches",
        ],
        alternatives=[
            "git revert: Create new commit that undoes changes (safe for shared branches)",
            "git checkout: Switch branches without moving HEAD",
            "git restore: Restore working tree files",
        ],
        see_also=[
            "git reflog - Find orphaned commits",
            "git stash - Temporarily save changes",
        ],
    ),
    OperationType.CHERRY_PICK: OperationExplanation(
        operation=OperationType.CHERRY_PICK,
        summary="Cherry-pick applies the changes from specific commits onto the current branch.",
        how_it_works=[
            "1. For each commit to pick:",
            "2. Calculate the diff the commit introduces (vs its parent)",
            "3. Apply that diff to the current HEAD",
            "4. Create a new commit with the same message",
            "5. New commit has different SHA but same changes",
        ],
        what_changes=[
            "• New commit created with same changes and message",
            "• New commit has different SHA",
            "• New commit's parent is current HEAD",
            "• Original commit is unchanged",
        ],
        risks=[
            "⚠️ DUPLICATE COMMITS: Same change exists in two places",
            "⚠️ CONFLICTS: May conflict with existing changes",
            "⚠️ CONFUSION: Can make history harder to understand",
        ],
        safety_tips=[
            "✓ Use -x flag to add source commit reference to message",
            "✓ Consider if merge or rebase is more appropriate",
            "✓ Cherry-pick in chronological order to avoid conflicts",
            "✓ Use git cherry-pick --abort if conflicts are too complex",
        ],
        alternatives=[
            "git merge: Bring in entire branch",
            "git rebase: Move entire branch to new base",
            "git format-patch / git am: For cross-repository picks",
        ],
        see_also=[
            "git log --cherry: Find un-cherry-picked commits",
            "git cherry: Show commits not merged upstream",
        ],
    ),
}


class ExplainRenderer:
    """Renders explanations for Git operations."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize the explain renderer."""
        self.console = console or Console()

    def explain(self, operation: OperationType) -> None:
        """
        Display a detailed explanation of an operation.

        Args:
            operation: The operation type to explain.
        """
        explanation = EXPLANATIONS.get(operation)
        if explanation is None:
            self.console.print(f"[red]No explanation available for {operation.name}[/red]")
            return

        # Summary
        self.console.print(Panel(
            explanation.summary,
            title=f"[bold blue]git {operation.name.lower()}[/bold blue]",
            border_style="blue",
        ))

        # How it works
        self.console.print("\n[bold]How it works:[/bold]")
        for step in explanation.how_it_works:
            self.console.print(f"  {step}")

        # What changes
        self.console.print("\n[bold]What changes:[/bold]")
        for change in explanation.what_changes:
            self.console.print(f"  {change}")

        # Risks
        self.console.print("\n[bold red]Risks:[/bold red]")
        for risk in explanation.risks:
            self.console.print(f"  {risk}")

        # Safety tips
        self.console.print("\n[bold green]Safety tips:[/bold green]")
        for tip in explanation.safety_tips:
            self.console.print(f"  {tip}")

        # Alternatives
        if explanation.alternatives:
            self.console.print("\n[bold]Alternatives:[/bold]")
            for alt in explanation.alternatives:
                self.console.print(f"  • {alt}")

        # See also
        if explanation.see_also:
            self.console.print("\n[dim]See also:[/dim]")
            for ref in explanation.see_also:
                self.console.print(f"  [dim]{ref}[/dim]")

    def render_safety_report(self, safety_info: SafetyInfo) -> None:
        """
        Render a safety analysis report.

        Args:
            safety_info: Safety analysis for an operation.
        """
        # Danger level styling
        level_styles = {
            DangerLevel.LOW: ("green", "LOW", "✓"),
            DangerLevel.MEDIUM: ("yellow", "MEDIUM", "⚠️"),
            DangerLevel.HIGH: ("red", "HIGH", "🔴"),
            DangerLevel.CRITICAL: ("red bold", "CRITICAL", "💀"),
        }

        style, label, icon = level_styles.get(
            safety_info.danger_level, ("white", "UNKNOWN", "?")
        )

        # Build content
        content = Table(show_header=False, box=None, padding=(0, 2))
        content.add_column("Label", style="bold")
        content.add_column("Value")

        content.add_row("Danger Level", f"[{style}]{icon} {label}[/{style}]")
        content.add_row("Reversible", "[green]Yes[/green]" if safety_info.reversible else "[red]No[/red]")
        content.add_row(
            "Force Push Required",
            "[yellow]Yes[/yellow]" if safety_info.requires_force_push else "[green]No[/green]"
        )

        self.console.print(Panel(content, title="[bold]Safety Analysis[/bold]", border_style=style))

        if safety_info.reasons:
            self.console.print("\n[bold]Reasons for rating:[/bold]")
            for reason in safety_info.reasons:
                self.console.print(f"  • {reason}")

        if safety_info.suggestions:
            self.console.print("\n[bold green]Suggestions:[/bold green]")
            for suggestion in safety_info.suggestions:
                self.console.print(f"  ✓ {suggestion}")


def explain_command(command: str, console: Optional[Console] = None) -> None:
    """
    Display explanation for a Git command.

    Args:
        command: Command name (rebase, merge, reset, cherry-pick).
        console: Optional Rich console.
    """
    command_map = {
        "rebase": OperationType.REBASE,
        "merge": OperationType.MERGE,
        "reset": OperationType.RESET,
        "cherry-pick": OperationType.CHERRY_PICK,
        "cherrypick": OperationType.CHERRY_PICK,
        "cherry_pick": OperationType.CHERRY_PICK,
    }

    operation = command_map.get(command.lower())
    if operation is None:
        console = console or Console()
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print(f"Available: {', '.join(command_map.keys())}")
        return

    renderer = ExplainRenderer(console)
    renderer.explain(operation)
