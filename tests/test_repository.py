"""Tests for Repository wrapper."""

import subprocess
from pathlib import Path

import pytest

from git_sim.core.exceptions import NotARepositoryError, RefNotFoundError
from git_sim.core.models import ChangeType
from git_sim.core.repository import Repository


class TestRepositoryInit:
    """Tests for Repository initialization."""

    def test_init_valid_repo(self, git_repo: Path):
        repo = Repository(git_repo)
        assert repo.path == git_repo

    def test_init_not_a_repo(self, temp_dir: Path):
        with pytest.raises(NotARepositoryError):
            Repository(temp_dir)


class TestRepositoryProperties:
    """Tests for Repository properties."""

    def test_head_sha(self, repository: Repository):
        assert len(repository.head_sha) == 40
        assert all(c in "0123456789abcdef" for c in repository.head_sha)

    def test_head_branch(self, repository: Repository):
        # Default branch after git init is usually main or master
        assert repository.head_branch in ("main", "master")


class TestGetCommit:
    """Tests for get_commit method."""

    def test_get_commit_by_sha(self, repository: Repository):
        head_sha = repository.head_sha
        commit = repository.get_commit(head_sha)

        assert commit.sha == head_sha
        assert len(commit.message) > 0
        assert len(commit.author) > 0

    def test_get_commit_by_branch(self, repository: Repository):
        branch = repository.head_branch
        commit = repository.get_commit(branch)

        assert commit.sha == repository.head_sha

    def test_get_commit_by_head(self, repository: Repository):
        commit = repository.get_commit("HEAD")
        assert commit.sha == repository.head_sha

    def test_get_commit_relative_ref(self, repository: Repository):
        head_commit = repository.get_commit("HEAD")
        parent_commit = repository.get_commit("HEAD~1")

        assert parent_commit.sha in head_commit.parent_shas

    def test_get_commit_not_found(self, repository: Repository):
        with pytest.raises(RefNotFoundError):
            repository.get_commit("nonexistent-branch")


class TestWalkCommits:
    """Tests for walk_commits method."""

    def test_walk_commits_from_head(self, repository: Repository):
        commits = list(repository.walk_commits(["HEAD"]))

        assert len(commits) == 3  # Initial, add A, add B
        assert commits[0].sha == repository.head_sha

    def test_walk_commits_with_limit(self, repository: Repository):
        commits = list(repository.walk_commits(["HEAD"], max_entries=2))

        assert len(commits) == 2

    def test_walk_commits_with_exclude(self, repository: Repository):
        # Exclude the initial commit
        all_commits = list(repository.walk_commits(["HEAD"]))
        initial_sha = all_commits[-1].sha

        commits = list(repository.walk_commits(["HEAD"], exclude=[initial_sha]))

        # Should have 2 commits (excluding initial)
        assert len(commits) == 2
        assert all(c.sha != initial_sha for c in commits)


class TestGetBranches:
    """Tests for get_branches method."""

    def test_get_branches_local(self, repository: Repository):
        branches = repository.get_branches()

        assert len(branches) >= 1
        branch_names = [b.name for b in branches]
        assert repository.head_branch in branch_names

    def test_get_branches_with_remote(self, branched_repository: Repository):
        branches = branched_repository.get_branches()

        branch_names = [b.name for b in branches]
        assert "main" in branch_names or "master" in branch_names
        assert "feature" in branch_names


class TestFindMergeBase:
    """Tests for find_merge_base method."""

    def test_find_merge_base(self, branched_repository: Repository):
        merge_base = branched_repository.find_merge_base("main", "feature")

        assert merge_base is not None
        assert len(merge_base) == 40

    def test_find_merge_base_same_branch(self, repository: Repository):
        merge_base = repository.find_merge_base("HEAD", "HEAD~1")

        # Merge base of HEAD and HEAD~1 is HEAD~1
        parent_commit = repository.get_commit("HEAD~1")
        assert merge_base == parent_commit.sha


class TestGetTreeChanges:
    """Tests for get_tree_changes and get_commit_changes methods."""

    def test_get_commit_changes(self, repository: Repository):
        # Get changes for the "Add file B" commit
        changes = repository.get_commit_changes(repository.head_sha)

        assert len(changes) == 1
        assert changes[0].path == "file_b.txt"
        assert changes[0].change_type == ChangeType.ADD

    def test_get_commit_changes_modify(self, branched_repository: Repository):
        # Switch to feature branch and get changes
        subprocess.run(
            ["git", "checkout", "feature"],
            cwd=branched_repository.path,
            capture_output=True,
            check=True,
        )

        # Reload repo
        repo = Repository(branched_repository.path)

        # Get the "Modify file A" commit (one before HEAD on feature)
        commits = list(repo.walk_commits(["HEAD"], max_entries=2))
        modify_commit = commits[1]  # Second most recent

        changes = repo.get_commit_changes(modify_commit.sha)

        # Should have a modification to file_a.txt
        modify_changes = [c for c in changes if c.change_type == ChangeType.MODIFY]
        assert len(modify_changes) == 1
        assert modify_changes[0].path == "file_a.txt"


class TestBuildGraph:
    """Tests for build_graph method."""

    def test_build_graph(self, repository: Repository):
        graph = repository.build_graph(["HEAD"])

        assert len(graph.commits) == 3
        assert graph.head_sha == repository.head_sha

    def test_build_graph_with_branches(self, branched_repository: Repository):
        graph = branched_repository.build_graph(["main", "feature"])

        # Should have commits from both branches
        assert len(graph.commits) >= 4  # At least: initial, add A, add B, and divergent commits

        # Check branch tips are recorded
        assert "main" in graph.branch_tips or "master" in graph.branch_tips


class TestGetFileContent:
    """Tests for get_file_content method."""

    def test_get_file_content(self, repository: Repository):
        commit = repository.get_commit("HEAD")
        content = repository.get_file_content(commit.tree_sha, "file_b.txt")

        assert content is not None
        assert b"Content B" in content

    def test_get_file_content_not_found(self, repository: Repository):
        commit = repository.get_commit("HEAD")
        content = repository.get_file_content(commit.tree_sha, "nonexistent.txt")

        assert content is None
