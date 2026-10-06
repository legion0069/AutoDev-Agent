"""
engineering_decision_engine.py - Autonomous Engineering Decision Engine for AutoDev (Version 1.8)

Enables AutoDev to discover multiple implementation strategies, evaluate technical tradeoffs,
estimate complexity, risk, maintainability, performance, testing effort, and future extensibility,
and deterministically choose the optimal engineering strategy before code generation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("AutoDev.EngineeringDecisionEngine")


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class DecisionOption:
    """
    Represents a concrete implementation strategy / architectural approach for a task.
    """
    id: str
    title: str
    description: str
    advantages: List[str] = field(default_factory=list)
    disadvantages: List[str] = field(default_factory=list)
    estimated_complexity: str = "Medium"  # "Low", "Medium", "High"
    estimated_files: List[str] = field(default_factory=list)
    estimated_risk: str = "Low"  # "Low", "Medium", "High"
    estimated_effort: str = "Medium"  # "Low", "Medium", "High"
    expected_performance: str = "High"
    expected_scalability: str = "High"
    expected_testability: str = "High"
    expected_maintainability: str = "High"
    implementation_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes DecisionOption to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "advantages": list(self.advantages),
            "disadvantages": list(self.disadvantages),
            "estimated_complexity": self.estimated_complexity,
            "estimated_files": list(self.estimated_files),
            "estimated_risk": self.estimated_risk,
            "estimated_effort": self.estimated_effort,
            "expected_performance": self.expected_performance,
            "expected_scalability": self.expected_scalability,
            "expected_testability": self.expected_testability,
            "expected_maintainability": self.expected_maintainability,
            "implementation_steps": list(self.implementation_steps),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DecisionOption:
        """Constructs DecisionOption from a dictionary."""
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            advantages=list(data.get("advantages", [])),
            disadvantages=list(data.get("disadvantages", [])),
            estimated_complexity=str(data.get("estimated_complexity", "Medium")),
            estimated_files=list(data.get("estimated_files", [])),
            estimated_risk=str(data.get("estimated_risk", "Low")),
            estimated_effort=str(data.get("estimated_effort", "Medium")),
            expected_performance=str(data.get("expected_performance", "High")),
            expected_scalability=str(data.get("expected_scalability", "High")),
            expected_testability=str(data.get("expected_testability", "High")),
            expected_maintainability=str(data.get("expected_maintainability", "High")),
            implementation_steps=list(data.get("implementation_steps", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DecisionEvaluation:
    """
    Deterministic quantitative scoring for a DecisionOption across multiple architectural criteria.
    """
    overall_score: float = 0.0
    performance_score: float = 0.0
    maintainability_score: float = 0.0
    complexity_score: float = 0.0  # Lower complexity yields higher score
    risk_score: float = 0.0  # Lower risk yields higher score
    testability_score: float = 0.0
    future_score: float = 0.0  # Future extensibility score
    scalability_score: float = 0.0
    documentation_score: float = 0.0
    weighted_score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes DecisionEvaluation to a dictionary."""
        return {
            "overall_score": round(self.overall_score, 2),
            "performance_score": round(self.performance_score, 2),
            "maintainability_score": round(self.maintainability_score, 2),
            "complexity_score": round(self.complexity_score, 2),
            "risk_score": round(self.risk_score, 2),
            "testability_score": round(self.testability_score, 2),
            "future_score": round(self.future_score, 2),
            "scalability_score": round(self.scalability_score, 2),
            "documentation_score": round(self.documentation_score, 2),
            "weighted_score": round(self.weighted_score, 2),
            "score_breakdown": {k: round(v, 2) for k, v in self.score_breakdown.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DecisionEvaluation:
        """Constructs DecisionEvaluation from a dictionary."""
        return cls(
            overall_score=float(data.get("overall_score", 0.0)),
            performance_score=float(data.get("performance_score", 0.0)),
            maintainability_score=float(data.get("maintainability_score", 0.0)),
            complexity_score=float(data.get("complexity_score", 0.0)),
            risk_score=float(data.get("risk_score", 0.0)),
            testability_score=float(data.get("testability_score", 0.0)),
            future_score=float(data.get("future_score", 0.0)),
            scalability_score=float(data.get("scalability_score", 0.0)),
            documentation_score=float(data.get("documentation_score", 0.0)),
            weighted_score=float(data.get("weighted_score", 0.0)),
            score_breakdown=dict(data.get("score_breakdown", {})),
        )


@dataclass
class EngineeringDecision:
    """
    The selected architectural strategy, alternative choices, rationale, tradeoffs, and confidence.
    """
    selected_option: DecisionOption
    alternative_options: List[DecisionOption] = field(default_factory=list)
    reasoning: str = ""
    tradeoffs: List[str] = field(default_factory=list)
    confidence: float = 0.90
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    task_id: str = ""
    task_title: str = ""
    evaluation: Optional[DecisionEvaluation] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes EngineeringDecision to a dictionary."""
        return {
            "selected_option": self.selected_option.to_dict(),
            "alternative_options": [opt.to_dict() for opt in self.alternative_options],
            "reasoning": self.reasoning,
            "tradeoffs": list(self.tradeoffs),
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "task_title": self.task_title,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EngineeringDecision:
        """Constructs EngineeringDecision from a dictionary."""
        sel = DecisionOption.from_dict(data.get("selected_option", {}))
        alts = [DecisionOption.from_dict(o) for o in data.get("alternative_options", [])]
        eval_obj = DecisionEvaluation.from_dict(data["evaluation"]) if data.get("evaluation") else None
        return cls(
            selected_option=sel,
            alternative_options=alts,
            reasoning=str(data.get("reasoning", "")),
            tradeoffs=list(data.get("tradeoffs", [])),
            confidence=float(data.get("confidence", 0.90)),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            task_id=str(data.get("task_id", "")),
            task_title=str(data.get("task_title", "")),
            evaluation=eval_obj,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DecisionReport:
    """
    Comprehensive Decision Report synthesizing candidate options, evaluations, chosen strategy,
    summary, and execution telemetry.
    """
    task: Dict[str, Any]
    options: List[DecisionOption]
    selected_option: DecisionOption
    evaluation: Dict[str, DecisionEvaluation]  # Option ID -> DecisionEvaluation
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes DecisionReport to a dictionary."""
        return {
            "task": dict(self.task),
            "options": [opt.to_dict() for opt in self.options],
            "selected_option": self.selected_option.to_dict(),
            "evaluation": {k: v.to_dict() for k, v in self.evaluation.items()},
            "summary": self.summary,
            "timestamp": self.timestamp,
            "telemetry": dict(self.telemetry),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DecisionReport:
        """Constructs DecisionReport from a dictionary."""
        opts = [DecisionOption.from_dict(o) for o in data.get("options", [])]
        sel = DecisionOption.from_dict(data.get("selected_option", {}))
        evals = {k: DecisionEvaluation.from_dict(v) for k, v in data.get("evaluation", {}).items()}
        return cls(
            task=dict(data.get("task", {})),
            options=opts,
            selected_option=sel,
            evaluation=evals,
            summary=str(data.get("summary", "")),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            telemetry=dict(data.get("telemetry", {})),
        )

    def to_markdown(self) -> str:
        """Renders DecisionReport as clean GitHub-flavored Markdown."""
        lines = [
            f"# Engineering Decision Report: {self.selected_option.title}",
            "",
            f"> **Task**: `{self.task.get('id', 'N/A')}` — {self.task.get('title', 'Untitled')}",
            f"> **Selected Option ID**: `{self.selected_option.id}` | **Confidence**: {self.telemetry.get('confidence', 0.90):.2f}",
            "",
            "## Summary",
            self.summary,
            "",
            "## Evaluated Strategies",
            "",
            "| Option ID | Strategy Title | Complexity | Risk | Score | Selected |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for opt in self.options:
            ev = self.evaluation.get(opt.id)
            score_str = f"{ev.weighted_score:.1f}" if ev else "N/A"
            is_sel = "✅ **YES**" if opt.id == self.selected_option.id else "No"
            lines.append(f"| `{opt.id}` | {opt.title} | {opt.estimated_complexity} | {opt.estimated_risk} | {score_str} | {is_sel} |")

        lines.append("")
        lines.append("## Chosen Strategy Implementation Steps")
        for idx, step in enumerate(self.selected_option.implementation_steps, 1):
            lines.append(f"{idx}. {step}")

        return "\n".join(lines)


# =============================================================================
# ENGINEERING DECISION ENGINE
# =============================================================================

class EngineeringDecisionEngine:
    """
    Autonomous Engineering Decision Engine for AutoDev.
    Discovers multiple implementation strategies, evaluates them across 8 deterministic
    architectural dimensions using weighted scoring, resolves ties, persists decision history,
    and integrates with MemoryManager, PromptBuilder, and Orchestrator.
    """

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "maintainability": 0.20,  # 20%
        "risk": 0.20,             # 20%
        "performance": 0.15,      # 15%
        "complexity": 0.15,       # 15%
        "testability": 0.10,      # 10%
        "scalability": 0.10,      # 10%
        "future": 0.10,           # 10%
    }

    DEFAULT_HISTORY_PATH = Path("memory/decision_history.json")

    def __init__(
        self,
        memory_manager: Optional[Any] = None,
        history_path: Optional[Union[str, Path]] = None,
        weights: Optional[Dict[str, float]] = None,
        auto_create_history: bool = True,
    ) -> None:
        """
        Initializes EngineeringDecisionEngine with configurable weights and persistence.
        """
        self.memory_manager = memory_manager
        self.history_path = Path(history_path).resolve() if history_path else self.DEFAULT_HISTORY_PATH.resolve()
        self.weights = self._normalize_weights(weights if weights is not None else self.DEFAULT_WEIGHTS)
        self.auto_create_history = auto_create_history
        self._decision_history: List[DecisionReport] = []
        self._telemetry: Dict[str, Any] = {
            "number_of_decisions": 0,
            "number_of_options": 0,
            "evaluation_time": 0.0,
            "evaluation_time_ms": 0.0,
            "selected_score": 0.0,
            "confidence": 0.0,
            "decision_history": [],
        }
        self._load_history_on_init()

    # -------------------------------------------------------------------------
    # Weight Management & Normalization
    # -------------------------------------------------------------------------

    def _normalize_weights(self, raw_weights: Dict[str, float]) -> Dict[str, float]:
        """Normalizes weights so their sum equals 1.0, ensuring non-negative values."""
        if not raw_weights:
            return dict(self.DEFAULT_WEIGHTS)

        sanitized: Dict[str, float] = {}
        for k, v in raw_weights.items():
            key = k.lower().strip()
            val = float(v)
            if val < 0.0:
                logger.warning("Negative weight for '%s' (%f). Clamping to 0.0.", k, val)
                val = 0.0
            sanitized[key] = val

        total = sum(sanitized.values())
        if total <= 0.0:
            logger.warning("Total weight sum is 0. Resetting to default weights.")
            return dict(self.DEFAULT_WEIGHTS)

        return {k: round(v / total, 4) for k, v in sanitized.items()}

    # -------------------------------------------------------------------------
    # Strategy Generation API
    # -------------------------------------------------------------------------

    def generate_options(
        self,
        task: Any,
        impact_report: Optional[Any] = None,
        code_context: Optional[Any] = None,
        symbol_graph: Optional[Any] = None,
        repository_overview: Optional[Any] = None,
        architecture_decisions: Optional[List[Any]] = None,
        refactoring_report: Optional[Any] = None,
    ) -> List[DecisionOption]:
        """
        Generates at least THREE distinct, concrete implementation strategies tailored to the given task.
        """
        task_id = str(getattr(task, "id", "") if hasattr(task, "id") else (task.get("id", "TASK-01") if isinstance(task, dict) else "TASK-01"))
        task_title = str(getattr(task, "title", "") if hasattr(task, "title") else (task.get("title", str(task)) if isinstance(task, dict) else str(task)))
        task_desc = str(getattr(task, "description", "") if hasattr(task, "description") else (task.get("description", "") if isinstance(task, dict) else ""))
        est_files = list(getattr(task, "estimated_files", []) if hasattr(task, "estimated_files") else (task.get("estimated_files", []) if isinstance(task, dict) else []))
        text_corpus = f"{task_title} {task_desc} {' '.join(est_files)}".lower()

        # Check if technical debt indicates Refactor First
        if refactoring_report and getattr(refactoring_report, "should_refactor_first", False):
            return self._generate_refactor_first_options(task_id, task_title, est_files, refactoring_report)

        # Tokenize corpus for exact keyword matching
        words = set(re.findall(r"\b\w+\b", text_corpus))

        # Determine Task Domain
        if words & {"auth", "jwt", "login", "oauth", "password", "session_auth", "authentication", "authorization", "rbac"}:
            return self._generate_auth_options(task_id, task_title, est_files)
        elif words & {"database", "sql", "sqlite", "postgres", "repository", "orm", "table", "tables", "persistence", "db"}:
            return self._generate_database_options(task_id, task_title, est_files)
        elif words & {"cache", "caching", "redis", "lru", "memoize", "ttl", "memcached"}:
            return self._generate_caching_options(task_id, task_title, est_files)
        elif words & {"log", "logger", "logging", "telemetry", "tracing", "metric", "metrics", "observability"}:
            return self._generate_logging_options(task_id, task_title, est_files)
        elif words & {"api", "endpoint", "endpoints", "rest", "restful", "router", "routes", "controller", "fastapi", "flask", "rpc", "graphql"}:
            return self._generate_api_options(task_id, task_title, est_files)
        elif words & {"refactor", "refactoring", "migrate", "migration", "cleanup", "reorganize", "decouple", "strangler"}:
            return self._generate_refactoring_options(task_id, task_title, est_files)
        elif words & {"test", "tests", "testing", "pytest", "fixture", "fixtures", "mock", "mocks", "coverage", "fuzz"}:
            return self._generate_testing_options(task_id, task_title, est_files)
        else:
            return self._generate_general_options(task_id, task_title, est_files)

    def _generate_refactor_first_options(
        self,
        task_id: str,
        title: str,
        est_files: List[str],
        refactoring_report: Any,
    ) -> List[DecisionOption]:
        files = est_files or ["src/core.py"]
        top_cand = getattr(refactoring_report, "candidates", [None])[0] if getattr(refactoring_report, "candidates", None) else None
        cand_title = getattr(top_cand, "title", "Critical Technical Debt") if top_cand else "Technical Debt Remediation"

        return [
            DecisionOption(
                id="OPT-1",
                title=f"Refactor First: Remediate {cand_title} then Implement Feature",
                description="Preemptively refactor detected technical debt, eliminate circular dependencies/high complexity, and implement the new feature on clean modular abstractions.",
                advantages=[
                    "Eliminates technical debt before adding new functionality.",
                    "Significantly lowers future maintenance cost and reduces defect probability.",
                    "Guarantees adherence to clean architectural boundaries.",
                ],
                disadvantages=[
                    "Requires upfront refactoring effort before feature delivery.",
                ],
                estimated_complexity="Low",
                estimated_files=files + (list(getattr(top_cand, "affected_files", [])) if top_cand else []),
                estimated_risk="Low",
                estimated_effort="Medium",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Execute safe refactoring actions to decompose god objects and decouple circular dependencies.",
                    "Run regression test suite to verify existing functionality remains green.",
                    "Implement the requested feature cleanly on the refactored abstractions.",
                    "Add comprehensive unit and integration tests for the new capability.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Implement Feature with Adapter / Layer Isolation (Defer Technical Debt)",
                description="Implement the requested feature behind an isolated Adapter or Facade, insulating new code while deferring legacy refactoring.",
                advantages=[
                    "Faster immediate feature completion without touching legacy modules.",
                    "Isolates new feature logic from existing technical debt.",
                ],
                disadvantages=[
                    "Leaves underlying technical debt unaddressed, accumulating maintenance overhead.",
                    "Introduces intermediate adapter boilerplate.",
                ],
                estimated_complexity="Medium",
                estimated_files=files + ["core/adapter.py"],
                estimated_risk="Medium",
                estimated_effort="Low",
                expected_performance="Medium",
                expected_scalability="Medium",
                expected_testability="Medium",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Define Adapter / Facade interface decoupling the new feature from debt-laden modules.",
                    "Implement the new feature against the clean adapter contract.",
                    "Write tests mocking the legacy integration boundary.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="Surgical In-Place Patch with Regression Guard Tests",
                description="Directly patch the existing codebase with minimal changes, relying heavily on extensive test fixtures to prevent regressions.",
                advantages=[
                    "Minimal lines of code changed and fastest initial turnaround.",
                ],
                disadvantages=[
                    "Increases cyclomatic complexity and worsens existing technical debt.",
                    "Higher risk of subtle regressions in legacy flows.",
                ],
                estimated_complexity="High",
                estimated_files=files,
                estimated_risk="High",
                estimated_effort="Low",
                expected_performance="Low",
                expected_scalability="Low",
                expected_testability="Low",
                expected_maintainability="Low",
                implementation_steps=[
                    "Implement the feature directly within existing complex routines.",
                    "Add regression tests covering edge cases around the modified lines.",
                ],
            ),
        ]

    def _generate_auth_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["core/auth.py", "core/security.py", "tests/test_auth.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="Stateless JWT Token Authentication with HMAC-SHA256",
                description="Issue signed JSON Web Tokens containing user claims. Verification is stateless and validated locally via cryptographic secret.",
                advantages=[
                    "Zero database lookups needed per request for token verification.",
                    "Horizontally scalable across multiple stateless worker processes.",
                    "Compact payload structure suitable for Authorization headers.",
                ],
                disadvantages=[
                    "Token revocation requires token blocklist or short TTL with refresh tokens.",
                    "Payload cannot be shrunk below base claims header size.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Implement TokenManager with encode/decode methods using HMAC-SHA256.",
                    "Create authentication middleware/dependency to extract and validate Bearer tokens.",
                    "Add token expiration handling and signature mismatch exception propagation.",
                    "Write unit tests verifying valid token decoding, expiration rejection, and tampered token detection.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Stateful Server-Side Session Authentication with In-Memory / Redis Store",
                description="Store active session identifiers in a server-side storage layer and associate them with client-side secure cookies.",
                advantages=[
                    "Instant session invalidation and global user logout capability.",
                    "Client receives an opaque session identifier, avoiding sensitive token decoding client-side.",
                    "Fine-grained session telemetry and active connection tracking.",
                ],
                disadvantages=[
                    "Requires central session storage lookup for every authenticated request.",
                    "Additional infrastructure complexity if Redis or distributed store is required.",
                ],
                estimated_complexity="Medium",
                estimated_files=files + ["core/session_store.py"],
                estimated_risk="Medium",
                estimated_effort="Medium",
                expected_performance="Medium",
                expected_scalability="Medium",
                expected_testability="High",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Implement SessionStore interface with in-memory fallback and TTL cleanup.",
                    "Create session cookie generation and verification handlers.",
                    "Add session invalidation and cleanup cron tasks.",
                    "Write tests validating session persistence, expiration, and multi-session isolation.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="OAuth2 / OIDC Delegated Identity Provider Architecture",
                description="Delegate identity management and token issuance to external OAuth2 / OIDC providers using authorization code flow.",
                advantages=[
                    "Eliminates local password storage, hashing, and credential security liability.",
                    "Standardized protocol compatible with enterprise SSO and third-party login.",
                ],
                disadvantages=[
                    "External network dependency on identity provider availability.",
                    "Higher setup complexity and local offline testing friction.",
                ],
                estimated_complexity="High",
                estimated_files=files + ["core/oauth_client.py"],
                estimated_risk="Medium",
                estimated_effort="High",
                expected_performance="Medium",
                expected_scalability="High",
                expected_testability="Medium",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Create OAuth2Client abstraction managing authorization URLs and token exchanges.",
                    "Implement JWKS public key retrieval and validation caching.",
                    "Add user profile mapping and fallback local account linking.",
                    "Write mock-based integration tests simulating authorization code exchange.",
                ],
            ),
        ]

    def _generate_database_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["core/database.py", "repositories/base.py", "tests/test_database.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="Repository Pattern with Abstract Interface & SQLite Connection Pooling",
                description="Encapsulate all database access and queries behind abstract repository interfaces, isolating business logic from SQL specifics.",
                advantages=[
                    "Strict separation of concerns; zero SQL queries leaked into business services.",
                    "Extremely easy to mock in unit tests via interface substitution.",
                    "Complies with AutoDev Architecture Decision Records (ADR-DATABASE).",
                ],
                disadvantages=[
                    "Requires creating repository interfaces and concrete implementations.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Define AbstractRepository base class with generic CRUD methods.",
                    "Implement SQLiteRepository with parameterized queries and transaction context manager.",
                    "Add thread-safe connection pooling and automatic schema migration check.",
                    "Write unit tests verifying CRUD operations, rollback on error, and mock repository behavior.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Active Record Pattern with Direct SQL Execution",
                description="Bind data models directly to database tables, allowing model instances to execute SQL persistence methods.",
                advantages=[
                    "Fast initial prototyping with minimal architectural boilerplate.",
                    "Intuitive model-level save() and delete() operations.",
                ],
                disadvantages=[
                    "Tightly couples domain models to database schema and SQL queries.",
                    "Violates separation of concerns and ADR repository constraints.",
                ],
                estimated_complexity="Medium",
                estimated_files=files,
                estimated_risk="High",
                estimated_effort="Low",
                expected_performance="Medium",
                expected_scalability="Medium",
                expected_testability="Medium",
                expected_maintainability="Low",
                implementation_steps=[
                    "Implement Model base class with direct execute methods.",
                    "Bind CRUD actions to model instance attributes.",
                    "Add database connection references to model classes.",
                    "Write tests for model persistence.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="In-Memory Key-Value Store with Write-Ahead Log (WAL) & JSON Persistence",
                description="Maintain an optimized in-memory dictionary index with append-only WAL and periodic atomic JSON snapshots.",
                advantages=[
                    "Zero external database dependency; pure Python execution.",
                    "Sub-millisecond read/write operations.",
                    "Deterministic atomic file snapshots prevent data corruption.",
                ],
                disadvantages=[
                    "Entire dataset must fit in memory.",
                    "Complex relational joins must be executed in application code.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="Medium",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Implement InMemoryStore with dictionary indexing and RLock protection.",
                    "Add append-only WAL transaction logger.",
                    "Implement atomic snapshot writing with tempfile swapping.",
                    "Write tests verifying concurrency safety and recovery from WAL.",
                ],
            ),
        ]

    def _generate_api_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["api/routes.py", "api/schemas.py", "tests/test_api.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="RESTful Controller Architecture with Schema Validation & Dependency Injection",
                description="Standard RESTful endpoints with explicit request/response schemas, structured HTTP status codes, and injected services.",
                advantages=[
                    "Industry-standard REST conventions, self-documenting schemas, and clean error codes.",
                    "Loose coupling between HTTP routing layer and business services.",
                    "Effortless automated OpenAPI / Swagger documentation generation.",
                ],
                disadvantages=[
                    "Multiple roundtrips needed if client requires nested relational resources.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Define request and response validation models using dataclasses/Pydantic.",
                    "Implement route handlers that delegate execution to injected service instances.",
                    "Add structured error handling middleware mapping exceptions to standard JSON error responses.",
                    "Write integration tests using TestClient covering happy paths, input validation, and 4xx/5xx responses.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Command-Query Responsibility Segregation (CQRS) & Mediator Pattern",
                description="Decouple API actions into distinct Command (mutation) and Query (read) handlers routed through a central mediator bus.",
                advantages=[
                    "High modularity with independent optimization for read and write pipelines.",
                    "Extensible pipeline behaviors (e.g. logging, validation, metrics) added via mediator decorators.",
                ],
                disadvantages=[
                    "Higher conceptual boilerplate and class count for simple CRUD tasks.",
                ],
                estimated_complexity="Medium",
                estimated_files=files + ["core/mediator.py", "commands/", "queries/"],
                estimated_risk="Low",
                estimated_effort="Medium",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Implement Mediator dispatcher with command/query registration.",
                    "Define Command and Query payload dataclasses.",
                    "Implement dedicated single-responsibility Handlers.",
                    "Write unit tests for individual handlers and mediator routing.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="Asynchronous RPC & Event-Driven Message Dispatcher",
                description="Expose JSON-RPC or event pub-sub endpoints allowing bidirectional communication and asynchronous task dispatch.",
                advantages=[
                    "Real-time bidirectional updates and asynchronous event streaming.",
                    "Flexible procedure invocation without strict REST resource hierarchy.",
                ],
                disadvantages=[
                    "Steeper learning curve for API consumers; less intuitive caching.",
                    "Requires stateful connection management.",
                ],
                estimated_complexity="High",
                estimated_files=files + ["core/rpc_dispatcher.py"],
                estimated_risk="Medium",
                estimated_effort="High",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="Medium",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Implement JSON-RPC 2.0 protocol parser and method registry.",
                    "Create async event loop worker and channel dispatcher.",
                    "Add connection lifecycle management and error code envelope.",
                    "Write asynchronous test suite for concurrent procedure calls.",
                ],
            ),
        ]

    def _generate_caching_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["core/cache.py", "tests/test_cache.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="Thread-Safe In-Memory LRU Cache with TTL Eviction & Decorator API",
                description="Local in-process LRU cache with time-to-live expiration, maximum entry limits, and decorator support.",
                advantages=[
                    "Zero external infrastructure dependencies; microsecond access latency.",
                    "Simple `@cached(ttl=300)` decorator interface for service methods.",
                    "Thread-safe execution with reader-writer locks.",
                ],
                disadvantages=[
                    "Cache state is isolated per process and reset on application restart.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="Medium",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Implement LRUCache with OrderedDict and TTL timestamp tracking.",
                    "Add thread-safe locking and automatic eviction of expired entries.",
                    "Create parameterized method decorator with deterministic cache key hashing.",
                    "Write tests validating TTL expiration, capacity eviction, and concurrent access.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Distributed Redis Cache Layer with Cache-Aside Pattern",
                description="Shared Redis caching layer using cache-aside pattern with serialized JSON/msgpack payloads.",
                advantages=[
                    "Shared cache consistency across multiple distributed application nodes.",
                    "Persists across process restarts; supports rich data structures.",
                ],
                disadvantages=[
                    "Requires running Redis instance; network latency overhead per cache query.",
                ],
                estimated_complexity="Medium",
                estimated_files=files + ["core/redis_client.py"],
                estimated_risk="Medium",
                estimated_effort="Medium",
                expected_performance="Medium",
                expected_scalability="High",
                expected_testability="Medium",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Create Redis client wrapper with connection pooling and retry logic.",
                    "Implement cache-aside read and write-through invalidation methods.",
                    "Add fallback to direct computation if Redis is unreachable.",
                    "Write tests with mock Redis client verifying fallback resilience.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="Two-Tier Hybrid Cache (L1 In-Memory + L2 Distributed Store)",
                description="Hierarchical cache checking ultra-fast local memory first (L1), falling back to distributed cache (L2).",
                advantages=[
                    "Combines sub-millisecond local speed with distributed cluster-wide consistency.",
                    "Shields distributed cache and database from thundering herd problems.",
                ],
                disadvantages=[
                    "High complexity to maintain cache invalidation synchronization between L1 and L2.",
                ],
                estimated_complexity="High",
                estimated_files=files + ["core/hybrid_cache.py"],
                estimated_risk="High",
                estimated_effort="High",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="Medium",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Implement two-tier CacheManager coordinating L1 and L2 stores.",
                    "Add pub-sub invalidation message listener for cross-process sync.",
                    "Add cache metrics telemetry (L1 hit rate, L2 hit rate, miss rate).",
                    "Write multi-node simulated test suite verifying cache coherence.",
                ],
            ),
        ]

    def _generate_refactoring_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["core/refactor.py", "tests/test_refactor.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="Incremental Adapter & Facade Pattern Refactoring",
                description="Wrap legacy components behind clean abstract interfaces and facades, migrating calls incrementally without breaking existing consumers.",
                advantages=[
                    "Zero downtime and continuous backward compatibility.",
                    "Allows incremental step-by-step verification through the existing test suite.",
                    "Low risk of regression.",
                ],
                disadvantages=[
                    "Requires maintaining adapter bridge until legacy callers are fully deprecated.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Define new clean interface matching future architecture requirements.",
                    "Implement Adapter routing new interface calls to existing implementation.",
                    "Migrate consumers one by one to use the new interface.",
                    "Write unit tests asserting behavior parity between adapter and legacy system.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Strangler Fig Migration with Parallel Run & Telemetry Verification",
                description="Run old and new implementations side-by-side in parallel, comparing outputs and routing traffic gradually.",
                advantages=[
                    "Empirical 100% verification of parity before decommissioning legacy code.",
                    "Immediate rollback capability by switching router flags.",
                ],
                disadvantages=[
                    "Temporary double execution overhead during parallel run phase.",
                ],
                estimated_complexity="Medium",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Medium",
                expected_performance="Medium",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Implement parallel execution harness invoking both implementations.",
                    "Add difference logging and mismatch alerting.",
                    "Introduce feature flag percentage rollout mechanism.",
                    "Write tests validating divergence detection.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="Complete In-Place Rewrite & Direct Cutover",
                description="Completely rewrite module internals and public interfaces in a single pass, replacing all legacy files simultaneously.",
                advantages=[
                    "Removes all legacy technical debt instantly with zero leftover adapters.",
                    "Cleanest possible final codebase state.",
                ],
                disadvantages=[
                    "High regression risk; difficult to isolate breaking changes if issues arise.",
                ],
                estimated_complexity="High",
                estimated_files=files,
                estimated_risk="High",
                estimated_effort="High",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="Medium",
                expected_maintainability="High",
                implementation_steps=[
                    "Draft comprehensive test suite capturing all required legacy behaviors.",
                    "Rewrite all target files from scratch using new clean architecture.",
                    "Update all import sites across the repository.",
                    "Run full test suite to catch broken call sites.",
                ],
            ),
        ]

    def _generate_logging_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["core/logger.py", "tests/test_logger.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="Structured JSON Logger with Context Filters & Rotating File Handlers",
                description="Standardized JSON logging format with contextual metadata (timestamp, correlation_id, module, log_level) and rotating disk handlers.",
                advantages=[
                    "Machine-readable structured output ideal for log aggregators (ELK, Datadog).",
                    "Prevents disk exhaustion via automatic size-based log rotation.",
                    "Zero external dependencies using standard library logging.",
                ],
                disadvantages=[
                    "Slightly less human-readable in raw console output without formatter.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Implement JSONLogFormatter outputting ISO timestamps and structured JSON strings.",
                    "Configure RotatingFileHandler with 10MB limit and 5 backup files.",
                    "Add ContextFilter injecting correlation_id and execution context.",
                    "Write tests verifying JSON format, rotation trigger, and context propagation.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Standard Python Logging with Colored Console Output",
                description="Lightweight formatted console and stream logging with colored level badges and standard format strings.",
                advantages=[
                    "Highly readable developer console output during local development.",
                    "Minimal setup overhead.",
                ],
                disadvantages=[
                    "Unstructured text makes automated metric parsing and querying difficult.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="Medium",
                expected_testability="High",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Configure logging.basicConfig with standard formatters and color codes.",
                    "Export helper `setup_logger` utility function.",
                    "Write tests for log message output.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="OpenTelemetry Distributed Tracing & Metric Telemetry Exporter",
                description="Comprehensive observability framework capturing distributed traces, spans, latency histograms, and structured logs.",
                advantages=[
                    "End-to-end distributed trace propagation across microservices.",
                    "Standardized OpenTelemetry metrics and APM integration.",
                ],
                disadvantages=[
                    "Heavy third-party dependencies and performance overhead if over-instrumented.",
                ],
                estimated_complexity="High",
                estimated_files=files + ["core/tracing.py"],
                estimated_risk="Medium",
                estimated_effort="High",
                expected_performance="Medium",
                expected_scalability="High",
                expected_testability="Medium",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Initialize OpenTelemetry TracerProvider and MeterProvider.",
                    "Add span context decorators to core orchestrator functions.",
                    "Configure OTLP trace exporter with batch processor.",
                    "Write tests validating trace context injection and span attributes.",
                ],
            ),
        ]

    def _generate_testing_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["tests/test_suite.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="Isolated Unit & Integration Test Suite with Pytest Fixtures & Mocks",
                description="Comprehensive unit test suite leveraging modular pytest fixtures, isolated temporary directories, and mock substitutions.",
                advantages=[
                    "Fast execution (< 1 second for hundreds of tests).",
                    "Completely isolated and deterministic; no reliance on external services.",
                    "High test coverage with clear failure diagnostics.",
                ],
                disadvantages=[
                    "Requires careful fixture design to avoid code duplication across test files.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Create conftest.py with shared fixtures (temp directories, mock LLM, sample configs).",
                    "Write unit tests covering all nominal and edge-case execution paths.",
                    "Add negative tests asserting expected exceptions and error handling.",
                    "Verify full test suite passes with pytest -v.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Property-Based & Fuzz Testing with Hypothesis Invariant Checks",
                description="Generate thousands of pseudo-random inputs to find edge cases and verify mathematical invariants.",
                advantages=[
                    "Discovers obscure boundary errors and parsing crashes.",
                    "High confidence in algorithmic robustness.",
                ],
                disadvantages=[
                    "Slower test run times; requires understanding property-based assertions.",
                ],
                estimated_complexity="Medium",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Medium",
                expected_performance="Medium",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Define state invariants and domain data strategies using Hypothesis.",
                    "Write property tests validating serialization roundtrips and idempotent operations.",
                    "Add failure case reproduction tests.",
                    "Run test suite verifying invariant adherence.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="End-to-End Subprocess / System Integration Testing",
                description="Execute the complete CLI and orchestrator workflows in isolated subprocesses verifying end-to-end user journeys.",
                advantages=[
                    "Tests exact production runtime behavior including argument parsing and file I/O.",
                ],
                disadvantages=[
                    "Significantly slower execution speed; higher susceptibility to flakiness.",
                ],
                estimated_complexity="Medium",
                estimated_files=files,
                estimated_risk="Medium",
                estimated_effort="Medium",
                expected_performance="Low",
                expected_scalability="Medium",
                expected_testability="Medium",
                expected_maintainability="Medium",
                implementation_steps=[
                    "Create subprocess invocation test harness.",
                    "Simulate full user interaction workflows.",
                    "Assert on exit codes and stdout/stderr output.",
                    "Run test suite verifying end-to-end success.",
                ],
            ),
        ]

    def _generate_general_options(self, task_id: str, title: str, est_files: List[str]) -> List[DecisionOption]:
        files = est_files or ["core/component.py", "tests/test_component.py"]
        return [
            DecisionOption(
                id="OPT-1",
                title="Modular Class Architecture with Dependency Injection & Interface Segregation",
                description="Design the component as a cohesive, single-responsibility class with constructor-injected dependencies and explicit typed interfaces.",
                advantages=[
                    "Follows SOLID principles and AutoDev architectural guidelines.",
                    "Easily testable via mock dependency injection.",
                    "High maintainability and clear separation of concerns.",
                ],
                disadvantages=[
                    "Requires minor boilerplate for interface declarations.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Declare abstract base interface / Protocol specifying public methods.",
                    "Implement primary class accepting dependencies in __init__.",
                    "Add comprehensive docstrings and explicit type hints.",
                    "Write complete unit test suite validating all methods.",
                ],
            ),
            DecisionOption(
                id="OPT-2",
                title="Lightweight Functional Pipeline with Pure Helper Functions",
                description="Implement behavior as pure, stateless transformation functions composed into a sequential pipeline.",
                advantages=[
                    "Extremely easy to reason about and test with zero state mutations.",
                    "Minimal class boilerplate.",
                ],
                disadvantages=[
                    "Less natural if the subsystem requires long-lived state or lifecycle hooks.",
                ],
                estimated_complexity="Low",
                estimated_files=files,
                estimated_risk="Low",
                estimated_effort="Low",
                expected_performance="High",
                expected_scalability="Medium",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Write pure transformation functions with type annotations.",
                    "Compose functions into a master pipeline runner.",
                    "Write unit tests for individual functions and the pipeline.",
                ],
            ),
            DecisionOption(
                id="OPT-3",
                title="Extensible Plugin / Event-Driven Architecture",
                description="Implement a dynamic registry and event hook system allowing modular plugins to extend functionality at runtime.",
                advantages=[
                    "Maximum future extensibility without modifying existing core code.",
                    "Supports pluggable third-party features.",
                ],
                disadvantages=[
                    "Higher upfront abstraction complexity.",
                ],
                estimated_complexity="Medium",
                estimated_files=files + ["core/plugin_manager.py"],
                estimated_risk="Low",
                estimated_effort="Medium",
                expected_performance="High",
                expected_scalability="High",
                expected_testability="High",
                expected_maintainability="High",
                implementation_steps=[
                    "Define Plugin base class and lifecycle hook specifications.",
                    "Implement PluginRegistry managing registration and hook invocation.",
                    "Add core default plugin implementations.",
                    "Write tests validating plugin registration and execution ordering.",
                ],
            ),
        ]

    # -------------------------------------------------------------------------
    # Evaluation & Scoring API
    # -------------------------------------------------------------------------

    def evaluate_options(
        self,
        options: List[DecisionOption],
        task: Optional[Any] = None,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, DecisionEvaluation]:
        """
        Computes deterministic quantitative scores across 8 architectural dimensions for each option.
        """
        weights = self._normalize_weights(custom_weights) if custom_weights is not None else self.weights
        evaluations: Dict[str, DecisionEvaluation] = {}

        for opt in options:
            eval_obj = self._evaluate_single_option(opt, weights)
            evaluations[opt.id] = eval_obj

        return evaluations

    def _evaluate_single_option(
        self,
        opt: DecisionOption,
        weights: Dict[str, float],
    ) -> DecisionEvaluation:
        """Evaluates a single DecisionOption against architectural scoring criteria."""
        # 1. Complexity Score (Low complexity = High score)
        c_map = {"low": 92.0, "medium": 76.0, "high": 52.0}
        complexity_score = c_map.get(opt.estimated_complexity.lower(), 75.0)

        # 2. Risk Score (Low risk = High score)
        r_map = {"low": 94.0, "medium": 72.0, "high": 45.0}
        risk_score = r_map.get(opt.estimated_risk.lower(), 75.0)

        # 3. Maintainability Score
        m_map = {"high": 92.0, "medium": 74.0, "low": 50.0}
        maintainability_score = m_map.get(opt.expected_maintainability.lower(), 80.0)

        # 4. Performance Score
        p_map = {"high": 95.0, "medium": 75.0, "low": 55.0}
        performance_score = p_map.get(opt.expected_performance.lower(), 80.0)

        # 5. Testability Score
        t_map = {"high": 93.0, "medium": 75.0, "low": 55.0}
        testability_score = t_map.get(opt.expected_testability.lower(), 80.0)

        # 6. Scalability Score
        s_map = {"high": 92.0, "medium": 75.0, "low": 55.0}
        scalability_score = s_map.get(opt.expected_scalability.lower(), 80.0)

        # 7. Future Extensibility Score
        f_map = {"high": 90.0, "medium": 76.0, "low": 54.0}
        future_score = f_map.get(opt.expected_maintainability.lower(), 80.0)
        # Bonus for plugin/modular design in title or advantages
        if "plugin" in opt.title.lower() or "extensible" in opt.title.lower() or "cqrs" in opt.title.lower():
            future_score = min(98.0, future_score + 6.0)

        # 8. Documentation Impact Score
        doc_score = 85.0
        if len(opt.implementation_steps) >= 4:
            doc_score = 92.0

        # Refine scores based on advantage / disadvantage counts
        maintainability_score = min(100.0, max(0.0, maintainability_score + (len(opt.advantages) * 1.5) - (len(opt.disadvantages) * 2.0)))
        risk_score = min(100.0, max(0.0, risk_score - (len(opt.disadvantages) * 2.5)))

        # Compute weighted score
        score_dict = {
            "maintainability": maintainability_score,
            "risk": risk_score,
            "performance": performance_score,
            "complexity": complexity_score,
            "testability": testability_score,
            "scalability": scalability_score,
            "future": future_score,
        }

        weighted_sum = sum(score_dict.get(k, 75.0) * w for k, w in weights.items())
        total_w = sum(weights.values())
        weighted_score = weighted_sum / total_w if total_w > 0 else weighted_sum

        overall_score = sum(score_dict.values()) / len(score_dict)

        return DecisionEvaluation(
            overall_score=round(overall_score, 2),
            performance_score=round(performance_score, 2),
            maintainability_score=round(maintainability_score, 2),
            complexity_score=round(complexity_score, 2),
            risk_score=round(risk_score, 2),
            testability_score=round(testability_score, 2),
            future_score=round(future_score, 2),
            scalability_score=round(scalability_score, 2),
            documentation_score=round(doc_score, 2),
            weighted_score=round(weighted_score, 2),
            score_breakdown={k: round(v, 2) for k, v in score_dict.items()},
        )

    # -------------------------------------------------------------------------
    # Decision Selection & Tie-Breaking API
    # -------------------------------------------------------------------------

    def choose_best_option(
        self,
        options: List[DecisionOption],
        evaluations: Dict[str, DecisionEvaluation],
        task: Optional[Any] = None,
    ) -> EngineeringDecision:
        """
        Selects the highest-scoring DecisionOption using deterministic weighted ranking and tie-breaking:
        1. Higher weighted_score
        2. Lower complexity (higher complexity_score)
        3. Lower risk (higher risk_score)
        4. Higher maintainability (higher maintainability_score)
        5. Deterministic Option ID order
        """
        if not options:
            raise ValueError("Cannot choose best option from an empty options list.")

        # Sorting key for tie-breaking
        def sort_key(opt: DecisionOption) -> Tuple[float, float, float, float, str]:
            ev = evaluations.get(opt.id, DecisionEvaluation())
            return (
                ev.weighted_score,
                ev.complexity_score,
                ev.risk_score,
                ev.maintainability_score,
                # Lexicographical tie break (inverted for max)
                opt.id,
            )

        ranked = sorted(options, key=sort_key, reverse=True)
        selected = ranked[0]
        alternatives = ranked[1:]
        sel_eval = evaluations.get(selected.id, DecisionEvaluation())

        # Confidence calculation based on margin over second place
        margin = 10.0
        if alternatives:
            sec_eval = evaluations.get(alternatives[0].id, DecisionEvaluation())
            margin = sel_eval.weighted_score - sec_eval.weighted_score

        base_confidence = 0.85
        confidence = min(0.98, max(0.70, base_confidence + (margin * 0.015)))

        # Build reasoning explanation
        reasoning = (
            f"Strategy '{selected.title}' selected with overall score {sel_eval.weighted_score:.1f}/100. "
            f"It delivers optimal balance: Low engineering risk ({selected.estimated_risk}), "
            f"manageable complexity ({selected.estimated_complexity}), and high maintainability "
            f"({sel_eval.maintainability_score:.1f}/100) while strictly preserving system invariants."
        )

        tradeoffs: List[str] = []
        if selected.advantages:
            tradeoffs.append(f"Advantages: {'; '.join(selected.advantages[:2])}")
        if selected.disadvantages:
            tradeoffs.append(f"Accepted Tradeoffs: {'; '.join(selected.disadvantages[:2])}")

        task_id = str(getattr(task, "id", "") if hasattr(task, "id") else (task.get("id", "") if isinstance(task, dict) else ""))
        task_title = str(getattr(task, "title", "") if hasattr(task, "title") else (task.get("title", "") if isinstance(task, dict) else ""))

        return EngineeringDecision(
            selected_option=selected,
            alternative_options=alternatives,
            reasoning=reasoning,
            tradeoffs=tradeoffs,
            confidence=round(confidence, 3),
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task_id,
            task_title=task_title,
            evaluation=sel_eval,
        )

    # -------------------------------------------------------------------------
    # End-to-End Decision & Report Generation API
    # -------------------------------------------------------------------------

    def decide(
        self,
        task: Any,
        impact_report: Optional[Any] = None,
        code_context: Optional[Any] = None,
        symbol_graph: Optional[Any] = None,
        repository_overview: Optional[Any] = None,
        architecture_decisions: Optional[List[Any]] = None,
        refactoring_report: Optional[Any] = None,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> DecisionReport:
        """
        Executes end-to-end engineering decision pipeline:
        1. Generates 3+ candidate strategies
        2. Evaluates each candidate deterministically
        3. Chooses best strategy with tie-breaking
        4. Promotes to MemoryManager (if configured)
        5. Persists report to decision history
        6. Returns complete DecisionReport with telemetry.
        """
        start_time = time.perf_counter()

        # 1. Generate options
        options = self.generate_options(
            task=task,
            impact_report=impact_report,
            code_context=code_context,
            symbol_graph=symbol_graph,
            repository_overview=repository_overview,
            architecture_decisions=architecture_decisions,
            refactoring_report=refactoring_report,
        )

        # 2. Evaluate options
        evaluations = self.evaluate_options(options, task=task, custom_weights=custom_weights)

        # 3. Choose best option
        decision = self.choose_best_option(options, evaluations, task=task)

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        # Build task dict representation
        task_dict = {
            "id": getattr(task, "id", "") if hasattr(task, "id") else (task.get("id", "") if isinstance(task, dict) else ""),
            "title": getattr(task, "title", "") if hasattr(task, "title") else (task.get("title", str(task)) if isinstance(task, dict) else str(task)),
            "estimated_files": getattr(task, "estimated_files", []) if hasattr(task, "estimated_files") else (task.get("estimated_files", []) if isinstance(task, dict) else []),
        }

        telemetry = {
            "number_of_options": len(options),
            "evaluation_time_ms": duration_ms,
            "selected_score": decision.evaluation.weighted_score if decision.evaluation else 0.0,
            "confidence": decision.confidence,
        }

        report = DecisionReport(
            task=task_dict,
            options=options,
            selected_option=decision.selected_option,
            evaluation=evaluations,
            summary=decision.reasoning,
            timestamp=decision.timestamp,
            telemetry=telemetry,
        )

        # 4. Integrate with MemoryManager
        self._record_to_memory_manager(decision, task_dict)

        # 5. Persist to history
        self.save_history(report)

        # 6. Update telemetry metrics
        self._telemetry["number_of_decisions"] += 1
        self._telemetry["number_of_options"] = len(options)
        self._telemetry["evaluation_time"] = round(duration_ms / 1000.0, 4)
        self._telemetry["evaluation_time_ms"] = duration_ms
        self._telemetry["selected_score"] = decision.evaluation.weighted_score if decision.evaluation else 0.0
        self._telemetry["confidence"] = decision.confidence
        self._telemetry["decision_history"] = [r.to_dict() for r in self._decision_history]

        return report

    def generate_report(
        self,
        task: Any,
        options: List[DecisionOption],
        selected_option: DecisionOption,
        evaluations: Dict[str, DecisionEvaluation],
        summary: Optional[str] = None,
    ) -> DecisionReport:
        """Constructs a DecisionReport from precomputed evaluations and selection."""
        task_dict = {
            "id": getattr(task, "id", "") if hasattr(task, "id") else (task.get("id", "") if isinstance(task, dict) else ""),
            "title": getattr(task, "title", "") if hasattr(task, "title") else (task.get("title", str(task)) if isinstance(task, dict) else str(task)),
            "estimated_files": getattr(task, "estimated_files", []) if hasattr(task, "estimated_files") else (task.get("estimated_files", []) if isinstance(task, dict) else []),
        }

        sel_eval = evaluations.get(selected_option.id, DecisionEvaluation())
        sum_text = summary or f"Selected {selected_option.title} with score {sel_eval.weighted_score:.1f}/100."

        report = DecisionReport(
            task=task_dict,
            options=options,
            selected_option=selected_option,
            evaluation=evaluations,
            summary=sum_text,
            timestamp=datetime.now(timezone.utc).isoformat(),
            telemetry={
                "number_of_options": len(options),
                "selected_score": sel_eval.weighted_score,
                "confidence": 0.92,
            },
        )
        return report

    # -------------------------------------------------------------------------
    # MemoryManager Integration
    # -------------------------------------------------------------------------

    def _record_to_memory_manager(self, decision: EngineeringDecision, task_dict: Dict[str, Any]) -> None:
        """Stores architectural decision in MemoryManager under ARCHITECTURE category."""
        if not self.memory_manager:
            return

        try:
            alts_str = ", ".join(o.title for o in decision.alternative_options)
            content = (
                f"Strategy: {decision.selected_option.title}\n"
                f"Rationale: {decision.reasoning}\n"
                f"Tradeoffs: {' | '.join(decision.tradeoffs)}\n"
                f"Alternatives Considered: {alts_str}"
            )
            title = f"Decision: {decision.selected_option.title} for Task [{task_dict.get('id', 'N/A')}]"

            if hasattr(self.memory_manager, "add_memory"):
                self.memory_manager.add_memory(
                    title=title,
                    content=content,
                    category="ARCHITECTURE",
                    tags=["engineering_decision", "architecture", "strategy"],
                    importance=5,
                )
            elif hasattr(self.memory_manager, "record_decision"):
                self.memory_manager.record_decision(
                    title=title,
                    decision=decision.selected_option.description,
                    context=content,
                )
            logger.info("Recorded engineering decision to MemoryManager for Task [%s].", task_dict.get("id"))
        except Exception as err:
            logger.warning("Failed to record decision to MemoryManager: %s", err)

    # -------------------------------------------------------------------------
    # Serialization & Deserialization
    # -------------------------------------------------------------------------

    def serialize(self, report: DecisionReport) -> Dict[str, Any]:
        """Serializes a DecisionReport to a dictionary."""
        return report.to_dict()

    def deserialize(self, data: Union[str, Dict[str, Any]]) -> DecisionReport:
        """Deserializes a DecisionReport from a JSON string or dictionary."""
        if isinstance(data, str):
            data = json.loads(data)
        return DecisionReport.from_dict(data)

    # -------------------------------------------------------------------------
    # History Persistence & Query API
    # -------------------------------------------------------------------------

    def _load_history_on_init(self) -> None:
        """Loads existing decision history from persistence path if available."""
        if self.history_path.is_file():
            try:
                self.load_history()
            except Exception as err:
                logger.warning("Could not load initial decision history: %s", err)

    def save_history(self, report: DecisionReport, path: Optional[Union[str, Path]] = None) -> Path:
        """Atomically appends or updates a DecisionReport in persistent history storage."""
        dest = Path(path).resolve() if path else self.history_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Update in-memory list
        existing_idx = next((i for i, r in enumerate(self._decision_history) if r.task.get("id") == report.task.get("id")), None)
        if existing_idx is not None and report.task.get("id"):
            self._decision_history[existing_idx] = report
        else:
            self._decision_history.append(report)

        payload = {
            "reports": [r.to_dict() for r in self._decision_history],
            "total_records": len(self._decision_history),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        tmp_dest = dest.with_suffix(".tmp")
        with open(tmp_dest, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        shutil.move(str(tmp_dest), str(dest))
        return dest

    def load_history(self, path: Optional[Union[str, Path]] = None) -> List[DecisionReport]:
        """Loads all DecisionReports from persistent JSON storage."""
        src = Path(path).resolve() if path else self.history_path
        if not src.is_file():
            if self.auto_create_history:
                self._decision_history = []
                self.save_history_batch([], src)
                return self._decision_history
            raise FileNotFoundError(f"Decision history file not found at '{src}'.")

        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)

            records = data if isinstance(data, list) else data.get("reports", [])
            self._decision_history = [DecisionReport.from_dict(r) for r in records]
            return self._decision_history
        except Exception as err:
            logger.warning("Failed to parse decision history JSON ('%s'). Resetting in-memory history.", err)
            self._decision_history = []
            return self._decision_history

    def save_history_batch(self, reports: List[DecisionReport], path: Optional[Union[str, Path]] = None) -> Path:
        """Atomically writes an entire list of DecisionReports to persistent storage."""
        dest = Path(path).resolve() if path else self.history_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        self._decision_history = list(reports)
        payload = {
            "reports": [r.to_dict() for r in self._decision_history],
            "total_records": len(self._decision_history),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        tmp_dest = dest.with_suffix(".tmp")
        with open(tmp_dest, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        shutil.move(str(tmp_dest), str(dest))
        return dest

    def query_history(
        self,
        task_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[DecisionReport]:
        """Queries historical decision reports by task ID or full-text query."""
        results = list(self._decision_history)

        if task_id:
            tid_norm = task_id.strip().lower()
            results = [r for r in results if r.task.get("id", "").lower() == tid_norm]

        if query:
            tokens = [t.lower() for t in query.split() if len(t) > 1]
            if tokens:
                matched: List[DecisionReport] = []
                for r in results:
                    corpus = f"{r.task.get('title', '')} {r.selected_option.title} {r.summary}".lower()
                    if any(tok in corpus for tok in tokens):
                        matched.append(r)
                results = matched

        if limit is not None and limit > 0:
            results = results[:limit]

        return results

    # -------------------------------------------------------------------------
    # Telemetry API
    # -------------------------------------------------------------------------

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns structured telemetry data regarding decision generation and evaluation."""
        self._telemetry["decision_history"] = [r.to_dict() for r in self._decision_history]
        return dict(self._telemetry)
