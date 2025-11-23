"""Cherry-pick simulation engine."""

import hashlib
from typing import Optional

from dulwich.repo import Repo as DulwichRepo

from git_sim.core.diff_analyzer import DiffAnalyzer
from git_sim.core.models import (
    CherryPickSimulation,
    CommitGraph,
    CommitInfo,
    OperationStep,
    PotentialConflict,
)
from git_sim.core.repository import Repository
from git_sim.simulation.base import BaseSimulator
from git_sim.simulation.conflict_detector import ConflictDetector


class CherryPickSimulator(BaseSimulator[CherryPickSimulation]):
    """
    Simulates cherry-picking commits.

    This simulator analyzes the repository to predict:
    - Which commits can be picked cleanly
    - What conflicts might occur
    - What the new commits will look like

    All operations are read-only; the repository is not modified.
    """

    def __init__(
        self,
        repo: Repository,
        commits: list[str],
        target: str = "HEAD",
    ):
        """
        Initialize the cherry-pick simulator.

        Args:
            repo: Repository wrapper.
            commits: List of commit SHAs or refs to cherry-pick.
            target: Target branch/ref to cherry-pick onto (default: HEAD).
        """
        super().__init__(repo)
        self.commit_refs = commits
        self.target = target
        self._conflict_detector = ConflictDetector()
        self._dulwich_repo: Optional[DulwichRepo] = None
        self._diff_analyzer: Optional[DiffAnalyzer] = None

    def _get_dulwich_repo(self) -> DulwichRepo:
        """Get the underlying Dulwich repo."""
        if self._dulwich_repo is None:
            self._dulwich_repo = DulwichRepo(str(self.repo.path))
        return self._dulwich_repo

    def _get_diff_analyzer(self) -> DiffAnalyzer:
        """Get the diff analyzer instance."""
        if self._diff_analyzer is None:
            self._diff_analyzer = DiffAnalyzer(self._get_dulwich_repo())
        return self._diff_analyzer

    def validate(self) -> tuple[list[str], list[str]]:
        """
        Validate that the cherry-pick operation is possible.

        Checks:
        - All commit refs exist
        - Target ref exists
        - Commits are not already in target history

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check target exists
        try:
            self.repo.get_commit(self.target)
        except Exception:
            errors.append(f"Target ref not found: {self.target}")
            return errors, warnings

        # Check each commit exists
        resolved_commits: list[CommitInfo] = []
        for ref in self.commit_refs:
            try:
                commit = self.repo.get_commit(ref)
                resolved_commits.append(commit)
            except Exception:
                errors.append(f"Commit not found: {ref}")

        if errors:
            return errors, warnings

        # Check if any commits are already in target history
        target_history = set()
        for commit in self.repo.walk_commits([self.target], max_entries=1000):
            target_history.add(commit.sha)

        for commit in resolved_commits:
            if commit.sha in target_history:
                warnings.append(
                    f"Commit {commit.short_sha} is already in target history"
                )

        # Check for merge commits
        for commit in resolved_commits:
            if commit.is_merge:
                warnings.append(
                    f"Commit {commit.short_sha} is a merge commit; "
                    "cherry-pick may behave unexpectedly"
                )

        return errors, warnings

    def simulate(self) -> CherryPickSimulation:
        """
        Simulate the cherry-pick operation.

        Algorithm:
        1. Resolve all commit refs to CommitInfo objects
        2. Get current target state
        3. For each commit to pick:
           a. Get the changes it introduces
           b. Detect conflicts against current simulated state
           c. Generate new commit info
        4. Build before/after commit graphs

        Returns:
            CherryPickSimulation with predicted results.
        """
        # Resolve commits
        commits_to_pick = [self.repo.get_commit(ref) for ref in self.commit_refs]
        target_commit = self.repo.get_commit(self.target)

        # Collect changes currently on target for conflict detection
        # (simplified: use changes from last N commits)
        accumulated_changes = self._get_recent_changes(target_commit.sha, depth=10)

        # Simulate each cherry-pick
        steps: list[OperationStep] = []
        simulated_head = target_commit.sha

        for i, commit in enumerate(commits_to_pick):
            step = self._simulate_pick(
                commit,
                simulated_head,
                accumulated_changes,
                step_number=i + 1,
            )
            steps.append(step)

            # Update state for next iteration
            if step.new_sha:
                simulated_head = step.new_sha
            commit_changes = self.repo.get_commit_changes(commit.sha)
            accumulated_changes.extend(commit_changes)

        # Build graphs
        before_graph = self._build_before_graph(
            target_commit.sha,
            [c.sha for c in commits_to_pick],
        )
        after_graph = self._build_after_graph(
            target_commit,
            steps,
        )

        # Get target branch name
        target_branch = self.target
        if target_branch == "HEAD":
            target_branch = self.repo.head_branch or "HEAD"

        return CherryPickSimulation(
            commits_to_pick=commits_to_pick,
            target_branch=target_branch,
            steps=steps,
            before_graph=before_graph,
            after_graph=after_graph,
        )

    def _get_recent_changes(self, from_sha: str, depth: int = 10):
        """Get file changes from recent commits."""
        from git_sim.core.models import FileChange

        changes: list[FileChange] = []
        for commit in self.repo.walk_commits([from_sha], max_entries=depth):
            commit_changes = self.repo.get_commit_changes(commit.sha)
            changes.extend(commit_changes)
        return changes

    def _simulate_pick(
        self,
        commit: CommitInfo,
        current_head: str,
        accumulated_changes,
        step_number: int,
    ) -> OperationStep:
        """Simulate picking a single commit."""
        # Get the changes this commit introduces
        commit_changes = self.repo.get_commit_changes(commit.sha)

        # Detect conflicts
        conflicts = self._conflict_detector.detect_conflicts(
            our_changes=accumulated_changes,
            their_changes=commit_changes,
        )

        # Generate new SHA
        new_sha = self._generate_picked_sha(commit.sha, current_head, step_number)

        return OperationStep(
            step_number=step_number,
            action="pick",
            commit_info=commit,
            original_sha=commit.sha,
            new_sha=new_sha,
            conflicts=conflicts,
            description=f"Cherry-pick {commit.short_sha}: {commit.first_line[:40]}",
        )

    def _generate_picked_sha(
        self, original_sha: str, onto_sha: str, step: int
    ) -> str:
        """Generate a fake SHA for the cherry-picked commit."""
        data = f"cherry-pick:{original_sha}:{onto_sha}:{step}".encode()
        return hashlib.sha1(data).hexdigest()

    def _build_before_graph(
        self,
        target_sha: str,
        source_shas: list[str],
    ) -> CommitGraph:
        """Build the commit graph showing state before cherry-pick."""
        # Include target and source commits
        refs = [target_sha] + source_shas
        return self.repo.build_graph(refs, max_commits=30)

    def _build_after_graph(
        self,
        target_commit: CommitInfo,
        steps: list[OperationStep],
    ) -> CommitGraph:
        """Build a simulated commit graph showing state after cherry-pick."""
        graph = CommitGraph()

        # Add target's history
        for commit in self.repo.walk_commits([target_commit.sha], max_entries=15):
            graph.add_commit(commit)

        # Add cherry-picked commits
        previous_sha = target_commit.sha
        for step in steps:
            if step.commit_info and step.new_sha:
                new_commit = CommitInfo(
                    sha=step.new_sha,
                    message=step.commit_info.message,
                    author=step.commit_info.author,
                    author_email=step.commit_info.author_email,
                    timestamp=step.commit_info.timestamp,
                    parent_shas=(previous_sha,),
                    tree_sha=step.commit_info.tree_sha,
                )
                graph.add_commit(new_commit)
                previous_sha = step.new_sha

        graph.head_sha = previous_sha
        graph.head_branch = self.repo.head_branch

        target_branch = self.target
        if target_branch == "HEAD":
            target_branch = self.repo.head_branch or "target"
        graph.branch_tips[target_branch] = graph.head_sha

        return graph
