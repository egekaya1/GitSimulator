"""Textual TUI for git-sim."""

try:
    from git_sim.tui.app import GitSimApp, run_tui

    __all__ = ["GitSimApp", "run_tui"]
except ImportError:  # pragma: no cover - optional dependency path

    def run_tui(repo_path: str = ".") -> None:
        """Run the TUI if textual is installed (placeholder when missing)."""
        raise ImportError("TUI requires textual. Install with: pip install git-sim[tui]")

    __all__ = ["run_tui"]
