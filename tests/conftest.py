"""Pytest fixtures for git-sim tests."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from git_sim.core.repository import Repository


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    path = Path(tempfile.mkdtemp())
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def git_repo(temp_dir: Path) -> Generator[Path, None, None]:
    """
    Create a temporary Git repository with a basic commit history.

    Structure:
    - main branch with 3 commits
    - Initial commit, add file A, add file B
    """
    repo_path = temp_dir / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Second commit
    (repo_path / "file_a.txt").write_text("Content A\nLine 2\nLine 3\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add file A"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Third commit
    (repo_path / "file_b.txt").write_text("Content B\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add file B"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    yield repo_path


@pytest.fixture
def branched_repo(git_repo: Path) -> Generator[Path, None, None]:
    """
    Create a repository with a feature branch.

    Structure:
        * (feature) Add feature file
        * (feature) Modify file A
        | * (main) Update README
        |/
        * Add file B
        * Add file A
        * Initial commit
    """
    # Create feature branch from current HEAD
    subprocess.run(
        ["git", "checkout", "-b", "feature"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    # Add commits on feature branch
    (git_repo / "file_a.txt").write_text("Modified A\nLine 2\nLine 3\nLine 4\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Modify file A"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    (git_repo / "feature.txt").write_text("Feature content\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add feature file"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    # Go back to main and add a commit
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    (git_repo / "README.md").write_text("# Test Repo\n\nUpdated readme.\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Update README"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    yield git_repo


@pytest.fixture
def conflict_repo(git_repo: Path) -> Generator[Path, None, None]:
    """
    Create a repository with conflicting changes.

    Both main and feature modify the same lines in file_a.txt.
    """
    # Create feature branch
    subprocess.run(
        ["git", "checkout", "-b", "feature"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    # Modify file A on feature
    (git_repo / "file_a.txt").write_text("Feature version\nLine 2\nLine 3\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Feature changes to A"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    # Go back to main and modify same file differently
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    (git_repo / "file_a.txt").write_text("Main version\nLine 2\nLine 3\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Main changes to A"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    yield git_repo


@pytest.fixture
def repository(git_repo: Path) -> Repository:
    """Create a Repository wrapper for the test repo."""
    return Repository(git_repo)


@pytest.fixture
def branched_repository(branched_repo: Path) -> Repository:
    """Create a Repository wrapper for the branched test repo."""
    return Repository(branched_repo)


@pytest.fixture
def conflict_repository(conflict_repo: Path) -> Repository:
    """Create a Repository wrapper for the conflict test repo."""
    return Repository(conflict_repo)
