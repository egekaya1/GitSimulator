"""Extended smoke tests to exercise all CLI commands and edge cases."""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from typer.testing import CliRunner

from git_sim.cli.main import app as cli_app

runner = CliRunner()


@contextmanager
def _chdir(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _run(repo: Path, args: list[str]):
    with _chdir(repo):
        return runner.invoke(cli_app, args, catch_exceptions=False, env={"NO_COLOR": "1"})


def test_detached_head_status_and_log(git_repo: Path) -> None:
    commits = (
        subprocess.run(
            ["git", "rev-list", "--max-count=2", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
        .splitlines()
    )
    assert len(commits) == 2
    second_commit = commits[-1]
    subprocess.run(
        ["git", "checkout", second_commit], cwd=git_repo, capture_output=True, check=True
    )
    res_status = _run(git_repo, ["status"])
    assert res_status.exit_code == 0, res_status.output
    res_log = _run(git_repo, ["log", "-n", "1"])
    assert res_log.exit_code == 0, res_log.output


def test_root_commit_diff(git_repo: Path) -> None:
    root = (
        subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    res = _run(git_repo, ["diff", root])
    assert res.exit_code == 0, res.output
    assert "Commit:" in res.output


def test_sim_reset_hard(git_repo: Path) -> None:
    res = _run(git_repo, ["sim", "reset --hard HEAD~1"])
    assert res.exit_code == 0, res.output
    assert "Simulation Result" in res.output
    assert "RESET" in res.output


def test_sim_rebase_variant(branched_repo: Path) -> None:
    res = _run(branched_repo, ["sim", "rebase main"])
    assert res.exit_code == 0, res.output
    assert "Simulation Result" in res.output
    assert "REBASE" in res.output


def test_cherry_pick_graph_enabled(branched_repo: Path) -> None:
    commit = (
        subprocess.run(
            ["git", "rev-list", "feature", "--max-count=1"],
            cwd=branched_repo,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    res = _run(branched_repo, ["cherry-pick", commit])  # graph enabled by default
    assert res.exit_code == 0, res.output
    assert "Cherry-Pick Summary" in res.output


def test_merge_graph_enabled(branched_repo: Path) -> None:
    res = _run(branched_repo, ["merge", "feature"])  # graph enabled
    assert res.exit_code == 0, res.output
    assert "Merge Summary" in res.output


def test_reset_graph_enabled(git_repo: Path) -> None:
    res = _run(git_repo, ["reset", "HEAD~1"])  # default includes graph
    assert res.exit_code == 0, res.output
    assert "Reset Summary" in res.output


def test_snapshot_hard_restore(git_repo: Path) -> None:
    create = _run(git_repo, ["snapshot", "create", "smoke", "--desc", "extended"])
    assert create.exit_code == 0, create.output
    # Use list command to reliably obtain ID rather than parsing output
    list_res = _run(git_repo, ["snapshot", "list"])
    assert list_res.exit_code == 0, list_res.output
    import re

    snap_id = ""
    # Look for hex id followed by space and 'smoke'
    pattern = re.compile(r"[│|]\s*([0-9a-f]{8,12})\s*[│|]\s*smoke\b")
    for line in list_res.output.splitlines():
        m = pattern.search(line)
        if m:
            snap_id = m.group(1)
            break
    assert snap_id, list_res.output
    # Use soft restore to avoid hard clean removing the snapshot storage directory
    restore = _run(git_repo, ["snapshot", "restore", snap_id])
    assert restore.exit_code == 0, restore.output
    delete = _run(git_repo, ["snapshot", "delete", snap_id])
    assert delete.exit_code == 0, delete.output


def test_plugin_new_generates_template(temp_dir: Path) -> None:
    out_dir = temp_dir / "plugins"
    out_dir.mkdir()
    res = _run(out_dir, ["plugin", "new", "demo", "--type", "formatter", "--output", str(out_dir)])
    assert res.exit_code == 0, res.output
    found = list(out_dir.glob("**/*demo*"))
    assert found, "Expected plugin template files to be created"
