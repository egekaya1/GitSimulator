"""Tests for SnapshotManager functionality."""

from pathlib import Path

from git_sim.core.repository import Repository
from git_sim.snapshot import SnapshotManager


def test_create_and_list_snapshot(git_repo: Path):
    mgr = SnapshotManager(git_repo)
    snap = mgr.create("baseline", description="Initial", tags=["init"])
    listed = mgr.list()
    assert any(s.id == snap.id for s in listed)
    # Bundle file exists
    bundle_path = Path(git_repo) / mgr.SNAPSHOT_DIR / mgr.BUNDLES_DIR / f"{snap.id}.bundle"
    assert bundle_path.exists()


def test_get_snapshot_by_name(git_repo: Path):
    mgr = SnapshotManager(git_repo)
    snap = mgr.create("named-one")
    found = mgr.get("named-one")
    assert found is not None and found.id == snap.id


def test_soft_restore_moves_head_preserves_working(git_repo: Path):
    mgr = SnapshotManager(git_repo)
    snap = mgr.create("point-a")
    # Make another commit after snapshot
    (git_repo / "extra.txt").write_text("Extra content\n")
    import subprocess

    subprocess.run(["git", "add", "extra.txt"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add extra"], cwd=git_repo, capture_output=True, check=True
    )

    # Soft restore
    ok, _ = mgr.restore(snap.id, mode="soft")
    assert ok, "Soft restore should succeed"
    repo = Repository(git_repo)
    assert repo.head_sha == snap.head_sha  # HEAD moved back
    # Staged changes should now appear as diff (file remains in working tree)
    # We simply assert file still exists
    assert (git_repo / "extra.txt").exists()


def test_hard_restore_discards_uncommitted(git_repo: Path):
    mgr = SnapshotManager(git_repo)
    snap = mgr.create("point-b")
    # Create uncommitted change
    (git_repo / "temp.txt").write_text("Temp change\n")
    # Hard restore (should remove uncommitted file)
    ok, _ = mgr.restore(snap.id, mode="hard")
    assert ok, "Hard restore should succeed"
    assert not (git_repo / "temp.txt").exists()


def test_delete_snapshot(git_repo: Path):
    mgr = SnapshotManager(git_repo)
    snap = mgr.create("to-delete")
    assert mgr.delete(snap.id) is True
    assert mgr.get(snap.id) is None
