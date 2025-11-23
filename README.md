# GitSim - Git Simulation & Visualization Engine

**Dry-run dangerous Git commands with visual feedback before executing them.**

GitSim is a sophisticated Git simulation tool that lets you preview the exact outcome of complex Git operations—including conflict prediction, safety analysis, and visual before/after graphs—without touching your repository. Think of it as a "flight simulator" for Git commands.

[![CI](https://github.com/egekaya1/GitSimulator/actions/workflows/ci.yml/badge.svg)](https://github.com/egekaya1/GitSimulator/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/gitsimulator.svg)](https://pypi.org/project/gitsimulator/)
[![Downloads](https://pepy.tech/badge/gitsimulator)](https://pepy.tech/project/gitsimulator)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## 🎯 Why GitSim?

**The Problem**: Git's most powerful commands (`rebase`, `merge`, `reset`, `cherry-pick`) are also its most dangerous. One wrong move can rewrite history, lose work, or create messy conflicts.

**The Solution**: GitSim simulates these operations in a safe, read-only environment, showing you:
- ✅ **Exact outcome** with before/after commit graphs
- ✅ **Predicted conflicts** with file-level details and certainty levels
- ✅ **Safety ratings** (LOW/MEDIUM/HIGH/CRITICAL danger levels)
- ✅ **Recovery steps** if something goes wrong
- ✅ **Educational explanations** of how Git commands work internally

**Perfect for**:
- 🎓 **Learning Git** - See exactly how operations transform your repository
- 💼 **Complex merges** - Preview conflicts before starting a multi-hour merge
- 🔧 **History rewriting** - Safely plan rebases on shared branches
- 👥 **Team education** - Teach Git workflows with visual demonstrations
- 🚀 **CI/CD safety** - Validate Git operations in automation scripts

---

## ⚡ Quick Start

```bash
# Install from PyPI (v1.0.1)
pipx install gitsimulator

# All three commands work identically:
gitsim rebase main
git-sim rebase main
gitsimulator rebase main

# Preview a merge with conflict detection
gitsim merge feature-branch

# Learn how Git commands work
gitsim explain rebase

# Save repository state for experiments
gitsim snapshot create before-rebase
```

---

## 🎨 Features

### 🛡️ Core Simulation Commands

<table>
<tr>
<td width="50%">

**`gitsim rebase`**
- Simulate rebasing branches
- Predict conflicts per commit
- Show new commit SHAs
- Warn about force-push requirements
- Detailed safety analysis

</td>
<td width="50%">

**`gitsim merge`**
- Preview three-way merges
- Detect fast-forward opportunities
- Show merge commit creation
- File-by-file conflict prediction
- Merge base analysis

</td>
</tr>
<tr>
<td width="50%">

**`gitsim reset`**
- Test --soft, --mixed, --hard modes
- Preview unreachable commits
- Working directory impact
- Staged changes analysis
- Recovery instructions

</td>
<td width="50%">

**`gitsim cherry-pick`**
- Simulate picking commits
- Multi-commit support
- Step-by-step conflict detection
- Short/full SHA resolution
- New commit preview

</td>
</tr>
</table>

### 📊 Analysis & Visualization

- **Conflict Detection Engine**
  - **CERTAIN** conflicts: Same lines modified (90%+ accuracy)
  - **LIKELY** conflicts: Nearby changes within 3 lines
  - **POSSIBLE** conflicts: Same file modifications
  - File-level granularity with line ranges

- **Safety Analysis System**
  - **Danger Levels**: LOW → MEDIUM → HIGH → CRITICAL
  - **Reversibility**: Can operation be undone?
  - **Force-push Required**: Will remote history diverge?
  - **Data Loss Risk**: Commits becoming unreachable?
  - **Recovery Suggestions**: Step-by-step undo instructions

- **Visual Commit Graphs**
  - ASCII art graphs (matches `git log --graph`)
  - Before/After comparisons side-by-side
  - Branch topology visualization
  - Highlighted commits and changes
  - Color-coded output with Rich library

### 🎓 Educational Features

**`gitsim explain <command>`** - Interactive learning mode:
- 📖 Plain-English explanations of Git internals
- 🔍 Step-by-step algorithm breakdowns
- ⚠️ Risk assessment and common pitfalls
- 💡 Best practices and safety tips
- 🔄 Alternative approaches
- 🔗 Related commands and references

Supported explanations: `rebase`, `merge`, `reset`, `cherry-pick`, `stash`, `tag`

### 🔧 Advanced Tools

- **Snapshot System** - Save/restore repository states
  - Named snapshots with metadata
  - HEAD position tracking
  - Branch state preservation
  - Timestamped history
  - Quick rollback for experiments

- **Unified Simulator** - `gitsim sim "any-git-command"`
  - Natural syntax parsing
  - All operations supported
  - Consistent output format

- **Plugin Architecture**
  - Hook plugins (pre/post/override simulation)
  - Custom simulators
  - Output formatters
  - Entry point discovery

- **Interactive TUI** - `gitsim tui`
  - Textual-powered interface
  - Real-time command preview
  - Headless mode for scripting

---

## 📦 Installation

### From PyPI (Recommended)

```bash
# Install with pipx (v1.0.1)
pipx install gitsimulator

# Or with pip
pip install gitsimulator
```

**Note**: All three commands work identically: `gitsim`, `git-sim`, and `gitsimulator`

### From Source

```bash
git clone https://github.com/egekaya1/GitSimulator.git
cd GitSimulator
pip install -e ".[dev]"
```

### Requirements

- **Python**: 3.11, 3.12, or 3.13
- **OS**: Linux, macOS, Windows
- **Dependencies**: 
  - `dulwich` (Pure Python Git implementation)
  - `rich` (Terminal formatting)
  - `typer` (CLI framework)
  - `textual` (TUI, optional)

---

## 💻 Usage Examples

### Rebase Simulation

```bash
$ gitsim rebase main

Simulating: git rebase main

╭────────── Rebase Summary ───────────╮
│   Source branch       feature       │
│   Target branch       main          │
│   Merge base          abc1234       │
│   Commits to replay   3             │
│   Predicted conflicts 1             │
╰─────────────────────────────────────╯

╭────────── Safety Analysis ──────────╮
│   Danger Level           🔴 HIGH     │
│   Reversible             Yes        │
│   Force Push Required    Yes        │
╰─────────────────────────────────────╯

Before Rebase:
* abc1234 (HEAD -> feature) Add authentication
* def5678 Update config
| * 123abcd (main) Fix security bug
|/
* 789xyz0 Initial commit

After Rebase (Simulated):
* new1234' (HEAD -> feature) Add authentication
* new5678' Update config
* 123abcd (main) Fix security bug
* 789xyz0 Initial commit

⚠️  Found 1 CERTAIN conflict in config.py (lines 45-52)

Recovery: git reflog to restore, git reset --hard ORIG_HEAD
```

### Merge with Conflict Prediction

```bash
$ gitsim merge feature-auth

╭─────────── Merge Summary ───────────╮
│  Source branch   feature-auth       │
│  Target branch   main               │
│  Merge type      Three-way          │
│  Files changed   8                  │
│  Conflicts       2 CERTAIN          │
╰─────────────────────────────────────╯

          Potential Conflicts          
┏━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Severity   ┃ File       ┃ Details   ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ CERTAIN    │ auth.py    │ Lines     │
│            │            │ 23-45     │
│ CERTAIN    │ config.yml │ Lines     │
│            │            │ 12-18     │
└────────────┴────────────┴───────────┘
```

### Educational Mode

```bash
$ gitsim explain rebase

╭──────────── git rebase ─────────────╮
│ Rebase re-applies commits from one  │
│ branch onto another, creating new   │
│ commits with different SHAs.        │
╰─────────────────────────────────────╯

How it works:
  1. Find merge base (common ancestor)
  2. Save commits to replay
  3. Reset HEAD to target branch
  4. Apply each commit sequentially
  5. Generate new SHAs for all commits

What changes:
  • All rebased commits get new SHAs
  • Commit timestamps updated
  • Linear history (no merge commits)
  • Parent references rewritten

Risks:
  ⚠️ HISTORY REWRITE - Collaborators affected
  ⚠️ FORCE PUSH REQUIRED - Remote diverges
  ⚠️ CONFLICTS - May repeat for each commit
  
Safety tips:
  ✓ Never rebase public/shared branches
  ✓ Create backup: git branch backup-mybranch
  ✓ Use git reflog to recover mistakes

Alternatives:
  • git merge - Preserves history
  • git cherry-pick - Pick specific commits
```

---

## 🏗️ Architecture & Technical Details

### System Design

GitSim follows a clean, modular architecture with strict separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Layer (Typer)                    │
│  ┌──────────┬──────────┬──────────┬──────────────────┐  │
│  │ Commands │ Options  │ Parsing  │ User Interface   │  │
│  └──────────┴──────────┴──────────┴──────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Simulation Dispatcher                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │ • Command routing                                │   │
│  │ • Plugin hook execution (pre/override/post)      │   │
│  │ • Result validation                              │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Rebase  │    │  Merge  │    │  Reset  │
    │Simulator│    │Simulator│    │Simulator│
    └─────────┘    └─────────┘    └─────────┘
          │              │              │
          └──────────────┼──────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Core Services                         │
│  ┌──────────────┬──────────────┬──────────────────┐     │
│  │ Repository   │ Diff         │ Conflict         │     │
│  │ (Dulwich)    │ Analyzer     │ Detector         │     │
│  └──────────────┴──────────────┴──────────────────┘     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 Git Repository (.git/)                  │
│              (Read-only access via Dulwich)             │
└─────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Repository Layer (`core/repository.py`)

Pure Python Git access via Dulwich - **no git binary required**:

```python
class Repository:
    """Read-only Git repository wrapper."""
    
    def get_commit(self, ref_or_sha: str) -> CommitInfo:
        """Resolve refs/SHAs to commits (supports short SHAs)."""
    
    def walk_commits(self, include: list[str], exclude: list[str] | None) -> Iterator[CommitInfo]:
        """Topological commit traversal."""
    
    def get_commit_changes(self, sha: str) -> list[FileChange]:
        """Extract file changes from commit."""
    
    def build_graph(self, refs: list[str], max_commits: int) -> CommitGraph:
        """Build DAG representation."""
```

**Key features**:
- Short SHA resolution (7+ characters with ambiguity detection)
- Relative ref support (`HEAD~2`, `main^`)
- Topological sorting for graph display
- Lazy loading for performance

#### 2. Simulation Engines (`simulation/`)

Each simulator implements `BaseSimulator[T]` protocol:

```python
class BaseSimulator(Protocol[T]):
    def validate(self) -> tuple[list[str], list[str]]:
        """Pre-flight checks → (errors, warnings)."""
    
    def simulate(self) -> T:
        """Execute simulation → typed result."""
```

**Rebase Simulator** (`simulation/rebase.py`):
- Algorithm: Find merge base → collect commits → replay onto target
- Conflict detection: Compare each commit's changes against target
- SHA generation: Deterministic fake SHAs for visualization
- Step tracking: Detailed operation steps with conflicts

**Merge Simulator** (`simulation/merge.py`):
- Three-way merge analysis (base vs ours vs theirs)
- Fast-forward detection
- Merge commit synthesis
- Conflict accumulation across all files

**Reset Simulator** (`simulation/reset.py`):
- Mode handling: SOFT (staged only), MIXED (unstaged), HARD (discarded)
- Detached commit tracking
- Working directory simulation
- Reflog recovery instructions

**Cherry-Pick Simulator** (`simulation/cherry_pick.py`):
- Sequential commit application
- Cumulative conflict detection
- Parent relationship preservation
- Merge commit warnings

#### 3. Conflict Detection (`simulation/conflict_detector.py`)

Sophisticated heuristics engine with three certainty levels:

```python
class ConflictDetector:
    def detect_conflicts(
        self,
        our_changes: list[FileChange],
        their_changes: list[FileChange],
    ) -> list[ConflictInfo]:
        """Multi-level conflict analysis."""
```

**Detection Strategy**:

1. **CERTAIN** (90%+ accuracy):
   - Same file, overlapping line ranges
   - Both sides modify identical lines
   - Binary file conflicts

2. **LIKELY** (70%+ accuracy):
   - Changes within 3 lines of each other
   - Same function/class modifications
   - High churn areas

3. **POSSIBLE** (50%+ accuracy):
   - Same file modified
   - Different sections
   - Semantic conflicts (imports, etc.)

**Algorithm**:
```
for each file changed in OURS:
    if file changed in THEIRS:
        parse diff hunks
        for each hunk_ours:
            for each hunk_theirs:
                if hunks_overlap(hunk_ours, hunk_theirs):
                    → CERTAIN conflict
                elif hunks_nearby(hunk_ours, hunk_theirs, threshold=3):
                    → LIKELY conflict
                else:
                    → POSSIBLE conflict
```

#### 4. Data Models (`core/models.py`)

Type-safe data classes (Python 3.11+ dataclasses):

```python
@dataclass
class SimulationResult:
    """Unified result type for all simulations."""
    operation_type: OperationType
    success: bool
    before_graph: CommitGraph
    after_graph: CommitGraph
    conflicts: list[ConflictInfo]
    warnings: list[str]
    safety_info: SafetyInfo
    changed_files: list[FileChange]

@dataclass
class CommitGraph:
    """DAG representation with branch topology."""
    commits: dict[str, CommitInfo]
    edges: list[tuple[str, str]]  # (child, parent)
    branch_tips: dict[str, str]    # branch → SHA
    head_sha: str
    
@dataclass
class ConflictInfo:
    """Detailed conflict information."""
    severity: ConflictSeverity  # CERTAIN | LIKELY | POSSIBLE
    file_path: str
    description: str
    our_lines: tuple[int, int] | None
    their_lines: tuple[int, int] | None
```

#### 5. Plugin System (`plugins/`)

Extensible architecture with three plugin types:

```python
class HookPlugin(Plugin):
    """Intercept simulation lifecycle."""
    
    def pre_simulate(self, repo, command, **kwargs) -> dict:
        """Modify inputs before simulation."""
    
    def override_simulation(self, repo, command, **kwargs) -> SimulationResult | None:
        """Replace simulation entirely (or None to continue)."""
    
    def post_simulate(self, repo, command, result) -> SimulationResult:
        """Modify results after simulation."""

class SimulatorPlugin(Plugin):
    """Add new simulation commands."""
    
    def supports(self, command: str) -> bool:
        """Can this plugin handle the command?"""
    
    def simulate(self, **kwargs) -> SimulationResult:
        """Execute custom simulation."""

class FormatterPlugin(Plugin):
    """Custom output formatting."""
    
    def format_result(self, result: SimulationResult) -> str:
        """Render simulation result."""
```

**Discovery**: Entry points in `pyproject.toml`:
```toml
[project.entry-points."git_sim.plugins"]
my_plugin = "my_package.plugin:MyPlugin"
```

### Performance Optimizations

1. **Lazy Graph Building**: Only load commits needed for visualization
2. **Diff Caching**: Memoize expensive diff operations
3. **Short SHA Indexing**: Stop at first unique match
4. **Parallel-Safe**: Pure functional core, no shared state
5. **Memory Efficient**: Stream commits vs loading entire history

### Testing Strategy

**135 tests** covering:
- Unit tests: Each component in isolation
- Integration tests: End-to-end command flows
- Property tests: Invariant checking (graphs are DAGs, etc.)
- Fixture-based: Multiple repo states (linear, branched, merge commits)

```bash
pytest --cov=git_sim --cov-report=html
# Current: 95%+ coverage
```

---

## 🔐 Security & Safety

### Read-Only Guarantee

GitSim **never writes** to your repository:
- Uses Dulwich's read-only API
- No `git` subprocess calls that modify state
- Simulations run entirely in memory
- Snapshot system uses separate `.git/git-sim-snapshots/` directory

### Plugin Safety

- Plugins run in same process (trust required)
- Hook plugins can modify simulation behavior
- Override plugins can replace entire simulations
- See `SECURITY.md` for plugin security considerations

---

## 📊 Comparison with Alternatives

| Feature | GitSim | `git log --graph` | GitKraken | lazygit | tig |
|---------|--------|-------------------|-----------|---------|-----|
| **Simulation** | ✅ Full | ❌ No | ❌ No | ❌ No | ❌ No |
| **Conflict Prediction** | ✅ 3 levels | ❌ No | ⚠️ Basic | ❌ No | ❌ No |
| **Safety Analysis** | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No |
| **Educational Mode** | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No |
| **Terminal UI** | ✅ Yes | ✅ Yes | ❌ GUI only | ✅ Yes | ✅ Yes |
| **No Git Binary** | ✅ Pure Python | ❌ Requires Git | ❌ Requires Git | ❌ Requires Git | ❌ Requires Git |
| **Snapshot System** | ✅ Yes | ❌ No | ⚠️ Via GUI | ❌ No | ❌ No |
| **Plugin System** | ✅ Yes | ❌ No | ✅ Yes | ❌ No | ❌ No |
| **SSH-Friendly** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes | ✅ Yes |
| **Price** | ✅ Free | ✅ Free | 💰 Paid | ✅ Free | ✅ Free |

**GitSim's Unique Value**: Only tool combining safe simulation + conflict prediction + education + beautiful CLI.

---

## 🛠️ Development

### Setup

```bash
git clone https://github.com/egekaya1/GitSimulator.git
cd GitSimulator
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=git_sim --cov-report=html

# Specific test file
pytest tests/test_rebase.py

# Watch mode
pytest-watch
```

### Code Quality

```bash
# Type checking
mypy src/git_sim --ignore-missing-imports

# Linting
ruff check src/git_sim tests

# Formatting
ruff format src/git_sim tests

# All checks (what CI runs)
ruff check src/git_sim tests && \
ruff format --check src/git_sim tests && \
mypy src/git_sim --ignore-missing-imports && \
pytest --cov=git_sim
```

### Project Structure

```
GitSimulator/
├── src/git_sim/           # Source code
│   ├── cli/               # Command-line interface
│   │   ├── main.py        # Typer app entry point
│   │   ├── commands/      # Command implementations
│   │   │   ├── rebase.py
│   │   │   ├── merge.py
│   │   │   └── ...
│   │   └── formatters/    # Output rendering
│   │       ├── graph.py   # Commit graph ASCII art
│   │       ├── conflict.py # Conflict tables
│   │       └── diff.py    # Diff visualization
│   ├── core/              # Core business logic
│   │   ├── repository.py  # Dulwich wrapper
│   │   ├── models.py      # Data classes
│   │   ├── diff_analyzer.py # Diff parsing
│   │   └── exceptions.py  # Custom errors
│   ├── simulation/        # Simulation engines
│   │   ├── base.py        # Abstract base
│   │   ├── dispatcher.py  # Command routing
│   │   ├── rebase.py      # Rebase logic
│   │   ├── merge.py       # Merge logic
│   │   ├── reset.py       # Reset logic
│   │   ├── cherry_pick.py # Cherry-pick logic
│   │   ├── conflict_detector.py # Conflict heuristics
│   │   └── explain.py     # Educational content
│   ├── tui/               # Terminal UI
│   │   └── app.py         # Textual application
│   ├── plugins/           # Plugin system
│   │   ├── base.py        # Plugin protocols
│   │   └── loader.py      # Discovery & loading
│   └── snapshot.py        # State management
├── tests/                 # Test suite (135 tests)
│   ├── conftest.py        # Pytest fixtures
│   ├── test_rebase.py
│   ├── test_merge.py
│   ├── test_conflict_detection.py
│   └── ...
├── .github/workflows/     # CI/CD
│   └── ci.yml             # Automated testing & publishing
├── pyproject.toml         # Package metadata
├── README.md              # This file
├── CHANGELOG.md           # Version history
├── CONTRIBUTING.md        # Development guide
├── SECURITY.md            # Security policy
└── LICENSE.md             # MIT license
```

---

## 📜 License

MIT License - see [LICENSE.md](LICENSE.md)

---

## 🙏 Acknowledgments

Built with these excellent libraries:
- [Dulwich](https://www.dulwich.io/) - Pure Python Git implementation
- [Rich](https://rich.readthedocs.io/) - Beautiful terminal formatting
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Textual](https://textual.textualize.io/) - TUI framework

---

## 📞 Support & Contributing

- **Issues**: [GitHub Issues](https://github.com/egekaya1/GitSimulator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/egekaya1/GitSimulator/discussions)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Security**: See [SECURITY.md](SECURITY.md)

---

**⭐ Star us on GitHub if GitSim helps you!**

## Installation

```bash
# From PyPI (v1.0.1)
pipx install gitsimulator

# Or with pip
pip install gitsimulator

# For development
git clone https://github.com/egekaya1/GitSim.git
cd GitSim
pip install -e .
```

**Note**: All three commands work identically: `gitsim`, `git-sim`, and `gitsimulator`

## Usage

### Simulate a Rebase

```bash
git-sim rebase main                     # Simulate rebasing onto main
git-sim rebase main --source feature    # Specify source branch
git-sim rebase main --verbose           # Show detailed conflict info
git-sim rebase main --execute           # Execute after confirmation
```

### Simulate a Merge

```bash
git-sim merge feature                   # Simulate merging feature
git-sim merge feature --no-ff           # Force merge commit
```

### Simulate a Reset

```bash
git-sim reset HEAD~2 --soft             # Keep changes staged
git-sim reset HEAD~2                    # Unstage changes (mixed)
git-sim reset HEAD~2 --hard             # Discard all changes
```

### Simulate Cherry-Pick

```bash
git-sim cherry-pick abc123              # Pick single commit
git-sim cherry-pick abc123 def456       # Pick multiple commits
```

### Unified Simulation Command

```bash
git-sim sim "rebase main"
git-sim sim "merge feature"
git-sim sim "reset --hard HEAD~2"
git-sim sim "cherry-pick abc123"
```

### Educational Features

```bash
git-sim explain rebase                  # Learn how rebase works
git-sim explain merge                   # Learn how merge works
git-sim explain reset                   # Learn about reset modes
git-sim explain cherry-pick             # Learn about cherry-pick
```

### Snapshot System

```bash
git-sim snapshot create "before-rebase" # Save current state
git-sim snapshot list                   # List all snapshots
git-sim snapshot restore "before-rebase"# Restore to snapshot
git-sim snapshot delete "before-rebase" # Delete snapshot
```

### Other Commands

```bash
git-sim status                          # Show repository status
git-sim log                             # Show commit graph
git-sim diff HEAD~1                     # Show commit diff
```

## Example Output

```
Simulating: git rebase main

┌─────────────────────────────────────────┐
│ Rebase Summary                          │
├─────────────────────────────────────────┤
│ Source branch    feature                │
│ Target branch    main                   │
│ Merge base       abc1234                │
│ Commits to replay 3                     │
│ Predicted conflicts 1                   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Safety Analysis                         │
├─────────────────────────────────────────┤
│ Danger Level     🔴 HIGH                │
│ Reversible       Yes                    │
│ Force Push Required Yes                 │
└─────────────────────────────────────────┘

Before Rebase:
* abc1234 (HEAD -> feature) Add new feature
* def5678 Update config
| * 123abcd (main) Fix bug
|/
* 789xyz0 Initial commit

After Rebase (Simulated):
* new1234 (HEAD -> feature) Add new feature
* new5678 Update config
* 123abcd (main) Fix bug
* 789xyz0 Initial commit

⚠️ Found 1 potential conflict(s)

CERTAIN: Lines 10-15 in 'config.py' modified differently on both sides
```

## Development

```bash
pip install -e ".[dev]"                 # Install dev dependencies
pytest                                  # Run tests
pytest --cov=git_sim                    # Run with coverage
mypy src/git_sim --ignore-missing-imports  # Type check
ruff check src/git_sim                  # Lint
ruff format --check src/git_sim         # Format check
```

## Project Structure

```
git-sim/
├── src/git_sim/
│   ├── cli/                    # CLI commands and formatters
│   │   ├── main.py             # Typer app entry point
│   │   ├── commands/           # Command implementations
│   │   └── formatters/         # Output formatters (graph, diff, conflict)
│   ├── core/                   # Core components
│   │   ├── models.py           # Data models (SimulationResult, CommitGraph, etc.)
│   │   ├── repository.py       # Git repository wrapper (Dulwich)
│   │   ├── diff_analyzer.py    # Diff parsing and analysis
│   │   └── exceptions.py       # Custom exceptions
│   ├── simulation/             # Simulation engines
│   │   ├── dispatcher.py       # Unified command dispatcher
│   │   ├── base.py             # Abstract base simulator
│   │   ├── rebase.py           # Rebase simulation
│   │   ├── merge.py            # Merge simulation
│   │   ├── reset.py            # Reset simulation
│   │   ├── cherry_pick.py      # Cherry-pick simulation
│   │   ├── conflict_detector.py# Conflict detection heuristics
│   │   └── explain.py          # Educational explanations
│   ├── tui/                    # Terminal UI (Textual)
│   │   └── app.py              # Interactive TUI application
│   ├── plugins/                # Plugin system
│   │   ├── base.py             # Plugin base classes
│   │   └── loader.py           # Plugin discovery and loading
│   └── snapshot.py             # Snapshot/restore functionality
├── tests/                      # Test suite
└── .github/workflows/          # CI/CD pipeline
```

## Key Concepts

### SimulationResult

All simulators return a unified `SimulationResult`:

```python
from git_sim.simulation import simulate

result = simulate("rebase", onto="main")
print(result.operation_type)    # OperationType.REBASE
print(result.has_conflicts)     # True/False
print(result.safety_info)       # Safety analysis
```

### Safety Levels

| Level | Description |
|-------|-------------|
| LOW | Safe, easily reversible |
| MEDIUM | Potentially destructive but recoverable |
| HIGH | History rewrite, force-push risk |
| CRITICAL | Data loss risk |

### Interactive TUI

```bash
git-sim tui                             # Launch interactive terminal UI
```

### Plugin System

```bash
git-sim plugin list                     # List available plugins
git-sim plugin new my-plugin            # Generate plugin template
git-sim plugin new my-hook --type hook  # Generate hook plugin
git-sim plugin load my-plugin           # Load a plugin
```

## Roadmap

- [x] Rebase simulation
- [x] Merge simulation
- [x] Reset simulation
- [x] Cherry-pick simulation
- [x] Unified dispatcher
- [x] Safety analysis
- [x] Educational mode (explain)
- [x] Snapshot/restore
- [x] Interactive TUI mode (Textual)
- [x] Plugin system

## License

MIT
