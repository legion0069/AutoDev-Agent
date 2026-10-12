"""
AutoDev Failure Classifier (v2.6)
Evidence-based classifier mapping error output, stack traces, and exit codes
to structured FailureTypes, with environmental distinction and flaky-test detection.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.test_result_models import (
    FailureType,
    SingleTestResult,
    TestStatus,
    TestSuiteResult,
)

logger = logging.getLogger(__name__)


class FailureClassifier:
    """Classifies test failures based on deterministic regex rules and evidence patterns."""

    # Deterministic pattern matchers in priority order
    CLASSIFICATION_RULES = [
        # Syntax & parsing
        (
            FailureType.SYNTAX_ERROR,
            [
                re.compile(r"SyntaxError:\s*.+", re.IGNORECASE),
                re.compile(r"IndentationError:\s*.+", re.IGNORECASE),
                re.compile(r"TabError:\s*.+", re.IGNORECASE),
                re.compile(r"invalid syntax", re.IGNORECASE),
            ],
        ),
        # Import & module resolution
        (
            FailureType.IMPORT_FAILURE,
            [
                re.compile(r"ModuleNotFoundError:\s*No module named ['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE),
                re.compile(r"ImportError:\s*cannot import name ['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE),
                re.compile(r"ImportError:\s*.+", re.IGNORECASE),
                re.compile(r"cannot find module ['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE),
            ],
        ),
        # Compilation & build
        (
            FailureType.COMPILATION_FAILURE,
            [
                re.compile(r"(?:javac|rustc|gcc|g\+\+|clang|tsc)\s*error", re.IGNORECASE),
                re.compile(r"Compilation failed", re.IGNORECASE),
                re.compile(r"Build failed with an exception", re.IGNORECASE),
            ],
        ),
        # Dependency resolution
        (
            FailureType.DEPENDENCY_RESOLUTION_FAILURE,
            [
                re.compile(r"ResolutionImpossible", re.IGNORECASE),
                re.compile(r"Could not find a version that satisfies the requirement", re.IGNORECASE),
                re.compile(r"npm ERR! code ERESOLVE", re.IGNORECASE),
                re.compile(r"DependencyResolutionException", re.IGNORECASE),
            ],
        ),
        # Test discovery
        (
            FailureType.TEST_DISCOVERY_FAILURE,
            [
                re.compile(r"PytestCollectionWarning", re.IGNORECASE),
                re.compile(r"Failed to collect test", re.IGNORECASE),
                re.compile(r"collected 0 items", re.IGNORECASE),
                re.compile(r"no tests were found", re.IGNORECASE),
            ],
        ),
        # Network & external services
        (
            FailureType.NETWORK_DEPENDENCY_FAILURE,
            [
                re.compile(r"ConnectionRefusedError:\s*.+", re.IGNORECASE),
                re.compile(r"ECONNREFUSED", re.IGNORECASE),
                re.compile(r"getaddrinfo failed", re.IGNORECASE),
                re.compile(r"Max retries exceeded with url", re.IGNORECASE),
                re.compile(r"could not connect to server", re.IGNORECASE),
                re.compile(r"socket\.timeout", re.IGNORECASE),
                re.compile(r"NewConnectionError", re.IGNORECASE),
            ],
        ),
        # Environment & configuration
        (
            FailureType.ENVIRONMENT_FAILURE,
            [
                re.compile(r"KeyError:\s*['\"](?:DATABASE_URL|REDIS_URL|API_KEY|ENV|PORT)['\"]", re.IGNORECASE),
                re.compile(r"EnvironmentError:\s*.+", re.IGNORECASE),
                re.compile(r"Missing required environment variable", re.IGNORECASE),
            ],
        ),
        # Resource exhaustion
        (
            FailureType.RESOURCE_EXHAUSTION,
            [
                re.compile(r"MemoryError", re.IGNORECASE),
                re.compile(r"OutOfMemoryError", re.IGNORECASE),
                re.compile(r"No space left on device", re.IGNORECASE),
                re.compile(r"ResourceExhausted", re.IGNORECASE),
            ],
        ),
        # Permission violation
        (
            FailureType.PERMISSION_VIOLATION,
            [
                re.compile(r"PermissionError:\s*.+", re.IGNORECASE),
                re.compile(r"EACCES", re.IGNORECASE),
                re.compile(r"AccessDeniedException", re.IGNORECASE),
                re.compile(r"Operation not permitted", re.IGNORECASE),
            ],
        ),
        # Timeout
        (
            FailureType.TEST_TIMEOUT,
            [
                re.compile(r"TimeoutExpired", re.IGNORECASE),
                re.compile(r"timed out after \d+ seconds", re.IGNORECASE),
                re.compile(r"pytest-timeout", re.IGNORECASE),
                re.compile(r"Execution timed out", re.IGNORECASE),
            ],
        ),
        # Type checking
        (
            FailureType.TYPE_CHECKING_FAILURE,
            [
                re.compile(r"TypeError:\s*.+", re.IGNORECASE),
                re.compile(r"Argument \d+ to [^\s]+ has incompatible type", re.IGNORECASE),
                re.compile(r"Incompatible return value type", re.IGNORECASE),
                re.compile(r"mypy error", re.IGNORECASE),
            ],
        ),
        # Assertions
        (
            FailureType.ASSERTION_FAILURE,
            [
                re.compile(r"AssertionError:\s*.+", re.IGNORECASE),
                re.compile(r"assert\s+.+", re.IGNORECASE),
                re.compile(r"Expected\s*:\s*.+\s*Actual\s*:\s*.+", re.IGNORECASE),
                re.compile(r"Expected .+ to equal .+", re.IGNORECASE),
            ],
        ),
        # General runtime exception
        (
            FailureType.RUNTIME_EXCEPTION,
            [
                re.compile(r"\b(?:AttributeError|IndexError|KeyError|ValueError|ZeroDivisionError|UnboundLocalError|NotImplementedError|RuntimeError):\s*.+", re.IGNORECASE),
                re.compile(r"Traceback \(most recent call last\):", re.IGNORECASE),
            ],
        ),
    ]

    @classmethod
    def classify(
        cls,
        message: str,
        stack_trace: str = "",
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
    ) -> Tuple[FailureType, float, str]:
        """
        Classifies failure based on extracted logs and stack trace.
        Returns: (FailureType, confidence_score [0.0 - 1.0], reason_summary)
        """
        if exit_code == 124:
            return FailureType.TEST_TIMEOUT, 1.0, "Process exited with timeout code 124"

        combined = f"{message}\n{stack_trace}\n{stderr}\n{stdout}"

        for ftype, patterns in cls.CLASSIFICATION_RULES:
            for pattern in patterns:
                match = pattern.search(combined)
                if match:
                    evidence = match.group(0).strip()
                    confidence = 0.95 if ftype in (FailureType.SYNTAX_ERROR, FailureType.IMPORT_FAILURE, FailureType.ASSERTION_FAILURE) else 0.85
                    return ftype, confidence, f"Matched pattern '{pattern.pattern}' with evidence: '{evidence}'"

        if exit_code != 0:
            return FailureType.UNKNOWN_FAILURE, 0.40, f"Unrecognized failure output with non-zero exit code {exit_code}"

        return FailureType.UNKNOWN_FAILURE, 0.10, "No failure detected"

    @classmethod
    def is_environmental(cls, failure_type: FailureType) -> bool:
        """Determines if the failure is likely due to external environment rather than code defect."""
        return failure_type in (
            FailureType.NETWORK_DEPENDENCY_FAILURE,
            FailureType.ENVIRONMENT_FAILURE,
            FailureType.RESOURCE_EXHAUSTION,
            FailureType.PERMISSION_VIOLATION,
            FailureType.INFRASTRUCTURE_FAILURE,
        )

    @classmethod
    def classify_test_result(cls, test: SingleTestResult, full_stdout: str = "", full_stderr: str = "") -> SingleTestResult:
        """Enriches a SingleTestResult with deterministic failure classification if not already classified."""
        if test.status in (TestStatus.PASSED, TestStatus.SKIPPED):
            test.failure_type = None
            return test

        ftype, _, _ = cls.classify(
            message=test.message,
            stack_trace=test.stack_trace,
            stdout=full_stdout or test.stdout_bounded,
            stderr=full_stderr or test.stderr_bounded,
        )
        test.failure_type = ftype
        return test


class FlakyTestDetector:
    """Evaluates test stability over bounded retries to identify non-deterministic failures."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max(2, min(max_retries, 5))

    def evaluate_test(
        self,
        runner_fn,  # Callable[[], SingleTestResult or bool]
        test_id: str,
    ) -> Tuple[bool, float, List[TestStatus]]:
        """
        Executes a test repeatedly to check for outcome variations.
        Returns: (is_flaky, pass_rate, list_of_statuses)
        """
        statuses: List[TestStatus] = []
        for _ in range(self.max_retries):
            res = runner_fn()
            if isinstance(res, SingleTestResult):
                statuses.append(res.status)
            elif isinstance(res, bool):
                statuses.append(TestStatus.PASSED if res else TestStatus.FAILED)
            else:
                statuses.append(TestStatus.PASSED if getattr(res, "success", False) else TestStatus.FAILED)

        passed_count = sum(1 for s in statuses if s == TestStatus.PASSED)
        pass_rate = passed_count / len(statuses)
        # Flaky if there is a mix of PASSED and FAILED/ERROR
        has_pass = any(s == TestStatus.PASSED for s in statuses)
        has_fail = any(s in (TestStatus.FAILED, TestStatus.ERROR, TestStatus.TIMEOUT) for s in statuses)
        is_flaky = has_pass and has_fail

        return is_flaky, pass_rate, statuses
