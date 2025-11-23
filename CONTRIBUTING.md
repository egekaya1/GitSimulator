# Contributing to Git-Sim

Thanks for your interest in contributing! This guide explains how to set up a development environment, run tests, follow style guidelines, and create plugins.

## Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/egekaya1/GitSim.git
   cd GitSim
   ```
2. Create virtual environment (Python 3.11+):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -e .[dev,tui]
   ```

## Running Tests & Type Checks

```bash
pytest -v
pytest --cov=src/git_sim --cov-report=term-missing
mypy --strict src/git_sim
ruff check src/git_sim
```

## Style Guidelines

- Use Ruff for linting (configured in `pyproject.toml`).
- Line length: 100.
- Prefer explicit typing; `mypy --strict` must pass.
- Avoid overly clever one-liners; clarity first.
- Keep patches focused: do not refactor unrelated code.

## Plugin Development

Git-Sim supports external plugins via entry points under `git_sim.plugins`.

### Creating a Plugin Template
```bash
python -m git_sim.plugins.loader create_template --name your-plugin --type simulator
```
(Or manually copy from examples in `loader.py`.)

Add to `pyproject.toml` of your plugin:
```toml
[project.entry-points."git_sim.plugins"]
your-plugin = "your_package.module:YourPluginClass"
```

### Hook & Override Behavior
- `HookPlugin.pre_simulate(repo, command, **kwargs)` can mutate args.
- `HookPlugin.override_simulation(repo, command, **kwargs)` returning a `SimulationResult` short-circuits default execution.
- `HookPlugin.post_simulate(repo, command, result)` can adjust final result.
- First override wins; all post hooks still run.

### Simulator Plugins
Implement:
```python
class MySimulator(SimulatorPlugin):
    def can_handle(self, command: str) -> bool: ...
    def simulate(self, repo: Repository, **kwargs) -> SimulationResult: ...
```

## Branching & Releases

- Use feature branches: `feat/...`, `fix/...`, `docs/...`, `refactor/...`.
- Keep `main` green (tests + mypy + ruff passing).
- Update `CHANGELOG.md` for user-facing changes.

## Commit Messages

Follow Conventional Commits where possible:
- `feat: add cherry-pick conflict aggregation`
- `fix: handle empty tree diff edge case`
- `docs: clarify plugin override semantics`

## Reporting Issues / Security

See `SECURITY.md` for reporting guidelines.

## Code of Conduct

Be respectful. Provide constructive feedback. Assume positive intent.

Thank you for improving Git-Sim!