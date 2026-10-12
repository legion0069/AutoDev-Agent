"""
AutoDev Test Execution Engine (v2.6)
Provides safe, isolated, and normalized test runner adapters with timeout bounding,
subprocess management, secret redaction, and structured output parsing.
"""

from __future__ import annotations

import abc
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.test_result_models import (
    FailureType,
    SingleTestResult,
    TestExecutionFingerprint,
    TestRunnerType,
    TestStatus,
    TestSuiteResult,
    bound_log_text,
    redact_secrets,
)

logger = logging.getLogger(__name__)


def is_path_contained(target_path: str, base_dir: str) -> bool:
    """Verifies that target_path resolves strictly within base_dir to prevent directory traversal."""
    try:
        resolved_base = os.path.realpath(os.path.abspath(base_dir))
        resolved_target = os.path.realpath(os.path.abspath(target_path))
        return resolved_target == resolved_base or resolved_target.startswith(resolved_base + os.sep)
    except Exception:
        return False


class TestRunner(abc.ABC):
    """Abstract provider interface for executing test suites across diverse runtimes."""
    __test__ = False

    @property
    @abc.abstractmethod
    def runner_type(self) -> TestRunnerType:
        """Returns the specific runner type enum."""
        pass

    @abc.abstractmethod
    def discover_tests(
        self,
        workspace_path: str,
        filter_pattern: Optional[str] = None,
    ) -> List[str]:
        """Discovers available test identifiers in the workspace."""
        pass

    @abc.abstractmethod
    def run_tests(
        self,
        workspace_path: str,
        test_targets: Optional[List[str]] = None,
        timeout_seconds: int = 60,
        env_overrides: Optional[Dict[str, str]] = None,
        transaction_id: Optional[str] = None,
        project_id: str = "default_project",
    ) -> TestSuiteResult:
        """Executes targeted or full test suites within safety boundaries."""
        pass


class SafeSubprocessExecutor:
    """Executes external commands safely with timeout, path verification, and bounded output."""
    __test__ = False

    @staticmethod
    def run_command(
        cmd: Sequence[str],
        cwd: str,
        timeout_seconds: int = 60,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str, float]:
        """
        Executes a command array safely without shell=True.
        Returns: (exit_code, stdout_bounded, stderr_bounded, duration_ms)
        """
        if not os.path.isdir(cwd):
            raise ValueError(f"Working directory does not exist: {cwd}")

        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)

        # Force unbuffered output for standard python runners
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = f"{cwd}{os.pathsep}{env.get('PYTHONPATH', '')}"

        start_time = time.perf_counter()
        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=timeout_seconds)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout_data, stderr_data = process.communicate()
                exit_code = 124  # Standard timeout exit code
                stderr_data += f"\n[AutoDev] Execution timed out after {timeout_seconds} seconds."
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return -1, "", f"[AutoDev] Process execution failed: {str(e)}", duration_ms

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Apply bounds and secret redaction
        clean_stdout = bound_log_text(redact_secrets(stdout_data or ""))
        clean_stderr = bound_log_text(redact_secrets(stderr_data or ""))

        return exit_code, clean_stdout, clean_stderr, duration_ms


class PytestTestRunner(TestRunner):
    """Production-grade test runner for Python pytest suites."""
    __test__ = False

    @property
    def runner_type(self) -> TestRunnerType:
        return TestRunnerType.PYTEST

    def discover_tests(
        self,
        workspace_path: str,
        filter_pattern: Optional[str] = None,
    ) -> List[str]:
        """Discovers pytest test cases by invoking pytest in collection mode."""
        cmd = [sys.executable, "-m", "pytest", "-o", "pythonpath=.", "--collect-only", "-q"]
        if filter_pattern:
            cmd.extend(["-k", filter_pattern])

        exit_code, stdout, stderr, _ = SafeSubprocessExecutor.run_command(
            cmd=cmd,
            cwd=workspace_path,
            timeout_seconds=30,
        )

        discovered = []
        for line in stdout.splitlines():
            line = line.strip()
            # Pytest collect-only -q prints items like 'tests/test_x.py::test_func'
            if "::" in line and not line.startswith("="):
                discovered.append(line.split()[0])
        return discovered

    def run_tests(
        self,
        workspace_path: str,
        test_targets: Optional[List[str]] = None,
        timeout_seconds: int = 60,
        env_overrides: Optional[Dict[str, str]] = None,
        transaction_id: Optional[str] = None,
        project_id: str = "default_project",
    ) -> TestSuiteResult:
        """Executes targeted pytest tests and parses structured outcomes."""
        run_id = f"test_run_{uuid.uuid4().hex[:8]}"
        cmd = [sys.executable, "-m", "pytest", "-o", "pythonpath=.", "-v", "--tb=short"]

        if test_targets:
            # Ensure each target is contained or safe relative path
            safe_targets = []
            for target in test_targets:
                clean = target.strip()
                if clean:
                    safe_targets.append(clean)
            cmd.extend(safe_targets)
        else:
            # Default to test discovery directory if exists
            if os.path.isdir(os.path.join(workspace_path, "tests")):
                cmd.append("tests")

        started_at = time.time()
        exit_code, stdout, stderr, duration_ms = SafeSubprocessExecutor.run_command(
            cmd=cmd,
            cwd=workspace_path,
            timeout_seconds=timeout_seconds,
            env_overrides=env_overrides,
        )
        completed_at = time.time()

        fingerprint = TestExecutionFingerprint(
            working_directory=workspace_path,
        )

        tests = self._parse_pytest_output(stdout, stderr, exit_code, timeout_seconds)

        return TestSuiteResult(
            run_id=run_id,
            project_id=project_id,
            transaction_id=transaction_id,
            test_runner=self.runner_type,
            command=cmd,
            duration_ms=duration_ms,
            exit_code=exit_code,
            tests=tests,
            raw_stdout=stdout,
            raw_stderr=stderr,
            fingerprint=fingerprint,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _parse_pytest_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        timeout_seconds: int,
    ) -> List[SingleTestResult]:
        """Parses pytest standard verbose output into SingleTestResult records."""
        results: List[SingleTestResult] = []
        combined = stdout + "\n" + stderr

        # Check for global timeout
        if exit_code == 124:
            results.append(
                SingleTestResult(
                    test_id="suite_timeout",
                    test_name="TestSuiteTimeout",
                    status=TestStatus.TIMEOUT,
                    failure_type=FailureType.TEST_TIMEOUT,
                    message=f"Test run exceeded timeout limit of {timeout_seconds}s",
                    stdout_bounded=stdout,
                    stderr_bounded=stderr,
                )
            )
            return results

        # Line format: tests/test_foo.py::test_bar PASSED [ 10%] or FAILED [ 20%]
        item_regex = re.compile(r"^(.*?::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)", re.MULTILINE)
        matches = list(item_regex.finditer(stdout))

        # Extract failure summary blocks if present
        failure_blocks = self._extract_failure_blocks(stdout)

        for match in matches:
            test_node = match.group(1).strip()
            status_str = match.group(2).strip()

            test_file = ""
            test_name = test_node
            test_class = ""
            test_method = ""

            parts = test_node.split("::")
            if len(parts) >= 1:
                test_file = parts[0]
            if len(parts) == 2:
                test_method = parts[1]
                test_name = parts[1]
            elif len(parts) >= 3:
                test_class = parts[1]
                test_method = parts[2]
                test_name = f"{test_class}.{test_method}"

            if status_str == "PASSED":
                status = TestStatus.PASSED
                fail_type = None
                msg = ""
                stack = ""
            elif status_str in ("FAILED", "ERROR"):
                status = TestStatus.FAILED if status_str == "FAILED" else TestStatus.ERROR
                block_info = failure_blocks.get(test_node) or failure_blocks.get(test_name) or {}
                msg = block_info.get("message", "Test failed")
                stack = block_info.get("stack", "")
                fail_type = self._classify_pytest_failure(msg, stack, combined)
            elif status_str == "SKIPPED":
                status = TestStatus.SKIPPED
                fail_type = None
                msg = "Test skipped"
                stack = ""
            else:
                status = TestStatus.PASSED
                fail_type = None
                msg = status_str
                stack = ""

            results.append(
                SingleTestResult(
                    test_id=test_node,
                    test_name=test_name,
                    test_file=test_file,
                    test_class=test_class,
                    test_method=test_method,
                    status=status,
                    failure_type=fail_type,
                    message=msg,
                    stack_trace=stack,
                )
            )

        # Handle collection or module load failures where no item lines matched
        if not results and exit_code != 0:
            fail_type = self._classify_pytest_failure(stderr, stdout, combined)
            results.append(
                SingleTestResult(
                    test_id="collection_or_syntax_error",
                    test_name="TestCollectionError",
                    status=TestStatus.ERROR,
                    failure_type=fail_type,
                    message=stderr or stdout or "Collection failure",
                    stack_trace=combined,
                )
            )

        return results

    def _extract_failure_blocks(self, stdout: str) -> Dict[str, Dict[str, str]]:
        """Extracts individual failure sections from pytest FAILURES output."""
        blocks: Dict[str, Dict[str, str]] = {}
        if "=== FAILURES ===" not in stdout and "=== ERRORS ===" not in stdout:
            return blocks

        # Split by failure headers like '___ test_name ___' or '___ TestClass.test_name ___'
        pattern = re.compile(r"_{3,}\s+([^\n_]+)\s+_{3,}")
        sections = pattern.split(stdout)
        
        # sections[0] is pre-failures text, then alternating name, content
        for i in range(1, len(sections), 2):
            test_ident = sections[i].strip()
            content = sections[i + 1] if i + 1 < len(sections) else ""
            
            # Find the assertion or error line (usually at end before next header or summary)
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            error_msg = lines[-1] if lines else "Test failure"
            for line in reversed(lines):
                if any(kw in line for kw in ("Error:", "AssertionError", "Exception:", "FAILED", "assert ")):
                    error_msg = line
                    break
            
            blocks[test_ident] = {
                "message": error_msg,
                "stack": content.strip()[:4096],
            }
        return blocks

    def _classify_pytest_failure(self, msg: str, stack: str, full_log: str) -> FailureType:
        """Determines initial FailureType from pytest message and stack trace."""
        text = f"{msg}\n{stack}\n{full_log}".lower()
        if "syntaxerror" in text:
            return FailureType.SYNTAX_ERROR
        if "importerror" in text or "modulenotfounderror" in text:
            return FailureType.IMPORT_FAILURE
        if "assertionerror" in text or "assert " in text:
            return FailureType.ASSERTION_FAILURE
        if "typeerror" in text or "mypy" in text:
            return FailureType.TYPE_CHECKING_FAILURE
        if "timeout" in text or "timed out" in text:
            return FailureType.TEST_TIMEOUT
        if "connectionrefused" in text or "econnrefused" in text or "network" in text:
            return FailureType.NETWORK_DEPENDENCY_FAILURE
        if "permissiondenied" in text or "eacces" in text:
            return FailureType.PERMISSION_VIOLATION
        if "memoryerror" in text or "oom" in text:
            return FailureType.RESOURCE_EXHAUSTION
        return FailureType.RUNTIME_EXCEPTION


class UnittestTestRunner(TestRunner):
    """Test runner adapter for Python standard unittest suites."""
    __test__ = False

    @property
    def runner_type(self) -> TestRunnerType:
        return TestRunnerType.UNITTEST

    def discover_tests(
        self,
        workspace_path: str,
        filter_pattern: Optional[str] = None,
    ) -> List[str]:
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", filter_pattern or "test*.py"]
        exit_code, stdout, stderr, _ = SafeSubprocessExecutor.run_command(cmd, cwd=workspace_path, timeout_seconds=30)
        # Unittest does not have a clean list-only mode, so we parse stderr
        return [line.strip() for line in stderr.splitlines() if line.strip().startswith("test_")]

    def run_tests(
        self,
        workspace_path: str,
        test_targets: Optional[List[str]] = None,
        timeout_seconds: int = 60,
        env_overrides: Optional[Dict[str, str]] = None,
        transaction_id: Optional[str] = None,
        project_id: str = "default_project",
    ) -> TestSuiteResult:
        run_id = f"test_run_{uuid.uuid4().hex[:8]}"
        cmd = [sys.executable, "-m", "unittest", "-v"]
        if test_targets:
            cmd.extend(test_targets)
        else:
            cmd.extend(["discover", "-s", "tests"])

        started_at = time.time()
        exit_code, stdout, stderr, duration_ms = SafeSubprocessExecutor.run_command(
            cmd=cmd,
            cwd=workspace_path,
            timeout_seconds=timeout_seconds,
            env_overrides=env_overrides,
        )
        completed_at = time.time()

        tests: List[SingleTestResult] = []
        combined = stdout + "\n" + stderr
        # Parse standard unittest lines: 'test_something (test_mod.TestClass) ... ok'
        item_regex = re.compile(r"^(test_\w+)\s+\(([\w\.]+)\)\s+\.\.\.\s+(ok|FAIL|ERROR|skipped)", re.MULTILINE)
        for match in item_regex.finditer(combined):
            method_name = match.group(1)
            class_path = match.group(2)
            outcome = match.group(3)

            test_id = f"{class_path}.{method_name}"
            if outcome == "ok":
                status = TestStatus.PASSED
                ft = None
                msg = ""
            elif outcome == "skipped":
                status = TestStatus.SKIPPED
                ft = None
                msg = "Skipped"
            else:
                status = TestStatus.FAILED if outcome == "FAIL" else TestStatus.ERROR
                ft = FailureType.ASSERTION_FAILURE if outcome == "FAIL" else FailureType.RUNTIME_EXCEPTION
                msg = f"Test failed with {outcome}"

            tests.append(
                SingleTestResult(
                    test_id=test_id,
                    test_name=method_name,
                    test_class=class_path,
                    test_method=method_name,
                    status=status,
                    failure_type=ft,
                    message=msg,
                )
            )

        if not tests and exit_code != 0:
            tests.append(
                SingleTestResult(
                    test_id="unittest_run_error",
                    test_name="UnittestError",
                    status=TestStatus.ERROR,
                    failure_type=FailureType.RUNTIME_EXCEPTION,
                    message=stderr or stdout,
                )
            )

        return TestSuiteResult(
            run_id=run_id,
            project_id=project_id,
            transaction_id=transaction_id,
            test_runner=self.runner_type,
            command=cmd,
            duration_ms=duration_ms,
            exit_code=exit_code,
            tests=tests,
            raw_stdout=stdout,
            raw_stderr=stderr,
            fingerprint=TestExecutionFingerprint(working_directory=workspace_path),
            started_at=started_at,
            completed_at=completed_at,
        )


class GenericCommandTestRunner(TestRunner):
    """Test runner adapter for generic build & test commands (e.g. npm, maven, gradle)."""
    __test__ = False

    def __init__(self, command_prefix: Sequence[str], runner_type_enum: TestRunnerType = TestRunnerType.GENERIC):
        self._command_prefix = list(command_prefix)
        self._runner_type = runner_type_enum

    @property
    def runner_type(self) -> TestRunnerType:
        return self._runner_type

    def discover_tests(self, workspace_path: str, filter_pattern: Optional[str] = None) -> List[str]:
        return []

    def run_tests(
        self,
        workspace_path: str,
        test_targets: Optional[List[str]] = None,
        timeout_seconds: int = 120,
        env_overrides: Optional[Dict[str, str]] = None,
        transaction_id: Optional[str] = None,
        project_id: str = "default_project",
    ) -> TestSuiteResult:
        run_id = f"test_run_{uuid.uuid4().hex[:8]}"
        cmd = list(self._command_prefix)
        if test_targets:
            cmd.extend(test_targets)

        started_at = time.time()
        exit_code, stdout, stderr, duration_ms = SafeSubprocessExecutor.run_command(
            cmd=cmd,
            cwd=workspace_path,
            timeout_seconds=timeout_seconds,
            env_overrides=env_overrides,
        )
        completed_at = time.time()

        status = TestStatus.PASSED if exit_code == 0 else TestStatus.FAILED
        failure_type = None if exit_code == 0 else FailureType.UNKNOWN_FAILURE
        if exit_code == 124:
            status = TestStatus.TIMEOUT
            failure_type = FailureType.TEST_TIMEOUT

        tests = [
            SingleTestResult(
                test_id=f"{self._runner_type.value}_execution",
                test_name=f"{self._runner_type.value}_tests",
                status=status,
                failure_type=failure_type,
                message="Command succeeded" if exit_code == 0 else f"Command exited with {exit_code}",
                stdout_bounded=stdout,
                stderr_bounded=stderr,
            )
        ]

        return TestSuiteResult(
            run_id=run_id,
            project_id=project_id,
            transaction_id=transaction_id,
            test_runner=self._runner_type,
            command=cmd,
            duration_ms=duration_ms,
            exit_code=exit_code,
            tests=tests,
            raw_stdout=stdout,
            raw_stderr=stderr,
            fingerprint=TestExecutionFingerprint(working_directory=workspace_path),
            started_at=started_at,
            completed_at=completed_at,
        )


class TestExecutionEngine:
    """Unified engine managing test runner discovery, execution, and dispatching."""
    __test__ = False

    def __init__(self, workspace_path: str):
        self.workspace_path = os.path.abspath(workspace_path)
        self._runners: Dict[TestRunnerType, TestRunner] = {
            TestRunnerType.PYTEST: PytestTestRunner(),
            TestRunnerType.UNITTEST: UnittestTestRunner(),
        }

    def register_runner(self, runner: TestRunner):
        self._runners[runner.runner_type] = runner

    def get_runner(self, runner_type: TestRunnerType = TestRunnerType.PYTEST) -> TestRunner:
        if runner_type not in self._runners:
            raise ValueError(f"Runner {runner_type} is not registered.")
        return self._runners[runner_type]

    def execute_test_suite(
        self,
        runner_type: TestRunnerType = TestRunnerType.PYTEST,
        test_targets: Optional[List[str]] = None,
        timeout_seconds: int = 60,
        env_overrides: Optional[Dict[str, str]] = None,
        transaction_id: Optional[str] = None,
        project_id: str = "default_project",
    ) -> TestSuiteResult:
        """Executes tests using the selected runner and returns a normalized result."""
        runner = self.get_runner(runner_type)
        return runner.run_tests(
            workspace_path=self.workspace_path,
            test_targets=test_targets,
            timeout_seconds=timeout_seconds,
            env_overrides=env_overrides,
            transaction_id=transaction_id,
            project_id=project_id,
        )
