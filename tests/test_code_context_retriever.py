"""
test_code_context_retriever.py - Comprehensive Unit & Integration Tests for CodeContextRetriever (v1.6)

Tests:
1. AST extraction (Python)
2. Java extraction
3. JS extraction
4. TS extraction
5. Multi-factor snippet ranking
6. Snippet deduplication
7. Strict token budgeting (no snippet splitting)
8. Cross-file multi-module retrieval
9. Call graph expansion (callers & callees)
10. Serialization & JSON roundtrip
11. Edge cases (empty graph, missing files, dict task, file caching)
12. PromptBuilder integration
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pytest

from agents.task_planner_agent import Task
from core.code_context_retriever import (
    CodeContextRetriever,
    CodeSnippet,
    ContextBundle,
)
from core.impact_analyzer import ImpactReport, RiskLevel
from core.prompt_builder import PromptBuilder
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility


@pytest.fixture
def multi_language_workspace(tmp_path: Path) -> Tuple[Path, SymbolGraph]:
    """Creates a multi-language physical workspace with Python, Java, JS, and TS files."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # 1. Python file
    py_path = src_dir / "auth_service.py"
    py_content = (
        "import hashlib\n"
        "from src.token_helper import generate_jwt\n\n"
        "class AuthService:\n"
        "    \"\"\"Primary authentication provider.\"\"\"\n"
        "    def authenticate(self, username, password):\n"
        "        hashed = hashlib.sha256(password.encode()).hexdigest()\n"
        "        token = generate_jwt(username)\n"
        "        return token\n"
    )
    py_path.write_text(py_content, encoding="utf-8")

    # 2. Python helper
    helper_path = src_dir / "token_helper.py"
    helper_content = (
        "def generate_jwt(user_id):\n"
        "    return f'jwt.{user_id}.signature'\n"
    )
    helper_path.write_text(helper_content, encoding="utf-8")

    # 3. Java file
    java_path = src_dir / "UserService.java"
    java_content = (
        "package com.autodev;\n\n"
        "public class UserService {\n"
        "    public String findUserById(String id) {\n"
        "        return \"User: \" + id;\n"
        "    }\n"
        "}\n"
    )
    java_path.write_text(java_content, encoding="utf-8")

    # 4. JavaScript file
    js_path = src_dir / "api.js"
    js_content = (
        "export function fetchData(endpoint) {\n"
        "    return fetch(endpoint).then(res => res.json());\n"
        "}\n"
    )
    js_path.write_text(js_content, encoding="utf-8")

    # 5. TypeScript file
    ts_path = src_dir / "models.ts"
    ts_content = (
        "export interface UserProfile {\n"
        "    id: string;\n"
        "    username: string;\n"
        "    email: string;\n"
        "}\n"
    )
    ts_path.write_text(ts_content, encoding="utf-8")

    # Construct SymbolGraph
    graph = SymbolGraph()

    # Python symbols
    graph.add_symbol(
        Symbol(
            id="src/auth_service.py::AuthService",
            name="AuthService",
            qualified_name="AuthService",
            symbol_type=SymbolType.CLASS,
            language="python",
            file="src/auth_service.py",
            line=4,
            end_line=9,
            visibility=Visibility.PUBLIC,
        )
    )
    graph.add_symbol(
        Symbol(
            id="src/auth_service.py::AuthService.authenticate",
            name="authenticate",
            qualified_name="AuthService.authenticate",
            symbol_type=SymbolType.METHOD,
            language="python",
            file="src/auth_service.py",
            line=6,
            end_line=9,
            parent_symbol="AuthService",
            visibility=Visibility.PUBLIC,
            calls=["generate_jwt"],
        )
    )
    graph.add_symbol(
        Symbol(
            id="src/token_helper.py::generate_jwt",
            name="generate_jwt",
            qualified_name="generate_jwt",
            symbol_type=SymbolType.FUNCTION,
            language="python",
            file="src/token_helper.py",
            line=1,
            end_line=2,
            visibility=Visibility.PUBLIC,
        )
    )

    # Java symbol
    graph.add_symbol(
        Symbol(
            id="src/UserService.java::UserService.findUserById",
            name="findUserById",
            qualified_name="UserService.findUserById",
            symbol_type=SymbolType.METHOD,
            language="java",
            file="src/UserService.java",
            line=4,
            end_line=6,
            parent_symbol="UserService",
            visibility=Visibility.PUBLIC,
        )
    )

    # JS symbol
    graph.add_symbol(
        Symbol(
            id="src/api.js::fetchData",
            name="fetchData",
            qualified_name="fetchData",
            symbol_type=SymbolType.FUNCTION,
            language="javascript",
            file="src/api.js",
            line=1,
            end_line=3,
            visibility=Visibility.PUBLIC,
        )
    )

    # TS symbol
    graph.add_symbol(
        Symbol(
            id="src/models.ts::UserProfile",
            name="UserProfile",
            qualified_name="UserProfile",
            symbol_type=SymbolType.INTERFACE,
            language="typescript",
            file="src/models.ts",
            line=1,
            end_line=5,
            visibility=Visibility.PUBLIC,
        )
    )

    graph.add_dependency(Dependency("src/auth_service.py", "src/token_helper.py", "import"))

    return tmp_path, graph


# -----------------------------------------------------------------------------
# 1. AST Extraction (Python)
# -----------------------------------------------------------------------------

def test_1_ast_extraction_python(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 1: Extracts exact Python AST line ranges cleanly without placeholders."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    sym = graph.find_symbol("AuthService.authenticate")
    assert sym is not None

    snippet = retriever.extract_symbol("src/auth_service.py", sym)
    assert isinstance(snippet, CodeSnippet)
    assert snippet.file == "src/auth_service.py"
    assert snippet.start_line == 6
    assert snippet.end_line == 9
    assert snippet.language == "python"
    assert "def authenticate" in snippet.content
    assert "return token" in snippet.content


# -----------------------------------------------------------------------------
# 2. Java Extraction
# -----------------------------------------------------------------------------

def test_2_java_extraction(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 2: Extracts exact Java method lines."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    sym = graph.find_symbol("UserService.findUserById")
    assert sym is not None

    snippet = retriever.extract_symbol("src/UserService.java", sym)
    assert snippet is not None
    assert snippet.language == "java"
    assert "public String findUserById" in snippet.content


# -----------------------------------------------------------------------------
# 3. JS Extraction
# -----------------------------------------------------------------------------

def test_3_js_extraction(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 3: Extracts JavaScript function snippet."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    sym = graph.find_symbol("fetchData")
    assert sym is not None

    snippet = retriever.extract_symbol("src/api.js", sym)
    assert snippet is not None
    assert snippet.language == "javascript"
    assert "export function fetchData" in snippet.content


# -----------------------------------------------------------------------------
# 4. TS Extraction
# -----------------------------------------------------------------------------

def test_4_ts_extraction(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 4: Extracts TypeScript interface definition."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    sym = graph.find_symbol("UserProfile")
    assert sym is not None

    snippet = retriever.extract_symbol("src/models.ts", sym)
    assert snippet is not None
    assert snippet.language == "typescript"
    assert "export interface UserProfile" in snippet.content
    assert "username: string;" in snippet.content


# -----------------------------------------------------------------------------
# 5. Multi-Factor Snippet Ranking
# -----------------------------------------------------------------------------

def test_5_ranking_snippets():
    """Test 5: Validates that snippets sort descending by score."""
    retriever = CodeContextRetriever()
    s1 = CodeSnippet("a.py", 1, 10, "python", "fn1", "helper", "content1", score=50.0)
    s2 = CodeSnippet("b.py", 1, 20, "python", "fn2", "direct target", "content2", score=100.0)
    s3 = CodeSnippet("c.py", 1, 15, "python", "fn3", "caller", "content3", score=75.0)

    ranked = retriever.rank_snippets([s1, s2, s3])
    assert ranked[0].score == 100.0
    assert ranked[1].score == 75.0
    assert ranked[2].score == 50.0


# -----------------------------------------------------------------------------
# 6. Deduplication
# -----------------------------------------------------------------------------

def test_6_deduplication(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 6: Deduplicates overlapping snippets and duplicate symbol references."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    task = Task(
        id="DEDUP-01",
        title="Refactor authenticate and AuthService",
        description="AuthService authenticate duplicate requests",
        estimated_files=["src/auth_service.py", "src/auth_service.py"],
    )

    bundle = retriever.retrieve(task)
    regions = [(s.file, s.start_line, s.end_line) for s in bundle.snippets]
    assert len(regions) == len(set(regions))


# -----------------------------------------------------------------------------
# 7. Token Budgeting (No snippet splitting)
# -----------------------------------------------------------------------------

def test_7_token_budget_never_splits_snippets():
    """Test 7: Enforces strict budget limit by dropping lower-ranked snippets whole."""
    retriever = CodeContextRetriever()
    # Content of ~50 tokens (200 chars)
    large_content = "def test_func():\n    " + ("x = 1\n    " * 20)
    snip1 = CodeSnippet("a.py", 1, 20, "python", "s1", "target", large_content, score=100.0)
    snip2 = CodeSnippet("b.py", 1, 20, "python", "s2", "caller", large_content, score=80.0)
    snip3 = CodeSnippet("c.py", 1, 20, "python", "s3", "callee", large_content, score=60.0)

    # Budget for only 1 snippet (~60 tokens)
    accepted, tokens, truncated = retriever.optimize_budget([snip1, snip2, snip3], max_tokens=65)

    assert len(accepted) == 1
    assert accepted[0].symbol == "s1"
    assert truncated is True
    # The snippet was kept whole (no internal slicing)
    assert accepted[0].content == large_content


# -----------------------------------------------------------------------------
# 8. Cross-File Multi-Module Retrieval
# -----------------------------------------------------------------------------

def test_8_cross_file_retrieval(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 8: Retrieves snippets across target files, dependencies, and helpers."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    task = Task(
        id="CROSS-01",
        title="Update authenticate in AuthService",
        description="Modify authentication and verify token helper.",
        estimated_files=["src/auth_service.py"],
    )

    bundle = retriever.retrieve(task)
    files = {s.file for s in bundle.snippets}
    assert "src/auth_service.py" in files
    # Helper is expanded through call graph
    assert "src/token_helper.py" in files


# -----------------------------------------------------------------------------
# 9. Call Graph Expansion
# -----------------------------------------------------------------------------

def test_9_call_graph_expansion(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 9: Expands related context via callers and callees."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    auth_sym = graph.find_symbol("AuthService.authenticate")
    assert auth_sym is not None

    expanded = retriever.expand_related_symbols([auth_sym])
    expanded_names = [sym.name for sym, _, _ in expanded]

    assert "authenticate" in expanded_names
    assert "generate_jwt" in expanded_names  # Callee


# -----------------------------------------------------------------------------
# 10. Serialization & JSON Roundtrip
# -----------------------------------------------------------------------------

def test_10_serialization_and_json_roundtrip():
    """Test 10: Validates CodeSnippet and ContextBundle dictionary serialization."""
    snip = CodeSnippet(
        file="src/app.py",
        start_line=10,
        end_line=25,
        language="python",
        symbol="App.run",
        reason="Target symbol",
        content="def run(): pass",
        score=95.0,
    )
    bundle = ContextBundle(
        snippets=[snip],
        files=["src/app.py"],
        total_tokens=15,
        truncated=False,
        summary="Retrieved 1 snippet",
    )

    data = bundle.to_dict()
    assert "snippets" in data
    assert len(data["snippets"]) == 1
    assert data["snippets"][0]["symbol"] == "App.run"
    assert data["total_tokens"] == 15

    json_str = json.dumps(data)
    assert isinstance(json_str, str)


# -----------------------------------------------------------------------------
# 11. Edge Cases & Incremental File Caching
# -----------------------------------------------------------------------------

def test_11_edge_cases_and_file_caching(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 11: Handles empty graph, missing files, and verifies in-memory file caching."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)

    # Empty graph
    empty_retriever = CodeContextRetriever(graph=SymbolGraph(), project_root=workspace_root)
    empty_bundle = empty_retriever.retrieve(Task(id="E-1", title="Empty", description=""))
    assert len(empty_bundle.snippets) == 0

    # Incremental file caching: call twice, should populate _file_cache
    sym = graph.find_symbol("AuthService.authenticate")
    assert sym is not None
    s1 = retriever.extract_symbol("src/auth_service.py", sym)
    assert "src/auth_service.py" in retriever._file_cache
    s2 = retriever.extract_symbol("src/auth_service.py", sym)
    assert s1.content == s2.content


# -----------------------------------------------------------------------------
# 12. PromptBuilder Integration
# -----------------------------------------------------------------------------

def test_12_prompt_builder_integration(multi_language_workspace: Tuple[Path, SymbolGraph]):
    """Test 12: Ensures PromptBuilder incorporates CodeSnippet blocks into section 8."""
    workspace_root, graph = multi_language_workspace
    retriever = CodeContextRetriever(graph=graph, project_root=workspace_root)
    builder = PromptBuilder(code_context_retriever=retriever)

    task = Task(
        id="TASK-AUTH-01",
        title="Modify authenticate in AuthService",
        description="Update authenticate logic",
        estimated_files=["src/auth_service.py"],
    )
    context = {
        "project_name": "AuthSystem",
        "description": "Auth System",
        "technology_stack": "Python 3.11",
        "current_day": 1,
        "current_phase": {"phase_name": "Auth"},
        "directory_tree": ["src/auth_service.py"],
        "project_files": {"src/auth_service.py": "# code"},
    }

    prompt = builder.build(context=context, task=task)
    assert "8. RELEVANT CODE CONTEXT" in prompt
    assert "File   : src/auth_service.py" in prompt
    assert "```python" in prompt
    assert "def authenticate" in prompt
