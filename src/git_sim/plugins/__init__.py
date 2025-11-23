"""Plugin system for git-sim."""

from git_sim.plugins.base import Plugin, PluginManager, PluginType
from git_sim.plugins.loader import discover_plugins, load_plugin

__all__ = [
    "Plugin",
    "PluginManager",
    "PluginType",
    "discover_plugins",
    "load_plugin",
]
