"""Integration tests for git-sim CLI commands via Typer runner.

These tests exercise the public CLI surface to ensure commands execute
without errors and produce expected key output markers.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from typer.testing import CliRunner

from git_sim.cli.main import app as cli_app
from git_sim.core.repository import Repository

runner = CliRunner()


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


@contextmanager
def chdir(path: Path) -> Iterator[None]:
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def test_status_shows_branch_and_head(git_repo: Path) -> None:
    with chdir(git_repo):
        result = runner.invoke(cli_app, ["status"])  # no color by default
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "Current branch:" in out
    assert "HEAD:" in out


def test_log_shows_commits(git_repo: Path) -> None:
    with chdir(git_repo):
        result = runner.invoke(cli_app, ["log", "-n", "3"])  # max-count=3
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    # Count commit glyph occurrences ('* ' preceded by spaces)
    commits = [line for line in out.splitlines() if "*" in line]
    assert len(commits) >= 1  # At least one commit rendered


def test_diff_head_commit_shows_file_changes(git_repo: Path) -> None:
    repo = Repository(git_repo)
    head_sha = repo.head_sha
    with chdir(git_repo):
        result = runner.invoke(cli_app, ["diff", head_sha])
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "Commit:" in out
    # Expect table or panel with at least one file row (file_a or README)
    assert "README" in out or "file_a" in out or "file_b" in out


def test_rebase_simulation_runs(branched_repo: Path) -> None:
    # Rebase feature onto main
    with chdir(branched_repo):
        result = runner.invoke(cli_app, ["rebase", "main", "--source", "feature", "--no-graph"])
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "Rebase Summary" in out
    assert "Source branch" in out and "Target branch" in out


def test_merge_simulation_runs(branched_repo: Path) -> None:
    # Ensure we are on main branch for merge
    with chdir(branched_repo):
        result = runner.invoke(cli_app, ["merge", "feature", "--no-graph"])
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "Merge Summary" in out
    assert "Source branch" in out


def test_reset_soft_runs(git_repo: Path) -> None:
    with chdir(git_repo):
        result = runner.invoke(cli_app, ["reset", "HEAD~1", "--soft", "--no-graph"])
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "Reset Summary" in out
    assert "Mode" in out and "SOFT" in out


def test_cherry_pick_simulation_runs(branched_repo: Path) -> None:
    repo = Repository(branched_repo)
    # Get newest commit on feature branch (head of feature after branching)
    # Use walker starting at feature
    commits = list(repo.walk_commits(["feature"], max_entries=2))
    assert commits, "Expected commits on feature branch"
    pick_sha = commits[0].sha
    with chdir(branched_repo):
        result = runner.invoke(cli_app, ["cherry-pick", pick_sha, "--no-graph"])
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "Cherry-Pick Summary" in out
    assert "Commits to pick" in out


def test_explain_command_outputs_sections() -> None:
    # Run outside of repo (explain doesn't need repo)
    result = runner.invoke(cli_app, ["explain", "rebase"])
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "How it works:" in out
    assert "Risks:" in out
    assert "Safety tips:" in out


def test_sim_unified_merge_matches_basic_output(branched_repo: Path) -> None:
    with chdir(branched_repo):
        result = runner.invoke(cli_app, ["sim", "merge feature"])
    assert result.exit_code == 0, result.output
    out = strip_ansi(result.output)
    assert "Simulation Result" in out
    assert "Operation" in out and "MERGE" in out


def test_snapshot_lifecycle(git_repo: Path) -> None:
    with chdir(git_repo):
        create_res = runner.invoke(cli_app, ["snapshot", "create", "test-snap", "--desc", "demo"])
        assert create_res.exit_code == 0, create_res.output
        create_out = strip_ansi(create_res.output)
        # Parse full snapshot ID from creation output
        snap_id = ""
        for line in create_out.splitlines():
            if line.strip().startswith("ID:"):
                parts = line.split("ID:", 1)[1].strip()
                snap_id = parts
                break
        assert snap_id, create_out

        list_res = runner.invoke(cli_app, ["snapshot", "list"])
        out = strip_ansi(list_res.output)
        assert "Snapshots" in out and "test-snap" in out

        # Restore (soft)
        restore_res = runner.invoke(cli_app, ["snapshot", "restore", snap_id])
        assert restore_res.exit_code == 0, restore_res.output
        delete_res = runner.invoke(cli_app, ["snapshot", "delete", snap_id])
        assert delete_res.exit_code == 0, delete_res.output


def test_plugin_list_shows_no_plugins() -> None:
    result = runner.invoke(cli_app, ["plugin", "list"])
    out = strip_ansi(result.output)
    assert result.exit_code == 0
    assert "No plugins" in out or "No plugins found" in out


def test_tui_command_invokes_run(monkeypatch) -> None:
    calls = []

    def fake_run_tui():  # pragma: no cover - simple stub
        calls.append("run")

    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setitem(globals(), "__name__", "test")  # ensure not main guard issue
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "40")

    monkeypatch.setattr("git_sim.tui.run_tui", fake_run_tui)
    result = runner.invoke(cli_app, ["tui"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert calls == ["run"]
