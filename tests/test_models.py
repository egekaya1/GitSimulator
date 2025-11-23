"""Tests for data models."""

import pytest

from git_sim.core.models import (
    ChangeType,
    CommitGraph,
    CommitInfo,
    ConflictSeverity,
    DiffHunk,
    FileChange,
    PotentialConflict,
    RebaseSimulation,
    RebaseStep,
)


class TestCommitInfo:
    """Tests for CommitInfo dataclass."""

    def test_short_sha(self):
        commit = CommitInfo(
            sha="abc1234567890def",
            message="Test commit",
            author="Test Author",
            author_email="test@example.com",
            timestamp=1234567890,
            parent_shas=(),
            tree_sha="tree123",
        )
        assert commit.short_sha == "abc1234"

    def test_is_merge_false(self):
        commit = CommitInfo(
            sha="abc123",
            message="Regular commit",
            author="Test",
            author_email="test@example.com",
            timestamp=1234567890,
            parent_shas=("parent1",),
            tree_sha="tree123",
        )
        assert commit.is_merge is False

    def test_is_merge_true(self):
        commit = CommitInfo(
            sha="abc123",
            message="Merge commit",
            author="Test",
            author_email="test@example.com",
            timestamp=1234567890,
            parent_shas=("parent1", "parent2"),
            tree_sha="tree123",
        )
        assert commit.is_merge is True

    def test_first_line(self):
        commit = CommitInfo(
            sha="abc123",
            message="First line\n\nMore details here",
            author="Test",
            author_email="test@example.com",
            timestamp=1234567890,
            parent_shas=(),
            tree_sha="tree123",
        )
        assert commit.first_line == "First line"

    def test_first_line_single_line(self):
        commit = CommitInfo(
            sha="abc123",
            message="Single line message",
            author="Test",
            author_email="test@example.com",
            timestamp=1234567890,
            parent_shas=(),
            tree_sha="tree123",
        )
        assert commit.first_line == "Single line message"


class TestDiffHunk:
    """Tests for DiffHunk dataclass."""

    def test_old_range(self):
        hunk = DiffHunk(old_start=10, old_count=5, new_start=12, new_count=7)
        assert hunk.old_range == (10, 15)

    def test_new_range(self):
        hunk = DiffHunk(old_start=10, old_count=5, new_start=12, new_count=7)
        assert hunk.new_range == (12, 19)


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_is_binary_false(self):
        fc = FileChange(
            path="test.txt",
            change_type=ChangeType.MODIFY,
            hunks=[DiffHunk(old_start=1, old_count=1, new_start=1, new_count=1)],
        )
        assert fc.is_binary is False

    def test_is_binary_true(self):
        fc = FileChange(
            path="image.png",
            change_type=ChangeType.MODIFY,
            hunks=[],
        )
        assert fc.is_binary is True

    def test_is_binary_add_no_hunks(self):
        # Add without hunks is not considered binary
        fc = FileChange(
            path="new.txt",
            change_type=ChangeType.ADD,
            hunks=[],
        )
        assert fc.is_binary is False


class TestPotentialConflict:
    """Tests for PotentialConflict dataclass."""

    def test_is_certain_true(self):
        conflict = PotentialConflict(
            path="test.txt",
            severity=ConflictSeverity.CERTAIN,
            description="Test conflict",
        )
        assert conflict.is_certain is True

    def test_is_certain_false(self):
        conflict = PotentialConflict(
            path="test.txt",
            severity=ConflictSeverity.LIKELY,
            description="Test conflict",
        )
        assert conflict.is_certain is False


class TestRebaseStep:
    """Tests for RebaseStep dataclass."""

    def test_has_conflicts_true(self):
        step = RebaseStep(
            original_sha="abc123",
            commit_info=CommitInfo(
                sha="abc123",
                message="Test",
                author="Test",
                author_email="test@example.com",
                timestamp=1234567890,
                parent_shas=(),
                tree_sha="tree",
            ),
            conflicts=[
                PotentialConflict(
                    path="test.txt",
                    severity=ConflictSeverity.CERTAIN,
                    description="Conflict",
                )
            ],
        )
        assert step.has_conflicts is True

    def test_has_conflicts_false(self):
        step = RebaseStep(
            original_sha="abc123",
            commit_info=CommitInfo(
                sha="abc123",
                message="Test",
                author="Test",
                author_email="test@example.com",
                timestamp=1234567890,
                parent_shas=(),
                tree_sha="tree",
            ),
        )
        assert step.has_conflicts is False


class TestCommitGraph:
    """Tests for CommitGraph dataclass."""

    def test_add_commit(self):
        graph = CommitGraph()
        commit = CommitInfo(
            sha="abc123",
            message="Test",
            author="Test",
            author_email="test@example.com",
            timestamp=1234567890,
            parent_shas=("parent1",),
            tree_sha="tree",
        )
        graph.add_commit(commit)

        assert "abc123" in graph.commits
        assert ("abc123", "parent1") in graph.edges

    def test_get_ancestors(self):
        graph = CommitGraph()

        # Build a simple chain: c3 -> c2 -> c1
        c1 = CommitInfo(
            sha="c1", message="C1", author="", author_email="",
            timestamp=1, parent_shas=(), tree_sha="",
        )
        c2 = CommitInfo(
            sha="c2", message="C2", author="", author_email="",
            timestamp=2, parent_shas=("c1",), tree_sha="",
        )
        c3 = CommitInfo(
            sha="c3", message="C3", author="", author_email="",
            timestamp=3, parent_shas=("c2",), tree_sha="",
        )

        graph.add_commit(c1)
        graph.add_commit(c2)
        graph.add_commit(c3)

        ancestors = graph.get_ancestors("c3")
        assert ancestors == ["c3", "c2", "c1"]


class TestRebaseSimulation:
    """Tests for RebaseSimulation dataclass."""

    def test_has_conflicts_true(self):
        conflict = PotentialConflict(
            path="test.txt",
            severity=ConflictSeverity.CERTAIN,
            description="Conflict",
        )
        step = RebaseStep(
            original_sha="abc123",
            commit_info=CommitInfo(
                sha="abc123", message="Test", author="", author_email="",
                timestamp=1, parent_shas=(), tree_sha="",
            ),
            conflicts=[conflict],
        )
        sim = RebaseSimulation(
            source_branch="feature",
            target_branch="main",
            onto_sha="main123",
            merge_base_sha="base123",
            steps=[step],
        )
        assert sim.has_conflicts is True
        assert sim.conflict_count == 1

    def test_has_conflicts_false(self):
        step = RebaseStep(
            original_sha="abc123",
            commit_info=CommitInfo(
                sha="abc123", message="Test", author="", author_email="",
                timestamp=1, parent_shas=(), tree_sha="",
            ),
        )
        sim = RebaseSimulation(
            source_branch="feature",
            target_branch="main",
            onto_sha="main123",
            merge_base_sha="base123",
            steps=[step],
        )
        assert sim.has_conflicts is False
        assert sim.conflict_count == 0

    def test_commits_to_replay(self):
        c1 = CommitInfo(
            sha="c1", message="C1", author="", author_email="",
            timestamp=1, parent_shas=(), tree_sha="",
        )
        c2 = CommitInfo(
            sha="c2", message="C2", author="", author_email="",
            timestamp=2, parent_shas=(), tree_sha="",
        )

        steps = [
            RebaseStep(original_sha="c1", commit_info=c1, action="pick"),
            RebaseStep(original_sha="c2", commit_info=c2, action="drop"),
        ]

        sim = RebaseSimulation(
            source_branch="feature",
            target_branch="main",
            onto_sha="main123",
            merge_base_sha="base123",
            steps=steps,
        )

        # Only c1 should be in commits_to_replay (c2 is dropped)
        assert len(sim.commits_to_replay) == 1
        assert sim.commits_to_replay[0].sha == "c1"

    def test_skipped_commits(self):
        c1 = CommitInfo(
            sha="c1", message="C1", author="", author_email="",
            timestamp=1, parent_shas=(), tree_sha="",
        )
        c2 = CommitInfo(
            sha="c2", message="C2", author="", author_email="",
            timestamp=2, parent_shas=(), tree_sha="",
        )

        steps = [
            RebaseStep(original_sha="c1", commit_info=c1, will_be_skipped=True),
            RebaseStep(original_sha="c2", commit_info=c2, will_be_skipped=False),
        ]

        sim = RebaseSimulation(
            source_branch="feature",
            target_branch="main",
            onto_sha="main123",
            merge_base_sha="base123",
            steps=steps,
        )

        assert len(sim.skipped_commits) == 1
        assert sim.skipped_commits[0].sha == "c1"
