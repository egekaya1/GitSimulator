"""Conflict detection heuristics for git-sim."""

from git_sim.core.models import (
    ChangeType,
    ConflictSeverity,
    DiffHunk,
    FileChange,
    PotentialConflict,
)


class ConflictDetector:
    """
    Detects potential conflicts without actually applying patches.

    Uses heuristics based on:
    1. File-level overlap (same files modified)
    2. Hunk-level overlap (overlapping line ranges)
    3. Content comparison (identical vs different changes)
    4. Delete/modify conflicts
    5. Rename conflicts
    """

    # Number of lines of context to consider as "adjacent"
    ADJACENCY_THRESHOLD = 3

    def detect_conflicts(
        self,
        our_changes: list[FileChange],
        their_changes: list[FileChange],
    ) -> list[PotentialConflict]:
        """
        Detect potential conflicts between two sets of changes.

        In rebase context:
        - "our" changes = changes already in the target branch
        - "their" changes = changes in the commit being rebased

        Args:
            our_changes: Changes from our side (target branch).
            their_changes: Changes from their side (commit being applied).

        Returns:
            List of potential conflicts detected.
        """
        conflicts: list[PotentialConflict] = []

        # Index changes by path
        our_by_path = {fc.path: fc for fc in our_changes}
        their_by_path = {fc.path: fc for fc in their_changes}

        # Also index by old_path for renames
        our_old_paths = {fc.old_path: fc for fc in our_changes if fc.old_path}
        their_old_paths = {fc.old_path: fc for fc in their_changes if fc.old_path}

        # Find files modified on both sides
        common_paths = set(our_by_path.keys()) & set(their_by_path.keys())

        for path in common_paths:
            conflict = self._analyze_file_conflict(
                path,
                our_by_path[path],
                their_by_path[path],
            )
            if conflict:
                conflicts.append(conflict)

        # Check for delete/modify conflicts
        conflicts.extend(self._detect_delete_modify_conflicts(our_changes, their_changes))

        # Check for rename conflicts
        conflicts.extend(
            self._detect_rename_conflicts(
                our_changes, their_changes, our_old_paths, their_old_paths
            )
        )

        return conflicts

    def _analyze_file_conflict(
        self,
        path: str,
        our_fc: FileChange,
        their_fc: FileChange,
    ) -> PotentialConflict | None:
        """
        Analyze if two changes to the same file will conflict.

        Args:
            path: Path to the file.
            our_fc: Our file change.
            their_fc: Their file change.

        Returns:
            PotentialConflict if conflict detected, None otherwise.
        """
        # Both delete - no conflict
        if our_fc.change_type == ChangeType.DELETE and their_fc.change_type == ChangeType.DELETE:
            return None

        # Both add with identical content - no conflict
        if (
            our_fc.change_type == ChangeType.ADD
            and their_fc.change_type == ChangeType.ADD
            and our_fc.new_sha == their_fc.new_sha
        ):
            return None

        # Both add with different content - certain conflict
        if our_fc.change_type == ChangeType.ADD and their_fc.change_type == ChangeType.ADD:
            return PotentialConflict(
                path=path,
                severity=ConflictSeverity.CERTAIN,
                description=f"Both sides add '{path}' with different content",
                our_change=our_fc,
                their_change=their_fc,
            )

        # One side deletes while the other modifies/adds - handled by specialized detector
        # Skip generic analysis here to avoid duplicate conflicts.
        if (
            our_fc.change_type == ChangeType.DELETE
            and their_fc.change_type in (ChangeType.MODIFY, ChangeType.ADD)
        ) or (
            their_fc.change_type == ChangeType.DELETE
            and our_fc.change_type in (ChangeType.MODIFY, ChangeType.ADD)
        ):
            return None

        # One adds, one modifies - file already exists conflict
        if our_fc.change_type == ChangeType.ADD or their_fc.change_type == ChangeType.ADD:
            return PotentialConflict(
                path=path,
                severity=ConflictSeverity.CERTAIN,
                description=f"File '{path}' added on one side, modified on other",
                our_change=our_fc,
                their_change=their_fc,
            )

        # Both modify - need to check hunks
        if not our_fc.hunks or not their_fc.hunks:
            # No hunks parsed (possibly binary) - assume conflict
            return PotentialConflict(
                path=path,
                severity=ConflictSeverity.LIKELY,
                description=f"Both sides modify '{path}' (could not analyze hunks)",
                our_change=our_fc,
                their_change=their_fc,
            )

        # Find overlapping hunks
        overlaps = self._find_overlapping_hunks(our_fc.hunks, their_fc.hunks)

        if not overlaps:
            # No overlapping hunks - changes can be merged cleanly
            return None

        # Check if overlapping changes are identical
        severity = self._classify_overlap_severity(our_fc.hunks, their_fc.hunks, overlaps)

        return PotentialConflict(
            path=path,
            severity=severity,
            description=self._describe_overlap(path, overlaps, severity),
            our_change=our_fc,
            their_change=their_fc,
            overlapping_ranges=overlaps,
        )

    def _find_overlapping_hunks(
        self,
        our_hunks: list[DiffHunk],
        their_hunks: list[DiffHunk],
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """
        Find hunks that affect overlapping or adjacent line ranges.

        Git considers hunks conflicting if they:
        - Overlap (share lines)
        - Are adjacent (touch at edges)
        - Are within ADJACENCY_THRESHOLD lines of each other

        Returns:
            List of ((our_start, our_end), (their_start, their_end)) tuples.
        """
        overlaps: list[tuple[tuple[int, int], tuple[int, int]]] = []

        for our_hunk in our_hunks:
            our_start, our_end = our_hunk.old_range

            for their_hunk in their_hunks:
                their_start, their_end = their_hunk.old_range

                # Check for overlap or adjacency (with threshold)
                # Two ranges overlap if: start1 <= end2 + threshold AND start2 <= end1 + threshold
                if (
                    our_start <= their_end + self.ADJACENCY_THRESHOLD
                    and their_start <= our_end + self.ADJACENCY_THRESHOLD
                ):
                    overlaps.append(((our_start, our_end), (their_start, their_end)))

        return overlaps

    def _classify_overlap_severity(
        self,
        our_hunks: list[DiffHunk],
        their_hunks: list[DiffHunk],
        overlaps: list[tuple[tuple[int, int], tuple[int, int]]],
    ) -> ConflictSeverity:
        """
        Classify the severity of overlapping hunks.

        If the overlapping changes are identical, severity is LIKELY (auto-resolvable).
        If they differ, severity is CERTAIN (manual resolution required).
        """
        # Build a map of line ranges to actual changes for comparison
        our_changes_by_range: dict[tuple[int, int], list[str]] = {}
        for hunk in our_hunks:
            our_changes_by_range[hunk.old_range] = [
                line for line in hunk.lines if line.startswith(("+", "-"))
            ]

        their_changes_by_range: dict[tuple[int, int], list[str]] = {}
        for hunk in their_hunks:
            their_changes_by_range[hunk.old_range] = [
                line for line in hunk.lines if line.startswith(("+", "-"))
            ]

        # For each overlap, check if changes are identical
        for our_range, their_range in overlaps:
            our_changes = our_changes_by_range.get(our_range, [])
            their_changes = their_changes_by_range.get(their_range, [])

            if our_changes != their_changes:
                return ConflictSeverity.CERTAIN

        return ConflictSeverity.LIKELY

    def _describe_overlap(
        self,
        path: str,
        overlaps: list[tuple[tuple[int, int], tuple[int, int]]],
        severity: ConflictSeverity,
    ) -> str:
        """Generate a human-readable description of the overlap."""
        if severity == ConflictSeverity.CERTAIN:
            if len(overlaps) == 1:
                our_range, their_range = overlaps[0]
                return (
                    f"Lines {our_range[0]}-{our_range[1]} in '{path}' "
                    f"modified differently on both sides"
                )
            return f"Multiple regions in '{path}' modified differently on both sides"
        else:
            if len(overlaps) == 1:
                our_range, _ = overlaps[0]
                return (
                    f"Lines {our_range[0]}-{our_range[1]} in '{path}' "
                    f"modified on both sides (identical changes, may auto-resolve)"
                )
            return (
                f"Multiple regions in '{path}' modified on both sides "
                f"(identical changes, may auto-resolve)"
            )

    def _detect_delete_modify_conflicts(
        self,
        our_changes: list[FileChange],
        their_changes: list[FileChange],
    ) -> list[PotentialConflict]:
        """Detect when one side deletes a file the other modifies."""
        conflicts: list[PotentialConflict] = []

        our_deleted = {fc.path: fc for fc in our_changes if fc.change_type == ChangeType.DELETE}
        their_modified = {
            fc.path: fc
            for fc in their_changes
            if fc.change_type in (ChangeType.MODIFY, ChangeType.ADD)
        }

        # Our deletes vs their modifies
        for path in set(our_deleted.keys()) & set(their_modified.keys()):
            conflicts.append(
                PotentialConflict(
                    path=path,
                    severity=ConflictSeverity.CERTAIN,
                    description=f"File '{path}' deleted on target but modified in commit",
                    our_change=our_deleted[path],
                    their_change=their_modified[path],
                )
            )

        # Their deletes vs our modifies
        their_deleted = {fc.path: fc for fc in their_changes if fc.change_type == ChangeType.DELETE}
        our_modified = {
            fc.path: fc
            for fc in our_changes
            if fc.change_type in (ChangeType.MODIFY, ChangeType.ADD)
        }

        for path in set(their_deleted.keys()) & set(our_modified.keys()):
            conflicts.append(
                PotentialConflict(
                    path=path,
                    severity=ConflictSeverity.CERTAIN,
                    description=f"File '{path}' modified on target but deleted in commit",
                    our_change=our_modified[path],
                    their_change=their_deleted[path],
                )
            )

        return conflicts

    def _detect_rename_conflicts(
        self,
        our_changes: list[FileChange],
        their_changes: list[FileChange],
        our_old_paths: dict[str, FileChange],
        their_old_paths: dict[str, FileChange],
    ) -> list[PotentialConflict]:
        """Detect rename-related conflicts."""
        conflicts: list[PotentialConflict] = []

        # Case 1: Both sides rename the same file to different names
        for old_path in set(our_old_paths.keys()) & set(their_old_paths.keys()):
            our_fc = our_old_paths[old_path]
            their_fc = their_old_paths[old_path]

            if our_fc.path != their_fc.path:
                conflicts.append(
                    PotentialConflict(
                        path=old_path,
                        severity=ConflictSeverity.CERTAIN,
                        description=(
                            f"File '{old_path}' renamed to '{our_fc.path}' on target "
                            f"but renamed to '{their_fc.path}' in commit"
                        ),
                        our_change=our_fc,
                        their_change=their_fc,
                    )
                )

        # Case 2: One side renames a file that the other modifies
        our_renames = {
            fc.old_path: fc
            for fc in our_changes
            if fc.change_type == ChangeType.RENAME and fc.old_path
        }
        their_modifies_paths = {
            fc.path for fc in their_changes if fc.change_type == ChangeType.MODIFY
        }

        for old_path, our_fc in our_renames.items():
            if old_path in their_modifies_paths:
                their_fc = next(fc for fc in their_changes if fc.path == old_path)
                conflicts.append(
                    PotentialConflict(
                        path=old_path,
                        severity=ConflictSeverity.LIKELY,
                        description=(
                            f"File '{old_path}' renamed to '{our_fc.path}' on target "
                            f"but modified in commit"
                        ),
                        our_change=our_fc,
                        their_change=their_fc,
                    )
                )

        # Reverse case
        their_renames = {
            fc.old_path: fc
            for fc in their_changes
            if fc.change_type == ChangeType.RENAME and fc.old_path
        }
        our_modifies_paths = {fc.path for fc in our_changes if fc.change_type == ChangeType.MODIFY}

        for old_path, their_fc in their_renames.items():
            if old_path in our_modifies_paths:
                our_fc = next(fc for fc in our_changes if fc.path == old_path)
                conflicts.append(
                    PotentialConflict(
                        path=old_path,
                        severity=ConflictSeverity.LIKELY,
                        description=(
                            f"File '{old_path}' modified on target but renamed to "
                            f"'{their_fc.path}' in commit"
                        ),
                        our_change=our_fc,
                        their_change=their_fc,
                    )
                )

        return conflicts

    def estimate_conflict_difficulty(self, conflict: PotentialConflict) -> str:
        """
        Estimate how difficult a conflict will be to resolve.

        Returns a human-readable difficulty assessment.
        """
        if conflict.severity == ConflictSeverity.LIKELY:
            return "Easy - likely auto-resolvable or simple manual fix"

        if not conflict.overlapping_ranges:
            # Delete/modify or rename conflict
            return "Moderate - requires decision on file-level action"

        total_overlap_lines = sum(
            max(our[1] - our[0], their[1] - their[0]) for our, their in conflict.overlapping_ranges
        )

        if total_overlap_lines <= 5:
            return "Easy - small region affected"
        elif total_overlap_lines <= 20:
            return "Moderate - medium-sized region affected"
        else:
            return "Hard - large region affected, careful review needed"
