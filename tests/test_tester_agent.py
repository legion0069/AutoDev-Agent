"""
test_tester_agent.py - Comprehensive Unit & Integration Tests for TesterAgent

Validates:
- Successful pytest execution and metrics capture
- Failing test execution and non-crashing failure reporting
- Skipped tests handling
- Project type detection rules (pytest.ini, tests/, pyproject.toml, requirements.txt)
- Missing test suite handling
- Invalid project directory error handling
- Subprocess timeout handling
- Pytest output parser correctness across various output formats
"""

import sys
import pytest
from pathlib import Path
from agents.tester_agent import (
    TesterAgent,
    TesterInfrastructureError,
    TestResult,
    parse_pytest_output,
)


@pytest.fixture
def mock_python_project(tmp_path: Path) -> Path:
    """Creates a temporary Python project workspace with a tests/ folder."""
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def test_parser_various_formats():
    """Unit tests verifying regex parser for multiple pytest summary formats."""
    # 1. Simple passing
    p, f, s, t = parse_pytest_output("=== 5 passed in 0.12s ===")
    assert p == 5 and f == 0 and s == 0 and t == 5

    # 2. Mixed passing, failing, and skipped
    p, f, s, t = parse_pytest_output("=== 3 passed, 2 failed, 1 skipped in 1.45s ===")
    assert p == 3 and f == 2 and s == 1 and t == 6

    # 3. Collection/runtime errors counted as failures
    p, f, s, t = parse_pytest_output("=== 1 passed, 1 error in 0.05s ===")
    assert p == 1 and f == 1 and s == 0 and t == 2

    # 4. No tests ran
    p, f, s, t = parse_pytest_output("=== no tests ran in 0.01s ===")
    assert p == 0 and f == 0 and s == 0 and t == 0

    # 5. Empty or unformatted string
    p, f, s, t = parse_pytest_output("Random logging without summary")
    assert p == 0 and f == 0 and s == 0 and t == 0


def test_successful_pytest_run(mock_python_project: Path):
    """Verifies that passing tests return TestResult with success=True and correct counts."""
    test_file = mock_python_project / "tests" / "test_math.py"
    test_file.write_text(
        "def test_add(): assert 1 + 1 == 2\n"
        "def test_sub(): assert 5 - 3 == 2\n",
        encoding="utf-8",
    )

    tester = TesterAgent()
    result = tester.run_tests(mock_python_project)

    assert isinstance(result, TestResult)
    assert result.success is True
    assert result.exit_code == 0
    assert result.passed == 2
    assert result.failed == 0
    assert result.total_tests == 2
    assert result.duration > 0
    assert "2 test(s) passed successfully" in result.message


def test_failing_pytest_run(mock_python_project: Path):
    """Verifies that failing tests return TestResult with success=False without raising exceptions."""
    test_file = mock_python_project / "tests" / "test_failing.py"
    test_file.write_text(
        "def test_pass(): assert True\n"
        "def test_fail(): assert 1 == 2\n",
        encoding="utf-8",
    )

    tester = TesterAgent()
    result = tester.run_tests(mock_python_project)

    assert isinstance(result, TestResult)
    assert result.success is False
    assert result.exit_code != 0
    assert result.passed == 1
    assert result.failed == 1
    assert result.total_tests == 2
    assert "Test suite failed with 1 failure(s)" in result.message


def test_skipped_pytest_run(mock_python_project: Path):
    """Verifies that skipped tests are properly parsed into the skipped metric."""
    test_file = mock_python_project / "tests" / "test_skipped.py"
    test_file.write_text(
        "import pytest\n"
        "@pytest.mark.skip(reason='testing skip')\n"
        "def test_skip(): pass\n"
        "def test_ok(): assert True\n",
        encoding="utf-8",
    )

    tester = TesterAgent()
    result = tester.run_tests(mock_python_project)

    assert isinstance(result, TestResult)
    assert result.success is True
    assert result.passed == 1
    assert result.skipped == 1
    assert result.failed == 0
    assert result.total_tests == 2


def test_no_test_suite_detected(tmp_path: Path):
    """Verifies that empty workspace without test files returns graceful non-error result."""
    empty_dir = tmp_path / "empty_project"
    empty_dir.mkdir(parents=True, exist_ok=True)

    tester = TesterAgent()
    result = tester.run_tests(empty_dir)

    assert result.success is True
    assert result.total_tests == 0
    assert result.command == ""
    assert "No test suite detected" in result.message


def test_detection_rules(tmp_path: Path):
    """Verifies detection of pytest through various project layout files."""
    tester = TesterAgent()

    # Case 1: pytest.ini
    p1 = tmp_path / "proj1"
    p1.mkdir()
    (p1 / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    assert tester.detect_test_command(p1) is not None

    # Case 2: pyproject.toml with pytest
    p2 = tmp_path / "proj2"
    p2.mkdir()
    (p2 / "pyproject.toml").write_text('[tool.pytest.ini_options]\n', encoding="utf-8")
    assert tester.detect_test_command(p2) is not None

    # Case 3: requirements.txt with pytest
    p3 = tmp_path / "proj3"
    p3.mkdir()
    (p3 / "requirements.txt").write_text('pytest>=7.0.0\n', encoding="utf-8")
    assert tester.detect_test_command(p3) is not None


def test_invalid_project_directory():
    """Verifies that non-existent directory raises TesterInfrastructureError."""
    tester = TesterAgent()
    with pytest.raises(TesterInfrastructureError, match="does not exist"):
        tester.run_tests("non_existent_path_xyz_12345")


def test_subprocess_timeout(mock_python_project: Path):
    """Verifies that long-running tests trigger timeout and return failure result."""
    test_file = mock_python_project / "tests" / "test_timeout.py"
    test_file.write_text(
        "import time\n"
        "def test_sleep(): time.sleep(3)\n",
        encoding="utf-8",
    )

    tester = TesterAgent(default_timeout_seconds=0.2)
    result = tester.run_tests(mock_python_project)

    assert result.success is False
    assert result.exit_code == -1
    assert "timed out" in result.message.lower()
