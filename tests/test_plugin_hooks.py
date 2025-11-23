"""Tests for plugin hook execution and override precedence."""

from __future__ import annotations

from typing import Any

from git_sim.core.models import (
    CommitGraph,
    DangerLevel,
    OperationType,
    SafetyInfo,
    SimulationResult,
)
from git_sim.core.repository import Repository
from git_sim.plugins.base import HookPlugin, PluginMetadata, PluginType, get_plugin_manager
from git_sim.simulation.dispatcher import SimulationDispatcher


class RecordingHook(HookPlugin):
    """Hook plugin that records execution order and can override."""

    def __init__(self, record: list[str], override: bool = False) -> None:
        self._record = record
        self._override = override

    @property
    def metadata(self) -> PluginMetadata:  # type: ignore[override]
        return PluginMetadata(
            name="RecordingHook",
            version="0.1.0",
            description="Test recording hook",
            plugin_type=PluginType.HOOK,
        )

    def initialize(self) -> None:  # type: ignore[override]
        """Initialize the plugin."""
        pass

    def cleanup(self) -> None:  # type: ignore[override]
        """Clean up plugin resources."""
        pass

    def pre_simulate(self, repo: Repository, command: str, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        self._record.append(f"pre:{command}")
        # Inject a marker into kwargs
        kwargs["_hook_marker"] = True
        return kwargs

    def override_simulation(
        self, repo: Repository, command: str, **kwargs: Any
    ) -> SimulationResult | None:  # type: ignore[override]
        if self._override and command == "merge":
            self._record.append(f"override:{command}")
            # Provide a synthetic result
            return SimulationResult(
                operation_type=OperationType.MERGE,
                success=True,
                before_graph=CommitGraph(),
                after_graph=CommitGraph(),
                warnings=["override"],
                conflicts=[],
                changed_files=[],
                safety_info=SafetyInfo(
                    danger_level=DangerLevel.LOW,
                    reasons=["Overridden by hook"],
                    suggestions=[],
                ),
            )
        return None

    def post_simulate(
        self, repo: Repository, command: str, result: SimulationResult
    ) -> SimulationResult:  # type: ignore[override]
        self._record.append(f"post:{command}")
        return result


def test_hook_order_and_override(branched_repository: Repository) -> None:
    record: list[str] = []
    manager = get_plugin_manager()
    # Ensure clean registry (tests may run multiple times)
    for meta in manager.list_plugins():
        manager.unregister(meta.name)

    # Register a hook with override capability
    hook = RecordingHook(record=record, override=True)
    manager.register(hook)

    dispatcher = SimulationDispatcher(repo=branched_repository)
    result = dispatcher.simulate("merge", source="feature", target="main")

    # Order validation
    assert record[0].startswith("pre:merge")
    assert any(r.startswith("override:merge") for r in record)
    assert record[-1].startswith("post:merge")

    # Result should reflect override (empty graphs, custom warning)
    assert result.warnings == ["override"]
    assert result.safety_info is not None
    assert any("Overridden" in reason for reason in result.safety_info.reasons)


def test_hook_no_override_falls_back(branched_repository: Repository) -> None:
    record: list[str] = []
    manager = get_plugin_manager()
    for meta in manager.list_plugins():
        manager.unregister(meta.name)

    hook = RecordingHook(record=record, override=False)
    manager.register(hook)

    dispatcher = SimulationDispatcher(repo=branched_repository)
    result = dispatcher.simulate("merge", source="feature", target="main")

    # Should still have pre and post entries but no override
    assert record[0] == "pre:merge"
    assert not any(r.startswith("override:") for r in record)
    assert record[-1] == "post:merge"

    # Result should have non-empty graphs (merge simulation executed)
    assert result.before_graph.commits
    assert result.after_graph.commits
    assert "override" not in result.warnings
