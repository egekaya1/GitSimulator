"""Diff analysis and parsing utilities."""

import hashlib
import io
import re
from typing import Optional

from dulwich.objects import Blob, Commit
from dulwich.patch import write_tree_diff
from dulwich.repo import Repo

from git_sim.core.models import CommitDiff, DiffHunk, FileChange


class DiffAnalyzer:
    """
    Analyzes diffs between commits and trees.

    Provides functionality for:
    - Parsing unified diffs into structured hunks
    - Computing patch-ids for duplicate detection
    - Extracting line-level change information
    """

    # Regex patterns for diff parsing
    HUNK_HEADER_RE = re.compile(
        r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$"
    )
    DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*) b/(.*)$")
    INDEX_RE = re.compile(r"^index ([0-9a-f]+)\.\.([0-9a-f]+)")

    def __init__(self, repo: Repo):
        """
        Initialize the diff analyzer.

        Args:
            repo: Dulwich Repo instance.
        """
        self._repo = repo
        self._object_store = repo.object_store

    def get_commit_diff(self, commit_sha: str) -> CommitDiff:
        """
        Get the diff for a commit against its first parent.

        Args:
            commit_sha: SHA of the commit.

        Returns:
            CommitDiff with parsed file changes and hunks.
        """
        commit = self._repo[commit_sha.encode()]
        if not isinstance(commit, Commit):
            raise ValueError(f"Not a commit: {commit_sha}")

        parent_sha = None
        parent_tree = None

        if commit.parents:
            parent_sha = commit.parents[0].decode()
            parent_commit = self._repo[commit.parents[0]]
            parent_tree = parent_commit.tree
        else:
            parent_tree = None

        # Generate unified diff
        output = io.BytesIO()
        write_tree_diff(output, self._object_store, parent_tree, commit.tree)
        diff_text = output.getvalue().decode("utf-8", errors="replace")

        # Parse the diff
        file_changes = self._parse_unified_diff(diff_text)

        return CommitDiff(
            commit_sha=commit_sha,
            parent_sha=parent_sha,
            file_changes=file_changes,
        )

    def _parse_unified_diff(self, diff_text: str) -> list[FileChange]:
        """
        Parse a unified diff into FileChange objects with hunks.

        Args:
            diff_text: The unified diff as a string.

        Returns:
            List of FileChange objects with parsed hunks.
        """
        file_changes: list[FileChange] = []
        lines = diff_text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for diff header
            match = self.DIFF_HEADER_RE.match(line)
            if match:
                old_path, new_path = match.groups()
                fc = self._parse_single_file_diff(lines, i, old_path, new_path)
                if fc:
                    file_changes.append(fc)
                    # Skip to end of this file's diff
                    i += 1
                    while i < len(lines) and not self.DIFF_HEADER_RE.match(lines[i]):
                        i += 1
                    continue

            i += 1

        return file_changes

    def _parse_single_file_diff(
        self, lines: list[str], start_idx: int, old_path: str, new_path: str
    ) -> Optional[FileChange]:
        """Parse a single file's diff section."""
        from git_sim.core.models import ChangeType

        hunks: list[DiffHunk] = []
        change_type = ChangeType.MODIFY
        old_sha = None
        new_sha = None
        additions = 0
        deletions = 0

        i = start_idx + 1  # Skip the "diff --git" line

        while i < len(lines):
            line = lines[i]

            # Check for next file's diff
            if self.DIFF_HEADER_RE.match(line):
                break

            # Parse index line
            idx_match = self.INDEX_RE.match(line)
            if idx_match:
                old_sha, new_sha = idx_match.groups()
                i += 1
                continue

            # Detect change type from special lines
            if line.startswith("new file"):
                change_type = ChangeType.ADD
                i += 1
                continue
            elif line.startswith("deleted file"):
                change_type = ChangeType.DELETE
                i += 1
                continue
            elif line.startswith("rename from"):
                change_type = ChangeType.RENAME
                i += 1
                continue

            # Parse hunk header
            hunk_match = self.HUNK_HEADER_RE.match(line)
            if hunk_match:
                hunk, hunk_additions, hunk_deletions, end_i = self._parse_hunk(
                    lines, i, hunk_match
                )
                hunks.append(hunk)
                additions += hunk_additions
                deletions += hunk_deletions
                i = end_i
                continue

            i += 1

        # Determine old_path for renames
        old_path_result = old_path if change_type == ChangeType.RENAME else None

        return FileChange(
            path=new_path,
            change_type=change_type,
            old_path=old_path_result,
            old_sha=old_sha,
            new_sha=new_sha,
            additions=additions,
            deletions=deletions,
            hunks=hunks,
        )

    def _parse_hunk(
        self, lines: list[str], start_idx: int, header_match: re.Match
    ) -> tuple[DiffHunk, int, int, int]:
        """
        Parse a single hunk from the diff.

        Returns:
            Tuple of (DiffHunk, additions, deletions, end_index)
        """
        old_start = int(header_match.group(1))
        old_count = int(header_match.group(2) or 1)
        new_start = int(header_match.group(3))
        new_count = int(header_match.group(4) or 1)
        header = header_match.group(5).strip()

        hunk_lines: list[str] = []
        additions = 0
        deletions = 0

        i = start_idx + 1  # Skip the @@ line

        while i < len(lines):
            line = lines[i]

            # End of hunk conditions
            if not line:
                i += 1
                continue
            if line.startswith("diff --git"):
                break
            if self.HUNK_HEADER_RE.match(line):
                break

            # Context and change lines
            if line.startswith("+"):
                hunk_lines.append(line)
                additions += 1
            elif line.startswith("-"):
                hunk_lines.append(line)
                deletions += 1
            elif line.startswith(" "):
                hunk_lines.append(line)
            elif line.startswith("\\"):
                # "\ No newline at end of file"
                hunk_lines.append(line)
            else:
                # Unknown line type, might be end of hunk
                break

            i += 1

        hunk = DiffHunk(
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            lines=hunk_lines,
            header=header,
        )

        return hunk, additions, deletions, i

    def compute_patch_id(self, commit_sha: str) -> str:
        """
        Compute a patch-id for a commit for duplicate detection.

        The patch-id is computed by normalizing the diff:
        - Stripping line numbers from hunk headers
        - Normalizing whitespace
        - Hashing the result

        Args:
            commit_sha: SHA of the commit.

        Returns:
            Hex string of the patch-id hash.
        """
        commit = self._repo[commit_sha.encode()]
        if not isinstance(commit, Commit):
            return ""

        if not commit.parents:
            # Root commits get a unique patch-id based on their content
            return hashlib.sha1(commit_sha.encode()).hexdigest()

        parent_tree = self._repo[commit.parents[0]].tree

        # Generate diff
        output = io.BytesIO()
        write_tree_diff(output, self._object_store, parent_tree, commit.tree)
        diff_bytes = output.getvalue()

        # Normalize the diff for patch-id computation
        normalized = self._normalize_for_patch_id(diff_bytes)

        return hashlib.sha1(normalized).hexdigest()

    def _normalize_for_patch_id(self, diff_bytes: bytes) -> bytes:
        """
        Normalize a diff for patch-id computation.

        This mimics git's patch-id behavior:
        - Removes index lines
        - Strips hunk line numbers
        - Normalizes whitespace
        """
        lines = diff_bytes.split(b"\n")
        normalized_lines: list[bytes] = []

        for line in lines:
            # Skip index lines
            if line.startswith(b"index "):
                continue

            # Skip diff --git lines (path can vary)
            if line.startswith(b"diff --git"):
                continue

            # Normalize hunk headers - strip line numbers
            if line.startswith(b"@@"):
                normalized_lines.append(b"@@")
                continue

            # Skip empty lines
            if not line.strip():
                continue

            # Keep content lines, normalize leading whitespace
            if line.startswith((b"+", b"-", b" ")):
                # Strip trailing whitespace but keep the prefix
                normalized_lines.append(line.rstrip())
            else:
                normalized_lines.append(line.rstrip())

        return b"\n".join(normalized_lines)

    def get_file_lines(self, tree_sha: str, path: str) -> Optional[list[str]]:
        """
        Get the lines of a file at a specific tree.

        Args:
            tree_sha: SHA of the tree.
            path: Path to the file.

        Returns:
            List of lines, or None if file doesn't exist.
        """
        from dulwich.objects import Tree

        tree = self._repo[tree_sha.encode()]
        if not isinstance(tree, Tree):
            return None

        parts = path.split("/")
        current = tree

        for i, part in enumerate(parts):
            part_bytes = part.encode()
            found = False

            for entry in current.items():
                if entry.path == part_bytes:
                    obj = self._repo[entry.sha]
                    if i == len(parts) - 1:
                        # Last part - should be a blob
                        if isinstance(obj, Blob):
                            content = obj.data.decode("utf-8", errors="replace")
                            return content.splitlines(keepends=True)
                        return None
                    elif isinstance(obj, Tree):
                        current = obj
                        found = True
                        break

            if not found and i < len(parts) - 1:
                return None

        return None

    def collect_patch_ids(
        self, repo_wrapper: "Repository", include: list[str], exclude: list[str]
    ) -> set[str]:
        """
        Collect patch-ids for commits in a range.

        Args:
            repo_wrapper: Repository wrapper for commit walking.
            include: Refs to start from.
            exclude: Refs to stop at.

        Returns:
            Set of patch-id hashes.
        """
        patch_ids: set[str] = set()

        for commit in repo_wrapper.walk_commits(include, exclude):
            patch_id = self.compute_patch_id(commit.sha)
            if patch_id:
                patch_ids.add(patch_id)

        return patch_ids


# Type hint for circular import
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from git_sim.core.repository import Repository
