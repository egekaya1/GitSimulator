"""Reset simulation engine."""

from git_sim.core.models import (
    CommitGraph,
    CommitInfo,
    ResetMode,
    ResetSimulation,
)
from git_sim.core.repository import Repository
from git_sim.simulation.base import BaseSimulator


class ResetSimulator(BaseSimulator[ResetSimulation]):
    """
    Simulates git reset operation.

    This simulator analyzes the repository to predict:
    - New HEAD position after reset
    - Commits that will become unreachable (detached)
    - Files affected based on reset mode (soft/mixed/hard)

    All operations are read-only; the repository is not modified.
    """

    def __init__(
        self,
        repo: Repository,
        target: str,
        mode: ResetMode = ResetMode.MIXED,
    ):
        """
        Initialize the reset simulator.

        Args:
            repo: Repository wrapper.
            target: Target commit/ref to reset to.
            mode: Reset mode (soft, mixed, hard).
        """
        super().__init__(repo)
        self.target = target
        self.mode = mode

    def validate(self) -> tuple[list[str], list[str]]:
        """
        Validate that the reset operation is possible.

        Checks:
        - Target ref exists
        - Warns about data loss for hard reset

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check target exists
        try:
            target_commit = self.repo.get_commit(self.target)
        except Exception:
            errors.append(f"Target ref not found: {self.target}")
            return errors, warnings

        # Get current HEAD
        try:
            current_commit = self.repo.get_commit("HEAD")
        except Exception:
            errors.append("Cannot determine current HEAD")
            return errors, warnings

        # Check if already at target
        if target_commit.sha == current_commit.sha:
            warnings.append("Already at target commit; reset will have no effect")
            return errors, warnings

        # Count commits that will become unreachable
        commits_to_lose = self._count_commits_between(target_commit.sha, current_commit.sha)

        if commits_to_lose > 0:
            warnings.append(f"{commits_to_lose} commit(s) will become unreachable")

        # Mode-specific warnings
        if self.mode == ResetMode.HARD:
            warnings.append("HARD reset: All uncommitted changes will be lost!")
        elif self.mode == ResetMode.MIXED:
            warnings.append("MIXED reset: Changes will be unstaged but kept in working directory")
        elif self.mode == ResetMode.SOFT:
            warnings.append("SOFT reset: Changes will remain staged")

        return errors, warnings

    def simulate(self) -> ResetSimulation:
        """
        Simulate the reset operation.

        Algorithm:
        1. Determine current HEAD position
        2. Find target commit
        3. Identify commits that will become unreachable
        4. Based on mode, determine file impacts
        5. Build before/after commit graphs

        Returns:
            ResetSimulation with predicted results.
        """
        current_commit = self.repo.get_commit("HEAD")
        target_commit = self.repo.get_commit(self.target)

        # Find commits that will become detached
        commits_detached = self._find_detached_commits(target_commit.sha, current_commit.sha)

        # Determine affected files based on mode
        files_unstaged: list[str] = []
        files_discarded: list[str] = []

        if self.mode in (ResetMode.MIXED, ResetMode.HARD):
            # Collect files changed in detached commits
            for commit in commits_detached:
                changes = self.repo.get_commit_changes(commit.sha)
                for fc in changes:
                    if self.mode == ResetMode.HARD:
                        if fc.path not in files_discarded:
                            files_discarded.append(fc.path)
                    else:
                        if fc.path not in files_unstaged:
                            files_unstaged.append(fc.path)

        # Build graphs
        before_graph = self._build_before_graph(current_commit.sha)
        after_graph = self._build_after_graph(target_commit, commits_detached)

        return ResetSimulation(
            target_sha=target_commit.sha,
            mode=self.mode,
            current_sha=current_commit.sha,
            commits_detached=commits_detached,
            files_unstaged=sorted(files_unstaged),
            files_discarded=sorted(files_discarded),
            before_graph=before_graph,
            after_graph=after_graph,
        )

    def _count_commits_between(self, base_sha: str, head_sha: str) -> int:
        """Count commits from head back to base (exclusive)."""
        count = 0
        for _commit in self.repo.walk_commits(include=[head_sha], exclude=[base_sha]):
            count += 1
        return count

    def _find_detached_commits(self, target_sha: str, current_sha: str) -> list[CommitInfo]:
        """Find commits that will become unreachable after reset."""
        if target_sha == current_sha:
            return []

        detached: list[CommitInfo] = []

        # Walk from current back, stopping at target
        for commit in self.repo.walk_commits(include=[current_sha]):
            if commit.sha == target_sha:
                break
            detached.append(commit)

        return detached

    def _build_before_graph(self, current_sha: str) -> CommitGraph:
        """Build the commit graph showing state before reset."""
        graph = self.repo.build_graph([current_sha], max_commits=20)
        return graph

    def _build_after_graph(
        self,
        target_commit: CommitInfo,
        detached_commits: list[CommitInfo],
    ) -> CommitGraph:
        """Build a simulated commit graph showing state after reset."""
        graph = CommitGraph()
        graph.head_sha = target_commit.sha
        graph.head_branch = self.repo.head_branch

        # Add commits from target backward
        for commit in self.repo.walk_commits([target_commit.sha], max_entries=20):
            graph.add_commit(commit)

        # Mark detached commits (they'll be shown as orphaned)
        for commit in detached_commits:
            graph.add_commit(commit)

        if graph.head_branch:
            graph.branch_tips[graph.head_branch] = target_commit.sha

        return graph


def parse_reset_mode(mode_str: str) -> ResetMode:
    """Parse a reset mode string into ResetMode enum."""
    mode_map = {
        "soft": ResetMode.SOFT,
        "mixed": ResetMode.MIXED,
        "hard": ResetMode.HARD,
    }
    return mode_map.get(mode_str.lower(), ResetMode.MIXED)
