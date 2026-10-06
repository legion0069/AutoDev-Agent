"""
context_builder.py - Context Builder for AutoDev

Responsible for aggregating project metadata, active development state,
directory structure, and existing codebase files into a unified context
dictionary for the CoderAgent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Directories to ignore during scanning
DEFAULT_IGNORED_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "target",
    "dist",
    "build",
    ".pytest_cache",
    ".idea",
    ".vscode",
}

# Common binary file extensions to skip
BINARY_EXTENSIONS: Set[str] = {
    ".pyc", ".pyd", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".sqlite", ".sqlite3", ".db", ".wasm",
}


def is_text_file(file_path: Path, block_size: int = 1024) -> bool:
    """
    Determines whether a file is text-based by checking extension and byte content.

    Args:
        file_path: Path to the target file.
        block_size: Number of initial bytes to inspect for null characters.

    Returns:
        True if the file is text-based, False if binary or unreadable.
    """
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return False

    try:
        with open(file_path, "rb") as f:
            chunk = f.read(block_size)
            # Binary files typically contain null bytes
            if b"\x00" in chunk:
                return False
        return True
    except (OSError, PermissionError):
        return False


class ContextBuilder:
    """
    Collects and synthesizes project plan data, state tracking, and workspace
    files into a structured context dictionary.
    """

    def __init__(
        self,
        plan_path: str | Path = "memory/project_plan.json",
        state_path: str | Path = "memory/state.json",
        project_root: Optional[str | Path] = None,
        ignored_dirs: Optional[Set[str]] = None,
        max_file_size_bytes: int = 1_000_000,
    ) -> None:
        """
        Initializes the ContextBuilder.

        Args:
            plan_path: Path to memory/project_plan.json.
            state_path: Path to memory/state.json.
            project_root: Root directory of the target project workspace.
            ignored_dirs: Set of directory names to ignore during scanning.
            max_file_size_bytes: Maximum size of text file to load into memory (default: 1MB).
        """
        self.plan_path = Path(plan_path)
        self.state_path = Path(state_path)
        self.project_root = Path(project_root) if project_root else None
        self.ignored_dirs = ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS
        self.max_file_size_bytes = max_file_size_bytes

    def load_project_plan(self) -> Dict[str, Any]:
        """
        Loads and returns the project plan from memory/project_plan.json.
        """
        if not self.plan_path.is_file():
            raise FileNotFoundError(f"Project plan file not found at '{self.plan_path}'.")

        with open(self.plan_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_state(self) -> Dict[str, Any]:
        """
        Loads and returns the execution state from memory/state.json.
        """
        if not self.state_path.is_file():
            return {
                "current_day": 0,
                "completed_phases": [],
                "status": "initialized",
            }

        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def scan_project_workspace(
        self,
        target_dir: Optional[Path] = None,
    ) -> tuple[List[str], Dict[str, str]]:
        """
        Scans the project directory tree and loads all text-based files.

        Args:
            target_dir: Optional override for the target workspace root.

        Returns:
            A tuple of (directory_tree_relative_paths, project_files_dict).
        """
        root = target_dir or self.project_root
        directory_tree: List[str] = []
        project_files: Dict[str, str] = {}

        if root is None or not root.exists() or not root.is_dir():
            return directory_tree, project_files

        for current_root, dirs, files in os.walk(root):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]

            rel_root = Path(current_root).relative_to(root)

            for directory in sorted(dirs):
                rel_dir_path = (rel_root / directory).as_posix()
                directory_tree.append(f"{rel_dir_path}/")

            for file_name in sorted(files):
                file_path = Path(current_root) / file_name
                rel_file_path = (rel_root / file_name).as_posix()

                directory_tree.append(rel_file_path)

                # Skip non-text files or files exceeding max size limit
                if not is_text_file(file_path):
                    continue

                try:
                    if file_path.stat().st_size <= self.max_file_size_bytes:
                        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                            project_files[rel_file_path] = f.read()
                except (OSError, PermissionError):
                    continue

        return directory_tree, project_files

    def build(self, project_root: Optional[str | Path] = None) -> Dict[str, Any]:
        """
        Builds and returns the complete context dictionary.

        Args:
            project_root: Optional directory override for the project codebase.

        Returns:
            Structured dictionary containing all project metadata, phases,
            workspace directory tree, and file contents.
        """
        target_root = Path(project_root) if project_root else self.project_root

        plan = self.load_project_plan()
        state = self.load_state()

        project_name = plan.get("project_name", "")
        description = plan.get("project_description", "")
        technology_stack = plan.get("technology_stack", "")
        phases = plan.get("phases", [])

        # Determine current active day
        raw_current_day = state.get("current_day", 0)
        # If current_day is 0 (unstarted), default active phase to Day 1
        current_day = raw_current_day if raw_current_day > 0 else 1

        # Extract current phase object
        current_phase: Dict[str, Any] = {}
        for phase in phases:
            if phase.get("day") == current_day:
                current_phase = phase
                break

        completed_phases: List[Any] = state.get("completed_phases", [])

        # Scan directory tree and source files
        directory_tree, project_files = self.scan_project_workspace(target_dir=target_root)

        context: Dict[str, Any] = {
            "project_name": project_name,
            "description": description,
            "technology_stack": technology_stack,
            "current_day": current_day,
            "current_phase": current_phase,
            "completed_phases": completed_phases,
            "directory_tree": directory_tree,
            "project_files": project_files,
        }

        return context


def build_context(
    project_root: Optional[str | Path] = None,
    plan_path: str | Path = "memory/project_plan.json",
    state_path: str | Path = "memory/state.json",
) -> Dict[str, Any]:
    """
    Convenience function to build and return the complete project context.

    Args:
        project_root: Optional project workspace directory.
        plan_path: Path to memory/project_plan.json.
        state_path: Path to memory/state.json.

    Returns:
        Structured context dictionary.
    """
    builder = ContextBuilder(
        plan_path=plan_path,
        state_path=state_path,
        project_root=project_root,
    )
    return builder.build()


if __name__ == "__main__":
    # Self-test / demonstration
    ctx = build_context(project_root=Path.cwd())
    print("Built Context Keys:", list(ctx.keys()))
    print(f"Project Name      : {ctx['project_name']}")
    print(f"Current Day       : {ctx['current_day']}")
    print(f"Current Phase     : {ctx['current_phase'].get('phase_name', 'None')}")
    print(f"Total Files Scanned: {len(ctx['project_files'])}")
    print(f"Directory Entries : {len(ctx['directory_tree'])}")
