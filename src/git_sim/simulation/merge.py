"""Merge simulation engine."""

import hashlib
from typing import Optional

from git_sim.core.models import (
    CommitGraph,
    CommitInfo,
    FileChange,
    MergeSimulation,
    PotentialConflict,
)
from git_sim.core.repository import Repository
from git_sim.simulation.base import BaseSimulator
from git_sim.simulation.conflict_detector import ConflictDetector


class MergeSimulator(BaseSimulator[MergeSimulation]):
    """
    Simulates merging one branch into another.

    This simulator analyzes the repository to predict:
    - Whether the merge can be fast-forwarded
    - What conflicts might occur
    - Which files merge cleanly
    - What the resulting commit graph will look like

    All operations are read-only; the repository is not modified.
    """

    def __init__(
        self,
        repo: Repository,
        source: str,
        target: str = "HEAD",
        no_ff: bool = False,
        strategy: str = "ort",
    ):
        """
        Initialize the merge simulator.

        Args:
            repo: Repository wrapper.
            source: Branch to merge from.
            target: Branch to merge into (default: HEAD/current branch).
            no_ff: If True, always create a merge commit (no fast-forward).
            strategy: Merge strategy to simulate (default: ort).
        """
        super().__init__(repo)
        self.source = source
        self.target = target
        self.no_ff = no_ff
        self.strategy = strategy
        self._conflict_detector = ConflictDetector()

    def validate(self) -> tuple[list[str], list[str]]:
        """
        Validate that the merge operation is possible.

        Checks:
        - Source ref exists
        - Target ref exists
        - Source and target are different
        - There is something to merge

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check source exists
        try:
            source_commit = self.repo.get_commit(self.source)
        except Exception:
            errors.append(f"Source branch not found: {self.source}")
            return errors, warnings

        # Check target exists
        try:
            target_commit = self.repo.get_commit(self.target)
        except Exception:
            errors.append(f"Target branch not found: {self.target}")
            return errors, warnings

        # Check they're different
        if source_commit.sha == target_commit.sha:
            warnings.append("Source and target are the same commit; nothing to merge")

        # Find merge base
        merge_base = self.repo.find_merge_base(self.source, self.target)
        if merge_base is None:
            errors.append(
                f"No common ancestor found between '{self.source}' and '{self.target}'"
            )
            return errors, warnings

        # Check for fast-forward possibility
        if merge_base == target_commit.sha:
            if self.no_ff:
                warnings.append(
                    "Fast-forward is possible, but --no-ff specified; "
                    "merge commit will be created"
                )
            else:
                warnings.append("This will be a fast-forward merge")

        # Check if already merged
        if merge_base == source_commit.sha:
            warnings.append(
                f"'{self.source}' is already merged into '{self.target}'"
            )

        return errors, warnings

    def simulate(self) -> MergeSimulation:
        """
        Simulate the merge operation.

        Algorithm:
        1. Find merge base between source and target
        2. Check for fast-forward possibility
        3. Collect changes on both sides since merge base
        4. Detect potential conflicts
        5. Identify files that merge cleanly
        6. Build before/after commit graphs

        Returns:
            MergeSimulation with predicted results.
        """
        source_commit = self.repo.get_commit(self.source)
        target_commit = self.repo.get_commit(self.target)
        merge_base_sha = self.repo.find_merge_base(self.source, self.target)

        if merge_base_sha is None:
            raise ValueError("No merge base found")

        # Check for fast-forward
        is_fast_forward = merge_base_sha == target_commit.sha and not self.no_ff

        # Collect changes on both sides
        source_changes = self._collect_changes(merge_base_sha, source_commit.sha)
        target_changes = self._collect_changes(merge_base_sha, target_commit.sha)

        # Detect conflicts
        conflicts = self._conflict_detector.detect_conflicts(
            our_changes=target_changes,
            their_changes=source_changes,
        )

        # Find files that merge cleanly
        files_merged_cleanly = self._find_clean_merges(
            source_changes, target_changes, conflicts
        )

        # Generate simulated merge commit SHA
        merge_commit_sha = ""
        if not is_fast_forward:
            merge_commit_sha = self._generate_merge_commit_sha(
                source_commit.sha, target_commit.sha
            )

        # Build graphs
        before_graph = self._build_before_graph(source_commit.sha, target_commit.sha)
        after_graph = self._build_after_graph(
            source_commit,
            target_commit,
            merge_commit_sha,
            is_fast_forward,
        )

        # Get branch names
        source_branch = self.source
        target_branch = self.target
        if target_branch == "HEAD":
            target_branch = self.repo.head_branch or "HEAD"

        return MergeSimulation(
            source_branch=source_branch,
            target_branch=target_branch,
            merge_base_sha=merge_base_sha,
            merge_commit_sha=merge_commit_sha if not is_fast_forward else source_commit.sha,
            strategy=self.strategy,
            is_fast_forward=is_fast_forward,
            conflicts=conflicts,
            files_merged_cleanly=files_merged_cleanly,
            before_graph=before_graph,
            after_graph=after_graph,
        )

    def _collect_changes(self, from_sha: str, to_sha: str) -> list[FileChange]:
        """Collect all file changes between two commits."""
        all_changes: list[FileChange] = []

        for commit in self.repo.walk_commits(include=[to_sha], exclude=[from_sha]):
            changes = self.repo.get_commit_changes(commit.sha)
            all_changes.extend(changes)

        return all_changes

    def _find_clean_merges(
        self,
        source_changes: list[FileChange],
        target_changes: list[FileChange],
        conflicts: list[PotentialConflict],
    ) -> list[str]:
        """Find files that can be merged without conflicts."""
        conflict_paths = {c.path for c in conflicts}

        # Files only changed on one side merge cleanly
        source_paths = {fc.path for fc in source_changes}
        target_paths = {fc.path for fc in target_changes}

        # Files only in source
        only_source = source_paths - target_paths

        # Files only in target
        only_target = target_paths - source_paths

        # Files in both but not in conflicts
        both_clean = (source_paths & target_paths) - conflict_paths

        return sorted(only_source | only_target | both_clean)

    def _generate_merge_commit_sha(self, source_sha: str, target_sha: str) -> str:
        """Generate a fake SHA for the merge commit."""
        data = f"merge:{source_sha}:{target_sha}".encode()
        return hashlib.sha1(data).hexdigest()

    def _build_before_graph(self, source_sha: str, target_sha: str) -> CommitGraph:
        """Build the commit graph showing state before merge."""
        return self.repo.build_graph([source_sha, target_sha], max_commits=30)

    def _build_after_graph(
        self,
        source_commit: CommitInfo,
        target_commit: CommitInfo,
        merge_commit_sha: str,
        is_fast_forward: bool,
    ) -> CommitGraph:
        """Build a simulated commit graph showing state after merge."""
        graph = CommitGraph()

        if is_fast_forward:
            # Fast-forward: target moves to source
            for commit in self.repo.walk_commits([source_commit.sha], max_entries=20):
                graph.add_commit(commit)
            graph.head_sha = source_commit.sha
        else:
            # Create merge commit
            merge_commit = CommitInfo(
                sha=merge_commit_sha,
                message=f"Merge branch '{self.source}' into {self.target}",
                author=target_commit.author,
                author_email=target_commit.author_email,
                timestamp=target_commit.timestamp + 1,
                parent_shas=(target_commit.sha, source_commit.sha),
                tree_sha="",  # Would be computed in real merge
            )
            graph.add_commit(merge_commit)

            # Add ancestors from both sides
            for commit in self.repo.walk_commits([target_commit.sha], max_entries=15):
                graph.add_commit(commit)
            for commit in self.repo.walk_commits([source_commit.sha], max_entries=15):
                graph.add_commit(commit)

            graph.head_sha = merge_commit_sha

        target_branch = self.target
        if target_branch == "HEAD":
            target_branch = self.repo.head_branch or "target"

        graph.head_branch = target_branch
        graph.branch_tips[target_branch] = graph.head_sha
        graph.branch_tips[self.source] = source_commit.sha

        return graph
