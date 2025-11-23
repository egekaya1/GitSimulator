"""Tests for the simulation dispatcher."""

import subprocess
from pathlib import Path

import pytest

from git_sim.core.models import OperationType
from git_sim.core.repository import Repository
from git_sim.simulation.dispatcher import SimulationDispatcher


class TestCommandParsing:
    """Tests for command string parsing."""

    def test_parse_rebase_command(self):
        dispatcher = SimulationDispatcher()
        parsed = dispatcher.parse_command("rebase main")

        assert parsed.operation == OperationType.REBASE
        assert parsed.args["onto"] == "main"

    def test_parse_merge_command(self):
        dispatcher = SimulationDispatcher()
        parsed = dispatcher.parse_command("merge feature")

        assert parsed.operation == OperationType.MERGE
        assert parsed.args["source"] == "feature"

    def test_parse_merge_no_ff(self):
        dispatcher = SimulationDispatcher()
        parsed = dispatcher.parse_command("merge feature --no-ff")

        assert parsed.operation == OperationType.MERGE
        assert parsed.args["no_ff"] is True

    def test_parse_reset_hard(self):
        dispatcher = SimulationDispatcher()
        parsed = dispatcher.parse_command("reset --hard HEAD~2")

        assert parsed.operation == OperationType.RESET
        assert parsed.args["mode"] == "hard"
        assert parsed.args["target"] == "HEAD~2"

    def test_parse_reset_soft(self):
        dispatcher = SimulationDispatcher()
        parsed = dispatcher.parse_command("reset --soft HEAD~1")

        assert parsed.operation == OperationType.RESET
        assert parsed.args["mode"] == "soft"

    def test_parse_cherry_pick(self):
        dispatcher = SimulationDispatcher()
        parsed = dispatcher.parse_command("cherry-pick abc123 def456")

        assert parsed.operation == OperationType.CHERRY_PICK
        assert parsed.args["commits"] == ["abc123", "def456"]

    def test_parse_unknown_command(self):
        dispatcher = SimulationDispatcher()

        with pytest.raises(ValueError, match="Unknown command"):
            dispatcher.parse_command("unknown-command arg")

    def test_parse_empty_command(self):
        dispatcher = SimulationDispatcher()

        with pytest.raises(ValueError, match="Empty command"):
            dispatcher.parse_command("")


class TestDispatcherSimulation:
    """Tests for running simulations through dispatcher."""

    def test_simulate_rebase(self, branched_repo: Path):
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        dispatcher = SimulationDispatcher(Repository(branched_repo))
        result = dispatcher.simulate("rebase", onto="main")

        assert result.operation_type == OperationType.REBASE
        assert result.target_ref == "main"

    def test_simulate_merge(self, branched_repo: Path):
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        dispatcher = SimulationDispatcher(Repository(branched_repo))
        result = dispatcher.simulate("merge", source="feature")

        assert result.operation_type == OperationType.MERGE
        assert result.source_ref == "feature"

    def test_simulate_reset(self, git_repo: Path):
        dispatcher = SimulationDispatcher(Repository(git_repo))
        result = dispatcher.simulate("reset", target="HEAD~1", mode="soft")

        assert result.operation_type == OperationType.RESET

    def test_run_from_string(self, branched_repo: Path):
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        dispatcher = SimulationDispatcher(Repository(branched_repo))
        result = dispatcher.run_from_string("merge feature")

        assert result.operation_type == OperationType.MERGE

    def test_unknown_simulation(self, git_repo: Path):
        dispatcher = SimulationDispatcher(Repository(git_repo))

        with pytest.raises(ValueError, match="Unknown command"):
            dispatcher.simulate("unknown-op", arg="value")


class TestDispatcherSafetyInfo:
    """Tests for safety info generation."""

    def test_rebase_has_safety_info(self, branched_repo: Path):
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        dispatcher = SimulationDispatcher(Repository(branched_repo))
        result = dispatcher.simulate("rebase", onto="main")

        assert result.safety_info is not None
        assert result.safety_info.requires_force_push is True

    def test_merge_has_safety_info(self, branched_repo: Path):
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )

        dispatcher = SimulationDispatcher(Repository(branched_repo))
        result = dispatcher.simulate("merge", source="feature")

        assert result.safety_info is not None
        assert result.safety_info.reversible is True
