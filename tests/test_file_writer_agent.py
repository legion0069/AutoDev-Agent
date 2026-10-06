"""
test_file_writer_agent.py - Comprehensive Unit & Security Tests for FileWriterAgent

Validates:
- Writing new files
- Creating nested directories
- Skipping identical files
- Overwriting existing files
- Backup creation (.bak)
- Path traversal & security sandbox protection
- Partial failure handling
"""

import pytest
from pathlib import Path
from agents.coder_agent import GeneratedFile, GeneratedResult
from agents.file_writer_agent import (
    FileWriterAgent,
    FileWriterError,
    PathTraversalError,
    WriteResult,
)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Provides a fresh isolated temporary project directory."""
    workspace = tmp_path / "test_project"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def test_write_new_files(temp_workspace: Path):
    """Verifies that new files are correctly written to the workspace."""
    writer = FileWriterAgent(project_root=temp_workspace)
    files = [
        GeneratedFile(path="README.md", content="# Test Project\n"),
        GeneratedFile(path="main.py", content="print('hello world')\n"),
    ]
    result = writer.write(files)

    assert result.success is True
    assert len(result.files_written) == 2
    assert (temp_workspace / "README.md").read_text(encoding="utf-8") == "# Test Project\n"
    assert (temp_workspace / "main.py").read_text(encoding="utf-8") == "print('hello world')\n"


def test_create_nested_directories(temp_workspace: Path):
    """Verifies that deep nested directories are created automatically."""
    writer = FileWriterAgent(project_root=temp_workspace)
    files = [
        GeneratedFile(
            path="src/api/v1/endpoints/users.py",
            content="# Users router\n",
        )
    ]
    result = writer.write(files)

    assert result.success is True
    assert (temp_workspace / "src/api/v1/endpoints/users.py").is_file()
    assert (temp_workspace / "src/api/v1/endpoints/users.py").read_text(encoding="utf-8") == "# Users router\n"


def test_skip_identical_files(temp_workspace: Path):
    """Verifies that files with identical content are skipped without rewrite."""
    target = temp_workspace / "config.py"
    target.write_text("DEBUG = True\n", encoding="utf-8")

    writer = FileWriterAgent(project_root=temp_workspace)
    files = [GeneratedFile(path="config.py", content="DEBUG = True\n")]
    result = writer.write(files)

    assert result.success is True
    assert len(result.files_written) == 0
    assert "config.py" in result.files_skipped


def test_overwrite_existing_files(temp_workspace: Path):
    """Verifies that existing files are updated when overwrite_existing=True."""
    target = temp_workspace / "version.py"
    target.write_text("VERSION = '0.1.0'\n", encoding="utf-8")

    writer = FileWriterAgent(project_root=temp_workspace, overwrite_existing=True)
    files = [GeneratedFile(path="version.py", content="VERSION = '0.2.0'\n")]
    result = writer.write(files)

    assert result.success is True
    assert len(result.files_written) == 1
    assert target.read_text(encoding="utf-8") == "VERSION = '0.2.0'\n"


def test_backup_creation_on_overwrite(temp_workspace: Path):
    """Verifies that .bak backup files are created before overwriting."""
    target = temp_workspace / "important.py"
    original_content = "# Original code\n"
    target.write_text(original_content, encoding="utf-8")

    writer = FileWriterAgent(project_root=temp_workspace, create_backups=True)
    files = [GeneratedFile(path="important.py", content="# Updated code\n")]
    result = writer.write(files)

    backup_file = temp_workspace / "important.py.bak"

    assert result.success is True
    assert len(result.backups_created) == 1
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == original_content
    assert target.read_text(encoding="utf-8") == "# Updated code\n"


def test_path_traversal_detection(temp_workspace: Path):
    """Verifies that path traversal attempts outside workspace are blocked and captured."""
    writer = FileWriterAgent(project_root=temp_workspace)
    malicious_files = [
        GeneratedFile(path="../../outside.txt", content="malicious\n"),
        GeneratedFile(path="src/valid.py", content="valid\n"),
    ]
    result = writer.write(malicious_files)

    assert result.success is False
    assert "../../outside.txt" in result.failed_files
    assert "Path traversal detected" in result.failed_files["../../outside.txt"]
    assert "src/valid.py" in result.files_written


def test_partial_failure_with_overwrite_disabled(temp_workspace: Path):
    """Verifies behavior when overwrite_existing=False and some files already exist."""
    existing_file = temp_workspace / "existing.py"
    existing_file.write_text("old content\n", encoding="utf-8")

    writer = FileWriterAgent(project_root=temp_workspace, overwrite_existing=False)
    batch = [
        GeneratedFile(path="existing.py", content="new content\n"),
        GeneratedFile(path="new_file.py", content="brand new\n"),
    ]
    result = writer.write(batch)

    assert result.success is False
    assert len(result.files_written) == 1
    assert "new_file.py" in result.files_written
    assert "existing.py" in result.failed_files
    assert "overwrite_existing is False" in result.failed_files["existing.py"]
    # Ensure original was not modified
    assert existing_file.read_text(encoding="utf-8") == "old content\n"


def test_generated_result_object_input(temp_workspace: Path):
    """Verifies that FileWriterAgent directly accepts a GeneratedResult object."""
    writer = FileWriterAgent(project_root=temp_workspace)
    gen_result = GeneratedResult(
        summary="Feature setup",
        files=[
            GeneratedFile(path="app.py", content="# App code\n"),
            GeneratedFile(path="test_app.py", content="# Test code\n"),
        ],
        explanation="Added app and test modules.",
    )
    result = writer.write(gen_result)

    assert result.success is True
    assert len(result.files_written) == 2
    assert (temp_workspace / "app.py").is_file()
    assert (temp_workspace / "test_app.py").is_file()
