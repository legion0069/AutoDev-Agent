"""
test_git_agent.py - Comprehensive Unit & Integration Tests for GitAgent

Validates:
- Repository detection with is_git_repository() and check_repository()
- Repository initialization (git init, initial branch, default .gitignore)
- Branch operations (create_branch, checkout_branch, get_current_branch)
- Working tree status parsing (clean, untracked, modified, staged)
- Staging operations (stage_all, stage_files)
- Commit execution (commit creation, get_latest_commit_hash, branch detection, telemetry)
- Empty commit prevention (clean directory returns success=False)
- Rollback operations (soft reset and hard reset via rollback_last_commit)
- Remote operations handling (push, pull without crashing on missing remote)
- Commit message synthesis (Task objects, dicts, review results with quality scores)
- Error handling on invalid repository operations
- Missing git executable and infrastructure failure handling
- Mock subprocess failures and timeout handling
- Zero network operations / remote operations safety
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agents.git_agent import (
    CommitFailureError,
    CommitResult,
    GitAgent,
    GitAgentException,
    GitCommandError,
    GitExecutableNotFoundError,
    GitOperationError,
    GitOperationResult,
    GitStatus,
    RepositoryNotFoundError,
)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Provides an isolated clean workspace directory."""
    ws = tmp_path / "test_repo"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture
def initialized_git_repo(temp_workspace: Path) -> GitAgent:
    """Provides a GitAgent initialized with an active local Git repository."""
    agent = GitAgent(
        project_root=temp_workspace,
        auto_init=True,
        user_name="AutoDev Tester",
        user_email="tester@autodev.local",
    )
    return agent


# =============================================================================
# 1. Repository Detection & Initialization Tests
# =============================================================================

def test_check_repository_on_empty_directory(temp_workspace: Path):
    """Verifies that is_git_repository returns False for an uninitialized folder."""
    agent = GitAgent(project_root=temp_workspace, auto_init=False)
    assert agent.is_git_repository() is False
    assert agent.check_repository() is False


def test_initialize_repository_creates_git_and_gitignore(temp_workspace: Path):
    """Verifies that initialize_repository initializes git and writes .gitignore."""
    agent = GitAgent(project_root=temp_workspace, auto_init=False)
    assert agent.is_git_repository() is False

    res = agent.initialize_repository(initial_branch="main")
    assert isinstance(res, GitOperationResult)
    assert res.success is True
    assert agent.is_git_repository() is True
    assert (temp_workspace / ".git").is_dir()
    assert (temp_workspace / ".gitignore").is_file()


def test_initialize_repository_idempotent_on_existing_repo(initialized_git_repo: GitAgent):
    """Verifies that re-running initialization on an existing repo succeeds safely."""
    assert initialized_git_repo.is_git_repository() is True
    res = initialized_git_repo.initialize_repository()
    assert res.success is True
    assert res.data.get("already_exists") is True


# =============================================================================
# 2. Branch Operations Tests
# =============================================================================

def test_create_and_checkout_branch(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies creating, listing, and checking out different branches."""
    # Create initial commit so branch head exists
    (temp_workspace / "init.txt").write_text("initial", encoding="utf-8")
    initialized_git_repo.commit(message="chore: initial commit")

    # Create new feature branch
    res_create = initialized_git_repo.create_branch("feature/auth")
    assert isinstance(res_create, GitOperationResult)
    assert res_create.success is True

    # Checkout branch
    res_checkout = initialized_git_repo.checkout_branch("feature/auth")
    assert isinstance(res_checkout, GitOperationResult)
    assert res_checkout.success is True
    assert initialized_git_repo.get_current_branch() == "feature/auth"


def test_checkout_new_branch_with_create_flag(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies checking out a non-existent branch with create=True."""
    (temp_workspace / "init.txt").write_text("initial", encoding="utf-8")
    initialized_git_repo.commit(message="chore: initial commit")

    res = initialized_git_repo.checkout_branch("feature/fast-track", create=True)
    assert res.success is True
    assert initialized_git_repo.get_current_branch() == "feature/fast-track"


def test_branch_operations_on_uninitialized_repo(temp_workspace: Path):
    """Verifies branch operations fail cleanly on uninitialized directory."""
    agent = GitAgent(project_root=temp_workspace, auto_init=False)
    res_create = agent.create_branch("dev")
    assert res_create.success is False
    assert "not a Git repository" in res_create.message

    res_checkout = agent.checkout_branch("dev")
    assert res_checkout.success is False
    assert "not a Git repository" in res_checkout.message


# =============================================================================
# 3. Status & Working Tree Telemetry Tests
# =============================================================================

def test_status_on_non_repository(temp_workspace: Path):
    """Verifies get_status returns repository_exists=False when outside git repo."""
    agent = GitAgent(project_root=temp_workspace, auto_init=False)
    status = agent.get_status()
    assert status.repository_exists is False
    assert status.current_branch is None
    assert status.clean is True


def test_status_detects_untracked_files(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies that creating a new file is detected in untracked_files."""
    new_file = temp_workspace / "module.py"
    new_file.write_text("print('hello')", encoding="utf-8")

    status = initialized_git_repo.get_status()
    assert status.repository_exists is True
    assert status.clean is False
    assert "module.py" in status.untracked_files or any("module.py" in f for f in status.untracked_files)


def test_status_detects_staged_and_modified_files(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies transition from untracked to staged and then modified."""
    new_file = temp_workspace / "app.py"
    new_file.write_text("x = 1\n", encoding="utf-8")

    # Stage app.py
    initialized_git_repo.stage_files(["app.py"])
    status = initialized_git_repo.get_status()
    assert any("app.py" in f for f in status.staged_files)

    # Initial commit
    initialized_git_repo.commit(message="chore: initial commit")

    # Modify app.py
    new_file.write_text("x = 2\n", encoding="utf-8")
    status_after_mod = initialized_git_repo.get_status()
    assert any("app.py" in f for f in status_after_mod.modified_files)


# =============================================================================
# 4. Staging & Commit Operations Tests
# =============================================================================

def test_stage_all_operation(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies stage_all stages all modified and untracked files."""
    (temp_workspace / "f1.py").write_text("# 1", encoding="utf-8")
    (temp_workspace / "f2.py").write_text("# 2", encoding="utf-8")

    res = initialized_git_repo.stage_all()
    assert isinstance(res, GitOperationResult)
    assert res.success is True
    assert len(res.data.get("staged_files", [])) >= 2


def test_stage_specific_files(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies staging only selected files."""
    (temp_workspace / "fileA.py").write_text("# A", encoding="utf-8")
    (temp_workspace / "fileB.py").write_text("# B", encoding="utf-8")

    initialized_git_repo.stage_files(["fileA.py"])
    status = initialized_git_repo.get_status()
    assert any("fileA.py" in f for f in status.staged_files)
    assert not any("fileB.py" in f for f in status.staged_files)


def test_successful_commit_flow(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies complete staging and commit lifecycle."""
    (temp_workspace / "main.py").write_text("def run(): pass\n", encoding="utf-8")

    result = initialized_git_repo.commit(message="feat: implement entry point")

    assert isinstance(result, CommitResult)
    assert result.success is True
    assert result.commit_hash is not None
    assert len(result.commit_hash) >= 7
    assert result.commit_message == "feat: implement entry point"
    assert result.error is None
    assert initialized_git_repo.get_latest_commit_hash() == result.commit_hash
    assert initialized_git_repo.get_status().clean is True


def test_empty_commit_prevention(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies that committing when working tree is clean returns success=False without crashing."""
    (temp_workspace / "init.py").write_text("# init", encoding="utf-8")
    res1 = initialized_git_repo.commit(message="initial")
    assert res1.success is True

    res2 = initialized_git_repo.commit(message="empty commit")
    assert res2.success is False
    assert "Nothing to commit" in res2.error


# =============================================================================
# 5. Remote Interface Tests (Push / Pull)
# =============================================================================

def test_push_and_pull_missing_remote_safe_failure(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies that push/pull on missing remote returns structured failure without crashing."""
    (temp_workspace / "data.py").write_text("content", encoding="utf-8")
    initialized_git_repo.commit(message="feat: data commit")

    push_res = initialized_git_repo.push(remote="nonexistent_remote")
    assert isinstance(push_res, GitOperationResult)
    assert push_res.success is False

    pull_res = initialized_git_repo.pull(remote="nonexistent_remote")
    assert isinstance(pull_res, GitOperationResult)
    assert pull_res.success is False


def test_push_and_pull_on_non_repo(temp_workspace: Path):
    """Verifies push and pull gracefully handle uninitialized repositories."""
    agent = GitAgent(project_root=temp_workspace, auto_init=False)
    assert agent.push().success is False
    assert agent.pull().success is False


# =============================================================================
# 6. Rollback Tests
# =============================================================================

def test_rollback_last_commit_soft(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies soft rollback keeps changes in working tree."""
    (temp_workspace / "base.py").write_text("base", encoding="utf-8")
    res1 = initialized_git_repo.commit(message="commit 1")
    hash1 = res1.commit_hash

    (temp_workspace / "feature.py").write_text("feature", encoding="utf-8")
    res2 = initialized_git_repo.commit(message="commit 2")
    hash2 = res2.commit_hash
    assert hash1 != hash2

    # Rollback commit 2
    res_rollback = initialized_git_repo.rollback_last_commit(hard=False)
    assert isinstance(res_rollback, GitOperationResult)
    assert res_rollback.success is True
    # Working tree should retain feature.py
    assert (temp_workspace / "feature.py").exists()


def test_rollback_last_commit_hard(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies hard rollback discards changes from reverted commit."""
    (temp_workspace / "base.py").write_text("base", encoding="utf-8")
    initialized_git_repo.commit(message="commit 1")

    (temp_workspace / "ephemeral.py").write_text("ephemeral", encoding="utf-8")
    initialized_git_repo.commit(message="commit 2")
    assert (temp_workspace / "ephemeral.py").exists()

    res_rollback = initialized_git_repo.rollback_last_commit(hard=True)
    assert res_rollback.success is True
    assert not (temp_workspace / "ephemeral.py").exists()


# =============================================================================
# 7. Commit Message Synthesis Tests
# =============================================================================

def test_generate_commit_message_from_task_object(initialized_git_repo: GitAgent):
    """Verifies message generation when a Task object is provided."""
    class DummyTask:
        id = "DAY1-TASK02"
        title = "Implement Database Connection Pool"

    msg = initialized_git_repo.generate_commit_message(task=DummyTask())
    assert "feat(DAY1-TASK02): Implement Database Connection Pool" in msg
    assert "Task ID: DAY1-TASK02" in msg


def test_generate_commit_message_with_review_score(initialized_git_repo: GitAgent):
    """Verifies message generation includes quality score when ReviewResult is present."""
    task_dict = {"id": "DAY2-TASK01", "title": "Add Auth Middleware"}
    review_dict = {"overall_quality_score": 94}

    msg = initialized_git_repo.generate_commit_message(task=task_dict, review_result=review_dict)
    assert "feat(DAY2-TASK01): Add Auth Middleware" in msg
    assert "Quality Score: 94/100" in msg


# =============================================================================
# 8. Error Handling & Subprocess Edge Cases
# =============================================================================

def test_stage_files_on_uninitialized_repo_raises_error(temp_workspace: Path):
    """Verifies that calling stage_files without a git repo raises RepositoryNotFoundError."""
    agent = GitAgent(project_root=temp_workspace, auto_init=False)
    with pytest.raises(RepositoryNotFoundError):
        agent.stage_files(["foo.py"])


def test_missing_git_executable_handling(temp_workspace: Path):
    """Verifies GitExecutableNotFoundError when git binary path is invalid."""
    agent = GitAgent(
        project_root=temp_workspace,
        git_executable="nonexistent_git_binary_xyz_123",
        auto_init=False,
    )
    with pytest.raises(GitExecutableNotFoundError):
        agent._run_git_command(["status"])


def test_mock_subprocess_failure_returns_structured_commit_result(initialized_git_repo: GitAgent, temp_workspace: Path):
    """Verifies that unexpected subprocess errors during commit return CommitResult with error."""
    (temp_workspace / "data.py").write_text("data", encoding="utf-8")

    original_run = initialized_git_repo._run_git_command

    def mock_run(args, **kwargs):
        if len(args) > 0 and args[0] == "commit":
            raise GitCommandError(
                command="git commit",
                exit_code=128,
                stdout="",
                stderr="fatal: mock internal git error",
            )
        return original_run(args, **kwargs)

    with patch.object(initialized_git_repo, "_run_git_command", side_effect=mock_run):
        result = initialized_git_repo.commit(message="test failure")

        assert result.success is False
        assert "fatal: mock internal git error" in result.error
