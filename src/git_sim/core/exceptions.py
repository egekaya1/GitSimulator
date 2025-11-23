"""Custom exceptions for git-sim."""


class GitSimError(Exception):
    """Base exception for git-sim errors."""

    pass


class RepositoryError(GitSimError):
    """Error related to repository operations."""

    pass


class NotARepositoryError(RepositoryError):
    """Raised when path is not a Git repository."""

    pass


class RefNotFoundError(RepositoryError):
    """Raised when a ref (branch, tag, SHA) cannot be found."""

    def __init__(self, ref: str):
        self.ref = ref
        super().__init__(f"Reference not found: {ref}")


class SimulationError(GitSimError):
    """Error during simulation."""

    pass


class InvalidOperationError(SimulationError):
    """Raised when the requested operation is invalid."""

    pass
