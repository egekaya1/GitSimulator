"""Tests for rebase simulation."""

import contextlib
import subprocess
from pathlib import Path

import pytest

from git_sim.core.exceptions import SimulationError
from git_sim.core.repository import Repository
from git_sim.simulation.rebase import RebaseSimulator


class TestRebaseSimulatorValidation:
    """Tests for RebaseSimulator validation."""

    def test_validate_valid_rebase(self, branched_repository: Repository):
        # Switch to feature branch
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repository.path,
            capture_output=True,
            check=True,
        )
        repo = Repository(branched_repository.path)

        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        errors, warnings = simulator.validate()

        assert len(errors) == 0

    def test_validate_source_not_found(self, repository: Repository):
        simulator = RebaseSimulator(repository, source="nonexistent", onto="main")
        errors, warnings = simulator.validate()

        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_validate_onto_not_found(self, repository: Repository):
        simulator = RebaseSimulator(repository, source="HEAD", onto="nonexistent")
        errors, warnings = simulator.validate()

        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_validate_same_commit_warning(self, repository: Repository):
        simulator = RebaseSimulator(repository, source="HEAD", onto="HEAD")
        errors, warnings = simulator.validate()

        assert len(errors) == 0
        assert any("same commit" in w.lower() for w in warnings)


class TestRebaseSimulation:
    """Tests for rebase simulation."""

    def test_simulate_rebase(self, branched_repo: Path):
        # Switch to feature branch
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        repo = Repository(branched_repo)

        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        result = simulator.run()

        assert result.source_branch == "feature"
        assert result.target_branch == "main"
        assert len(result.steps) == 2  # Two commits on feature branch
        assert result.merge_base_sha is not None

    def test_simulate_rebase_no_conflicts(self, branched_repo: Path):
        # Switch to feature branch
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        repo = Repository(branched_repo)

        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        result = simulator.run()

        # The branched_repo fixture doesn't have conflicting changes
        # (main modifies README, feature modifies file_a and adds feature.txt)
        # So there should be no conflicts
        assert result.has_conflicts is False

    def test_simulate_rebase_with_conflicts(self, conflict_repo: Path):
        # Switch to feature branch
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=conflict_repo,
            capture_output=True,
            check=True,
        )
        repo = Repository(conflict_repo)

        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        result = simulator.run()

        # Both branches modify the same file, so conflicts expected
        assert result.has_conflicts is True
        assert result.conflict_count >= 1

        # Find the conflict
        conflicts = [c for step in result.steps for c in step.conflicts]
        assert any(c.path == "file_a.txt" for c in conflicts)

    def test_simulate_rebase_graphs(self, branched_repo: Path):
        # Switch to feature branch
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        repo = Repository(branched_repo)

        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        result = simulator.run()

        # Check before graph has commits from both branches
        assert len(result.before_graph.commits) > 0

        # Check after graph has simulated rebased commits
        assert len(result.after_graph.commits) > 0

        # After graph should have new SHAs for rebased commits
        for step in result.steps:
            if not step.will_be_skipped and step.new_sha:
                assert step.new_sha in result.after_graph.commits

    def test_simulate_rebase_steps(self, branched_repo: Path):
        # Switch to feature branch
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        repo = Repository(branched_repo)

        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        result = simulator.run()

        # Check step properties
        for step in result.steps:
            assert step.original_sha is not None
            assert step.commit_info is not None
            assert step.action == "pick"

            if not step.will_be_skipped:
                assert step.new_sha is not None


class TestRebaseSimulatorRun:
    """Tests for the run() method with validation."""

    def test_run_with_invalid_source(self, repository: Repository):
        simulator = RebaseSimulator(repository, source="nonexistent", onto="main")

        with pytest.raises(SimulationError):
            simulator.run()

    def test_run_preserves_warnings(self, repository: Repository):
        # Rebase HEAD onto itself should produce a warning
        simulator = RebaseSimulator(repository, source="HEAD", onto="HEAD")

        # This will produce warnings but not errors
        with contextlib.suppress(SimulationError):
            simulator.run()  # May fail for other reasons

        # Check warnings were recorded
        assert any("same commit" in w.lower() for w in simulator.warnings), (
            "Expected same commit warning to be preserved"
        )


class TestConflictPrediction:
    """Tests specifically for conflict prediction accuracy."""

    def test_delete_modify_conflict(self, git_repo: Path):
        # Create a scenario where one branch deletes a file
        # and another modifies it

        # Create feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Modify file_a on feature
        (git_repo / "file_a.txt").write_text("Modified content\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Modify file A"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Go back to main and delete file_a
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        (git_repo / "file_a.txt").unlink()
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Delete file A"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Now simulate rebasing feature onto main
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        repo = Repository(git_repo)
        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        result = simulator.run()

        # Should predict a delete/modify conflict
        assert result.has_conflicts
        conflicts = [c for step in result.steps for c in step.conflicts]
        assert any(
            "delete" in c.description.lower() or "modify" in c.description.lower()
            for c in conflicts
        )

    def test_no_conflict_disjoint_files(self, git_repo: Path):
        # Create a scenario where branches modify different files

        # Create feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Add new file on feature
        (git_repo / "feature_only.txt").write_text("Feature content\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add feature file"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Go back to main and add different file
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        (git_repo / "main_only.txt").write_text("Main content\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add main file"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Simulate rebasing feature onto main
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        repo = Repository(git_repo)
        simulator = RebaseSimulator(repo, source="HEAD", onto="main")
        result = simulator.run()

        # Should have no conflicts
        assert not result.has_conflicts
