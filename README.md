# Git-Sim

Git simulation and visualization engine - dry run dangerous Git commands with visual feedback.

[![CI](https://github.com/your-org/git-sim/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/git-sim/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Safe Simulation**: Analyze Git operations without modifying your repository
- **Conflict Prediction**: Detect potential merge conflicts before they happen
- **Visual Feedback**: ASCII commit graphs showing before/after states
- **Multiple Operations**: Simulate rebase, merge, reset, and cherry-pick
- **Safety Analysis**: Danger level ratings and recovery suggestions
- **Educational Mode**: Learn how Git commands work internally
- **Snapshot System**: Save and restore repository states for exploration

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/git-sim.git
cd git-sim

# Install in development mode
pip install -e ".[dev]"

# Or with all extras (including TUI)
pip install -e ".[all]"
```

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
