"""Base classes for git-sim simulators."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from git_sim.core.exceptions import SimulationError
from git_sim.core.repository import Repository

T = TypeVar("T")  # Simulation result type


class BaseSimulator(ABC, Generic[T]):
    """
    Abstract base class for all Git operation simulators.

    Provides a common interface and validation pattern for
    simulating Git operations.
    """

    def __init__(self, repo: Repository):
        """
        Initialize the simulator.

        Args:
            repo: Repository wrapper instance.
        """
        self.repo = repo
        self._validated = False
        self._validation_errors: list[str] = []
        self._validation_warnings: list[str] = []

    @abstractmethod
    def simulate(self) -> T:
        """
        Execute the simulation and return results.

        This method should be implemented by subclasses to perform
        the actual simulation logic.

        Returns:
            Simulation result of type T.
        """
        pass

    @abstractmethod
    def validate(self) -> tuple[list[str], list[str]]:
        """
        Validate preconditions for the simulation.

        Returns:
            Tuple of (errors, warnings). If errors is non-empty,
            the simulation should not proceed.
        """
        pass

    def run(self) -> T:
        """
        Validate preconditions and run the simulation.

        Returns:
            Simulation result of type T.

        Raises:
            SimulationError: If validation fails.
        """
        errors, warnings = self.validate()
        self._validation_errors = errors
        self._validation_warnings = warnings

        if errors:
            raise SimulationError(
                f"Validation failed: {'; '.join(errors)}"
            )

        self._validated = True
        return self.simulate()

    @property
    def warnings(self) -> list[str]:
        """Get validation warnings after running validate()."""
        return self._validation_warnings
