"""
test_code_context_retriever.py - Comprehensive Unit & Integration Tests for CodeContextRetriever (v1.5)
"""

import json
from pathlib import Path
from typing import Any, Dict
import pytest

from agents.task_planner_agent import Task
from core.code_context_retriever import (
    CodeContextResult,
    CodeContextRetriever,
    RelevantFile,
    RelevantSymbol,
)
from core.prompt_builder import PromptBuilder
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility


@pytest.fixture
def sample_symbol_graph() -> SymbolGraph:
    """Creates a rich, multi-tiered SymbolGraph for deterministic testing."""
    graph = SymbolGraph()

    # 1. Base Class
    base_auth = Symbol(
        id="src/base_auth.py::BaseAuthService",
        name="BaseAuthService",
        qualified_name="BaseAuthService",
        symbol_type=SymbolType.CLASS,
        language="python",
        file="src/base_auth.py",
        line=1,
        end_line=20,
        visibility=Visibility.PUBLIC,
        docstring="Base authentication provider abstraction.",
    )
    graph.add_symbol(base_auth)

    # 2. Main Service Class & Method
    user_service = Symbol(
        id="src/user_service.py::UserService",
        name="UserService",
        qualified_name="UserService",
        symbol_type=SymbolType.CLASS,
        language="python",
        file="src/user_service.py",
        line=1,
        end_line=50,
        inherits=["BaseAuthService"],
        visibility=Visibility.PUBLIC,
        docstring="Primary user service managing authentication and sessions.",
    )
    graph.add_symbol(user_service)

    auth_method = Symbol(
        id="src/user_service.py::UserService.authenticate",
        name="authenticate",
        qualified_name="UserService.authenticate",
        symbol_type=SymbolType.METHOD,
        language="python",
        file="src/user_service.py",
        line=15,
        end_line=35,
        visibility=Visibility.PUBLIC,
        calls=["generate_token", "hash_password"],
        docstring="Authenticates user credentials and issues JWT token.",
    )
    graph.add_symbol(auth_method)

    # 3. Callee Helpers
    token_helper = Symbol(
        id="src/token_helper.py::generate_token",
        name="generate_token",
        qualified_name="generate_token",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        file="src/token_helper.py",
        line=1,
        end_line=15,
        visibility=Visibility.PUBLIC,
        docstring="Generates cryptographically secure JWT tokens.",
    )
    graph.add_symbol(token_helper)

    # 4. Caller Controller
    auth_controller = Symbol(
        id="src/auth_controller.py::AuthController.login",
        name="login",
        qualified_name="AuthController.login",
        symbol_type=SymbolType.METHOD,
        language="python",
        file="src/auth_controller.py",
        line=10,
        end_line=30,
        visibility=Visibility.PUBLIC,
        calls=["authenticate"],
        docstring="HTTP endpoint for user login flow.",
    )
    graph.add_symbol(auth_controller)

    # 5. Subclass
    oauth_service = Symbol(
        id="src/oauth_service.py::UserOAuthService",
        name="UserOAuthService",
        qualified_name="UserOAuthService",
        symbol_type=SymbolType.CLASS,
        language="python",
        file="src/oauth_service.py",
        line=1,
        end_line=40,
        inherits=["UserService"],
        visibility=Visibility.PUBLIC,
        docstring="OAuth2 specialization of UserService.",
    )
    graph.add_symbol(oauth_service)

    # 6. Test File Symbols
    test_auth_sym = Symbol(
        id="tests/test_user_service.py::test_user_authentication",
        name="test_user_authentication",
        qualified_name="test_user_authentication",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        file="tests/test_user_service.py",
        line=5,
        end_line=25,
        visibility=Visibility.PUBLIC,
        calls=["authenticate", "UserService"],
        docstring="Unit test verifying UserService.authenticate behavior.",
    )
    graph.add_symbol(test_auth_sym)

    # File Dependencies
    graph.add_dependency(Dependency("src/user_service.py", "src/token_helper.py", "import"))
    graph.add_dependency(Dependency("src/user_service.py", "src/base_auth.py", "import"))
    graph.add_dependency(Dependency("src/auth_controller.py", "src/user_service.py", "import"))
    graph.add_dependency(Dependency("src/oauth_service.py", "src/user_service.py", "import"))
    graph.add_dependency(Dependency("tests/test_user_service.py", "src/user_service.py", "import"))

    return graph


@pytest.fixture
def mock_workspace(tmp_path: Path, sample_symbol_graph: SymbolGraph) -> Path:
    """Creates physical workspace files corresponding to sample_symbol_graph."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "base_auth.py").write_text("class BaseAuthService:\n    pass\n", encoding="utf-8")
    (src_dir / "user_service.py").write_text(
        "from src.token_helper import generate_token\n"
        "from src.base_auth import BaseAuthService\n\n"
        "class UserService(BaseAuthService):\n"
        "    def authenticate(self, username, password):\n"
        "        token = generate_token(username)\n"
        "        return token\n",
        encoding="utf-8",
    )
    (src_dir / "token_helper.py").write_text("def generate_token(user):\n    return f'token_{user}'\n", encoding="utf-8")
    (src_dir / "auth_controller.py").write_text(
        "from src.user_service import UserService\n\n"
        "class AuthController:\n"
        "    def login(self, u, p):\n"
        "        return UserService().authenticate(u, p)\n",
        encoding="utf-8",
    )
    (src_dir / "oauth_service.py").write_text(
        "from src.user_service import UserService\n\n"
        "class UserOAuthService(UserService):\n"
        "    pass\n",
        encoding="utf-8",
    )
    (tests_dir / "test_user_service.py").write_text(
        "from src.user_service import UserService\n\n"
        "def test_user_authentication():\n"
        "    svc = UserService()\n"
        "    assert svc.authenticate('alice', 'secret') is not None\n",
        encoding="utf-8",
    )

    # Save index to memory/code_index.json
    index_file = mem_dir / "code_index.json"
    sample_symbol_graph.export_json(index_file)

    return tmp_path


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------

def test_1_direct_symbol_retrieval(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 1: Directly retrieves target symbol matching task description."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-AUTH-01",
        title="Modify authenticate method in UserService",
        description="Enhance UserService.authenticate to validate password complexity.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    assert isinstance(result, CodeContextResult)
    assert result.task_id == "TASK-AUTH-01"
    symbol_names = [s.name for s in result.relevant_symbols]
    assert "authenticate" in symbol_names
    assert "UserService" in symbol_names


def test_2_estimated_file_matching(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 2: Matches and scores symbols residing within task estimated_files."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-TOKEN-01",
        title="Refactor token generation",
        description="Update signature of token generator.",
        estimated_files=["src/token_helper.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    file_paths = [f.path for f in result.relevant_files]
    assert "src/token_helper.py" in file_paths
    assert any(s.file == "src/token_helper.py" for s in result.relevant_symbols)


def test_3_caller_retrieval(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 3: Correctly retrieves upstream callers of target method."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-CALL-01",
        title="Update authenticate signature",
        description="Modify authenticate method parameters.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    assert any("AuthController.login" in caller or "login" in caller for caller in result.callers)


def test_4_callee_retrieval(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 4: Correctly retrieves downstream callees used by target method."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-CALLEE-01",
        title="Refactor authenticate logic",
        description="Inspect callees within UserService.authenticate.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    assert any("generate_token" in callee for callee in result.callees)


def test_5_dependency_retrieval(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 5: Retrieves direct imported dependencies for the target files."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-DEP-01",
        title="Refactor UserService",
        description="Inspect dependencies of UserService.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    assert "src/token_helper.py" in result.dependencies
    assert "src/base_auth.py" in result.dependencies


def test_6_reverse_dependency_retrieval(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 6: Retrieves reverse dependents importing the target files."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-REV-01",
        title="Update UserService dependencies",
        description="Check modules depending on UserService.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    assert "src/auth_controller.py" in result.dependents
    assert "src/oauth_service.py" in result.dependents


def test_7_inheritance_context(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 7: Retrieves base classes and subclasses in inheritance hierarchy."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-INH-01",
        title="Inheritance audit for UserService",
        description="Verify BaseAuthService and UserOAuthService relationships.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    assert "BaseAuthService" in result.base_classes
    assert any("UserOAuthService" in sub for sub in result.subclasses)


def test_8_relevant_tests_discovery(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 8: Automatically detects test files associated with target symbols."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-TEST-01",
        title="Fix bug in authenticate",
        description="Ensure tests for authenticate are discovered.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    assert "tests/test_user_service.py" in result.test_files


def test_9_token_budget_enforcement(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 9: Respects maximum token budget and flags truncation when exceeded."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-BUDGET-01",
        title="Modify authenticate",
        description="Authenticate token testing under strict budget.",
        estimated_files=["src/user_service.py"],
    )

    # Restrict to very tight token budget
    result = retriever.retrieve(context={}, task=task, max_tokens=25)
    assert result.token_estimate <= 35
    assert len(result.relevant_files) > 0


def test_10_graph_depth_protection(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 10: Enforces max_graph_depth to prevent unlimited graph explosion."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
        max_graph_depth=1,
    )
    task = Task(
        id="TASK-DEPTH-01",
        title="Modify authenticate",
        description="Authenticate with 1-hop limit.",
        estimated_files=["src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    # Check that retrieved files are within direct or 1-hop scope
    for f in result.relevant_files:
        assert f.path in {
            "src/user_service.py",
            "src/token_helper.py",
            "src/base_auth.py",
            "src/auth_controller.py",
            "src/oauth_service.py",
            "tests/test_user_service.py",
        }


def test_11_duplicate_elimination(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 11: Ensures no duplicate files or symbols appear in retrieval result."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-DEDUP-01",
        title="Refactor authenticate and UserService in src/user_service.py",
        description="UserService authenticate method",
        estimated_files=["src/user_service.py", "src/user_service.py"],
    )

    result = retriever.retrieve(context={}, task=task)
    file_paths = [f.path for f in result.relevant_files]
    assert len(file_paths) == len(set(file_paths))
    symbol_ids = [s.symbol_id for s in result.relevant_symbols]
    assert len(symbol_ids) == len(set(symbol_ids))


def test_12_deterministic_ranking(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 12: Multiple retrieval runs on the exact same task yield identical output."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    task = Task(
        id="TASK-DETERM-01",
        title="Update authenticate in UserService",
        description="Deterministic verification of ranking order.",
        estimated_files=["src/user_service.py"],
    )

    res1 = retriever.retrieve(context={}, task=task)
    res2 = retriever.retrieve(context={}, task=task)

    assert res1.to_dict() == res2.to_dict()


def test_13_empty_graph_handling(tmp_path: Path):
    """Test 13: Handles empty symbol graph gracefully without errors."""
    empty_graph = SymbolGraph()
    retriever = CodeContextRetriever(symbol_graph=empty_graph, project_root=tmp_path)
    task = Task(id="EMPTY-01", title="Some task", description="No indexed files")

    result = retriever.retrieve(context={}, task=task)
    assert result.task_id == "EMPTY-01"
    assert len(result.relevant_symbols) == 0
    assert len(result.relevant_files) == 0


def test_14_unsupported_project_no_files(tmp_path: Path):
    """Test 14: Handles project with missing files without crashing."""
    graph = SymbolGraph()
    graph.add_symbol(
        Symbol(
            id="missing.py::Foo",
            name="Foo",
            qualified_name="Foo",
            symbol_type=SymbolType.CLASS,
            language="python",
            file="missing.py",
            line=1,
            end_line=10,
        )
    )
    retriever = CodeContextRetriever(symbol_graph=graph, project_root=tmp_path)
    task = Task(id="MISSING-01", title="Foo task", description="Foo implementation")

    result = retriever.retrieve(context={}, task=task)
    assert len(result.relevant_symbols) == 1
    # Missing physical file is omitted from content slice safely
    assert len(result.relevant_files) == 0


def test_15_prompt_builder_integration(mock_workspace: Path, sample_symbol_graph: SymbolGraph):
    """Test 15: Validates complete end-to-end integration into PromptBuilder."""
    retriever = CodeContextRetriever(
        symbol_graph=sample_symbol_graph,
        project_root=mock_workspace,
    )
    builder = PromptBuilder(code_context_retriever=retriever)

    task = Task(
        id="TASK-INTEG-01",
        title="Modify UserService.authenticate",
        description="Update authentication routine to handle lockout.",
        estimated_files=["src/user_service.py"],
    )
    context = {
        "project_name": "AuthEngine",
        "description": "Enterprise Authentication Engine",
        "technology_stack": "Python 3.11",
        "current_day": 1,
        "current_phase": {"phase_name": "Core Security", "goals": ["Implement JWT auth"]},
        "directory_tree": ["src/", "src/user_service.py"],
        "project_files": {"src/user_service.py": "class UserService:\n    pass\n"},
    }

    prompt = builder.build(context=context, task=task)
    assert "8. RELEVANT CODE CONTEXT" in prompt
    assert "src/user_service.py" in prompt
    assert "12. ENGINEERING CONSTRAINTS" in prompt
    assert "Inspect impact information before changing public APIs" in prompt
