"""
test_code_indexer.py - Comprehensive Unit Tests for AutoDev CodeIndexer & SymbolGraph

Tests AST/regex parsing for Python, Java, JS/TS, inheritance hierarchies, call graphs,
file dependencies, topological ordering, search API, incremental indexing with SHA256,
and JSON persistence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.code_indexer import CodeIndexer
from core.symbol_graph import (
    Dependency,
    IndexStatistics,
    Reference,
    Symbol,
    SymbolGraph,
    SymbolType,
    Visibility,
)


@pytest.fixture
def mock_project(tmp_path: Path) -> Path:
    """Sets up a multi-language mock repository for indexing."""
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # 1. Python files
    py_models = project_dir / "models.py"
    py_models.write_text(
        '"""Database models module."""\n'
        'DEFAULT_TIMEOUT = 30\n'
        'max_retries = 3\n\n'
        'class BaseModel:\n'
        '    """Base entity model."""\n'
        '    def __init__(self, id: str):\n'
        '        self.id = id\n\n'
        '    def save(self) -> bool:\n'
        '        return True\n\n'
        'class UserModel(BaseModel):\n'
        '    """User record model."""\n'
        '    def __init__(self, id: str, username: str):\n'
        '        super().__init__(id)\n'
        '        self.username = username\n\n'
        '    def authenticate(self, password: str) -> bool:\n'
        '        self.save()\n'
        '        return True\n',
        encoding="utf-8",
    )

    py_service = project_dir / "service.py"
    py_service.write_text(
        'from models import UserModel, DEFAULT_TIMEOUT\n\n'
        'def create_user(user_id: str, name: str) -> UserModel:\n'
        '    """Creates and returns a new user."""\n'
        '    user = UserModel(user_id, name)\n'
        '    user.save()\n'
        '    return user\n',
        encoding="utf-8",
    )

    # 2. Java files
    java_dir = project_dir / "src" / "main" / "java" / "com" / "example"
    java_dir.mkdir(parents=True, exist_ok=True)
    java_service = java_dir / "AuthService.java"
    java_service.write_text(
        'package com.example;\n'
        'import java.util.List;\n\n'
        'public interface IAuthService {\n'
        '    boolean login(String username, String password);\n'
        '}\n\n'
        'public class AuthService implements IAuthService {\n'
        '    private String secretKey;\n\n'
        '    public AuthService(String secretKey) {\n'
        '        this.secretKey = secretKey;\n'
        '    }\n\n'
        '    /** Authenticates user with credentials. */\n'
        '    @Override\n'
        '    public boolean login(String username, String password) {\n'
        '        return true;\n'
        '    }\n'
        '}\n',
        encoding="utf-8",
    )

    # 3. TypeScript files
    ts_dir = project_dir / "src" / "frontend"
    ts_dir.mkdir(parents=True, exist_ok=True)
    ts_file = ts_dir / "apiClient.ts"
    ts_file.write_text(
        'import { Config } from "./config";\n\n'
        'export interface ApiResponse<T> {\n'
        '    data: T;\n'
        '    status: number;\n'
        '}\n\n'
        'export enum HttpMethod {\n'
        '    GET = "GET",\n'
        '    POST = "POST"\n'
        '}\n\n'
        'export class ApiClient {\n'
        '    async fetchUser(id: string): Promise<ApiResponse<any>> {\n'
        '        return { data: { id }, status: 200 };\n'
        '    }\n'
        '}\n\n'
        'export const initClient = (baseUrl: string) => {\n'
        '    return new ApiClient();\n'
        '};\n',
        encoding="utf-8",
    )

    return project_dir


# =============================================================================
# 1. Python AST Parsing Tests
# =============================================================================

def test_python_parsing(mock_project: Path, tmp_path: Path):
    """Verifies that Python classes, methods, constructors, constants, and calls are parsed."""
    indexer = CodeIndexer(
        project_root=mock_project,
        output_path=tmp_path / "code_index.json",
        auto_load=False,
    )
    graph = indexer.index_project()

    # Verify Classes
    base_model = graph.find_symbol("BaseModel")
    assert base_model is not None
    assert base_model.symbol_type == SymbolType.CLASS
    assert base_model.docstring == "Base entity model."

    user_model = graph.find_symbol("UserModel")
    assert user_model is not None
    assert "BaseModel" in user_model.inherits

    # Verify Constructors and Methods
    user_init = graph.find_symbol("UserModel.__init__")
    assert user_init is not None
    assert user_init.symbol_type == SymbolType.CONSTRUCTOR

    user_auth = graph.find_symbol("UserModel.authenticate")
    assert user_auth is not None
    assert user_auth.symbol_type == SymbolType.METHOD
    assert "self.save" in user_auth.calls or "save" in user_auth.calls

    # Verify Constant & Variable
    timeout_const = graph.find_symbol("DEFAULT_TIMEOUT")
    assert timeout_const is not None
    assert timeout_const.symbol_type == SymbolType.CONSTANT

    # Verify Functions
    create_fn = graph.find_symbol("create_user")
    assert create_fn is not None
    assert create_fn.symbol_type == SymbolType.FUNCTION
    assert "UserModel" in create_fn.calls


# =============================================================================
# 2. Java Parsing Tests
# =============================================================================

def test_java_parsing(mock_project: Path, tmp_path: Path):
    """Verifies parsing Java interfaces, classes, constructors, methods, and annotations."""
    indexer = CodeIndexer(
        project_root=mock_project,
        output_path=tmp_path / "code_index.json",
        auto_load=False,
    )
    graph = indexer.index_project()

    # Interface
    auth_iface = graph.find_symbol("IAuthService")
    assert auth_iface is not None
    assert auth_iface.symbol_type == SymbolType.INTERFACE

    # Class & Implements
    auth_class = graph.find_symbol("AuthService")
    assert auth_class is not None
    assert auth_class.symbol_type == SymbolType.CLASS
    assert "IAuthService" in auth_class.implements

    # Constructor & Method
    auth_ctor = graph.find_symbol("AuthService.AuthService")
    assert auth_ctor is not None
    assert auth_ctor.symbol_type == SymbolType.CONSTRUCTOR

    login_method = graph.find_symbol("AuthService.login")
    assert login_method is not None
    assert login_method.symbol_type == SymbolType.METHOD
    assert "@Override" in login_method.decorators
    assert login_method.docstring == "Authenticates user with credentials."


# =============================================================================
# 3. TypeScript Parsing Tests
# =============================================================================

def test_typescript_parsing(mock_project: Path, tmp_path: Path):
    """Verifies parsing TypeScript interfaces, enums, classes, methods, and arrow functions."""
    indexer = CodeIndexer(
        project_root=mock_project,
        output_path=tmp_path / "code_index.json",
        auto_load=False,
    )
    graph = indexer.index_project()

    # Interface & Enum
    resp_iface = graph.find_symbol("ApiResponse")
    assert resp_iface is not None
    assert resp_iface.symbol_type == SymbolType.INTERFACE

    http_enum = graph.find_symbol("HttpMethod")
    assert http_enum is not None
    assert http_enum.symbol_type == SymbolType.ENUM

    # Class
    client_class = graph.find_symbol("ApiClient")
    assert client_class is not None
    assert client_class.symbol_type == SymbolType.CLASS

    # Arrow function
    init_fn = graph.find_symbol("initClient")
    assert init_fn is not None
    assert init_fn.symbol_type == SymbolType.FUNCTION


# =============================================================================
# 4. Graph Traversals: Subclasses, Callers, Dependencies
# =============================================================================

def test_inheritance_and_subclass_queries(mock_project: Path, tmp_path: Path):
    """Verifies finding subclasses and base classes."""
    indexer = CodeIndexer(mock_project, output_path=tmp_path / "code_index.json")
    graph = indexer.index_project()

    subclasses = graph.find_subclasses("BaseModel")
    assert len(subclasses) == 1
    assert subclasses[0].name == "UserModel"

    bases = graph.find_base_classes("UserModel")
    assert "BaseModel" in bases


def test_file_dependencies_and_topological_order(mock_project: Path, tmp_path: Path):
    """Verifies file dependency edges and topological ordering."""
    indexer = CodeIndexer(mock_project, output_path=tmp_path / "code_index.json")
    graph = indexer.index_project()

    # service.py imports models.py
    dependents = graph.find_dependents("models.py")
    assert "service.py" in dependents

    dependencies = graph.find_dependencies("service.py")
    assert "models.py" in dependencies

    order = graph.topological_order()
    assert "models.py" in order
    assert "service.py" in order
    # models.py must appear before service.py in topological order
    assert order.index("models.py") < order.index("service.py")


# =============================================================================
# 5. Search API Tests
# =============================================================================

def test_search_api_queries(mock_project: Path, tmp_path: Path):
    """Verifies name, type, file, language, docstring, and regex searches."""
    indexer = CodeIndexer(mock_project, output_path=tmp_path / "code_index.json")
    graph = indexer.index_project()

    # Search by name
    assert len(graph.search_by_name("User")) >= 2
    assert len(graph.search_by_name("UserModel", exact=True)) == 1

    # Search by type
    classes = graph.search_by_type(SymbolType.CLASS)
    assert any(c.name == "UserModel" for c in classes)
    assert any(c.name == "AuthService" for c in classes)

    # Search by language
    py_syms = graph.search_by_language("python")
    assert len(py_syms) >= 4

    # Search docstrings
    doc_matches = graph.search_docstring("credentials")
    assert len(doc_matches) == 1
    assert doc_matches[0].name == "login"

    # Search regex
    regex_matches = graph.search_regex(r"^Auth.*")
    assert any(s.name == "AuthService" for s in regex_matches)


# =============================================================================
# 6. Incremental Indexing with SHA256 Tests
# =============================================================================

def test_incremental_indexing_skips_unmodified_files(mock_project: Path, tmp_path: Path):
    """Verifies that indexing unchanged files reuses previous hashes."""
    indexer = CodeIndexer(mock_project, output_path=tmp_path / "code_index.json")
    g1 = indexer.index_project()
    initial_hash = g1.file_hashes["models.py"]

    # Re-indexing without modifications
    g2 = indexer.index_project()
    assert g2.file_hashes["models.py"] == initial_hash

    # Modify models.py
    py_models = mock_project / "models.py"
    py_models.write_text(
        py_models.read_text(encoding="utf-8") + "\nclass CustomerModel(BaseModel):\n    pass\n",
        encoding="utf-8",
    )

    g3 = indexer.index_project()
    assert g3.file_hashes["models.py"] != initial_hash
    assert g3.find_symbol("CustomerModel") is not None


def test_incremental_indexing_handles_deleted_files(mock_project: Path, tmp_path: Path):
    """Verifies that deleted files are removed from the index."""
    indexer = CodeIndexer(mock_project, output_path=tmp_path / "code_index.json")
    indexer.index_project()
    assert indexer.graph.find_symbol("create_user") is not None

    # Delete service.py
    (mock_project / "service.py").unlink()

    indexer.index_project()
    assert indexer.graph.find_symbol("create_user") is None
    assert "service.py" not in indexer.graph.file_hashes


# =============================================================================
# 7. JSON Persistence & Statistics Tests
# =============================================================================

def test_export_import_json(mock_project: Path, tmp_path: Path):
    """Verifies exporting and importing SymbolGraph via JSON."""
    index_file = tmp_path / "exported_index.json"
    indexer = CodeIndexer(mock_project, output_path=index_file)
    graph = indexer.index_project()

    exported_str = graph.export_json(index_file)
    assert index_file.exists()
    assert "UserModel" in exported_str

    # Load into fresh graph
    fresh_graph = SymbolGraph()
    fresh_graph.import_json(index_file)
    assert fresh_graph.find_symbol("UserModel") is not None
    assert len(fresh_graph.symbols) == len(graph.symbols)


def test_statistics_telemetry(mock_project: Path, tmp_path: Path):
    """Verifies index statistics computation."""
    indexer = CodeIndexer(mock_project, output_path=tmp_path / "code_index.json")
    indexer.index_project()
    stats = indexer.statistics()

    assert stats.total_files == 4
    assert stats.total_symbols > 0
    assert stats.classes >= 3
    assert stats.functions >= 2
    assert "python" in stats.languages
    assert "java" in stats.languages
    assert "typescript" in stats.languages

    stats_dict = stats.to_dict()
    assert stats_dict["total_files"] == 4
