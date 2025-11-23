"""Smoke test for GitSim TUI headless simulation."""

from git_sim.tui.app import GitSimApp


def test_tui_headless_simulation(branched_repository) -> None:
    app = GitSimApp(repo_path=str(branched_repository.path))  # type: ignore[attr-defined]
    result = app.headless_simulate("merge feature")
    assert result.operation_type.name == "MERGE"
    assert result.before_graph.commits
    assert result.after_graph.commits
