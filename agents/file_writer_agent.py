"""
file_writer_agent.py - File Writer Agent for AutoDev

Responsible for safely materializing validated source code files generated
by CoderAgent onto the local filesystem within a sandboxed project workspace.
"""

from __future__ import annotations

import logging
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.coder_agent import GeneratedFile, GeneratedResult

# Module logger
logger = logging.getLogger("AutoDev.FileWriterAgent")


class FileWriterError(Exception):
    """Base exception for file writing failures."""
    pass


class PathTraversalError(FileWriterError):
    """Raised when a file path attempts to escape the designated project workspace."""
    pass


@dataclass
class WriteResult:
    """
    Summary of file writing operations performed by FileWriterAgent.
    """
    files_written: List[str] = field(default_factory=list)
    files_skipped: List[str] = field(default_factory=list)
    backups_created: List[str] = field(default_factory=list)
    failed_files: Dict[str, str] = field(default_factory=dict)
    success: bool = True
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to a serializable dictionary."""
        return asdict(self)


class FileWriterAgent:
    """
    Safely writes validated GeneratedResult files into a target project directory.

    Features:
    - Path traversal sandbox security
    - Automatic nested directory creation
    - Content-based identical file skip
    - Optional .bak backup creation before overwriting
    - Fine-grained WriteResult telemetry
    """

    def __init__(
        self,
        project_root: str | Path = "projects",
        overwrite_existing: bool = True,
        create_backups: bool = False,
    ) -> None:
        """
        Initializes the FileWriterAgent.

        Args:
            project_root: Root directory of the target project workspace.
            overwrite_existing: Whether to overwrite existing files with different content.
            create_backups: Whether to create a .bak backup file before overwriting.
        """
        self.project_root = Path(project_root).resolve()
        self.overwrite_existing = overwrite_existing
        self.create_backups = create_backups

    def _resolve_safe_path(self, relative_path: str, base_dir: Optional[Path] = None) -> Path:
        """
        Resolves a file path and strictly validates that it remains inside the workspace root.

        Args:
            relative_path: The file path string.
            base_dir: Optional workspace directory override (defaults to self.project_root).

        Returns:
            Resolved absolute Path.

        Raises:
            PathTraversalError: If the path escapes the sandbox directory.
        """
        root = (base_dir or self.project_root).resolve()
        clean_path = Path(relative_path)

        if clean_path.is_absolute():
            try:
                resolved = clean_path.resolve()
                resolved.relative_to(root)
                return resolved
            except ValueError as exc:
                raise PathTraversalError(
                    f"Absolute path '{relative_path}' is outside project workspace '{root}'."
                ) from exc

        # Relative path resolution
        resolved = (root / clean_path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PathTraversalError(
                f"Path traversal detected: '{relative_path}' escapes project workspace '{root}'."
            ) from exc

        return resolved

    def write_single_file(
        self,
        file: GeneratedFile,
        target_dir: Optional[Path] = None,
        overwrite: Optional[bool] = None,
        backup: Optional[bool] = None,
    ) -> tuple[str, Optional[str]]:
        """
        Writes a single GeneratedFile to disk.

        Args:
            file: The GeneratedFile object containing relative path and content.
            target_dir: Optional workspace root override.
            overwrite: Optional override for overwrite_existing.
            backup: Optional override for create_backups.

        Returns:
            A tuple of (action_status, backup_path_or_none) where action_status is
            'written' or 'skipped'.

        Raises:
            FileWriterError: If writing fails or overwrite is disabled.
        """
        should_overwrite = self.overwrite_existing if overwrite is None else overwrite
        should_backup = self.create_backups if backup is None else backup
        root = (target_dir or self.project_root).resolve()

        target_path = self._resolve_safe_path(file.path, base_dir=root)
        rel_display = target_path.relative_to(root).as_posix()
        backup_rel_path: Optional[str] = None

        # Check if file already exists
        if target_path.exists():
            if target_path.is_dir():
                raise FileWriterError(f"Target path '{rel_display}' already exists as a directory.")

            try:
                existing_content = target_path.read_text(encoding="utf-8", errors="replace")
                # Skip identical content
                if existing_content == file.content:
                    logger.info("Skipping identical file: %s", rel_display)
                    return "skipped", None
            except OSError as exc:
                raise FileWriterError(f"Failed to read existing file '{rel_display}': {exc}") from exc

            # File differs but overwrite is False
            if not should_overwrite:
                raise FileWriterError(
                    f"File '{rel_display}' already exists and overwrite_existing is False."
                )

            # Create backup if requested
            if should_backup:
                backup_path = target_path.parent / f"{target_path.name}.bak"
                try:
                    shutil.copy2(target_path, backup_path)
                    backup_rel_path = backup_path.relative_to(root).as_posix()
                    logger.info("Created backup for '%s' at '%s'", rel_display, backup_rel_path)
                except OSError as exc:
                    raise FileWriterError(f"Failed to create backup for '{rel_display}': {exc}") from exc

        # Create parent directories automatically
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file content
        try:
            target_path.write_text(file.content, encoding="utf-8")
            logger.info("Successfully written file: %s", rel_display)
        except OSError as exc:
            raise FileWriterError(f"Failed to write file '{rel_display}': {exc}") from exc

        return "written", backup_rel_path

    def write(
        self,
        result: Union[GeneratedResult, List[GeneratedFile]],
        target_dir: Optional[str | Path] = None,
        overwrite: Optional[bool] = None,
        backup: Optional[bool] = None,
    ) -> WriteResult:
        """
        Writes all generated files to disk within the target project directory.

        Args:
            result: GeneratedResult instance or list of GeneratedFile objects.
            target_dir: Optional project workspace directory override.
            overwrite: Optional override for overwrite_existing.
            backup: Optional override for create_backups.

        Returns:
            WriteResult dataclass detailing files written, skipped, backups, and failures.
        """
        root = Path(target_dir).resolve() if target_dir else self.project_root
        files_to_write = result.files if isinstance(result, GeneratedResult) else result

        files_written: List[str] = []
        files_skipped: List[str] = []
        backups_created: List[str] = []
        failed_files: Dict[str, str] = {}

        logger.info("Starting batch write of %d file(s) into '%s'...", len(files_to_write), root)

        for gen_file in files_to_write:
            try:
                status, backup_path = self.write_single_file(
                    file=gen_file,
                    target_dir=root,
                    overwrite=overwrite,
                    backup=backup,
                )
                if status == "written":
                    files_written.append(gen_file.path)
                elif status == "skipped":
                    files_skipped.append(gen_file.path)

                if backup_path:
                    backups_created.append(backup_path)

            except Exception as exc:
                logger.error("Failed writing file '%s': %s", gen_file.path, exc)
                failed_files[gen_file.path] = str(exc)

        has_failures = len(failed_files) > 0
        success = not has_failures

        if success:
            msg = f"Successfully processed {len(files_to_write)} file(s) ({len(files_written)} written, {len(files_skipped)} skipped)."
        else:
            msg = f"Batch write completed with {len(failed_files)} failure(s) out of {len(files_to_write)} file(s)."

        return WriteResult(
            files_written=files_written,
            files_skipped=files_skipped,
            backups_created=backups_created,
            failed_files=failed_files,
            success=success,
            message=msg,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-5s] %(message)s")

    # Quick demo using temporary directory
    demo_dir = Path("projects/demo_app")
    writer = FileWriterAgent(project_root=demo_dir, create_backups=True)

    demo_files = [
        GeneratedFile(path="src/main.py", content="print('Hello AutoDev')\n"),
        GeneratedFile(path="src/utils/helpers.py", content="def add(a, b):\n    return a + b\n"),
    ]
    demo_result = GeneratedResult(
        summary="Demo app initialized",
        files=demo_files,
        explanation="Created demo app files.",
    )

    result = writer.write(demo_result)
    print("\nWrite Result Summary:")
    print(result)
