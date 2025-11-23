"""Tests for cherry-pick simulation."""

import subprocess
from pathlib import Path

import pytest

from git_sim.core.repository import Repository
from git_sim.simulation.cherry_pick import CherryPickSimulator


class TestCherryPickSimulation:
    """Tests for cherry-pick simulation."""

    def test_simulate_single_commit(self, branched_repo: Path):
        """Test cherry-picking a single commit."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        # Get a commit from feature branch to cherry-pick
        result = subprocess.run(
            ["git", "rev-parse", "feature~1"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        commit_sha = result.stdout.decode().strip()

        repo = Repository(branched_repo)
        simulator = CherryPickSimulator(repo, commits=[commit_sha])
        result = simulator.run()

        assert len(result.commits_to_pick) == 1
        assert len(result.steps) == 1
        assert result.steps[0].commit_info.sha == commit_sha

    def test_simulate_multiple_commits(self, branched_repo: Path):
        """Test cherry-picking multiple commits."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        # Get commits from feature branch
        result = subprocess.run(
            ["git", "log", "feature", "--format=%H", "-n", "2"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        commits = result.stdout.decode().strip().split("\n")

        repo = Repository(branched_repo)
        simulator = CherryPickSimulator(repo, commits=commits)
        result = simulator.run()

        assert len(result.commits_to_pick) == 2
        assert len(result.steps) == 2

    def test_simulate_cherry_pick_with_conflicts(self, conflict_repo: Path):
        """Test cherry-pick that would cause conflicts."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=conflict_repo,
            capture_output=True,
            check=True,
        )

        # Get commit from feature that conflicts with main
        result = subprocess.run(
            ["git", "rev-parse", "feature"],
            cwd=conflict_repo,
            capture_output=True,
            check=True,
        )
        commit_sha = result.stdout.decode().strip()

        repo = Repository(conflict_repo)
        simulator = CherryPickSimulator(repo, commits=[commit_sha])
        result = simulator.run()

        assert result.has_conflicts
        assert any(c.path == "file_a.txt" for c in result.conflicts)


class TestCherryPickValidation:
    """Tests for cherry-pick validation."""

    def test_validate_commit_not_found(self, git_repo: Path):
        """Test validation with non-existent commit."""
        repo = Repository(git_repo)
        simulator = CherryPickSimulator(repo, commits=["nonexistent123"])
        errors, warnings = simulator.validate()

        assert len(errors) >= 1
        assert any("nonexistent" in e.lower() for e in errors)

    def test_validate_already_in_history(self, git_repo: Path):
        """Test validation when commit is already in history."""
        # Get a commit that's already in current history
        result = subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        commit_sha = result.stdout.decode().strip()

        repo = Repository(git_repo)
        simulator = CherryPickSimulator(repo, commits=[commit_sha])
        errors, warnings = simulator.validate()

        assert any("already" in w.lower() for w in warnings)


class TestCherryPickGraphs:
    """Tests for cherry-pick graph generation."""

    def test_after_graph_contains_new_commits(self, branched_repo: Path):
        """Test that after graph contains cherry-picked commits."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        result = subprocess.run(
            ["git", "rev-parse", "feature"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        commit_sha = result.stdout.decode().strip()

        repo = Repository(branched_repo)
        simulator = CherryPickSimulator(repo, commits=[commit_sha])
        result = simulator.run()

        # After graph should have the new cherry-picked commit
        for step in result.steps:
            if step.new_sha:
                assert step.new_sha in result.after_graph.commits
