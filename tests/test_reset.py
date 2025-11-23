"""Tests for reset simulation."""

import subprocess
from pathlib import Path

import pytest

from git_sim.core.models import ResetMode
from git_sim.core.repository import Repository
from git_sim.simulation.reset import ResetSimulator, parse_reset_mode


class TestResetModeParser:
    """Tests for reset mode parsing."""

    def test_parse_hard(self):
        assert parse_reset_mode("hard") == ResetMode.HARD
        assert parse_reset_mode("HARD") == ResetMode.HARD

    def test_parse_soft(self):
        assert parse_reset_mode("soft") == ResetMode.SOFT

    def test_parse_mixed(self):
        assert parse_reset_mode("mixed") == ResetMode.MIXED

    def test_parse_default(self):
        assert parse_reset_mode("unknown") == ResetMode.MIXED


class TestResetSimulation:
    """Tests for reset simulation."""

    def test_simulate_reset_soft(self, git_repo: Path):
        """Test soft reset simulation."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="HEAD~1", mode=ResetMode.SOFT)
        result = simulator.run()

        assert result.mode == ResetMode.SOFT
        assert len(result.commits_detached) == 1
        # Soft reset doesn't affect files
        assert len(result.files_unstaged) == 0
        assert len(result.files_discarded) == 0

    def test_simulate_reset_mixed(self, git_repo: Path):
        """Test mixed reset simulation."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="HEAD~1", mode=ResetMode.MIXED)
        result = simulator.run()

        assert result.mode == ResetMode.MIXED
        assert len(result.commits_detached) == 1
        # Mixed reset unstages files
        assert len(result.files_unstaged) > 0

    def test_simulate_reset_hard(self, git_repo: Path):
        """Test hard reset simulation."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="HEAD~1", mode=ResetMode.HARD)
        result = simulator.run()

        assert result.mode == ResetMode.HARD
        assert len(result.commits_detached) == 1
        # Hard reset discards files
        assert len(result.files_discarded) > 0

    def test_simulate_reset_multiple_commits(self, git_repo: Path):
        """Test reset that affects multiple commits."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="HEAD~2", mode=ResetMode.SOFT)
        result = simulator.run()

        assert len(result.commits_detached) == 2

    def test_simulate_reset_same_commit(self, git_repo: Path):
        """Test reset to current commit (no change)."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="HEAD", mode=ResetMode.SOFT)
        errors, warnings = simulator.validate()

        assert any("already" in w.lower() or "no effect" in w.lower() for w in warnings)


class TestResetSafetyInfo:
    """Tests for reset safety analysis."""

    def test_hard_reset_is_dangerous(self, git_repo: Path):
        """Test that hard reset is flagged as dangerous."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="HEAD~1", mode=ResetMode.HARD)
        result = simulator.run()

        sim_result = result.to_simulation_result()
        assert sim_result.safety_info is not None
        assert sim_result.safety_info.is_dangerous or not sim_result.safety_info.reversible

    def test_soft_reset_is_safe(self, git_repo: Path):
        """Test that soft reset is considered safe."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="HEAD~1", mode=ResetMode.SOFT)
        result = simulator.run()

        sim_result = result.to_simulation_result()
        assert sim_result.safety_info is not None
        assert sim_result.safety_info.reversible


class TestResetValidation:
    """Tests for reset validation."""

    def test_validate_invalid_target(self, git_repo: Path):
        """Test validation with invalid target."""
        repo = Repository(git_repo)
        simulator = ResetSimulator(repo, target="nonexistent", mode=ResetMode.SOFT)
        errors, warnings = simulator.validate()

        assert len(errors) == 1
        assert "nonexistent" in errors[0]
