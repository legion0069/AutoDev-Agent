"""
git_agent.py - Automated Local Version Control Agent for AutoDev

Responsible for managing local Git lifecycle operations:
- Detecting and initializing local repositories
- Branch creation and branch switching
- Staging files with .gitignore compliance
- Creating atomic commits and tracking commit hashes
- Retrieving branch and status telemetry
- Pull and push interface with safe local fallback
- Rollback operations
- Returning structured dataclasses for every operation
- Capturing stdout, stderr, exit code, and execution message
- Operating purely via subprocess without LLM invocations or remote credentials
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("AutoDev.GitAgent")


# =============================================================================
# Custom Exception Hierarchy
# =============================================================================

class GitAgentException(Exception):
    """Base exception for all GitAgent operations."""
    pass


class GitOperationError(GitAgentException):
    """Raised on critical infrastructure failures (e.g. missing git binary, OS errors)."""
    pass


class RepositoryNotFoundError(GitAgentException):
    """Raised when a Git operation is attempted in a non-repository directory."""
    pass


class GitExecutableNotFoundError(GitOperationError):
    """Raised when the git executable is not available on the system PATH."""
    pass


class GitCommandError(GitAgentException):
    """Raised when a git subprocess command exits with a non-zero code."""

    def __init__(self, command: str, exit_code: int, stdout: str, stderr: str) -> None:
        super().__init__(
            f"Git command failed (Exit {exit_code}): '{command}'\n"
            f"STDOUT: {stdout.strip()}\n"
            f"STDERR: {stderr.strip()}"
        )
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class CommitFailureError(GitAgentException):
    """Raised when commit creation fails."""
    pass


# =============================================================================
# Telemetry Dataclasses
# =============================================================================

@dataclass
class GitOperationResult:
    """
    Standardized result structure returned for Git operations.
    """
    success: bool
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    message: str = ""
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to a serializable dictionary."""
        return {
            "success": self.success,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "message": self.message,
            "data": dict(self.data) if self.data else {},
        }


@dataclass
class GitStatus:
    """
    Structured status telemetry of the local Git repository working tree.
    """
    repository_exists: bool
    current_branch: Optional[str] = None
    modified_files: List[str] = field(default_factory=list)
    staged_files: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)
    clean: bool = True
    command: str = "git status"
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts git status to a serializable dictionary."""
        return {
            "repository_exists": self.repository_exists,
            "current_branch": self.current_branch,
            "modified_files": list(self.modified_files),
            "staged_files": list(self.staged_files),
            "untracked_files": list(self.untracked_files),
            "clean": self.clean,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "message": self.message,
        }


@dataclass
class CommitResult:
    """
    Structured result returned after creating a Git commit.
    """
    success: bool
    commit_hash: Optional[str] = None
    commit_message: Optional[str] = None
    files_committed: List[str] = field(default_factory=list)
    branch: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    error: Optional[str] = None
    command: str = "git commit"
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts commit result to a serializable dictionary."""
        return {
            "success": self.success,
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "files_committed": list(self.files_committed),
            "branch": self.branch,
            "timestamp": self.timestamp,
            "error": self.error,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "message": self.message,
        }


# =============================================================================
# GitAgent Subsystem
# =============================================================================

class GitAgent:
    """
    Coordinates local Git version control operations for AutoDev.
    Operates strictly locally via subprocess without LLM invocations or remote credentials.
    """

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        auto_init: bool = False,
        git_executable: str = "git",
        user_name: str = "AutoDev Agent",
        user_email: str = "autodev@agent.local",
    ) -> None:
        """
        Initializes the GitAgent.

        Args:
            project_root: Target workspace directory.
            auto_init: Whether to automatically initialize git if missing.
            git_executable: Path or name of the git binary.
            user_name: Default author name for local commits.
            user_email: Default author email for local commits.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self.git_executable = git_executable
        self.user_name = user_name
        self.user_email = user_email

        if auto_init and not self.is_git_repository():
            self.initialize_repository()

    # -------------------------------------------------------------------------
    # Subprocess Helper
    # -------------------------------------------------------------------------

    def _run_git_command(
        self,
        args: List[str],
        cwd: Optional[Union[str, Path]] = None,
        check: bool = True,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """
        Executes a git CLI command via subprocess with author configuration.

        Args:
            args: Git subcommands and arguments (e.g. ['status', '--porcelain']).
            cwd: Working directory override.
            check: Whether to raise GitCommandError on non-zero exit code.
            timeout: Subprocess timeout in seconds.

        Returns:
            subprocess.CompletedProcess instance containing stdout/stderr strings.

        Raises:
            GitExecutableNotFoundError: If git binary is not found.
            GitOperationError: On critical OS / launch failures.
            GitCommandError: If command fails and check=True.
        """
        target_dir = Path(cwd).resolve() if cwd else self.project_root
        cmd = [
            self.git_executable,
            "-c", f"user.name={self.user_name}",
            "-c", f"user.email={self.user_email}",
        ] + args

        try:
            result = subprocess.run(
                cmd,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except (FileNotFoundError, OSError) as exc:
            logger.error("Git binary '%s' not found or inaccessible: %s", self.git_executable, exc)
            raise GitExecutableNotFoundError(
                f"Git executable '{self.git_executable}' is not available: {exc}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            logger.error("Git command timed out after %ds: %s", timeout, " ".join(cmd))
            raise GitOperationError(f"Command timed out after {timeout} seconds: {' '.join(cmd)}") from exc

        if check and result.returncode != 0:
            cmd_str = " ".join(cmd)
            logger.debug("Git command failed (code %d): %s\n%s", result.returncode, cmd_str, result.stderr)
            raise GitCommandError(
                command=cmd_str,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        return result

    # -------------------------------------------------------------------------
    # Repository Verification & Initialization
    # -------------------------------------------------------------------------

    def is_git_repository(self, project_root: Optional[Union[str, Path]] = None) -> bool:
        """
        Checks whether the specified target directory is inside an active Git repository.

        Args:
            project_root: Optional target workspace path override.

        Returns:
            True if target is an initialized Git repository, False otherwise.
        """
        target = Path(project_root).resolve() if project_root else self.project_root
        if not (target / ".git").exists():
            return False

        try:
            res = self._run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=target, check=False)
            return res.returncode == 0 and res.stdout.strip() == "true"
        except GitAgentException:
            return False

    def check_repository(self, project_root: Optional[Union[str, Path]] = None) -> bool:
        """
        Alias for is_git_repository for backwards compatibility.
        """
        return self.is_git_repository(project_root=project_root)

    def initialize_repository(
        self,
        project_root: Optional[Union[str, Path]] = None,
        initial_branch: str = "main",
    ) -> GitOperationResult:
        """
        Initializes a new Git repository if one does not exist.

        Args:
            project_root: Optional directory path to initialize.
            initial_branch: Default initial branch name (default: 'main').

        Returns:
            GitOperationResult describing initialization outcome.
        """
        target = Path(project_root).resolve() if project_root else self.project_root
        target.mkdir(parents=True, exist_ok=True)

        if self.is_git_repository(target):
            logger.info("Git repository already exists at '%s'.", target)
            return GitOperationResult(
                success=True,
                command="git init",
                stdout="Repository already exists.",
                stderr="",
                exit_code=0,
                message=f"Git repository already initialized at '{target}'.",
                data={"already_exists": True, "project_root": str(target)},
            )

        logger.info("Initializing Git repository at '%s' (branch: %s)...", target, initial_branch)

        try:
            res = self._run_git_command(["init", "-b", initial_branch], cwd=target, check=False)
            if res.returncode != 0:
                # Fallback for older git versions
                res = self._run_git_command(["init"], cwd=target, check=False)
                self._run_git_command(["checkout", "-b", initial_branch], cwd=target, check=False)

            # Ensure default .gitignore exists
            gitignore_path = target / ".gitignore"
            if not gitignore_path.exists():
                default_ignores = (
                    "__pycache__/\n"
                    "*.py[cod]\n"
                    ".pytest_cache/\n"
                    "*.tmp\n"
                    "*.bak\n"
                )
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(default_ignores)

            success = self.is_git_repository(target)
            return GitOperationResult(
                success=success,
                command="git init",
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                message=f"Repository initialized successfully at '{target}'.",
                data={"project_root": str(target), "initial_branch": initial_branch},
            )
        except Exception as exc:
            logger.error("Failed to initialize repository at '%s': %s", target, exc)
            return GitOperationResult(
                success=False,
                command="git init",
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                message=f"Failed to initialize repository: {exc}",
            )

    # -------------------------------------------------------------------------
    # Branch Operations
    # -------------------------------------------------------------------------

    def create_branch(self, branch_name: str) -> GitOperationResult:
        """
        Creates a new local branch in the repository.

        Args:
            branch_name: Name of branch to create.

        Returns:
            GitOperationResult structure.
        """
        if not self.is_git_repository():
            return GitOperationResult(
                success=False,
                command=f"git branch {branch_name}",
                stderr="Not a git repository.",
                exit_code=1,
                message=f"Cannot create branch: '{self.project_root}' is not a Git repository.",
            )

        try:
            res = self._run_git_command(["branch", branch_name], check=False)
            success = res.returncode == 0
            return GitOperationResult(
                success=success,
                command=f"git branch {branch_name}",
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                message=f"Branch '{branch_name}' created." if success else f"Failed to create branch: {res.stderr.strip()}",
                data={"branch": branch_name},
            )
        except Exception as exc:
            return GitOperationResult(
                success=False,
                command=f"git branch {branch_name}",
                stderr=str(exc),
                exit_code=-1,
                message=f"Error creating branch: {exc}",
            )

    def checkout_branch(self, branch_name: str, create: bool = False) -> GitOperationResult:
        """
        Switches to a specified branch, optionally creating it if missing.

        Args:
            branch_name: Name of branch to switch to.
            create: Whether to create branch if it does not exist ('-b' flag).

        Returns:
            GitOperationResult structure.
        """
        if not self.is_git_repository():
            return GitOperationResult(
                success=False,
                command=f"git checkout {branch_name}",
                stderr="Not a git repository.",
                exit_code=1,
                message=f"Cannot checkout branch: '{self.project_root}' is not a Git repository.",
            )

        args = ["checkout", "-b", branch_name] if create else ["checkout", branch_name]
        cmd_str = f"git {' '.join(args)}"

        try:
            res = self._run_git_command(args, check=False)
            success = res.returncode == 0
            return GitOperationResult(
                success=success,
                command=cmd_str,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                message=f"Switched to branch '{branch_name}'." if success else f"Checkout failed: {res.stderr.strip()}",
                data={"current_branch": self.get_current_branch()},
            )
        except Exception as exc:
            return GitOperationResult(
                success=False,
                command=cmd_str,
                stderr=str(exc),
                exit_code=-1,
                message=f"Error checking out branch: {exc}",
            )

    # -------------------------------------------------------------------------
    # Status & Branch Queries
    # -------------------------------------------------------------------------

    def get_current_branch(self) -> Optional[str]:
        """
        Retrieves the name of the active Git branch.

        Returns:
            Branch name string or None if not in a repository / unborn branch.
        """
        if not self.is_git_repository():
            return None

        res = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
        if res.returncode == 0:
            branch = res.stdout.strip()
            return branch if branch != "HEAD" else None
        return None

    def get_latest_commit_hash(self) -> Optional[str]:
        """
        Retrieves the full SHA commit hash of the latest commit on HEAD.

        Returns:
            Commit hash string or None if repository has no commits.
        """
        if not self.is_git_repository():
            return None

        res = self._run_git_command(["rev-parse", "HEAD"], check=False)
        if res.returncode == 0:
            return res.stdout.strip()
        return None

    def get_status(self) -> GitStatus:
        """
        Parses working tree status into structured GitStatus telemetry.

        Returns:
            GitStatus instance with modified, staged, and untracked file lists.
        """
        if not self.is_git_repository():
            return GitStatus(
                repository_exists=False,
                current_branch=None,
                modified_files=[],
                staged_files=[],
                untracked_files=[],
                clean=True,
                exit_code=1,
                message="Target directory is not a Git repository.",
            )

        branch = self.get_current_branch()
        res = self._run_git_command(["status", "--porcelain=v1"], check=False)
        if res.returncode != 0:
            return GitStatus(
                repository_exists=True,
                current_branch=branch,
                clean=True,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                message="Failed to retrieve porcelain status.",
            )

        staged: List[str] = []
        modified: List[str] = []
        untracked: List[str] = []

        for line in res.stdout.splitlines():
            if not line or len(line) < 3:
                continue

            index_status = line[0]
            worktree_status = line[1]
            file_path = line[3:].strip().strip('"')

            if index_status in ("M", "A", "D", "R", "C"):
                staged.append(file_path)
            if worktree_status in ("M", "D"):
                modified.append(file_path)
            if index_status == "?" and worktree_status == "?":
                untracked.append(file_path)

        clean = len(staged) == 0 and len(modified) == 0 and len(untracked) == 0

        return GitStatus(
            repository_exists=True,
            current_branch=branch,
            modified_files=modified,
            staged_files=staged,
            untracked_files=untracked,
            clean=clean,
            stdout=res.stdout,
            stderr=res.stderr,
            exit_code=0,
            message="Working tree clean." if clean else f"{len(staged)} staged, {len(modified)} modified, {len(untracked)} untracked.",
        )

    # -------------------------------------------------------------------------
    # Staging Operations
    # -------------------------------------------------------------------------

    def stage_all(self) -> GitOperationResult:
        """
        Stages all modified and untracked files in the repository.

        Returns:
            GitOperationResult describing staging outcome.
        """
        if not self.is_git_repository():
            return GitOperationResult(
                success=False,
                command="git add .",
                stderr="Not a git repository.",
                exit_code=1,
                message=f"Cannot stage files: '{self.project_root}' is not a Git repository.",
            )

        try:
            res = self._run_git_command(["add", "."])
            status = self.get_status()
            return GitOperationResult(
                success=True,
                command="git add .",
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=0,
                message=f"Staged {len(status.staged_files)} file(s).",
                data={"staged_files": status.staged_files},
            )
        except Exception as exc:
            return GitOperationResult(
                success=False,
                command="git add .",
                stderr=str(exc),
                exit_code=-1,
                message=f"Staging failed: {exc}",
            )

    def stage_files(
        self,
        files: Optional[List[Union[str, Path]]] = None,
    ) -> List[str]:
        """
        Stages files for commit. Respects .gitignore rules.

        Args:
            files: Optional list of specific file paths to stage.
                   If None or empty, stages all changes ('git add .').

        Returns:
            List of currently staged file paths.

        Raises:
            RepositoryNotFoundError: If project_root is not a Git repo.
            GitCommandError: If git add fails.
        """
        if not self.is_git_repository():
            raise RepositoryNotFoundError(f"Cannot stage files: '{self.project_root}' is not a Git repository.")

        if files:
            normalized_paths = [str(Path(f).as_posix()) for f in files]
            self._run_git_command(["add", "--"] + normalized_paths)
        else:
            self.stage_all()

        status = self.get_status()
        return status.staged_files

    # -------------------------------------------------------------------------
    # Commit Message Generation & Local Commit
    # -------------------------------------------------------------------------

    def generate_commit_message(
        self,
        task: Any = None,
        review_result: Optional[Any] = None,
    ) -> str:
        """
        Synthesizes a standardized commit message from task & review metadata.

        Args:
            task: Task object, dict, or title string.
            review_result: Optional ReviewResult object or dictionary.

        Returns:
            Descriptive formatted commit message string.
        """
        task_id = "TASK"
        task_title = "Update codebase"

        if task is not None:
            if hasattr(task, "id") and hasattr(task, "title"):
                task_id = str(task.id)
                task_title = str(task.title)
            elif isinstance(task, dict):
                task_id = str(task.get("id", "TASK"))
                task_title = str(task.get("title", "Update codebase"))
            elif isinstance(task, str):
                task_title = task

        header = f"feat({task_id}): {task_title}"
        body_lines: List[str] = [
            "",
            f"- Task ID: {task_id}",
            f"- Automated execution by AutoDev Agent",
        ]

        if review_result is not None:
            score = None
            if hasattr(review_result, "overall_quality_score"):
                score = review_result.overall_quality_score
            elif isinstance(review_result, dict):
                score = review_result.get("overall_quality_score")

            if score is not None:
                body_lines.append(f"- AI Code Review Quality Score: {score}/100")

        return f"{header}\n" + "\n".join(body_lines)

    def commit(
        self,
        message: Optional[str] = None,
        task: Optional[Any] = None,
        review_result: Optional[Any] = None,
        files_to_stage: Optional[List[Union[str, Path]]] = None,
        allow_empty: bool = False,
    ) -> CommitResult:
        """
        Stages and commits changes locally. Returns structured CommitResult telemetry.

        Args:
            message: Explicit commit message override.
            task: Optional Task object for auto-generating message.
            review_result: Optional ReviewResult object for message telemetry.
            files_to_stage: Optional specific files to stage before committing.
            allow_empty: Whether to allow commits with no modified files.

        Returns:
            CommitResult containing status, commit hash, branch, and metadata.
        """
        timestamp = datetime.now().isoformat(timespec="seconds")

        try:
            if not self.is_git_repository():
                raise RepositoryNotFoundError(f"Directory '{self.project_root}' is not a Git repository.")

            # Stage files
            self.stage_files(files_to_stage)

            # Check status before committing
            status = self.get_status()
            if not status.staged_files and not allow_empty:
                logger.info("Nothing to commit: working tree clean or no files staged.")
                return CommitResult(
                    success=False,
                    commit_hash=None,
                    commit_message=None,
                    files_committed=[],
                    branch=status.current_branch,
                    timestamp=timestamp,
                    error="Nothing to commit (working tree clean).",
                    exit_code=1,
                    message="Nothing to commit (working tree clean).",
                )

            # Generate or use provided message
            commit_msg = message or self.generate_commit_message(task=task, review_result=review_result)

            # Perform local commit
            commit_cmd = ["commit", "-m", commit_msg]
            if allow_empty:
                commit_cmd.append("--allow-empty")

            commit_proc = self._run_git_command(commit_cmd)

            # Retrieve new commit hash and current branch
            commit_hash = self.get_latest_commit_hash()
            branch = self.get_current_branch()

            logger.info("Created local commit [%s] on branch '%s'.", str(commit_hash)[:8], branch)

            return CommitResult(
                success=True,
                commit_hash=commit_hash,
                commit_message=commit_msg,
                files_committed=status.staged_files,
                branch=branch,
                timestamp=timestamp,
                error=None,
                stdout=commit_proc.stdout,
                stderr=commit_proc.stderr,
                exit_code=0,
                message=f"Commit created successfully ({str(commit_hash)[:8]}).",
            )

        except Exception as exc:
            logger.error("Commit operation failed: %s", exc)
            return CommitResult(
                success=False,
                commit_hash=None,
                commit_message=message,
                files_committed=[],
                branch=self.get_current_branch(),
                timestamp=timestamp,
                error=str(exc),
                exit_code=-1,
                message=f"Commit failed: {exc}",
            )

    # -------------------------------------------------------------------------
    # Remote Interface (Push / Pull)
    # -------------------------------------------------------------------------

    def push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
    ) -> GitOperationResult:
        """
        Pushes commits to the specified remote repository.
        Captures network or authentication errors without terminating the application.

        Args:
            remote: Remote name (default: 'origin').
            branch: Branch to push (defaults to active branch).
            set_upstream: Whether to pass '-u' flag.

        Returns:
            GitOperationResult telemetry.
        """
        if not self.is_git_repository():
            return GitOperationResult(
                success=False,
                command=f"git push {remote}",
                stderr="Not a git repository.",
                exit_code=1,
                message=f"Cannot push: '{self.project_root}' is not a Git repository.",
            )

        target_branch = branch or self.get_current_branch() or "main"
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.extend([remote, target_branch])
        cmd_str = f"git {' '.join(args)}"

        try:
            res = self._run_git_command(args, check=False)
            success = res.returncode == 0
            return GitOperationResult(
                success=success,
                command=cmd_str,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                message="Pushed successfully." if success else f"Push failed: {res.stderr.strip()}",
                data={"remote": remote, "branch": target_branch},
            )
        except Exception as exc:
            return GitOperationResult(
                success=False,
                command=cmd_str,
                stderr=str(exc),
                exit_code=-1,
                message=f"Push error: {exc}",
            )

    def pull(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
    ) -> GitOperationResult:
        """
        Pulls updates from the specified remote repository.

        Args:
            remote: Remote name (default: 'origin').
            branch: Branch to pull (defaults to active branch).

        Returns:
            GitOperationResult telemetry.
        """
        if not self.is_git_repository():
            return GitOperationResult(
                success=False,
                command=f"git pull {remote}",
                stderr="Not a git repository.",
                exit_code=1,
                message=f"Cannot pull: '{self.project_root}' is not a Git repository.",
            )

        target_branch = branch or self.get_current_branch() or "main"
        args = ["pull", remote, target_branch]
        cmd_str = f"git {' '.join(args)}"

        try:
            res = self._run_git_command(args, check=False)
            success = res.returncode == 0
            return GitOperationResult(
                success=success,
                command=cmd_str,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                message="Pulled successfully." if success else f"Pull failed: {res.stderr.strip()}",
                data={"remote": remote, "branch": target_branch},
            )
        except Exception as exc:
            return GitOperationResult(
                success=False,
                command=cmd_str,
                stderr=str(exc),
                exit_code=-1,
                message=f"Pull error: {exc}",
            )

    # -------------------------------------------------------------------------
    # Rollback Operations
    # -------------------------------------------------------------------------

    def rollback_last_commit(self, hard: bool = False) -> GitOperationResult:
        """
        Rolls back the most recent commit locally.

        Args:
            hard: If True, resets working tree (destructive).
                  If False (default), performs soft reset keeping modified files.

        Returns:
            GitOperationResult telemetry describing rollback outcome.
        """
        if not self.is_git_repository():
            raise RepositoryNotFoundError(f"Cannot rollback: '{self.project_root}' is not a Git repository.")

        reset_flag = "--hard" if hard else "--soft"
        cmd_str = f"git reset {reset_flag} HEAD~1"
        logger.warning("Rolling back last commit with %s reset...", reset_flag)

        try:
            res = self._run_git_command(["reset", reset_flag, "HEAD~1"], check=False)
            success = res.returncode == 0
            return GitOperationResult(
                success=success,
                command=cmd_str,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                message="Rollback completed successfully." if success else f"Rollback failed: {res.stderr.strip()}",
                data={"hard": hard},
            )
        except Exception as exc:
            logger.error("Failed to rollback commit: %s", exc)
            return GitOperationResult(
                success=False,
                command=cmd_str,
                stderr=str(exc),
                exit_code=-1,
                message=f"Rollback error: {exc}",
            )


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        agent = GitAgent(project_root=tmp_dir, auto_init=True)
        print(f"Repository initialized: {agent.is_git_repository()}")

        sample_file = Path(tmp_dir) / "app.py"
        sample_file.write_text("print('Hello AutoDev')\n", encoding="utf-8")

        status_before = agent.get_status()
        print(f"Untracked files: {status_before.untracked_files}")

        res = agent.commit(message="feat: initial commit")
        print(f"Commit Success: {res.success}, Hash: {res.commit_hash[:8] if res.commit_hash else 'N/A'}")
