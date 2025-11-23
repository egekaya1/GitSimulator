"""Repository wrapper providing a clean read-only API over Dulwich."""

from pathlib import Path
from typing import Iterator, Optional

from dulwich.diff_tree import TreeChange, tree_changes
from dulwich.objects import Commit, Tree
from dulwich.repo import Repo
from dulwich.walk import Walker

from git_sim.core.exceptions import NotARepositoryError, RefNotFoundError
from git_sim.core.models import BranchInfo, ChangeType, CommitGraph, CommitInfo, FileChange


class Repository:
    """
    High-level wrapper around Dulwich providing a clean read-only API.

    This class provides all the repository access methods needed for
    simulation without modifying the repository.
    """

    def __init__(self, path: str | Path = "."):
        """
        Initialize repository wrapper.

        Args:
            path: Path to the Git repository (or any subdirectory).

        Raises:
            NotARepositoryError: If path is not within a Git repository.
        """
        self.path = Path(path).resolve()
        try:
            self._repo = Repo(str(self.path))
        except Exception as e:
            raise NotARepositoryError(f"Not a Git repository: {self.path}") from e

    @property
    def head_sha(self) -> str:
        """Get the SHA of HEAD."""
        return self._repo.head().decode()

    @property
    def head_branch(self) -> Optional[str]:
        """Get the name of the current branch, or None if detached HEAD."""
        try:
            ref = self._repo.refs.read_ref(b"HEAD")
            if ref and ref.startswith(b"ref: refs/heads/"):
                return ref[16:].decode()
        except Exception:
            pass
        return None

    def _resolve_ref(self, ref_or_sha: str) -> bytes:
        """
        Resolve a reference (branch name, tag, or SHA) to a commit SHA.

        Args:
            ref_or_sha: Branch name, tag name, or commit SHA.

        Returns:
            The resolved SHA as bytes.

        Raises:
            RefNotFoundError: If the reference cannot be resolved.
        """
        ref_bytes = ref_or_sha.encode() if isinstance(ref_or_sha, str) else ref_or_sha

        # Try as a direct SHA first
        if len(ref_or_sha) == 40:
            try:
                obj = self._repo[ref_bytes]
                if isinstance(obj, Commit):
                    return ref_bytes
            except KeyError:
                pass

        # Try as refs/heads/<branch>
        try:
            sha = self._repo.refs[b"refs/heads/" + ref_bytes]
            return sha
        except KeyError:
            pass

        # Try as refs/tags/<tag>
        try:
            sha = self._repo.refs[b"refs/tags/" + ref_bytes]
            return sha
        except KeyError:
            pass

        # Try as refs/remotes/<remote>
        try:
            sha = self._repo.refs[b"refs/remotes/" + ref_bytes]
            return sha
        except KeyError:
            pass

        # Try HEAD special case
        if ref_or_sha.upper() == "HEAD":
            return self._repo.head()

        # Try relative refs like HEAD~1, HEAD^2
        if ref_or_sha.startswith("HEAD"):
            return self._resolve_relative_ref(ref_or_sha)

        raise RefNotFoundError(ref_or_sha)

    def _resolve_relative_ref(self, ref: str) -> bytes:
        """Resolve relative references like HEAD~2 or HEAD^."""
        current = self._repo.head()

        i = 4  # Skip "HEAD"
        while i < len(ref):
            commit = self._repo[current]
            if not isinstance(commit, Commit):
                raise RefNotFoundError(ref)

            if ref[i] == "~":
                # ~N means N-th first parent
                i += 1
                n = 0
                while i < len(ref) and ref[i].isdigit():
                    n = n * 10 + int(ref[i])
                    i += 1
                n = n or 1
                for _ in range(n):
                    if not commit.parents:
                        raise RefNotFoundError(ref)
                    current = commit.parents[0]
                    commit = self._repo[current]
            elif ref[i] == "^":
                # ^N means N-th parent
                i += 1
                n = 0
                while i < len(ref) and ref[i].isdigit():
                    n = n * 10 + int(ref[i])
                    i += 1
                n = n or 1
                if n > len(commit.parents):
                    raise RefNotFoundError(ref)
                current = commit.parents[n - 1] if commit.parents else current
            else:
                raise RefNotFoundError(ref)

        return current

    def _commit_to_info(self, commit: Commit) -> CommitInfo:
        """Convert a Dulwich Commit to CommitInfo."""
        author = commit.author.decode("utf-8", errors="replace")
        # Parse author to extract email
        email = ""
        if "<" in author and ">" in author:
            start = author.index("<") + 1
            end = author.index(">")
            email = author[start:end]
            author = author[: start - 1].strip()

        return CommitInfo(
            sha=commit.id.decode() if isinstance(commit.id, bytes) else str(commit.id),
            message=commit.message.decode("utf-8", errors="replace"),
            author=author,
            author_email=email,
            timestamp=commit.commit_time,
            parent_shas=tuple(
                p.decode() if isinstance(p, bytes) else str(p) for p in commit.parents
            ),
            tree_sha=(
                commit.tree.decode() if isinstance(commit.tree, bytes) else str(commit.tree)
            ),
        )

    def get_commit(self, ref_or_sha: str) -> CommitInfo:
        """
        Get commit information by ref name or SHA.

        Args:
            ref_or_sha: Branch name, tag name, or commit SHA.

        Returns:
            CommitInfo for the specified commit.

        Raises:
            RefNotFoundError: If the reference cannot be found.
        """
        sha = self._resolve_ref(ref_or_sha)
        commit = self._repo[sha]
        if not isinstance(commit, Commit):
            raise RefNotFoundError(ref_or_sha)
        return self._commit_to_info(commit)

    def walk_commits(
        self,
        include: list[str],
        exclude: Optional[list[str]] = None,
        order: str = "topo",
        max_entries: Optional[int] = None,
    ) -> Iterator[CommitInfo]:
        """
        Walk commits from include refs, stopping at exclude refs.

        Args:
            include: List of refs to start from.
            exclude: List of refs to stop at (exclusive).
            order: Sort order - 'topo' for topological, 'date' for date order.
            max_entries: Maximum number of commits to return.

        Yields:
            CommitInfo for each commit in the walk.
        """
        include_shas = [self._resolve_ref(r) for r in include]
        exclude_shas = [self._resolve_ref(r) for r in (exclude or [])]

        walker = Walker(
            self._repo.object_store,
            include=include_shas,
            exclude=exclude_shas,
            order=order,  # type: ignore
            max_entries=max_entries,
        )

        for entry in walker:
            yield self._commit_to_info(entry.commit)

    def get_branches(self, include_remote: bool = False) -> list[BranchInfo]:
        """
        Get list of all branches.

        Args:
            include_remote: If True, include remote-tracking branches.

        Returns:
            List of BranchInfo objects.
        """
        branches = []

        for ref_name, sha in self._repo.refs.items():
            ref_str = ref_name.decode() if isinstance(ref_name, bytes) else ref_name
            sha_str = sha.decode() if isinstance(sha, bytes) else str(sha)

            if ref_str.startswith("refs/heads/"):
                name = ref_str[11:]  # Remove "refs/heads/"
                branches.append(BranchInfo(name=name, head_sha=sha_str, is_remote=False))
            elif include_remote and ref_str.startswith("refs/remotes/"):
                name = ref_str[13:]  # Remove "refs/remotes/"
                branches.append(BranchInfo(name=name, head_sha=sha_str, is_remote=True))

        return branches

    def find_merge_base(self, ref1: str, ref2: str) -> Optional[str]:
        """
        Find the merge base (common ancestor) between two refs.

        Args:
            ref1: First reference.
            ref2: Second reference.

        Returns:
            SHA of the merge base, or None if no common ancestor exists.
        """
        sha1 = self._resolve_ref(ref1)
        sha2 = self._resolve_ref(ref2)

        # Collect ancestors of sha1
        ancestors1: set[bytes] = set()
        stack = [sha1]
        while stack:
            current = stack.pop()
            if current in ancestors1:
                continue
            ancestors1.add(current)
            try:
                commit = self._repo[current]
                if isinstance(commit, Commit):
                    stack.extend(commit.parents)
            except KeyError:
                pass

        # Walk sha2's ancestors to find first common one
        stack = [sha2]
        visited: set[bytes] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            if current in ancestors1:
                return current.decode()

            try:
                commit = self._repo[current]
                if isinstance(commit, Commit):
                    stack.extend(commit.parents)
            except KeyError:
                pass

        return None

    def _tree_change_to_file_change(self, change: TreeChange) -> FileChange:
        """Convert a Dulwich TreeChange to FileChange."""
        if change.type == "add":
            return FileChange(
                path=change.new.path.decode(),
                change_type=ChangeType.ADD,
                new_mode=change.new.mode,
                new_sha=change.new.sha.decode() if change.new.sha else None,
            )
        elif change.type == "delete":
            return FileChange(
                path=change.old.path.decode(),
                change_type=ChangeType.DELETE,
                old_mode=change.old.mode,
                old_sha=change.old.sha.decode() if change.old.sha else None,
            )
        elif change.type == "modify":
            return FileChange(
                path=change.new.path.decode(),
                change_type=ChangeType.MODIFY,
                old_mode=change.old.mode,
                new_mode=change.new.mode,
                old_sha=change.old.sha.decode() if change.old.sha else None,
                new_sha=change.new.sha.decode() if change.new.sha else None,
            )
        elif change.type == "rename":
            return FileChange(
                path=change.new.path.decode(),
                change_type=ChangeType.RENAME,
                old_path=change.old.path.decode(),
                old_mode=change.old.mode,
                new_mode=change.new.mode,
                old_sha=change.old.sha.decode() if change.old.sha else None,
                new_sha=change.new.sha.decode() if change.new.sha else None,
            )
        else:  # copy
            return FileChange(
                path=change.new.path.decode(),
                change_type=ChangeType.COPY,
                old_path=change.old.path.decode() if change.old else None,
                new_mode=change.new.mode,
                new_sha=change.new.sha.decode() if change.new.sha else None,
            )

    def get_tree_changes(self, old_tree_sha: str, new_tree_sha: str) -> list[FileChange]:
        """
        Get list of changes between two trees.

        Args:
            old_tree_sha: SHA of the old tree (or empty string for empty tree).
            new_tree_sha: SHA of the new tree.

        Returns:
            List of FileChange objects.
        """
        old_sha = old_tree_sha.encode() if old_tree_sha else None
        new_sha = new_tree_sha.encode()

        changes = tree_changes(
            self._repo.object_store,
            old_sha,
            new_sha,
        )

        return [self._tree_change_to_file_change(c) for c in changes]

    def get_commit_changes(self, commit_sha: str) -> list[FileChange]:
        """
        Get the file changes introduced by a commit.

        Args:
            commit_sha: SHA of the commit.

        Returns:
            List of FileChange objects.
        """
        commit = self.get_commit(commit_sha)

        if not commit.parent_shas:
            # Root commit - compare against empty tree
            return self.get_tree_changes("", commit.tree_sha)

        # Compare against first parent
        parent = self.get_commit(commit.parent_shas[0])
        return self.get_tree_changes(parent.tree_sha, commit.tree_sha)

    def get_file_content(self, tree_sha: str, path: str) -> Optional[bytes]:
        """
        Get the content of a file at a specific tree.

        Args:
            tree_sha: SHA of the tree.
            path: Path to the file within the tree.

        Returns:
            File content as bytes, or None if file doesn't exist.
        """
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
                        return obj.data if hasattr(obj, "data") else None
                    elif isinstance(obj, Tree):
                        current = obj
                        found = True
                        break
            if not found and i < len(parts) - 1:
                return None

        return None

    def build_graph(
        self,
        refs: list[str],
        max_commits: int = 50,
    ) -> CommitGraph:
        """
        Build a CommitGraph from the given refs.

        Args:
            refs: List of refs to include in the graph.
            max_commits: Maximum number of commits to include.

        Returns:
            CommitGraph containing commits reachable from refs.
        """
        graph = CommitGraph()
        graph.head_sha = self.head_sha
        graph.head_branch = self.head_branch

        # Add branch tips
        for ref in refs:
            try:
                commit = self.get_commit(ref)
                graph.branch_tips[ref] = commit.sha
            except RefNotFoundError:
                pass

        # Walk commits from all refs
        seen: set[str] = set()
        for commit in self.walk_commits(refs, max_entries=max_commits):
            if commit.sha not in seen:
                seen.add(commit.sha)
                graph.add_commit(commit)

        return graph
