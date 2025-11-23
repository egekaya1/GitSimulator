"""Rebase simulation engine."""

import hashlib
from typing import Optional

from dulwich.repo import Repo as DulwichRepo

from git_sim.core.diff_analyzer import DiffAnalyzer
from git_sim.core.exceptions import RefNotFoundError
from git_sim.core.models import (
    CommitGraph,
    CommitInfo,
    FileChange,
    RebaseSimulation,
    RebaseStep,
)
from git_sim.core.repository import Repository
from git_sim.simulation.base import BaseSimulator
from git_sim.simulation.conflict_detector import ConflictDetector


class RebaseSimulator(BaseSimulator[RebaseSimulation]):
    """
    Simulates rebasing a branch onto another branch.

    This simulator analyzes the repository to predict:
    - Which commits will be replayed
    - Which commits will be skipped (duplicate patch-ids)
    - What conflicts might occur
    - What the resulting commit graph will look like

    All operations are read-only; the repository is not modified.
    """

    def __init__(
        self,
        repo: Repository,
        source: str = "HEAD",
        onto: str = "main",
    ):
        """
        Initialize the rebase simulator.

        Args:
            repo: Repository wrapper.
            source: Branch/ref to rebase (default: HEAD/current branch).
            onto: Branch/ref to rebase onto.
        """
        super().__init__(repo)
        self.source = source
        self.onto = onto
        self._dulwich_repo: Optional[DulwichRepo] = None
        self._diff_analyzer: Optional[DiffAnalyzer] = None
        self._conflict_detector = ConflictDetector()

    def _get_dulwich_repo(self) -> DulwichRepo:
        """Get the underlying Dulwich repo for low-level operations."""
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
        Validate that the rebase operation is possible.

        Checks:
        - Source ref exists
        - Onto ref exists
        - Source and onto are different
        - There are commits to rebase

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check source exists
        try:
            source_commit = self.repo.get_commit(self.source)
        except RefNotFoundError:
            errors.append(f"Source ref not found: {self.source}")
            return errors, warnings

        # Check onto exists
        try:
            onto_commit = self.repo.get_commit(self.onto)
        except RefNotFoundError:
            errors.append(f"Target ref not found: {self.onto}")
            return errors, warnings

        # Check they're different
        if source_commit.sha == onto_commit.sha:
            warnings.append("Source and target are the same commit; nothing to rebase")

        # Find merge base
        merge_base = self.repo.find_merge_base(self.source, self.onto)
        if merge_base is None:
            errors.append(
                f"No common ancestor found between '{self.source}' and '{self.onto}'"
            )
            return errors, warnings

        # Check if source is already based on onto
        if merge_base == onto_commit.sha:
            warnings.append(
                f"'{self.source}' is already based on '{self.onto}'; "
                f"rebase would have no effect"
            )

        # Check if onto is ancestor of source (fast-forward possible)
        if merge_base == source_commit.sha:
            warnings.append(
                f"'{self.onto}' is ahead of '{self.source}'; "
                f"consider 'git reset' instead of rebase"
            )

        return errors, warnings

    def simulate(self) -> RebaseSimulation:
        """
        Simulate the rebase operation.

        Algorithm:
        1. Find merge base between source and onto
        2. Collect commits from merge-base..source (topological order)
        3. Collect patch-ids from merge-base..onto for skip detection
        4. For each commit to replay:
           a. Check if patch-id matches (mark as skip)
           b. Detect potential conflicts against accumulated changes
        5. Build before/after commit graphs

        Returns:
            RebaseSimulation with predicted results.
        """
        source_commit = self.repo.get_commit(self.source)
        onto_commit = self.repo.get_commit(self.onto)
        merge_base_sha = self.repo.find_merge_base(self.source, self.onto)

        if merge_base_sha is None:
            # Should have been caught in validation
            raise ValueError("No merge base found")

        # Collect commits to replay (from merge-base exclusive to source inclusive)
        commits_to_replay = self._collect_commits_to_replay(merge_base_sha, source_commit.sha)

        # Collect patch-ids from onto's history for duplicate detection
        onto_patch_ids = self._collect_onto_patch_ids(merge_base_sha, onto_commit.sha)

        # Collect changes that have been made on the onto branch since merge-base
        onto_changes = self._collect_accumulated_changes(merge_base_sha, onto_commit.sha)

        # Simulate each step
        steps = self._simulate_steps(
            commits_to_replay,
            onto_patch_ids,
            onto_changes,
            onto_commit.sha,
        )

        # Build graphs
        before_graph = self._build_before_graph(source_commit.sha, onto_commit.sha)
        after_graph = self._build_after_graph(steps, onto_commit)

        # Get source branch name if available
        source_branch = self.source
        if source_branch == "HEAD":
            source_branch = self.repo.head_branch or "HEAD"

        return RebaseSimulation(
            source_branch=source_branch,
            target_branch=self.onto,
            onto_sha=onto_commit.sha,
            merge_base_sha=merge_base_sha,
            steps=steps,
            before_graph=before_graph,
            after_graph=after_graph,
        )

    def _collect_commits_to_replay(
        self, merge_base_sha: str, source_sha: str
    ) -> list[CommitInfo]:
        """
        Collect commits that will be replayed during rebase.

        Walks from source back to merge-base (exclusive) in reverse
        topological order (oldest first for replay).
        """
        commits = list(
            self.repo.walk_commits(
                include=[source_sha],
                exclude=[merge_base_sha],
            )
        )
        # Reverse to get oldest-first order for replay
        commits.reverse()
        return commits

    def _collect_onto_patch_ids(
        self, merge_base_sha: str, onto_sha: str
    ) -> set[str]:
        """
        Collect patch-ids from the onto branch for duplicate detection.

        Commits with matching patch-ids will be skipped during rebase.
        """
        diff_analyzer = self._get_diff_analyzer()
        return diff_analyzer.collect_patch_ids(
            self.repo, include=[onto_sha], exclude=[merge_base_sha]
        )

    def _collect_accumulated_changes(
        self, merge_base_sha: str, onto_sha: str
    ) -> list[FileChange]:
        """
        Collect all file changes made on the onto branch since merge-base.

        These represent "our" changes for conflict detection.
        """
        all_changes: list[FileChange] = []

        for commit in self.repo.walk_commits(
            include=[onto_sha], exclude=[merge_base_sha]
        ):
            changes = self.repo.get_commit_changes(commit.sha)
            all_changes.extend(changes)

        return all_changes

    def _simulate_steps(
        self,
        commits: list[CommitInfo],
        onto_patch_ids: set[str],
        onto_changes: list[FileChange],
        onto_sha: str,
    ) -> list[RebaseStep]:
        """
        Simulate replaying each commit.

        For each commit:
        1. Check if it will be skipped (duplicate patch-id)
        2. Detect potential conflicts with onto changes
        3. Update accumulated changes for next iteration
        """
        steps: list[RebaseStep] = []
        diff_analyzer = self._get_diff_analyzer()

        # Track accumulated changes as we "apply" commits
        accumulated_changes = list(onto_changes)

        for commit in commits:
            # Check for duplicate patch-id
            patch_id = diff_analyzer.compute_patch_id(commit.sha)
            will_skip = patch_id in onto_patch_ids

            # Get changes this commit introduces
            commit_changes = self.repo.get_commit_changes(commit.sha)

            # Detect conflicts (unless skipping)
            conflicts = []
            if not will_skip:
                conflicts = self._conflict_detector.detect_conflicts(
                    our_changes=accumulated_changes,
                    their_changes=commit_changes,
                )

            # Generate simulated new SHA
            new_sha = self._generate_simulated_sha(commit, onto_sha, len(steps))

            step = RebaseStep(
                original_sha=commit.sha,
                commit_info=commit,
                action="pick",
                new_sha=new_sha if not will_skip else None,
                conflicts=conflicts,
                will_be_skipped=will_skip,
            )
            steps.append(step)

            # Update accumulated changes for next commit
            if not will_skip:
                accumulated_changes.extend(commit_changes)

        return steps

    def _generate_simulated_sha(
        self, commit: CommitInfo, onto_sha: str, step_index: int
    ) -> str:
        """
        Generate a fake SHA for the rebased commit.

        This is for visualization purposes only. In a real rebase,
        the SHA would be computed from the actual commit object.
        """
        data = f"{commit.sha}:{onto_sha}:{step_index}".encode()
        return hashlib.sha1(data).hexdigest()

    def _build_before_graph(self, source_sha: str, onto_sha: str) -> CommitGraph:
        """Build the commit graph showing state before rebase."""
        return self.repo.build_graph([source_sha, onto_sha], max_commits=30)

    def _build_after_graph(
        self, steps: list[RebaseStep], onto_commit: CommitInfo
    ) -> CommitGraph:
        """
        Build a simulated commit graph showing state after rebase.

        Creates fake commits for the rebased commits, linked to onto.
        """
        graph = CommitGraph()
        graph.head_sha = steps[-1].new_sha if steps and steps[-1].new_sha else onto_commit.sha
        graph.head_branch = self.repo.head_branch

        # Add onto commit and its ancestors
        for commit in self.repo.walk_commits([self.onto], max_entries=15):
            graph.add_commit(commit)

        # Add rebased commits (only non-skipped ones)
        previous_sha = onto_commit.sha
        for step in steps:
            if step.will_be_skipped or not step.new_sha:
                continue

            # Create a simulated commit with new parent
            new_commit = CommitInfo(
                sha=step.new_sha,
                message=step.commit_info.message,
                author=step.commit_info.author,
                author_email=step.commit_info.author_email,
                timestamp=step.commit_info.timestamp,
                parent_shas=(previous_sha,),
                tree_sha=step.commit_info.tree_sha,  # Would be different in reality
            )
            graph.add_commit(new_commit)
            previous_sha = step.new_sha

        # Update branch tip
        source_branch = self.source
        if source_branch == "HEAD":
            source_branch = self.repo.head_branch or "source"
        graph.branch_tips[source_branch] = graph.head_sha
        graph.branch_tips[self.onto] = onto_commit.sha

        return graph
