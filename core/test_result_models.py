"""
AutoDev Test Result Models (v2.6)
Structured, normalized representations for test execution results, failures, and execution fingerprints.
"""

from __future__ import annotations

import enum
import hashlib
import os
import platform
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


class TestStatus(str, enum.Enum):
    """Normalized test execution status."""
    __test__ = False
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    ERROR = "error"
    TIMEOUT = "timeout"


class FailureType(str, enum.Enum):
    """Evidence-based failure classification taxonomy."""
    ASSERTION_FAILURE = "assertion_failure"
    COMPILATION_FAILURE = "compilation_failure"
    IMPORT_FAILURE = "import_failure"
    SYNTAX_ERROR = "syntax_error"
    TYPE_CHECKING_FAILURE = "type_checking_failure"
    DEPENDENCY_RESOLUTION_FAILURE = "dependency_resolution_failure"
    TEST_DISCOVERY_FAILURE = "test_discovery_failure"
    TEST_TIMEOUT = "test_timeout"
    RUNTIME_EXCEPTION = "runtime_exception"
    ENVIRONMENT_FAILURE = "environment_failure"
    NETWORK_DEPENDENCY_FAILURE = "network_dependency_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    PERMISSION_VIOLATION = "permission_violation"
    FLAKY_FAILURE = "flaky_failure"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    UNKNOWN_FAILURE = "unknown_failure"


class TestRunnerType(str, enum.Enum):
    """Supported test runner types."""
    __test__ = False
    PYTEST = "pytest"
    UNITTEST = "unittest"
    GENERIC = "generic"
    NPM = "npm"
    MAVEN = "maven"
    GRADLE = "gradle"


# Secret redaction regex patterns
SECRET_PATTERNS = [
    re.compile(r'(?i)(?:api_key|apikey|secret|token|password|passwd|auth|bearer|private_key|privkey)[\s:=]+["\']?([a-zA-Z0-9_\-\.\/+=]{8,})["\']?'),
    re.compile(r'(?i)bearer\s+([a-zA-Z0-9_\-\.]{16,})'),
    re.compile(r'ghp_[a-zA-Z0-9]{36}'),
    re.compile(r'xox[baprs]-[a-zA-Z0-9]{10,48}'),
    re.compile(r'-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH)?\s*PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA|EC|DSA|OPENSSH)?\s*PRIVATE\s+KEY-----'),
]


def redact_secrets(text: str) -> str:
    """Redacts potential secrets, credentials, and tokens from output logs."""
    if not text:
        return ""
    sanitized = text
    for pat in SECRET_PATTERNS:
        def _replace_match(m: re.Match) -> str:
            full = m.group(0)
            if len(m.groups()) >= 1 and m.group(1):
                secret = m.group(1)
                return full.replace(secret, "[REDACTED_SECRET]")
            return "[REDACTED_SECRET]"
        sanitized = pat.sub(_replace_match, sanitized)
    return sanitized


def bound_log_text(text: str, max_bytes: int = 65536) -> str:
    """Truncates log output to a safe memory bound while preserving head and tail."""
    if not text:
        return ""
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    half = max_bytes // 2
    head = text[: half // 2]
    tail = text[- (half // 2):]
    return f"{head}\n\n... [LOG TRUNCATED: {len(text)} characters total] ...\n\n{tail}"


@dataclass
class TestExecutionFingerprint:
    """Environment fingerprint ensuring diagnostic reproducibility."""
    __test__ = False
    os_name: str = field(default_factory=lambda: platform.system())
    os_version: str = field(default_factory=lambda: platform.version())
    os_arch: str = field(default_factory=lambda: platform.machine())
    python_version: str = field(default_factory=lambda: sys.version.split()[0])
    working_directory: str = ""
    source_revision: str = ""
    changed_files: List[str] = field(default_factory=list)
    env_hash: str = ""

    def __post_init__(self):
        if not self.env_hash:
            raw = f"{self.os_name}:{self.python_version}:{self.working_directory}:{sorted(self.changed_files)}"
            self.env_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SingleTestResult:
    """Detailed result for an individual test case."""
    __test__ = False
    test_id: str
    test_name: str
    test_file: str = ""
    test_class: str = ""
    test_method: str = ""
    status: TestStatus = TestStatus.PASSED
    failure_type: Optional[FailureType] = None
    message: str = ""
    stack_trace: str = ""
    duration_ms: float = 0.0
    stdout_bounded: str = ""
    stderr_bounded: str = ""
    stdout_reference: Optional[str] = None
    stderr_reference: Optional[str] = None
    attempt_number: int = 1
    flaky: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["failure_type"] = self.failure_type.value if self.failure_type else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SingleTestResult:
        payload = dict(data)
        if isinstance(payload.get("status"), str):
            payload["status"] = TestStatus(payload["status"])
        if payload.get("failure_type") and isinstance(payload["failure_type"], str):
            payload["failure_type"] = FailureType(payload["failure_type"])
        return cls(**payload)


@dataclass
class TestSuiteResult:
    """Aggregated result for a full test suite or targeted test execution run."""
    __test__ = False
    run_id: str
    project_id: str = "default_project"
    transaction_id: Optional[str] = None
    task_id: Optional[str] = None
    test_runner: TestRunnerType = TestRunnerType.PYTEST
    command: List[str] = field(default_factory=list)
    total_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    blocked_count: int = 0
    duration_ms: float = 0.0
    exit_code: int = 0
    success: bool = True
    tests: List[SingleTestResult] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""
    fingerprint: Optional[TestExecutionFingerprint] = None
    started_at: float = field(default_factory=time.time)
    completed_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.tests and self.total_count == 0:
            pass
        elif self.tests:
            self.total_count = len(self.tests)
            self.passed_count = sum(1 for t in self.tests if t.status == TestStatus.PASSED)
            self.failed_count = sum(1 for t in self.tests if t.status in (TestStatus.FAILED, TestStatus.TIMEOUT))
            self.error_count = sum(1 for t in self.tests if t.status == TestStatus.ERROR)
            self.skipped_count = sum(1 for t in self.tests if t.status == TestStatus.SKIPPED)
            self.blocked_count = sum(1 for t in self.tests if t.status == TestStatus.BLOCKED)
            self.success = (self.failed_count == 0 and self.error_count == 0 and self.blocked_count == 0 and self.exit_code == 0)

    @property
    def failing_tests(self) -> List[SingleTestResult]:
        return [t for t in self.tests if t.status in (TestStatus.FAILED, TestStatus.ERROR, TestStatus.TIMEOUT)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "transaction_id": self.transaction_id,
            "task_id": self.task_id,
            "test_runner": self.test_runner.value,
            "command": self.command,
            "total_count": self.total_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "blocked_count": self.blocked_count,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "success": self.success,
            "tests": [t.to_dict() for t in self.tests],
            "raw_stdout": self.raw_stdout,
            "raw_stderr": self.raw_stderr,
            "fingerprint": self.fingerprint.to_dict() if self.fingerprint else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TestSuiteResult:
        payload = dict(data)
        if isinstance(payload.get("test_runner"), str):
            payload["test_runner"] = TestRunnerType(payload["test_runner"])
        if payload.get("tests"):
            payload["tests"] = [SingleTestResult.from_dict(t) for t in payload["tests"]]
        if payload.get("fingerprint"):
            payload["fingerprint"] = TestExecutionFingerprint(**payload["fingerprint"])
        return cls(**payload)
