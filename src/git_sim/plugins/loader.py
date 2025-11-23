"""Plugin discovery and loading utilities."""

import importlib.metadata
import logging
from typing import Any

from git_sim.plugins.base import Plugin, PluginManager, get_plugin_manager

logger = logging.getLogger(__name__)

# Entry point group name for git-sim plugins
ENTRY_POINT_GROUP = "git_sim.plugins"


def discover_plugins() -> list[tuple[str, str]]:
    """
    Discover available plugins via entry points.

    Returns a list of (name, module_path) tuples for available plugins.
    """
    plugins: list[tuple[str, str]] = []

    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        for ep in eps:
            plugins.append((ep.name, ep.value))
    except Exception as e:
        logger.warning(f"Error discovering plugins: {e}")

    return plugins


def load_plugin(
    name: str,
    config: dict[str, Any] | None = None,
    manager: PluginManager | None = None,
) -> Plugin | None:
    """
    Load a plugin by entry point name.

    Args:
        name: The entry point name of the plugin
        config: Optional configuration dict to pass to the plugin
        manager: Optional plugin manager (uses global if not provided)

    Returns:
        The loaded plugin instance, or None if loading failed
    """
    if manager is None:
        manager = get_plugin_manager()

    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        matching = [ep for ep in eps if ep.name == name]

        if not matching:
            logger.warning(f"Plugin not found: {name}")
            return None

        ep = matching[0]
        plugin_class = ep.load()

        # Instantiate and initialize
        plugin: Plugin = plugin_class()
        plugin.initialize(config)

        # Register with manager
        manager.register(plugin)

        logger.info(f"Loaded plugin: {plugin.metadata.name} v{plugin.metadata.version}")
        return plugin

    except Exception as e:
        logger.error(f"Error loading plugin {name}: {e}")
        return None


def load_all_plugins(
    config: dict[str, dict[str, Any]] | None = None,
    manager: PluginManager | None = None,
) -> list[Plugin]:
    """
    Discover and load all available plugins.

    Args:
        config: Optional dict mapping plugin names to their configs
        manager: Optional plugin manager (uses global if not provided)

    Returns:
        List of successfully loaded plugins
    """
    if manager is None:
        manager = get_plugin_manager()

    config = config or {}
    loaded: list[Plugin] = []

    for name, _ in discover_plugins():
        plugin_config = config.get(name)
        plugin = load_plugin(name, plugin_config, manager)
        if plugin:
            loaded.append(plugin)

    return loaded


def create_plugin_template(
    name: str,
    plugin_type: str = "simulator",
    output_dir: str = ".",
) -> str:
    """
    Generate a plugin template file.

    Args:
        name: Name for the new plugin
        plugin_type: Type of plugin (simulator, formatter, hook)
        output_dir: Directory to write the template to

    Returns:
        Path to the generated file
    """
    templates = {
        "simulator": '''"""Example simulator plugin for git-sim."""

from typing import Any

from git_sim.core.models import (
    CommitGraph,
    DangerLevel,
    OperationType,
    SafetyInfo,
    SimulationResult,
)
from git_sim.core.repository import Repository
from git_sim.plugins.base import PluginMetadata, PluginType, SimulatorPlugin


class {class_name}(SimulatorPlugin):
    """Custom simulator plugin."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="{name}",
            version="0.1.0",
            description="Custom simulation for {name}",
            author="Your Name",
            plugin_type=PluginType.SIMULATOR,
        )

    def can_handle(self, command: str) -> bool:
        """Check if this plugin handles the command."""
        return command.startswith("{name}")

    def simulate(self, repo: Repository, **kwargs: Any) -> SimulationResult:
        """Run the custom simulation."""
        # Build before graph
        before_graph = repo.build_graph([repo.head_sha], max_commits=20)

        # TODO: Implement your simulation logic here
        after_graph = before_graph  # Modify as needed

        return SimulationResult(
            operation_type=OperationType.REBASE,  # Or create custom
            success=True,
            before_graph=before_graph,
            after_graph=after_graph,
            conflicts=[],
            commits_affected=[],
            commits_created=[],
            safety_info=SafetyInfo(
                danger_level=DangerLevel.LOW,
                reversible=True,
                requires_force_push=False,
                data_loss_risk=False,
            ),
        )
''',
        "formatter": '''"""Example formatter plugin for git-sim."""

from git_sim.core.models import SimulationResult
from git_sim.plugins.base import FormatterPlugin, PluginMetadata, PluginType


class {class_name}(FormatterPlugin):
    """Custom output formatter plugin."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="{name}",
            version="0.1.0",
            description="Custom formatter: {name}",
            author="Your Name",
            plugin_type=PluginType.FORMATTER,
        )

    def format(self, result: SimulationResult) -> str:
        """Format simulation result."""
        lines = [
            f"Operation: {{result.operation_type.name}}",
            f"Success: {{result.success}}",
            f"Conflicts: {{result.conflict_count}}",
        ]
        return "\\n".join(lines)
''',
        "hook": '''"""Example hook plugin for git-sim."""

from typing import Any

from git_sim.core.models import SimulationResult
from git_sim.core.repository import Repository
from git_sim.plugins.base import HookPlugin, PluginMetadata, PluginType


class {class_name}(HookPlugin):
    """Custom hook plugin."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="{name}",
            version="0.1.0",
            description="Custom hook: {name}",
            author="Your Name",
            plugin_type=PluginType.HOOK,
        )

    def pre_simulate(
        self, repo: Repository, command: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Called before simulation."""
        print(f"[{name}] Pre-simulation hook for: {{command}}")
        return kwargs

    def post_simulate(
        self, repo: Repository, command: str, result: SimulationResult
    ) -> SimulationResult:
        """Called after simulation."""
        print(f"[{name}] Post-simulation: {{result.operation_type.name}}")
        return result
''',
    }

    if plugin_type not in templates:
        raise ValueError(f"Unknown plugin type: {plugin_type}")

    # Generate class name from plugin name
    class_name = "".join(word.capitalize() for word in name.replace("-", "_").split("_"))
    class_name += "Plugin"

    content = templates[plugin_type].format(name=name, class_name=class_name)

    from pathlib import Path

    output_path = Path(output_dir) / f"{name.replace('-', '_')}_plugin.py"
    output_path.write_text(content)

    return str(output_path)
