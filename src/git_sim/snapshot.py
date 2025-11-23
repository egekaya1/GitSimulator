"""Snapshot and restore functionality for simulation exploration."""

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from git_sim.core.repository import Repository


@dataclass
class Snapshot:
    """A saved repository state snapshot."""

    id: str
    name: str
    created_at: str
    head_sha: str
    head_branch: Optional[str]
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        """Create from dictionary."""
        return cls(**data)


class SnapshotManager:
    """
    Manages repository state snapshots.

    Snapshots allow users to save the current state before
    running simulations or actual Git commands, and restore
    to those states later.
    """

    SNAPSHOT_DIR = ".git-sim"
    SNAPSHOTS_FILE = "snapshots.json"
    BUNDLES_DIR = "bundles"

    def __init__(self, repo_path: str | Path = "."):
        """
        Initialize the snapshot manager.

        Args:
            repo_path: Path to the Git repository.
        """
        self.repo_path = Path(repo_path).resolve()
        self.snapshot_dir = self.repo_path / self.SNAPSHOT_DIR
        self.bundles_dir = self.snapshot_dir / self.BUNDLES_DIR

    def _ensure_dirs(self) -> None:
        """Ensure snapshot directories exist."""
        self.snapshot_dir.mkdir(exist_ok=True)
        self.bundles_dir.mkdir(exist_ok=True)

    def _load_snapshots(self) -> list[Snapshot]:
        """Load snapshots from disk."""
        snapshots_file = self.snapshot_dir / self.SNAPSHOTS_FILE
        if not snapshots_file.exists():
            return []

        try:
            with open(snapshots_file) as f:
                data = json.load(f)
            return [Snapshot.from_dict(s) for s in data]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_snapshots(self, snapshots: list[Snapshot]) -> None:
        """Save snapshots to disk."""
        self._ensure_dirs()
        snapshots_file = self.snapshot_dir / self.SNAPSHOTS_FILE

        data = [s.to_dict() for s in snapshots]
        with open(snapshots_file, "w") as f:
            json.dump(data, f, indent=2)

    def _generate_id(self, name: str) -> str:
        """Generate a unique snapshot ID."""
        timestamp = datetime.now().isoformat()
        data = f"{name}:{timestamp}".encode()
        return hashlib.sha1(data).hexdigest()[:12]

    def create(
        self,
        name: str,
        description: str = "",
        tags: Optional[list[str]] = None,
    ) -> Snapshot:
        """
        Create a new snapshot of the current repository state.

        This creates a git bundle of the current state that can
        be used to restore later.

        Args:
            name: Name for the snapshot.
            description: Optional description.
            tags: Optional list of tags.

        Returns:
            The created Snapshot.
        """
        self._ensure_dirs()

        # Get current state
        repo = Repository(self.repo_path)
        head_sha = repo.head_sha
        head_branch = repo.head_branch

        # Generate ID
        snapshot_id = self._generate_id(name)

        # Create bundle
        bundle_path = self.bundles_dir / f"{snapshot_id}.bundle"
        self._create_bundle(bundle_path)

        # Create snapshot record
        snapshot = Snapshot(
            id=snapshot_id,
            name=name,
            created_at=datetime.now().isoformat(),
            head_sha=head_sha,
            head_branch=head_branch,
            description=description,
            tags=tags or [],
        )

        # Save to snapshots list
        snapshots = self._load_snapshots()
        snapshots.append(snapshot)
        self._save_snapshots(snapshots)

        return snapshot

    def _create_bundle(self, bundle_path: Path) -> None:
        """Create a git bundle of all refs."""
        subprocess.run(
            ["git", "bundle", "create", str(bundle_path), "--all"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )

    def list(self, tag: Optional[str] = None) -> list[Snapshot]:
        """
        List all snapshots.

        Args:
            tag: If provided, filter by this tag.

        Returns:
            List of snapshots, optionally filtered.
        """
        snapshots = self._load_snapshots()

        if tag:
            snapshots = [s for s in snapshots if tag in s.tags]

        return sorted(snapshots, key=lambda s: s.created_at, reverse=True)

    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        """
        Get a snapshot by ID.

        Args:
            snapshot_id: Snapshot ID or name.

        Returns:
            The snapshot if found, None otherwise.
        """
        snapshots = self._load_snapshots()

        for snapshot in snapshots:
            if snapshot.id == snapshot_id or snapshot.id.startswith(snapshot_id):
                return snapshot
            if snapshot.name == snapshot_id:
                return snapshot

        return None

    def delete(self, snapshot_id: str) -> bool:
        """
        Delete a snapshot.

        Args:
            snapshot_id: Snapshot ID or name.

        Returns:
            True if deleted, False if not found.
        """
        snapshots = self._load_snapshots()
        snapshot = self.get(snapshot_id)

        if snapshot is None:
            return False

        # Remove bundle file
        bundle_path = self.bundles_dir / f"{snapshot.id}.bundle"
        if bundle_path.exists():
            bundle_path.unlink()

        # Remove from list
        snapshots = [s for s in snapshots if s.id != snapshot.id]
        self._save_snapshots(snapshots)

        return True

    def restore(
        self,
        snapshot_id: str,
        mode: str = "soft",
    ) -> tuple[bool, str]:
        """
        Restore repository to a snapshot state.

        Args:
            snapshot_id: Snapshot ID or name.
            mode: Restore mode:
                - "soft": Only move HEAD (keep working changes)
                - "hard": Full restore (discard all changes)

        Returns:
            Tuple of (success, message).
        """
        snapshot = self.get(snapshot_id)
        if snapshot is None:
            return False, f"Snapshot not found: {snapshot_id}"

        bundle_path = self.bundles_dir / f"{snapshot.id}.bundle"
        if not bundle_path.exists():
            return False, f"Bundle file missing for snapshot: {snapshot_id}"

        try:
            if mode == "hard":
                # Hard reset to the snapshot state
                subprocess.run(
                    ["git", "reset", "--hard", snapshot.head_sha],
                    cwd=self.repo_path,
                    capture_output=True,
                    check=True,
                )

                # Checkout the branch if it existed
                if snapshot.head_branch:
                    subprocess.run(
                        ["git", "checkout", snapshot.head_branch],
                        cwd=self.repo_path,
                        capture_output=True,
                        check=False,  # Might fail if branch doesn't exist
                    )

                return True, f"Restored to snapshot '{snapshot.name}' (hard)"

            else:  # soft
                # Just checkout the commit
                subprocess.run(
                    ["git", "checkout", snapshot.head_sha],
                    cwd=self.repo_path,
                    capture_output=True,
                    check=True,
                )

                return True, f"Checked out snapshot '{snapshot.name}' (soft/detached HEAD)"

        except subprocess.CalledProcessError as e:
            return False, f"Failed to restore: {e.stderr.decode() if e.stderr else str(e)}"

    def create_from_reflog(
        self,
        reflog_entry: int = 0,
        name: Optional[str] = None,
    ) -> Snapshot:
        """
        Create a snapshot from a reflog entry.

        Args:
            reflog_entry: Reflog index (0 = current, 1 = previous, etc.)
            name: Optional name (defaults to "reflog-{entry}")

        Returns:
            The created Snapshot.
        """
        # Get the SHA from reflog
        result = subprocess.run(
            ["git", "rev-parse", f"HEAD@{{{reflog_entry}}}"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )
        sha = result.stdout.decode().strip()

        # Get the reflog message
        result = subprocess.run(
            ["git", "reflog", "-1", "--format=%gs", f"HEAD@{{{reflog_entry}}}"],
            cwd=self.repo_path,
            capture_output=True,
            check=True,
        )
        description = result.stdout.decode().strip()

        name = name or f"reflog-{reflog_entry}"

        return self.create(
            name=name,
            description=f"From reflog: {description}",
            tags=["reflog"],
        )

    def cleanup_old(self, keep: int = 10) -> int:
        """
        Remove old snapshots, keeping the most recent.

        Args:
            keep: Number of snapshots to keep.

        Returns:
            Number of snapshots deleted.
        """
        snapshots = self._load_snapshots()

        if len(snapshots) <= keep:
            return 0

        # Sort by date and keep most recent
        snapshots.sort(key=lambda s: s.created_at, reverse=True)
        to_delete = snapshots[keep:]

        for snapshot in to_delete:
            bundle_path = self.bundles_dir / f"{snapshot.id}.bundle"
            if bundle_path.exists():
                bundle_path.unlink()

        self._save_snapshots(snapshots[:keep])
        return len(to_delete)
