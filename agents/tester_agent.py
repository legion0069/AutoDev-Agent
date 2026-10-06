"""
tester_agent.py - Automated Testing & Quality Assurance Agent for AutoDev

Responsible for detecting project test configurations, executing test suites via
isolated subprocesses, capturing telemetry (stdout, stderr, duration, exit code),
and parsing test outcome summaries into structured TestResult metrics.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Module logger
logger = logging.getLogger("AutoDev.TesterAgent")


class TesterInfrastructureError(Exception):
    """
    Raised when test execution cannot start due to environmental or infrastructure issues
    (e.g., invalid directory, missing binary, subprocess launch failure).
    """
    __test__ = False


@dataclass
class TestResult:
    """
    Structured execution summary and metrics of a project test suite run.
    """
    __test__ = False

    success: bool
    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration: float
    stdout: str
    stderr: str
    exit_code: int
    command: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Converts test result to a serializable dictionary."""
        return asdict(self)


def parse_pytest_output(output: str) -> tuple[int, int, int, int]:
    """
    Parses pytest terminal output and extracts counts for passed, failed, and skipped tests.

    Args:
        output: Combined stdout/stderr string from pytest.

    Returns:
        tuple of (passed, failed, skipped, total_tests)
    """
    passed = 0
    failed = 0
    skipped = 0

    # Look for the terminal summary line in pytest output, e.g.:
    # "=== 2 failed, 5 passed, 1 skipped, 1 error in 0.45s ==="
    # or "=== 1 passed in 0.01s ==="
    summary_match = re.search(r"=+\s*(.*?)\s+in\s+[\d\.]+s\s*=+", output, re.IGNORECASE)
    search_target = summary_match.group(1) if summary_match else output

    # Match passed count
    m_passed = re.search(r"(\d+)\s+passed", search_target, re.IGNORECASE)
    if m_passed:
        passed = int(m_passed.group(1))

    # Match failed count (and add collection/runtime errors)
    m_failed = re.search(r"(\d+)\s+failed", search_target, re.IGNORECASE)
    if m_failed:
        failed += int(m_failed.group(1))

    m_error = re.search(r"(\d+)\s+error", search_target, re.IGNORECASE)
    if m_error:
        failed += int(m_error.group(1))

    # Match skipped count
    m_skipped = re.search(r"(\d+)\s+skipped", search_target, re.IGNORECASE)
    if m_skipped:
        skipped = int(m_skipped.group(1))

    total = passed + failed + skipped
    return passed, failed, skipped, total


class TesterAgent:
    """
    Automated testing agent that detects, orchestrates, and parses test suite runs.
    """
    __test__ = False

    def __init__(self, default_timeout_seconds: float = 60.0) -> None:
        """
        Initializes the TesterAgent.

        Args:
            default_timeout_seconds: Maximum time in seconds allowed for test execution.
        """
        self.default_timeout_seconds = default_timeout_seconds

    def detect_test_command(self, project_root: Path) -> Optional[List[str]]:
        """
        Inspects project layout and configuration to determine the appropriate test command.

        Detection rules (Python):
        - pytest.ini exists
        - OR tests/ directory exists
        - OR pyproject.toml contains 'pytest'
        - OR requirements.txt contains 'pytest'

        Args:
            project_root: Workspace root directory.

        Returns:
            Command list (e.g. [sys.executable, "-m", "pytest", "-v"]) or None if no tests detected.
        """
        # Rule 1: pytest.ini exists
        if (project_root / "pytest.ini").is_file():
            logger.info("Detected 'pytest.ini' in project root.")
            return [sys.executable, "-m", "pytest", "-v"]

        # Rule 2: tests/ directory exists
        if (project_root / "tests").is_dir():
            logger.info("Detected 'tests/' directory in project root.")
            return [sys.executable, "-m", "pytest", "-v"]

        # Rule 3: pyproject.toml references pytest
        pyproject_path = project_root / "pyproject.toml"
        if pyproject_path.is_file():
            try:
                content = pyproject_path.read_text(encoding="utf-8", errors="replace")
                if "pytest" in content.lower():
                    logger.info("Detected pytest in 'pyproject.toml'.")
                    return [sys.executable, "-m", "pytest", "-v"]
            except OSError:
                pass

        # Rule 4: requirements.txt references pytest
        req_path = project_root / "requirements.txt"
        if req_path.is_file():
            try:
                content = req_path.read_text(encoding="utf-8", errors="replace")
                if "pytest" in content.lower():
                    logger.info("Detected pytest in 'requirements.txt'.")
                    return [sys.executable, "-m", "pytest", "-v"]
            except OSError:
                pass

        logger.info("No supported test suite configuration detected in '%s'.", project_root)
        return None

    def run_tests(
        self,
        project_root: Union[str, Path],
        command: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> TestResult:
        """
        Executes the test suite in the specified project directory.

        Args:
            project_root: Path to the target project workspace.
            command: Optional explicit command list override.
            timeout_seconds: Execution timeout limit.

        Returns:
            TestResult object with execution telemetry and test metrics.

        Raises:
            TesterInfrastructureError: If project directory is invalid or subprocess fails to launch.
        """
        target_path = Path(project_root).resolve()
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds

        # Validate workspace path
        if not target_path.exists():
            raise TesterInfrastructureError(
                f"Project directory '{target_path}' does not exist."
            )
        if not target_path.is_dir():
            raise TesterInfrastructureError(
                f"Project path '{target_path}' is not a directory."
            )

        # Detect test command if not explicitly supplied
        cmd = command or self.detect_test_command(target_path)

        if cmd is None:
            logger.info("Skipping test run: No test suite found in '%s'.", target_path)
            return TestResult(
                success=True,
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                duration=0.0,
                stdout="",
                stderr="",
                exit_code=0,
                command="",
                message="No test suite detected in project workspace.",
            )

        cmd_str = " ".join(cmd)
        logger.info("Executing test command in '%s': %s", target_path, cmd_str)

        start_time = time.time()

        try:
            process = subprocess.run(
                cmd,
                cwd=str(target_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = round(time.time() - start_time, 3)
            stdout = process.stdout or ""
            stderr = process.stderr or ""
            exit_code = process.returncode

        except subprocess.TimeoutExpired as exc:
            duration = round(time.time() - start_time, 3)
            logger.error("Test execution timed out after %s seconds.", timeout)
            return TestResult(
                success=False,
                total_tests=0,
                passed=0,
                failed=1,
                skipped=0,
                duration=duration,
                stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr or f"Execution timed out after {timeout} seconds.",
                exit_code=-1,
                command=cmd_str,
                message=f"Test suite execution timed out after {timeout} seconds.",
            )

        except (OSError, ValueError) as exc:
            logger.error("Failed to launch test subprocess: %s", exc)
            raise TesterInfrastructureError(
                f"Failed to launch test subprocess with command '{cmd_str}': {exc}"
            ) from exc

        # Parse test metrics from output
        passed, failed, skipped, total = parse_pytest_output(stdout + "\n" + stderr)

        # Exit code 0 means all tests passed
        if exit_code == 0:
            success = True
            if total > 0:
                message = f"All {passed} test(s) passed successfully in {duration}s."
            else:
                message = f"Test suite ran successfully with 0 tests executed in {duration}s."
        elif exit_code == 5:
            # Pytest exit code 5: No tests were collected
            success = True
            message = "No tests were collected by pytest."
        else:
            success = False
            message = f"Test suite failed with {failed} failure(s) out of {total} test(s) (exit code {exit_code})."

        logger.info(
            "Test run finished in %.3fs. Result: %s (Passed: %d, Failed: %d, Skipped: %d, Total: %d)",
            duration,
            "SUCCESS" if success else "FAILED",
            passed,
            failed,
            skipped,
            total,
        )

        return TestResult(
            success=success,
            total_tests=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration=duration,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            command=cmd_str,
            message=message,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-5s] %(message)s")

    # Run tests on current repository
    tester = TesterAgent()
    current_repo = Path.cwd()
    result = tester.run_tests(current_repo)

    print("\n" + "=" * 60)
    print("                 TESTER AGENT EXECUTION RESULT")
    print("=" * 60)
    print(f"Success     : {result.success}")
    print(f"Total Tests : {result.total_tests}")
    print(f"Passed      : {result.passed}")
    print(f"Failed      : {result.failed}")
    print(f"Skipped     : {result.skipped}")
    print(f"Duration    : {result.duration}s")
    print(f"Exit Code   : {result.exit_code}")
    print(f"Command     : {result.command}")
    print(f"Message     : {result.message}")
    print("=" * 60 + "\n")
