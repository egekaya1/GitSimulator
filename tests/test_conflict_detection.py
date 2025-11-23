"""Tests for conflict detection."""

import pytest

from git_sim.core.models import ChangeType, ConflictSeverity, DiffHunk, FileChange
from git_sim.simulation.conflict_detector import ConflictDetector


class TestConflictDetector:
    """Tests for ConflictDetector."""

    @pytest.fixture
    def detector(self):
        return ConflictDetector()

    def test_no_conflict_disjoint_files(self, detector: ConflictDetector):
        our_changes = [FileChange(path="file_a.txt", change_type=ChangeType.MODIFY)]
        their_changes = [FileChange(path="file_b.txt", change_type=ChangeType.MODIFY)]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 0

    def test_no_conflict_both_delete(self, detector: ConflictDetector):
        our_changes = [FileChange(path="file.txt", change_type=ChangeType.DELETE)]
        their_changes = [FileChange(path="file.txt", change_type=ChangeType.DELETE)]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 0

    def test_conflict_both_add_different_content(self, detector: ConflictDetector):
        our_changes = [
            FileChange(
                path="new_file.txt",
                change_type=ChangeType.ADD,
                new_sha="abc123",
            )
        ]
        their_changes = [
            FileChange(
                path="new_file.txt",
                change_type=ChangeType.ADD,
                new_sha="def456",  # Different content
            )
        ]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.CERTAIN
        assert "add" in conflicts[0].description.lower()

    def test_no_conflict_both_add_same_content(self, detector: ConflictDetector):
        our_changes = [
            FileChange(
                path="new_file.txt",
                change_type=ChangeType.ADD,
                new_sha="abc123",
            )
        ]
        their_changes = [
            FileChange(
                path="new_file.txt",
                change_type=ChangeType.ADD,
                new_sha="abc123",  # Same content
            )
        ]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 0

    def test_conflict_delete_modify(self, detector: ConflictDetector):
        our_changes = [FileChange(path="file.txt", change_type=ChangeType.DELETE)]
        their_changes = [FileChange(path="file.txt", change_type=ChangeType.MODIFY)]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.CERTAIN
        assert "delete" in conflicts[0].description.lower()

    def test_conflict_modify_delete(self, detector: ConflictDetector):
        our_changes = [FileChange(path="file.txt", change_type=ChangeType.MODIFY)]
        their_changes = [FileChange(path="file.txt", change_type=ChangeType.DELETE)]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.CERTAIN

    def test_conflict_overlapping_hunks(self, detector: ConflictDetector):
        our_changes = [
            FileChange(
                path="file.txt",
                change_type=ChangeType.MODIFY,
                hunks=[
                    DiffHunk(
                        old_start=10,
                        old_count=5,
                        new_start=10,
                        new_count=6,
                        lines=["-old line", "+new line our"],
                    )
                ],
            )
        ]
        their_changes = [
            FileChange(
                path="file.txt",
                change_type=ChangeType.MODIFY,
                hunks=[
                    DiffHunk(
                        old_start=12,  # Overlaps with our change (10-15)
                        old_count=3,
                        new_start=12,
                        new_count=4,
                        lines=["-old line", "+new line their"],
                    )
                ],
            )
        ]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 1
        assert conflicts[0].path == "file.txt"
        # Since the changes are different, severity should be CERTAIN
        assert conflicts[0].severity == ConflictSeverity.CERTAIN

    def test_no_conflict_non_overlapping_hunks(self, detector: ConflictDetector):
        our_changes = [
            FileChange(
                path="file.txt",
                change_type=ChangeType.MODIFY,
                hunks=[
                    DiffHunk(
                        old_start=10,
                        old_count=5,
                        new_start=10,
                        new_count=6,
                        lines=["-old", "+new"],
                    )
                ],
            )
        ]
        their_changes = [
            FileChange(
                path="file.txt",
                change_type=ChangeType.MODIFY,
                hunks=[
                    DiffHunk(
                        old_start=100,  # Far away from our change
                        old_count=3,
                        new_start=101,
                        new_count=4,
                        lines=["-old", "+new"],
                    )
                ],
            )
        ]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 0

    def test_likely_conflict_identical_changes(self, detector: ConflictDetector):
        # When both sides make identical changes to overlapping lines,
        # it's a LIKELY conflict (may auto-resolve)
        same_lines = ["-old line", "+new line"]

        our_changes = [
            FileChange(
                path="file.txt",
                change_type=ChangeType.MODIFY,
                hunks=[
                    DiffHunk(
                        old_start=10,
                        old_count=1,
                        new_start=10,
                        new_count=1,
                        lines=same_lines,
                    )
                ],
            )
        ]
        their_changes = [
            FileChange(
                path="file.txt",
                change_type=ChangeType.MODIFY,
                hunks=[
                    DiffHunk(
                        old_start=10,
                        old_count=1,
                        new_start=10,
                        new_count=1,
                        lines=same_lines,  # Identical changes
                    )
                ],
            )
        ]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.LIKELY

    def test_rename_to_different_names_conflict(self, detector: ConflictDetector):
        our_changes = [
            FileChange(
                path="file_new_ours.txt",
                change_type=ChangeType.RENAME,
                old_path="file.txt",
            )
        ]
        their_changes = [
            FileChange(
                path="file_new_theirs.txt",  # Different new name
                change_type=ChangeType.RENAME,
                old_path="file.txt",
            )
        ]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.CERTAIN
        assert "rename" in conflicts[0].description.lower()

    def test_rename_vs_modify_conflict(self, detector: ConflictDetector):
        our_changes = [
            FileChange(
                path="file_renamed.txt",
                change_type=ChangeType.RENAME,
                old_path="file.txt",
            )
        ]
        their_changes = [
            FileChange(
                path="file.txt",
                change_type=ChangeType.MODIFY,
            )
        ]

        conflicts = detector.detect_conflicts(our_changes, their_changes)

        assert len(conflicts) == 1
        assert conflicts[0].severity == ConflictSeverity.LIKELY


class TestOverlappingHunks:
    """Tests for hunk overlap detection."""

    @pytest.fixture
    def detector(self):
        return ConflictDetector()

    def test_exact_overlap(self, detector: ConflictDetector):
        our_hunks = [DiffHunk(old_start=10, old_count=5, new_start=10, new_count=5)]
        their_hunks = [DiffHunk(old_start=10, old_count=5, new_start=10, new_count=5)]

        overlaps = detector._find_overlapping_hunks(our_hunks, their_hunks)

        assert len(overlaps) == 1

    def test_partial_overlap(self, detector: ConflictDetector):
        our_hunks = [DiffHunk(old_start=10, old_count=10, new_start=10, new_count=10)]
        their_hunks = [DiffHunk(old_start=15, old_count=10, new_start=15, new_count=10)]

        overlaps = detector._find_overlapping_hunks(our_hunks, their_hunks)

        # 10-20 overlaps with 15-25
        assert len(overlaps) == 1

    def test_adjacent_hunks(self, detector: ConflictDetector):
        # Hunks that touch at edges should be considered overlapping
        our_hunks = [DiffHunk(old_start=10, old_count=5, new_start=10, new_count=5)]
        their_hunks = [DiffHunk(old_start=15, old_count=5, new_start=15, new_count=5)]

        overlaps = detector._find_overlapping_hunks(our_hunks, their_hunks)

        # With adjacency threshold of 3, these should overlap
        assert len(overlaps) >= 1

    def test_no_overlap(self, detector: ConflictDetector):
        our_hunks = [DiffHunk(old_start=10, old_count=5, new_start=10, new_count=5)]
        their_hunks = [DiffHunk(old_start=100, old_count=5, new_start=100, new_count=5)]

        overlaps = detector._find_overlapping_hunks(our_hunks, their_hunks)

        assert len(overlaps) == 0


class TestDifficultyEstimation:
    """Tests for conflict difficulty estimation."""

    @pytest.fixture
    def detector(self):
        return ConflictDetector()

    def test_easy_likely_conflict(self, detector: ConflictDetector):
        from git_sim.core.models import PotentialConflict

        conflict = PotentialConflict(
            path="file.txt",
            severity=ConflictSeverity.LIKELY,
            description="May auto-resolve",
        )

        difficulty = detector.estimate_conflict_difficulty(conflict)

        assert "easy" in difficulty.lower() or "auto" in difficulty.lower()

    def test_hard_large_region(self, detector: ConflictDetector):
        from git_sim.core.models import PotentialConflict

        conflict = PotentialConflict(
            path="file.txt",
            severity=ConflictSeverity.CERTAIN,
            description="Large conflict",
            overlapping_ranges=[((1, 50), (1, 50))],  # 50 lines
        )

        difficulty = detector.estimate_conflict_difficulty(conflict)

        assert "hard" in difficulty.lower() or "large" in difficulty.lower()
