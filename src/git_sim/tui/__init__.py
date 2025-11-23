"""Textual TUI for git-sim."""

try:
    from git_sim.tui.app import GitSimApp, run_tui

    __all__ = ["GitSimApp", "run_tui"]
except ImportError:
    # Textual not installed
    def run_tui(*args, **kwargs):
        raise ImportError(
            "TUI requires textual. Install with: pip install git-sim[tui]"
        )

    __all__ = ["run_tui"]
