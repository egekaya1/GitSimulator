"""Base classes for git-sim plugin system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from git_sim.core.models import SimulationResult
from git_sim.core.repository import Repository


class PluginType(Enum):
    """Types of plugins supported."""

    SIMULATOR = auto()  # Custom simulation engines
    FORMATTER = auto()  # Custom output formatters
    HOOK = auto()  # Pre/post simulation hooks
    COMMAND = auto()  # Custom CLI commands


@dataclass
class PluginMetadata:
    """Metadata about a plugin."""

    name: str
    version: str
    description: str
    author: str = ""
    plugin_type: PluginType = PluginType.SIMULATOR
    dependencies: list[str] = field(default_factory=list)


class Plugin(ABC):
    """Base class for all git-sim plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        ...

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with optional configuration."""
        pass

    def cleanup(self) -> None:
        """Cleanup when plugin is unloaded."""
        pass


class SimulatorPlugin(Plugin):
    """Base class for custom simulator plugins."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.__class__.__name__,
            version="0.1.0",
            description="Custom simulator plugin",
            plugin_type=PluginType.SIMULATOR,
        )

    @abstractmethod
    def can_handle(self, command: str) -> bool:
        """Return True if this plugin can handle the given command."""
        ...

    @abstractmethod
    def simulate(self, repo: Repository, **kwargs: Any) -> SimulationResult:
        """Run the simulation and return results."""
        ...


class FormatterPlugin(Plugin):
    """Base class for custom output formatter plugins."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.__class__.__name__,
            version="0.1.0",
            description="Custom formatter plugin",
            plugin_type=PluginType.FORMATTER,
        )

    @abstractmethod
    def format(self, result: SimulationResult) -> str:
        """Format the simulation result for output."""
        ...


class HookPlugin(Plugin):
    """Base class for pre/post simulation hook plugins."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.__class__.__name__,
            version="0.1.0",
            description="Hook plugin",
            plugin_type=PluginType.HOOK,
        )

    def pre_simulate(self, repo: Repository, command: str, **kwargs: Any) -> dict[str, Any]:
        """Called before simulation. Can modify kwargs."""
        return kwargs

    def post_simulate(
        self, repo: Repository, command: str, result: SimulationResult
    ) -> SimulationResult:
        """Called after simulation. Can modify result."""
        return result


@dataclass
class PluginRegistry:
    """Registry of loaded plugins by type."""

    simulators: dict[str, SimulatorPlugin] = field(default_factory=dict)
    formatters: dict[str, FormatterPlugin] = field(default_factory=dict)
    hooks: list[HookPlugin] = field(default_factory=list)
    commands: dict[str, Callable[..., Any]] = field(default_factory=dict)


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self) -> None:
        self._registry = PluginRegistry()
        self._plugins: dict[str, Plugin] = {}

    @property
    def registry(self) -> PluginRegistry:
        """Get the plugin registry."""
        return self._registry

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        meta = plugin.metadata
        self._plugins[meta.name] = plugin

        if isinstance(plugin, SimulatorPlugin):
            self._registry.simulators[meta.name] = plugin
        elif isinstance(plugin, FormatterPlugin):
            self._registry.formatters[meta.name] = plugin
        elif isinstance(plugin, HookPlugin):
            self._registry.hooks.append(plugin)

    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name."""
        if name not in self._plugins:
            return False

        plugin = self._plugins.pop(name)
        plugin.cleanup()

        if isinstance(plugin, SimulatorPlugin):
            self._registry.simulators.pop(name, None)
        elif isinstance(plugin, FormatterPlugin):
            self._registry.formatters.pop(name, None)
        elif isinstance(plugin, HookPlugin):
            self._registry.hooks = [h for h in self._registry.hooks if h.metadata.name != name]

        return True

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self, plugin_type: PluginType | None = None) -> list[PluginMetadata]:
        """List all registered plugins, optionally filtered by type."""
        plugins = list(self._plugins.values())
        if plugin_type is not None:
            plugins = [p for p in plugins if p.metadata.plugin_type == plugin_type]
        return [p.metadata for p in plugins]

    def find_simulator(self, command: str) -> SimulatorPlugin | None:
        """Find a simulator plugin that can handle the given command."""
        for simulator in self._registry.simulators.values():
            if simulator.can_handle(command):
                return simulator
        return None

    def run_pre_hooks(
        self, repo: Repository, command: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Run all pre-simulation hooks."""
        for hook in self._registry.hooks:
            kwargs = hook.pre_simulate(repo, command, **kwargs)
        return kwargs

    def run_post_hooks(
        self, repo: Repository, command: str, result: SimulationResult
    ) -> SimulationResult:
        """Run all post-simulation hooks."""
        for hook in self._registry.hooks:
            result = hook.post_simulate(repo, command, result)
        return result


# Global plugin manager instance
_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get or create the global plugin manager."""
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager
