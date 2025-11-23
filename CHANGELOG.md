# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and uses semantic versioning.

## [Unreleased]

## [0.1.0] - 2025-11-23

### 🎉 Initial Release

**Git-Sim** is a Git simulation and visualization engine that lets you dry-run dangerous Git commands with visual feedback before executing them.

### ✨ Core Features

#### Simulation Commands
- **Rebase Simulation** (`gitsim rebase`) - Simulate rebasing branches with conflict prediction
- **Merge Simulation** (`gitsim merge`) - Preview merge operations before execution
- **Reset Simulation** (`gitsim reset`) - Test reset operations (--soft, --mixed, --hard) safely
- **Cherry-Pick Simulation** (`gitsim cherry-pick`) - Preview cherry-picking commits with conflict detection
- **Unified Simulator** (`gitsim sim`) - Simulate any Git command using unified syntax

#### Visualization & Analysis
- **Status Display** (`gitsim status`) - Rich repository status with branch information
- **Commit Log** (`gitsim log`) - Visual commit graph with color-coded output
- **Diff Viewer** (`gitsim diff`) - Beautiful diff visualization with file change tables
- **Explain Mode** (`gitsim explain`) - Educational explanations of how Git commands work internally

#### Advanced Features
- **Snapshot System** (`gitsim snapshot`) - Save and restore repository states for exploration
  - Create, list, restore, and delete snapshots
  - Useful for experimental workflows
- **Plugin System** (`gitsim plugin`) - Extensible architecture for custom functionality
  - Hook plugins (pre/post simulation, override capabilities)
  - Simulator plugins
  - Formatter plugins
  - Plugin discovery via entry points
- **Interactive TUI** (`gitsim tui`) - Terminal user interface powered by Textual
  - Headless simulation mode for scripting
  - Interactive exploration (requires textual extra)

### 🔍 Technical Features

#### Safety & Analysis
- **Conflict Detection** - Sophisticated heuristics for predicting merge conflicts
  - CERTAIN: High confidence conflicts (same lines modified)
  - LIKELY: Nearby modifications (within 3 lines)
  - POSSIBLE: Same file modifications
- **Safety Ratings** - Danger level analysis (LOW, MEDIUM, HIGH, CRITICAL)
  - Reversibility checks
  - Force-push requirements
  - Data loss risk assessment
- **Before/After Graphs** - Visual representation of repository state changes
- **Recovery Suggestions** - Actionable advice for undoing operations

#### Architecture
- **Read-Only Operations** - All simulations are non-destructive
- **Dulwich Backend** - Pure Python Git implementation (no git binary required)
- **Type-Safe** - Full type annotations with mypy strict mode
- **Modular Design** - Clean separation of concerns
  - `core/` - Repository access, models, diff analysis
  - `simulation/` - Simulation engines for each operation
  - `cli/` - Command-line interface and formatters
  - `plugins/` - Plugin system and loader
  - `tui/` - Terminal user interface

### 🎨 User Experience

#### Rich Terminal Output
- Color-coded commit graphs using Rich library
- Beautiful tables for file changes and conflicts
- Box drawings for summaries and safety analysis
- Progress indicators and status messages

#### Multiple Interfaces
- **CLI Commands** - Individual commands for each operation
- **Unified Interface** - `gitsim sim "command"` for any Git command
- **TUI Mode** - Interactive terminal interface
- **Programmatic API** - Use as a library in Python scripts

### 📦 Installation

```bash
# Basic installation
pip install gitsimulator

# With TUI support
pip install gitsimulator[tui]

# Development installation
pip install gitsimulator[dev]

# All features
pip install gitsimulator[all]
```

### 🔧 Command-Line Interface

Both `git-sim` and `gitsim` entry points are available:

```bash
gitsim --version              # Show version
gitsim --help                 # Show help
gitsim rebase main            # Simulate rebase
gitsim merge feature          # Simulate merge
gitsim reset HEAD~2 --hard    # Simulate hard reset
gitsim cherry-pick abc123     # Simulate cherry-pick
gitsim explain rebase         # Learn about rebase
gitsim snapshot create backup # Create snapshot
gitsim tui                    # Launch TUI
```

### 🧪 Testing

- **135 unit tests** covering all core functionality
- **pytest** test suite with coverage support
- **Type checking** with mypy
- **Linting** with ruff
- Test fixtures for various repository states

### 📚 Documentation

- Comprehensive README with examples
- Inline code documentation and docstrings
- Type annotations throughout
- CONTRIBUTING.md for development guidelines
- SECURITY.md for security considerations

### 🔐 Security

- All operations are read-only and safe by default
- Plugin system documented with security considerations
- No modification of repository unless explicitly requested with `--execute` flag

### ⚙️ Requirements

- Python 3.11 or higher
- Core dependencies:
  - dulwich >= 0.21.0 (Git implementation)
  - rich >= 13.0.0 (Terminal formatting)
  - typer >= 0.9.0 (CLI framework)
- Optional dependencies:
  - textual >= 0.40.0 (TUI support)

### 🐛 Known Issues

None at this time.

### 🙏 Acknowledgments

Built with:
- [Dulwich](https://www.dulwich.io/) - Pure Python Git implementation
- [Rich](https://rich.readthedocs.io/) - Beautiful terminal formatting
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Textual](https://textual.textualize.io/) - TUI framework

---

**Full Changelog**: https://github.com/egekaya1/GitSimulator/commits/v0.1.0
