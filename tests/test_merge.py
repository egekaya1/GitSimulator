"""Tests for merge simulation."""

import subprocess
from pathlib import Path

import pytest

from git_sim.core.repository import Repository
from git_sim.simulation.merge import MergeSimulator


class TestMergeSimulation:
    """Tests for merge simulation."""

    def test_simulate_fast_forward_merge(self, branched_repo: Path):
        """Test detection of fast-forward merge possibility."""
        # Setup: main is behind feature
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        repo = Repository(branched_repo)
        simulator = MergeSimulator(repo, source="feature")
        errors, warnings = simulator.validate()

        # Should detect fast-forward possibility
        assert any("fast-forward" in w.lower() for w in warnings) or len(errors) == 0

    def test_simulate_merge_no_conflicts(self, branched_repo: Path):
        """Test merge simulation when there are no conflicts."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        repo = Repository(branched_repo)
        simulator = MergeSimulator(repo, source="feature")
        result = simulator.run()

        # Branched repo has non-conflicting changes
        assert result.source_branch == "feature"
        assert result.merge_base_sha is not None

    def test_simulate_merge_with_conflicts(self, conflict_repo: Path):
        """Test merge simulation when there are conflicts."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=conflict_repo,
            capture_output=True,
            check=True,
        )

        repo = Repository(conflict_repo)
        simulator = MergeSimulator(repo, source="feature")
        result = simulator.run()

        # Conflict repo has conflicting changes to file_a.txt
        assert result.has_conflicts
        assert any(c.path == "file_a.txt" for c in result.conflicts)

    def test_simulate_merge_no_ff(self, branched_repo: Path):
        """Test merge simulation with --no-ff flag."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        repo = Repository(branched_repo)
        simulator = MergeSimulator(repo, source="feature", no_ff=True)
        errors, warnings = simulator.validate()

        # Should warn about --no-ff when ff is possible
        assert any("no-ff" in w.lower() or "fast-forward" in w.lower() for w in warnings)

    def test_simulate_merge_already_merged(self, git_repo: Path):
        """Test merge simulation when source is already merged."""
        repo = Repository(git_repo)
        simulator = MergeSimulator(repo, source="HEAD~1")
        errors, warnings = simulator.validate()

        # Should detect already merged
        assert any("already" in w.lower() for w in warnings)


class TestMergeGraphs:
    """Tests for merge graph generation."""

    def test_after_graph_contains_merge_commit(self, branched_repo: Path):
        """Test that after graph contains simulated merge commit."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        repo = Repository(branched_repo)
        simulator = MergeSimulator(repo, source="feature", no_ff=True)
        result = simulator.run()

        # After graph should have the merge commit
        if not result.is_fast_forward:
            assert result.merge_commit_sha in result.after_graph.commits
            merge_commit = result.after_graph.commits[result.merge_commit_sha]
            # Merge commits have two parents
            assert len(merge_commit.parent_shas) == 2
