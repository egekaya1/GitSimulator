"""Repository wrapper providing a clean read-only API over Dulwich."""

from collections.abc import Iterable, Iterator
from pathlib import Path

from dulwich.diff_tree import TreeChange, tree_changes
from dulwich.objects import Commit, Tree, TreeEntry
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
        # Use absolute path without resolving symlinks to keep test path equality stable
        self.path = Path(path).absolute()
        try:
            self._repo: Repo = Repo(str(self.path))
        except Exception as e:
            raise NotARepositoryError(f"Not a Git repository: {self.path}") from e

    @property
    def head_sha(self) -> str:
        """Get the SHA of HEAD."""
        try:
            return self._repo.head().decode()
        except (KeyError, ValueError) as e:
            raise NotARepositoryError("Repository has no commits yet") from e

    @property
    def head_branch(self) -> str | None:
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
            ref_or_sha: Branch name, tag name, or commit SHA (full or short).

        Returns:
            The resolved SHA as bytes.

        Raises:
            RefNotFoundError: If the reference cannot be resolved.
        """
        ref_bytes = ref_or_sha.encode() if isinstance(ref_or_sha, str) else ref_or_sha

        # Try as a direct SHA first (full 40-char SHA)
        if len(ref_or_sha) == 40:
            try:
                obj = self._repo[ref_bytes]
                if isinstance(obj, Commit):
                    return ref_bytes
            except KeyError:
                pass

        # Try as a short SHA (7+ characters)
        if len(ref_or_sha) >= 7 and all(c in "0123456789abcdef" for c in ref_or_sha.lower()):
            prefix = ref_or_sha.lower()
            matches = []
            for sha in self._repo.object_store:
                sha_str = sha.decode() if isinstance(sha, bytes) else str(sha)
                if sha_str.startswith(prefix):
                    try:
                        obj = self._repo[sha]
                        if isinstance(obj, Commit):
                            matches.append(sha)
                    except (KeyError, AttributeError):
                        continue

            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                raise RefNotFoundError(f"{ref_or_sha} is ambiguous ({len(matches)} matches)")
            # If no matches, continue trying other resolution methods

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
            obj = self._repo[current]
            if not isinstance(obj, Commit):
                raise RefNotFoundError(ref)
            commit: Commit = obj

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
                    parent_obj = self._repo[current]
                    if not isinstance(parent_obj, Commit):
                        raise RefNotFoundError(ref)
                    commit = parent_obj
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
            tree_sha=(commit.tree.decode() if isinstance(commit.tree, bytes) else str(commit.tree)),
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
        exclude: list[str] | None = None,
        order: str = "topo",
        max_entries: int | None = None,
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

        walker: Walker = Walker(
            self._repo.object_store,
            include=include_shas,
            exclude=exclude_shas,
            order=order,
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

        # Dulwich refs container does not expose items(); iterate over keys directly
        for ref_name in self._repo.refs:
            sha = self._repo.refs[ref_name]
            ref_str = ref_name.decode() if isinstance(ref_name, bytes) else ref_name
            sha_str = sha.decode() if isinstance(sha, bytes) else str(sha)

            if ref_str.startswith("refs/heads/"):
                name = ref_str[11:]  # Remove "refs/heads/"
                branches.append(BranchInfo(name=name, head_sha=sha_str, is_remote=False))
            elif include_remote and ref_str.startswith("refs/remotes/"):
                name = ref_str[13:]  # Remove "refs/remotes/"
                branches.append(BranchInfo(name=name, head_sha=sha_str, is_remote=True))

        return branches

    def find_merge_base(self, ref1: str, ref2: str) -> str | None:
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
        old_entry = change.old
        new_entry = change.new
        # Safely access entry attributes (TreeChange entries may be optional in type hints)
        if change.type == "add":
            path = new_entry.path.decode() if new_entry and new_entry.path else ""
            return FileChange(
                path=path,
                change_type=ChangeType.ADD,
                new_mode=new_entry.mode if new_entry else None,
                new_sha=new_entry.sha.decode() if new_entry and new_entry.sha else None,
            )
        if change.type == "delete":
            path = old_entry.path.decode() if old_entry and old_entry.path else ""
            return FileChange(
                path=path,
                change_type=ChangeType.DELETE,
                old_mode=old_entry.mode if old_entry else None,
                old_sha=old_entry.sha.decode() if old_entry and old_entry.sha else None,
            )
        if change.type == "modify":
            path = new_entry.path.decode() if new_entry and new_entry.path else ""
            return FileChange(
                path=path,
                change_type=ChangeType.MODIFY,
                old_mode=old_entry.mode if old_entry else None,
                new_mode=new_entry.mode if new_entry else None,
                old_sha=old_entry.sha.decode() if old_entry and old_entry.sha else None,
                new_sha=new_entry.sha.decode() if new_entry and new_entry.sha else None,
            )
        if change.type == "rename":
            path_new = new_entry.path.decode() if new_entry and new_entry.path else ""
            path_old = old_entry.path.decode() if old_entry and old_entry.path else ""
            return FileChange(
                path=path_new,
                change_type=ChangeType.RENAME,
                old_path=path_old,
                old_mode=old_entry.mode if old_entry else None,
                new_mode=new_entry.mode if new_entry else None,
                old_sha=old_entry.sha.decode() if old_entry and old_entry.sha else None,
                new_sha=new_entry.sha.decode() if new_entry and new_entry.sha else None,
            )
        # copy
        path = new_entry.path.decode() if new_entry and new_entry.path else ""
        return FileChange(
            path=path,
            change_type=ChangeType.COPY,
            old_path=old_entry.path.decode() if old_entry and old_entry.path else None,
            new_mode=new_entry.mode if new_entry else None,
            new_sha=new_entry.sha.decode() if new_entry and new_entry.sha else None,
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

        changes: Iterable[TreeChange] = tree_changes(
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

    def get_file_content(self, tree_sha: str, path: str) -> bytes | None:
        """
        Get the content of a file at a specific tree.

        Args:
            tree_sha: SHA of the tree.
            path: Path to the file within the tree.

        Returns:
            File content as bytes, or None if file doesn't exist.
        """
        tree_obj = self._repo[tree_sha.encode()]
        tree: Tree
        if isinstance(tree_obj, Tree):
            tree = tree_obj
        else:
            return None

        parts = path.split("/")
        current: Tree = tree

        for i, part in enumerate(parts):
            part_bytes = part.encode()
            found = False
            for entry in current.items():
                if entry is None:
                    continue
                if not isinstance(entry, TreeEntry):  # Narrow type for mypy
                    continue
                if entry.path == part_bytes:
                    obj = self._repo[entry.sha]
                    if i == len(parts) - 1:
                        # Last part - should be a blob
                        return obj.data if hasattr(obj, "data") else None
                    if isinstance(obj, Tree):
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
            refs: List of refs (branch names, tags, or SHAs) to include in the graph.
            max_commits: Maximum number of commits to include.

        Returns:
            CommitGraph containing commits reachable from refs.
        """
        graph = CommitGraph()
        graph.head_sha = self.head_sha
        graph.head_branch = self.head_branch

        # Add branch tips - map branch names to their SHAs
        branches = self.get_branches()
        for branch in branches:
            if branch.head_sha in refs or branch.name in refs:
                graph.branch_tips[branch.name] = branch.head_sha

        # Walk commits from all refs
        seen: set[str] = set()
        for commit in self.walk_commits(refs, max_entries=max_commits):
            if commit.sha not in seen:
                seen.add(commit.sha)
                graph.add_commit(commit)

        return graph
