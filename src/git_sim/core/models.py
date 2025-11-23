"""Data models for git-sim."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class ChangeType(Enum):
    """Type of file change in a diff."""

    ADD = auto()
    DELETE = auto()
    MODIFY = auto()
    RENAME = auto()
    COPY = auto()


class ConflictSeverity(Enum):
    """Severity level of a potential conflict."""

    NONE = auto()  # No conflict
    LIKELY = auto()  # Overlapping changes, might auto-resolve
    CERTAIN = auto()  # Same lines modified differently, manual resolution required


@dataclass(frozen=True)
class CommitInfo:
    """Immutable representation of a Git commit."""

    sha: str
    message: str
    author: str
    author_email: str
    timestamp: int
    parent_shas: tuple[str, ...]
    tree_sha: str

    @property
    def short_sha(self) -> str:
        """Return first 7 characters of SHA."""
        return self.sha[:7]

    @property
    def is_merge(self) -> bool:
        """Check if this is a merge commit."""
        return len(self.parent_shas) > 1

    @property
    def first_line(self) -> str:
        """Return the first line of the commit message."""
        return self.message.split("\n", 1)[0]


@dataclass(frozen=True)
class BranchInfo:
    """Representation of a Git branch."""

    name: str
    head_sha: str
    is_remote: bool = False
    upstream: Optional[str] = None


@dataclass
class DiffHunk:
    """A single hunk in a unified diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)  # Prefixed with +, -, or space
    header: str = ""  # Optional function/class context

    @property
    def old_range(self) -> tuple[int, int]:
        """Returns (start, end) line range in old file."""
        return (self.old_start, self.old_start + self.old_count)

    @property
    def new_range(self) -> tuple[int, int]:
        """Returns (start, end) line range in new file."""
        return (self.new_start, self.new_start + self.new_count)


@dataclass
class FileChange:
    """Single file change in a diff."""

    path: str
    change_type: ChangeType
    old_path: Optional[str] = None  # For renames/copies
    old_mode: Optional[int] = None
    new_mode: Optional[int] = None
    old_sha: Optional[str] = None
    new_sha: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def is_binary(self) -> bool:
        """Check if this is a binary file change."""
        return not self.hunks and self.change_type == ChangeType.MODIFY


@dataclass
class CommitDiff:
    """Diff between a commit and its parent."""

    commit_sha: str
    parent_sha: Optional[str]
    file_changes: list[FileChange] = field(default_factory=list)

    @property
    def files_modified(self) -> set[str]:
        """Return set of all modified file paths."""
        paths = {fc.path for fc in self.file_changes}
        # Include old paths for renames
        paths.update(fc.old_path for fc in self.file_changes if fc.old_path)
        return paths


@dataclass
class PotentialConflict:
    """Detected potential merge/rebase conflict."""

    path: str
    severity: ConflictSeverity
    description: str
    our_change: Optional[FileChange] = None
    their_change: Optional[FileChange] = None
    overlapping_ranges: list[tuple[tuple[int, int], tuple[int, int]]] = field(
        default_factory=list
    )

    @property
    def is_certain(self) -> bool:
        """Check if this conflict will definitely occur."""
        return self.severity == ConflictSeverity.CERTAIN


@dataclass
class RebaseStep:
    """Single step in a rebase operation."""

    original_sha: str
    commit_info: CommitInfo
    action: str = "pick"  # 'pick', 'squash', 'fixup', 'reword', 'drop'
    new_sha: Optional[str] = None  # Simulated new SHA after rebase
    conflicts: list[PotentialConflict] = field(default_factory=list)
    will_be_skipped: bool = False  # True if patch-id matches existing commit

    @property
    def has_conflicts(self) -> bool:
        """Check if this step has any predicted conflicts."""
        return len(self.conflicts) > 0


@dataclass
class CommitGraph:
    """DAG representation for visualization."""

    commits: dict[str, CommitInfo] = field(default_factory=dict)  # sha -> CommitInfo
    edges: list[tuple[str, str]] = field(default_factory=list)  # (child, parent) pairs
    branch_tips: dict[str, str] = field(default_factory=dict)  # branch_name -> sha
    head_sha: str = ""
    head_branch: Optional[str] = None

    def add_commit(self, commit: CommitInfo) -> None:
        """Add a commit to the graph."""
        self.commits[commit.sha] = commit
        for parent_sha in commit.parent_shas:
            self.edges.append((commit.sha, parent_sha))

    def get_ancestors(self, sha: str, limit: int = 100) -> list[str]:
        """Get ancestor SHAs in topological order."""
        ancestors = []
        visited = set()
        stack = [sha]

        while stack and len(ancestors) < limit:
            current = stack.pop()
            if current in visited or current not in self.commits:
                continue
            visited.add(current)
            ancestors.append(current)
            commit = self.commits[current]
            stack.extend(commit.parent_shas)

        return ancestors


class OperationType(Enum):
    """Type of Git operation being simulated."""

    REBASE = auto()
    MERGE = auto()
    RESET = auto()
    CHERRY_PICK = auto()


class ResetMode(Enum):
    """Reset mode types."""

    SOFT = auto()  # Only move HEAD
    MIXED = auto()  # Move HEAD, reset index
    HARD = auto()  # Move HEAD, reset index and working tree


class DangerLevel(Enum):
    """Safety rating for operations."""

    LOW = auto()  # Safe, easily reversible
    MEDIUM = auto()  # Potentially destructive but recoverable
    HIGH = auto()  # History rewrite, force-push risk
    CRITICAL = auto()  # Data loss risk


@dataclass
class SafetyInfo:
    """Safety analysis for an operation."""

    danger_level: DangerLevel
    reasons: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    reversible: bool = True
    requires_force_push: bool = False

    @property
    def is_dangerous(self) -> bool:
        """Check if operation is considered dangerous."""
        return self.danger_level in (DangerLevel.HIGH, DangerLevel.CRITICAL)


@dataclass
class SimulationResult:
    """
    Unified result structure for all simulation types.

    Every simulator returns this object, providing a consistent
    interface for the CLI and any consumers.
    """

    operation_type: OperationType
    success: bool
    before_graph: CommitGraph = field(default_factory=CommitGraph)
    after_graph: CommitGraph = field(default_factory=CommitGraph)
    conflicts: list[PotentialConflict] = field(default_factory=list)
    changed_files: list[FileChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safety_info: Optional[SafetyInfo] = None

    # Operation-specific details
    commits_affected: list[CommitInfo] = field(default_factory=list)
    commits_dropped: list[CommitInfo] = field(default_factory=list)
    commits_created: list[CommitInfo] = field(default_factory=list)

    # Metadata
    source_ref: str = ""
    target_ref: str = ""
    merge_base_sha: str = ""
    new_head_sha: str = ""

    # For detailed step-by-step operations
    steps: list["OperationStep"] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Check if simulation predicts any conflicts."""
        return len(self.conflicts) > 0

    @property
    def conflict_count(self) -> int:
        """Total number of predicted conflicts."""
        return len(self.conflicts)

    @property
    def is_safe(self) -> bool:
        """Check if the operation is considered safe."""
        return self.safety_info is None or not self.safety_info.is_dangerous


@dataclass
class OperationStep:
    """A single step in a multi-step operation (rebase, cherry-pick)."""

    step_number: int
    action: str  # 'pick', 'merge', 'reset', etc.
    commit_info: Optional[CommitInfo] = None
    original_sha: str = ""
    new_sha: str = ""
    conflicts: list[PotentialConflict] = field(default_factory=list)
    will_be_skipped: bool = False
    description: str = ""

    @property
    def has_conflicts(self) -> bool:
        """Check if this step has predicted conflicts."""
        return len(self.conflicts) > 0


@dataclass
class RebaseSimulation:
    """Complete rebase simulation result."""

    source_branch: str
    target_branch: str
    onto_sha: str
    merge_base_sha: str
    steps: list[RebaseStep] = field(default_factory=list)
    before_graph: CommitGraph = field(default_factory=CommitGraph)
    after_graph: CommitGraph = field(default_factory=CommitGraph)

    @property
    def has_conflicts(self) -> bool:
        """Check if any step has predicted conflicts."""
        return any(step.has_conflicts for step in self.steps)

    @property
    def conflict_count(self) -> int:
        """Total number of predicted conflicts."""
        return sum(len(step.conflicts) for step in self.steps)

    @property
    def commits_to_replay(self) -> list[CommitInfo]:
        """List of commits that will be replayed."""
        return [s.commit_info for s in self.steps if s.action != "drop"]

    @property
    def skipped_commits(self) -> list[CommitInfo]:
        """List of commits that will be skipped (duplicate patch-ids)."""
        return [s.commit_info for s in self.steps if s.will_be_skipped]

    def to_simulation_result(self) -> SimulationResult:
        """Convert to unified SimulationResult."""
        all_conflicts = [c for step in self.steps for c in step.conflicts]

        return SimulationResult(
            operation_type=OperationType.REBASE,
            success=not self.has_conflicts,
            before_graph=self.before_graph,
            after_graph=self.after_graph,
            conflicts=all_conflicts,
            commits_affected=[s.commit_info for s in self.steps],
            commits_dropped=self.skipped_commits,
            source_ref=self.source_branch,
            target_ref=self.target_branch,
            merge_base_sha=self.merge_base_sha,
            new_head_sha=self.steps[-1].new_sha if self.steps else "",
            steps=[
                OperationStep(
                    step_number=i + 1,
                    action=s.action,
                    commit_info=s.commit_info,
                    original_sha=s.original_sha,
                    new_sha=s.new_sha or "",
                    conflicts=s.conflicts,
                    will_be_skipped=s.will_be_skipped,
                )
                for i, s in enumerate(self.steps)
            ],
        )


@dataclass
class MergeSimulation:
    """Complete merge simulation result."""

    source_branch: str
    target_branch: str
    merge_base_sha: str
    merge_commit_sha: str = ""  # Simulated merge commit
    strategy: str = "ort"  # merge strategy
    is_fast_forward: bool = False
    conflicts: list[PotentialConflict] = field(default_factory=list)
    files_merged_cleanly: list[str] = field(default_factory=list)
    before_graph: CommitGraph = field(default_factory=CommitGraph)
    after_graph: CommitGraph = field(default_factory=CommitGraph)

    @property
    def has_conflicts(self) -> bool:
        """Check if merge would have conflicts."""
        return len(self.conflicts) > 0

    def to_simulation_result(self) -> SimulationResult:
        """Convert to unified SimulationResult."""
        return SimulationResult(
            operation_type=OperationType.MERGE,
            success=not self.has_conflicts,
            before_graph=self.before_graph,
            after_graph=self.after_graph,
            conflicts=self.conflicts,
            source_ref=self.source_branch,
            target_ref=self.target_branch,
            merge_base_sha=self.merge_base_sha,
            new_head_sha=self.merge_commit_sha,
            warnings=["Fast-forward merge possible"] if self.is_fast_forward else [],
        )


@dataclass
class ResetSimulation:
    """Complete reset simulation result."""

    target_sha: str
    mode: ResetMode
    current_sha: str
    commits_detached: list[CommitInfo] = field(default_factory=list)
    files_unstaged: list[str] = field(default_factory=list)  # For mixed reset
    files_discarded: list[str] = field(default_factory=list)  # For hard reset
    before_graph: CommitGraph = field(default_factory=CommitGraph)
    after_graph: CommitGraph = field(default_factory=CommitGraph)

    @property
    def commits_lost(self) -> int:
        """Number of commits that would become unreachable."""
        return len(self.commits_detached)

    def to_simulation_result(self) -> SimulationResult:
        """Convert to unified SimulationResult."""
        warnings = []
        if self.commits_detached:
            warnings.append(
                f"{len(self.commits_detached)} commit(s) will become unreachable"
            )
        if self.files_discarded:
            warnings.append(
                f"{len(self.files_discarded)} file(s) will have changes discarded"
            )

        danger = DangerLevel.LOW
        if self.mode == ResetMode.HARD:
            danger = DangerLevel.HIGH if self.files_discarded else DangerLevel.MEDIUM
        elif self.commits_detached:
            danger = DangerLevel.MEDIUM

        return SimulationResult(
            operation_type=OperationType.RESET,
            success=True,
            before_graph=self.before_graph,
            after_graph=self.after_graph,
            commits_dropped=self.commits_detached,
            source_ref=self.current_sha,
            target_ref=self.target_sha,
            new_head_sha=self.target_sha,
            warnings=warnings,
            safety_info=SafetyInfo(
                danger_level=danger,
                reasons=[
                    f"Reset mode: {self.mode.name}",
                    f"Commits affected: {len(self.commits_detached)}",
                ],
                reversible=self.mode != ResetMode.HARD,
            ),
        )


@dataclass
class CherryPickSimulation:
    """Complete cherry-pick simulation result."""

    commits_to_pick: list[CommitInfo] = field(default_factory=list)
    target_branch: str = ""
    steps: list[OperationStep] = field(default_factory=list)
    before_graph: CommitGraph = field(default_factory=CommitGraph)
    after_graph: CommitGraph = field(default_factory=CommitGraph)

    @property
    def has_conflicts(self) -> bool:
        """Check if any cherry-pick would have conflicts."""
        return any(step.has_conflicts for step in self.steps)

    @property
    def conflicts(self) -> list[PotentialConflict]:
        """All conflicts from all steps."""
        return [c for step in self.steps for c in step.conflicts]

    def to_simulation_result(self) -> SimulationResult:
        """Convert to unified SimulationResult."""
        return SimulationResult(
            operation_type=OperationType.CHERRY_PICK,
            success=not self.has_conflicts,
            before_graph=self.before_graph,
            after_graph=self.after_graph,
            conflicts=self.conflicts,
            commits_affected=self.commits_to_pick,
            commits_created=[
                s.commit_info for s in self.steps
                if s.commit_info and s.new_sha
            ],
            target_ref=self.target_branch,
            steps=self.steps,
        )
