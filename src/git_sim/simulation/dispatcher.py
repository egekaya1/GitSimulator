"""Unified command simulation dispatcher."""

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Type

from git_sim.core.models import (
    OperationType,
    ResetMode,
    SimulationResult,
)
from git_sim.core.repository import Repository
from git_sim.simulation.base import BaseSimulator


class SimulatorProtocol(Protocol):
    """Protocol that all simulators must implement."""

    def run(self) -> Any:
        """Run the simulation."""
        ...

    def validate(self) -> tuple[list[str], list[str]]:
        """Validate preconditions."""
        ...

    @property
    def warnings(self) -> list[str]:
        """Get validation warnings."""
        ...


@dataclass
class SimulationCommand:
    """Parsed simulation command."""

    operation: OperationType
    args: dict[str, Any]


class SimulationDispatcher:
    """
    Unified dispatcher for all simulation types.

    Provides a central entry point for running any simulation,
    with consistent error handling and result formatting.
    """

    def __init__(self, repo: Optional[Repository] = None):
        """
        Initialize the dispatcher.

        Args:
            repo: Repository wrapper. If None, will use current directory.
        """
        self._repo = repo

    @property
    def repo(self) -> Repository:
        """Get or create repository wrapper."""
        if self._repo is None:
            self._repo = Repository(".")
        return self._repo

    def simulate(
        self,
        command: str,
        **kwargs: Any,
    ) -> SimulationResult:
        """
        Run a simulation based on command string.

        Args:
            command: Command name (rebase, merge, reset, cherry-pick).
            **kwargs: Command-specific arguments.

        Returns:
            SimulationResult with unified result format.

        Raises:
            ValueError: If command is not recognized.
        """
        command_lower = command.lower().replace("-", "_")

        dispatcher_map = {
            "rebase": self._simulate_rebase,
            "merge": self._simulate_merge,
            "reset": self._simulate_reset,
            "cherry_pick": self._simulate_cherry_pick,
            "cherrypick": self._simulate_cherry_pick,
        }

        handler = dispatcher_map.get(command_lower)
        if handler is None:
            raise ValueError(f"Unknown command: {command}")

        return handler(**kwargs)

    def _simulate_rebase(
        self,
        onto: str,
        source: str = "HEAD",
        **kwargs: Any,
    ) -> SimulationResult:
        """Run rebase simulation."""
        from git_sim.simulation.rebase import RebaseSimulator

        simulator = RebaseSimulator(self.repo, source=source, onto=onto)
        result = simulator.run()
        sim_result = result.to_simulation_result()
        sim_result.warnings.extend(simulator.warnings)

        # Add safety info for rebase
        from git_sim.core.models import DangerLevel, SafetyInfo

        sim_result.safety_info = SafetyInfo(
            danger_level=DangerLevel.HIGH if result.has_conflicts else DangerLevel.MEDIUM,
            reasons=["History rewrite operation", "Commits will get new SHAs"],
            suggestions=[
                "Ensure you have pushed your current branch before rebasing",
                "Use 'git reflog' to recover if needed",
            ],
            requires_force_push=True,
        )

        return sim_result

    def _simulate_merge(
        self,
        source: str,
        target: str = "HEAD",
        no_ff: bool = False,
        **kwargs: Any,
    ) -> SimulationResult:
        """Run merge simulation."""
        from git_sim.simulation.merge import MergeSimulator

        simulator = MergeSimulator(
            self.repo, source=source, target=target, no_ff=no_ff
        )
        result = simulator.run()
        sim_result = result.to_simulation_result()
        sim_result.warnings.extend(simulator.warnings)

        # Add safety info for merge
        from git_sim.core.models import DangerLevel, SafetyInfo

        danger = DangerLevel.LOW
        if result.has_conflicts:
            danger = DangerLevel.MEDIUM

        sim_result.safety_info = SafetyInfo(
            danger_level=danger,
            reasons=["Creates new merge commit"] if not result.is_fast_forward else [],
            suggestions=[],
            reversible=True,
        )

        return sim_result

    def _simulate_reset(
        self,
        target: str,
        mode: str = "mixed",
        **kwargs: Any,
    ) -> SimulationResult:
        """Run reset simulation."""
        from git_sim.simulation.reset import ResetSimulator, parse_reset_mode

        reset_mode = parse_reset_mode(mode)
        simulator = ResetSimulator(self.repo, target=target, mode=reset_mode)
        result = simulator.run()
        sim_result = result.to_simulation_result()
        sim_result.warnings.extend(simulator.warnings)

        return sim_result

    def _simulate_cherry_pick(
        self,
        commits: list[str],
        target: str = "HEAD",
        **kwargs: Any,
    ) -> SimulationResult:
        """Run cherry-pick simulation."""
        from git_sim.simulation.cherry_pick import CherryPickSimulator

        simulator = CherryPickSimulator(
            self.repo, commits=commits, target=target
        )
        result = simulator.run()
        sim_result = result.to_simulation_result()
        sim_result.warnings.extend(simulator.warnings)

        # Add safety info
        from git_sim.core.models import DangerLevel, SafetyInfo

        sim_result.safety_info = SafetyInfo(
            danger_level=DangerLevel.LOW if not result.has_conflicts else DangerLevel.MEDIUM,
            reasons=["Creates new commits with different SHAs"],
            suggestions=[],
            reversible=True,
        )

        return sim_result

    def parse_command(self, command_string: str) -> SimulationCommand:
        """
        Parse a git-style command string into a SimulationCommand.

        Examples:
            "rebase main" -> SimulationCommand(REBASE, {onto: "main"})
            "merge feature" -> SimulationCommand(MERGE, {source: "feature"})
            "reset --hard HEAD~2" -> SimulationCommand(RESET, {target: "HEAD~2", mode: "hard"})

        Args:
            command_string: Git-style command string.

        Returns:
            Parsed SimulationCommand.
        """
        parts = command_string.split()
        if not parts:
            raise ValueError("Empty command string")

        command = parts[0].lower()
        args = parts[1:]

        if command == "rebase":
            return self._parse_rebase_command(args)
        elif command == "merge":
            return self._parse_merge_command(args)
        elif command == "reset":
            return self._parse_reset_command(args)
        elif command in ("cherry-pick", "cherrypick"):
            return self._parse_cherry_pick_command(args)
        else:
            raise ValueError(f"Unknown command: {command}")

    def _parse_rebase_command(self, args: list[str]) -> SimulationCommand:
        """Parse rebase command arguments."""
        parsed: dict[str, Any] = {"source": "HEAD"}

        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ("--onto", "-o") and i + 1 < len(args):
                parsed["onto"] = args[i + 1]
                i += 2
            elif not arg.startswith("-"):
                if "onto" not in parsed:
                    parsed["onto"] = arg
                i += 1
            else:
                i += 1

        if "onto" not in parsed:
            raise ValueError("Rebase requires a target branch")

        return SimulationCommand(operation=OperationType.REBASE, args=parsed)

    def _parse_merge_command(self, args: list[str]) -> SimulationCommand:
        """Parse merge command arguments."""
        parsed: dict[str, Any] = {"target": "HEAD", "no_ff": False}

        for arg in args:
            if arg == "--no-ff":
                parsed["no_ff"] = True
            elif not arg.startswith("-"):
                parsed["source"] = arg

        if "source" not in parsed:
            raise ValueError("Merge requires a source branch")

        return SimulationCommand(operation=OperationType.MERGE, args=parsed)

    def _parse_reset_command(self, args: list[str]) -> SimulationCommand:
        """Parse reset command arguments."""
        parsed: dict[str, Any] = {"mode": "mixed"}

        for arg in args:
            if arg == "--hard":
                parsed["mode"] = "hard"
            elif arg == "--soft":
                parsed["mode"] = "soft"
            elif arg == "--mixed":
                parsed["mode"] = "mixed"
            elif not arg.startswith("-"):
                parsed["target"] = arg

        if "target" not in parsed:
            raise ValueError("Reset requires a target commit")

        return SimulationCommand(operation=OperationType.RESET, args=parsed)

    def _parse_cherry_pick_command(self, args: list[str]) -> SimulationCommand:
        """Parse cherry-pick command arguments."""
        commits = [arg for arg in args if not arg.startswith("-")]

        if not commits:
            raise ValueError("Cherry-pick requires at least one commit")

        return SimulationCommand(
            operation=OperationType.CHERRY_PICK,
            args={"commits": commits, "target": "HEAD"},
        )

    def run_from_string(self, command_string: str) -> SimulationResult:
        """
        Parse and run a simulation from a command string.

        Args:
            command_string: Git-style command string.

        Returns:
            SimulationResult with unified result format.
        """
        parsed = self.parse_command(command_string)

        operation_map = {
            OperationType.REBASE: "rebase",
            OperationType.MERGE: "merge",
            OperationType.RESET: "reset",
            OperationType.CHERRY_PICK: "cherry_pick",
        }

        command_name = operation_map[parsed.operation]
        return self.simulate(command_name, **parsed.args)


# Convenience function for quick simulations
def simulate(command: str, **kwargs) -> SimulationResult:
    """
    Run a simulation with default repository.

    Args:
        command: Command name (rebase, merge, reset, cherry-pick).
        **kwargs: Command-specific arguments.

    Returns:
        SimulationResult with unified result format.
    """
    dispatcher = SimulationDispatcher()
    return dispatcher.simulate(command, **kwargs)
