"""
playbook_engine.py - Autonomous Engineering Playbook Engine for AutoDev (v3.1)

Manages, evolves, and dispenses battle-tested Engineering Playbooks across major software project archetypes:
REST API, Spring Boot, Python CLI, AI Agent, Web Dashboard, Microservices, Authentication, CRUD, Event Streaming,
and Distributed Workers. Continuously incorporates learnings from completed projects.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.learning.learning_models import (
    EngineeringPlaybook,
    LearningEvent,
    LearningEventType,
    PlaybookArchetype,
)

logger = logging.getLogger("AutoDev.Learning.PlaybookEngine")


class PlaybookEngine:
    """
    Autonomous Engineering Playbook Engine.
    Provides standard implementation sequences, best practices, and mistake avoidance rules by archetype.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        self._playbooks: Dict[PlaybookArchetype, EngineeringPlaybook] = {}

        # Initialize standard playbooks
        self._init_default_playbooks()

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create playbook storage directory: %s", e)

    def _init_default_playbooks(self) -> None:
        """Initializes foundational engineering playbooks across 10 archetypes."""
        playbook_defs = [
            (
                PlaybookArchetype.REST_API,
                "REST API Service Playbook",
                "Standard engineering sequence for building production-grade REST APIs.",
                [
                    "1. Define domain models and dataclasses in `models/`",
                    "2. Implement repository interfaces and database adapters in `repositories/`",
                    "3. Implement business logic domain services in `services/`",
                    "4. Implement HTTP route controllers and request validators in `api/`",
                    "5. Write unit tests for services and integration tests for endpoints in `tests/`",
                ],
                [
                    "Use explicit request and response DTO schemas and Pydantic validation",
                    "Handle all exceptions with structured JSON error envelopes",
                    "Implement database connection pooling and query timeouts",
                    "Enforce authentication and rate limiting middleware",
                ],
                [
                    "Exposing raw database entities directly to API responses",
                    "Executing database queries inside loops (N+1 query defect)",
                    "Catching broad `except Exception` and returning HTTP 200 on failure",
                ],
                12.0,
                {"min_coverage_pct": 92.0, "min_test_coverage_pct": 92.0, "max_cyclomatic_complexity": 8.0},
                ["models/dto.py", "repositories/repo.py", "services/service.py", "api/routes.py", "tests/"],
            ),
            (
                PlaybookArchetype.SPRING_BOOT,
                "Spring Boot Microservice Playbook",
                "Clean enterprise Spring Boot development sequence with JPA and layered controllers.",
                [
                    "1. Define JPA entity models and repository interfaces",
                    "2. Implement business service layer with transaction management",
                    "3. Wire REST controllers with Bean validation",
                    "4. Configure application.yml profiles and security filters",
                    "5. Build JUnit 5 and Mockito test suite",
                ],
                [
                    "Use constructor injection instead of field injection",
                    "Wrap external service calls with CircuitBreaker",
                    "Use DTO records for API contract immutability",
                ],
                [
                    "Using @Transactional on private methods",
                    "LazyInitializationException on detached JPA entities",
                    "Hardcoding configuration properties",
                ],
                14.0,
                {"min_coverage_pct": 90.0, "min_test_coverage_pct": 90.0, "max_cyclomatic_complexity": 8.0},
                ["domain/", "repository/", "service/", "controller/", "config/"],
            ),
            (
                PlaybookArchetype.PYTHON_CLI,
                "Python CLI Application Playbook",
                "Best practices for command-line utilities and developer tooling.",
                [
                    "1. Define argument parser with subcommands and flags in `cli.py`",
                    "2. Implement core business logic in `core/engine.py`",
                    "3. Implement output formatters (JSON, tabular, plain text) in `formatters.py`",
                    "4. Write tests invoking subcommands and verifying exit codes in `tests/`",
                    "5. Package as zero-dependency self-contained executable",
                ],
                [
                    "Support `--json` flag for machine-readable output",
                    "Return non-zero exit codes on failure",
                    "Provide clear `--help` text with command examples",
                ],
                [
                    "Writing business logic directly inside argument parsing handlers",
                    "Failing silently without writing to stderr on errors",
                    "Importing heavy modules at module top-level slowing CLI startup",
                ],
                6.0,
                {"min_coverage_pct": 90.0, "min_test_coverage_pct": 90.0, "max_cyclomatic_complexity": 8.0},
                ["cli/main.py", "cli/commands.py", "core/engine.py", "tests/test_cli.py"],
            ),
            (
                PlaybookArchetype.AI_AGENT,
                "Autonomous AI Agent Playbook",
                "Deterministic architecture for AI agents with memory, tools, and reflection.",
                [
                    "1. Define state machine lifecycle states and transition contracts",
                    "2. Implement tool dispatcher with strict path containment and sandbox verification",
                    "3. Implement memory store and reflection logger",
                    "4. Implement prompt synthesizer with token budgeting and pattern injection",
                    "5. Write unit tests mocking provider LLM outputs to guarantee deterministic behavior",
                ],
                [
                    "Enforce strict timeouts on tool executions and LLM invocations",
                    "Redact API keys and secrets before logging prompts and responses",
                    "Maintain append-only execution journal for deterministic replay",
                ],
                [
                    "Unbounded retry loops without exponential backoff or max attempt limits",
                    "Allowing tools to execute arbitrary unvalidated shell commands",
                    "Assuming LLM responses always adhere strictly to JSON without regex validation",
                ],
                16.0,
                {"min_coverage_pct": 92.0, "min_test_coverage_pct": 92.0, "max_cyclomatic_complexity": 8.0},
                ["agent/agent.py", "agent/tools.py", "agent/memory.py", "agent/prompts.py", "tests/"],
            ),
            (
                PlaybookArchetype.WEB_DASHBOARD,
                "Glassmorphic Web Dashboard Playbook",
                "Architecture for low-latency live observability dashboards.",
                [
                    "1. Create responsive glassmorphic HTML/CSS design tokens",
                    "2. Implement SSE stream client in JavaScript with automatic reconnection",
                    "3. Implement backend SSE event broadcaster and REST query endpoints",
                    "4. Wire chart visualizations and interactive filter controls",
                    "5. Write DOM verification tests and backend event throughput tests",
                ],
                [
                    "Use CSS variables for theme and glassmorphism styling",
                    "Implement Last-Event-ID replay for network disconnects",
                    "Keep DOM updates batched using requestAnimationFrame",
                ],
                [
                    "Polling backend REST endpoints at high frequencies instead of using SSE",
                    "Blocking HTTP server worker threads with long-lived SSE connections",
                    "Inline styling without reusable design tokens",
                ],
                10.0,
                {"min_coverage_pct": 90.0, "min_test_coverage_pct": 90.0, "max_cyclomatic_complexity": 9.0},
                ["dashboard/index.html", "dashboard/styles.css", "dashboard/app.js", "server.py"],
            ),
            (
                PlaybookArchetype.MICROSERVICES,
                "Microservices Distributed Architecture Playbook",
                "Patterns for multi-service distributed systems with event streaming.",
                [
                    "1. Define service contracts and Protobuf / OpenAPI schemas",
                    "2. Implement independent service engines with isolated databases",
                    "3. Implement asynchronous event bus communication",
                    "4. Implement centralized health checking and telemetry collectors",
                    "5. Write end-to-end integration tests validating inter-service messaging",
                ],
                [
                    "Enforce database-per-service isolation",
                    "Implement idempotent event consumers with message deduplication",
                    "Use correlation IDs across all distributed requests",
                ],
                [
                    "Shared database tables between independent services",
                    "Synchronous cascading HTTP calls causing distributed deadlocks",
                    "Missing circuit breakers on inter-service requests",
                ],
                24.0,
                {"min_coverage_pct": 90.0, "min_test_coverage_pct": 90.0, "max_cyclomatic_complexity": 10.0},
                ["services/gateway/", "services/core/", "proto/", "common/messaging.py", "tests/"],
            ),
            (
                PlaybookArchetype.AUTHENTICATION,
                "Authentication & RBAC Identity Playbook",
                "Security-hardened user identity, JWT issuing, password hashing, and role-based permissions.",
                [
                    "1. Implement Argon2 / Bcrypt password hashing with constant-time comparison",
                    "2. Implement signed JWT token generator with expiration and audience claims",
                    "3. Build permission policy engine and RBAC middleware",
                    "4. Wire login, refresh, and revoke token endpoints",
                    "5. Write security fuzzing tests and token tampering validation tests",
                ],
                [
                    "Never store plaintext passwords or tokens in database",
                    "Validate issuer, audience, and algorithm header explicitly",
                    "Use short-lived access tokens and revocable refresh tokens",
                ],
                [
                    "Allowing 'none' algorithm in JWT header validation",
                    "Logging authentication tokens in debug logs",
                    "Timing attack vulnerability on password comparison",
                ],
                12.0,
                {"min_coverage_pct": 95.0, "min_test_coverage_pct": 95.0, "max_cyclomatic_complexity": 7.0},
                ["auth/tokens.py", "auth/hashing.py", "auth/rbac.py", "auth/routes.py", "tests/"],
            ),
            (
                PlaybookArchetype.CRUD_APPLICATION,
                "CRUD Application Playbook",
                "Standard data-entry, filtering, pagination, and persistent storage workflow.",
                [
                    "1. Define database schema and primary keys with creation timestamps",
                    "2. Implement Repository CRUD operations with transaction rollback",
                    "3. Implement service validation rules and pagination limits",
                    "4. Implement REST CRUD endpoints with standard HTTP status codes",
                    "5. Write unit tests for data integrity and edge-case pagination",
                ],
                [
                    "Use HTTP 201 for POST creations and HTTP 204 for DELETE operations",
                    "Always enforce maximum limit on pagination query parameters",
                    "Use optimistic concurrency control for concurrent edits",
                ],
                [
                    "Unpaginated SQL queries loading entire tables into RAM",
                    "Missing unique constraints causing duplicate data entries",
                    "Ignoring soft-delete audit trails",
                ],
                8.0,
                {"min_coverage_pct": 90.0, "min_test_coverage_pct": 90.0, "max_cyclomatic_complexity": 8.0},
                ["models/entity.py", "crud/repo.py", "services/crud_service.py", "api/routes.py"],
            ),
            (
                PlaybookArchetype.EVENT_STREAMING,
                "Event Streaming & Pub/Sub Playbook",
                "Scalable event-driven pipelines with consumer groups and dead-letter queues.",
                [
                    "1. Define canonical event payload schemas with schema versioning",
                    "2. Implement producer with transactional outbox pattern",
                    "3. Implement consumer handlers with idempotent processing and ACK protocol",
                    "4. Implement Dead Letter Queue (DLQ) retry policy with exponential backoff",
                    "5. Write throughput benchmark tests and poison message recovery tests",
                ],
                [
                    "Use idempotent message keys to safely handle at-least-once delivery",
                    "Monitor consumer group lag metrics continuously",
                    "Route failed payloads to DLQ after max retries",
                ],
                [
                    "Blocking consumer event loop on slow synchronous third-party HTTP calls",
                    "Modifying event schema without backward-compatible versioning",
                    "Losing events due to auto-commit before message handling succeeds",
                ],
                18.0,
                {"min_coverage_pct": 90.0, "min_test_coverage_pct": 90.0, "max_cyclomatic_complexity": 9.0},
                ["events/schemas.py", "events/producer.py", "events/consumer.py", "events/dlq.py"],
            ),
            (
                PlaybookArchetype.DISTRIBUTED_WORKER,
                "Distributed Background Worker Playbook",
                "Task execution engines with lease heartbeats, worker pools, and fault tolerance.",
                [
                    "1. Define task contract, priority queues, and execution payload",
                    "2. Implement worker heartbeat manager and lease renewal loop",
                    "3. Implement execution sandbox with memory and timeout limits",
                    "4. Implement worker failover and stale task reassignment supervisor",
                    "5. Write node crash recovery tests and concurrent task scheduling tests",
                ],
                [
                    "Renew task leases periodically before TTL expiration",
                    "Isolate worker execution within sandboxed process boundaries",
                    "Handle SIGTERM / SIGINT gracefully with checkpointing",
                ],
                [
                    "Zombie worker processes holding dead task leases indefinitely",
                    "Unbounded concurrency causing host memory exhaustion",
                    "Swallowing worker task exceptions without reporting failure status",
                ],
                20.0,
                {"min_coverage_pct": 90.0, "min_test_coverage_pct": 90.0, "max_cyclomatic_complexity": 9.0},
                ["workers/pool.py", "workers/lease.py", "workers/executor.py", "workers/supervisor.py"],
            ),
        ]

        now = time.time()
        for arch, title, desc, seq, best, errs, eff, metrics, struct in playbook_defs:
            self._playbooks[arch] = EngineeringPlaybook(
                playbook_id=f"PB-{arch.value}-01",
                archetype=arch,
                title=title,
                description=desc,
                recommended_sequence=seq,
                best_practices=best,
                common_mistakes=errs,
                estimated_effort_hours=eff,
                quality_metrics=metrics,
                sample_file_structure=struct,
                usage_count=0,
                success_rate=1.0,
                version="1.0.0",
                created_at=now,
                updated_at=now,
            )

    def get_playbook(self, archetype: Union[PlaybookArchetype, str]) -> Optional[EngineeringPlaybook]:
        """Retrieves playbook for a specific project archetype."""
        with self._lock:
            # Handle string and enum conversions
            target_arch = archetype
            if isinstance(archetype, str):
                arch_str = archetype.upper().replace("-", "_").replace(" ", "_")
                if arch_str in PlaybookArchetype.__members__:
                    target_arch = PlaybookArchetype[arch_str]
                elif arch_str == "CRUD":
                    target_arch = PlaybookArchetype.CRUD_APPLICATION
                elif arch_str == "LLM_INTEGRATION":
                    target_arch = PlaybookArchetype.AI_AGENT
                elif arch_str == "EVENT_DRIVEN":
                    target_arch = PlaybookArchetype.EVENT_STREAMING
                else:
                    for a in PlaybookArchetype:
                        if a.value == arch_str or a.name == arch_str:
                            target_arch = a
                            break

            p = self._playbooks.get(target_arch)
            if not p and isinstance(target_arch, str):
                for k, v in self._playbooks.items():
                    if k.value == target_arch or k.name == target_arch:
                        return copy.deepcopy(v)
            return copy.deepcopy(p) if p else None

    def get_all_playbooks(self) -> List[EngineeringPlaybook]:
        """Returns all registered engineering playbooks."""
        with self._lock:
            return [copy.deepcopy(p) for p in self._playbooks.values()]

    def list_playbooks(self) -> List[EngineeringPlaybook]:
        """Alias for get_all_playbooks."""
        return self.get_all_playbooks()

    def register_playbook(self, playbook: EngineeringPlaybook) -> EngineeringPlaybook:
        """Registers or replaces an engineering playbook."""
        with self._lock:
            self._playbooks[playbook.archetype] = playbook
            if self.auto_persist:
                self._persist_state()
            logger.info("Registered EngineeringPlaybook '%s' for %s", playbook.title, playbook.archetype.value)
            return copy.deepcopy(playbook)

    def create_playbook(
        self,
        archetype: PlaybookArchetype,
        title: str,
        description: str,
        recommended_sequence: List[str],
        best_practices: List[str],
        common_mistakes: List[str],
        estimated_effort_hours: float = 10.0,
        quality_metrics: Optional[Dict[str, float]] = None,
        sample_file_structure: Optional[List[str]] = None,
    ) -> EngineeringPlaybook:
        """Creates and registers a new playbook."""
        pb = EngineeringPlaybook(
            playbook_id=f"PB-{archetype.value}-{int(time.time() * 1000)}",
            archetype=archetype,
            title=title,
            description=description,
            recommended_sequence=list(recommended_sequence),
            best_practices=list(best_practices),
            common_mistakes=list(common_mistakes),
            estimated_effort_hours=estimated_effort_hours,
            quality_metrics=dict(quality_metrics or {"min_coverage_pct": 90.0}),
            sample_file_structure=list(sample_file_structure or []),
            version="1.1.0",
        )
        return self.register_playbook(pb)

    def record_playbook_experience(
        self,
        archetype: Union[PlaybookArchetype, str],
        success: bool = True,
        actual_effort_hours: Optional[float] = None,
        duration_minutes: Optional[float] = None,
        review_score: Optional[float] = None,
        **kwargs: Any,
    ) -> Optional[EngineeringPlaybook]:
        """Records an execution experience against a playbook and updates its success rate and effort estimate."""
        with self._lock:
            target_arch = archetype
            if isinstance(archetype, str):
                arch_str = archetype.upper().replace("-", "_").replace(" ", "_")
                if arch_str in PlaybookArchetype.__members__:
                    target_arch = PlaybookArchetype[arch_str]
                elif arch_str == "CRUD":
                    target_arch = PlaybookArchetype.CRUD_APPLICATION
                elif arch_str == "LLM_INTEGRATION":
                    target_arch = PlaybookArchetype.AI_AGENT
                elif arch_str == "EVENT_DRIVEN":
                    target_arch = PlaybookArchetype.EVENT_STREAMING

            pb = self._playbooks.get(target_arch)
            if not pb:
                return None
            
            past_successes = round(pb.usage_count * pb.success_rate)
            pb.usage_count += 1
            if success:
                past_successes += 1
            pb.success_rate = round(past_successes / max(1, pb.usage_count), 2)

            effort = actual_effort_hours
            if effort is None and duration_minutes is not None:
                effort = duration_minutes / 60.0
            
            if effort is not None and effort > 0:
                pb.estimated_effort_hours = round(
                    0.7 * pb.estimated_effort_hours + 0.3 * effort, 2
                )
            
            pb.updated_at = time.time()
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(pb)

    def update_playbook_from_experience(
        self,
        archetype: PlaybookArchetype,
        learning_event: LearningEvent,
    ) -> Optional[EngineeringPlaybook]:
        """Dynamically updates a playbook with new bug fixes or best practices."""
        with self._lock:
            pb = self._playbooks.get(archetype)
            if not pb:
                return None

            pb.updated_at = time.time()
            if learning_event.category == LearningEventType.BUG_FIXED and learning_event.root_cause:
                mistake_entry = f"Avoid: {learning_event.root_cause}"
                if mistake_entry not in pb.common_mistakes:
                    pb.common_mistakes.append(mistake_entry)
                if learning_event.solution:
                    best_entry = f"Practice: {learning_event.solution}"
                    if best_entry not in pb.best_practices:
                        pb.best_practices.append(best_entry)

            elif learning_event.category == LearningEventType.ARCHITECTURE_SUCCESS and learning_event.summary:
                if learning_event.summary not in pb.best_practices:
                    pb.best_practices.append(f"Architectural Success: {learning_event.summary}")

            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(pb)

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            out_file = self.storage_dir / "playbooks.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump([p.to_dict() for p in self._playbooks.values()], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist playbooks: %s", e)

    def _load_state(self) -> None:
        out_file = self.storage_dir / "playbooks.json"
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        p = EngineeringPlaybook.from_dict(item)
                        self._playbooks[p.archetype] = p
            except Exception as e:
                logger.warning("Could not load playbooks: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_playbooks": len(self._playbooks),
                "archetypes_available": [a.value for a in self._playbooks.keys()],
            }
