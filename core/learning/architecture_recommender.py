"""
architecture_recommender.py - Autonomous Architecture Recommendation Engine for AutoDev (v3.1)

Analyzes new incoming project requirements against historical successes, discovered patterns, and
domain playbooks to synthesize prescriptive recommendations for project folder structures, design patterns,
database choices, API styles, testing strategies, and security models.
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
    ArchitectureRecommendation,
    PlaybookArchetype,
)

logger = logging.getLogger("AutoDev.Learning.ArchitectureRecommender")


class ArchitectureRecommendationEngine:
    """
    Autonomous Architecture Recommendation Engine.
    Synthesizes optimal architecture design blueprints based on historical learning.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        self._recommendations: Dict[str, ArchitectureRecommendation] = {}

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create recommendation storage directory: %s", e)

    def _detect_archetype(self, text: str) -> PlaybookArchetype:
        """Determines best matching project archetype from requirement text."""
        t = text.lower()
        if "microservice" in t or "distributed" in t or "cluster" in t:
            return PlaybookArchetype.MICROSERVICES
        elif "spring" in t or "java" in t:
            return PlaybookArchetype.SPRING_BOOT
        elif "cli" in t or "command line" in t or "lint" in t or "terminal" in t:
            return PlaybookArchetype.PYTHON_CLI
        elif "agent" in t or "llm" in t or "ai" in t or "reasoning" in t:
            return PlaybookArchetype.AI_AGENT
        elif "dashboard" in t or "frontend" in t or "web" in t:
            return PlaybookArchetype.WEB_DASHBOARD
        elif "stream" in t or "kafka" in t or "event" in t:
            return PlaybookArchetype.EVENT_STREAMING
        elif "auth" in t or "jwt" in t or "login" in t:
            return PlaybookArchetype.AUTHENTICATION
        elif "crud" in t or "admin" in t:
            return PlaybookArchetype.CRUD_APPLICATION
        else:
            return PlaybookArchetype.REST_API

    def recommend(
        self,
        requirement: str = "",
        project_name: Optional[str] = None,
        requirements: Optional[str] = None,
        scale: str = "medium",
        domain_tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ArchitectureRecommendation:
        """Alias for recommend_architecture."""
        return self.recommend_architecture(
            requirement=requirement,
            project_name=project_name,
            requirements=requirements,
            scale=scale,
            domain_tags=domain_tags,
            **kwargs,
        )

    def recommend_architecture(
        self,
        requirement: str = "",
        project_name: Optional[str] = None,
        requirements: Optional[str] = None,
        scale: str = "medium",
        domain_tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ArchitectureRecommendation:
        """
        Synthesizes architecture design recommendations based on requirements and learned patterns.
        """
        with self._lock:
            now = time.time()
            req_text = requirement or requirements or project_name or "General Application"
            proj_name = project_name or req_text
            archetype = self._detect_archetype(req_text)

            rec_id = f"REC-ARCH-{int(now * 1000)}-{len(self._recommendations) + 1:03d}"

            if archetype == PlaybookArchetype.REST_API:
                folder_struct = {
                    "api": "api/v1/routes.py",
                    "core": "core/services.py",
                    "models": "models/domain.py",
                    "repositories": "repositories/repo.py",
                    "tests": "tests/unit/",
                }
                patterns = ["Repository Pattern", "Clean Architecture", "DTO Serializer"]
                db = "PostgreSQL with connection pooling"
                api_style = "RESTful JSON API with OpenAPI documentation"
                test_strat = "Pytest unit tests + integration test fixtures"
                sec_model = "Bearer JWT authentication + rate limiting"
                rationale = "REST APIs achieve high stability and testability using Repository Pattern and Clean Layering."
                conf = 0.94

            elif archetype == PlaybookArchetype.AI_AGENT:
                folder_struct = {
                    "agents": "agent/core_agent.py",
                    "tools": "agent/tools/",
                    "memory": "agent/memory_store.py",
                    "schemas": "schemas/contracts.py",
                    "tests": "tests/test_agent.py",
                }
                patterns = ["Agent-Tool Interface", "Pipeline Pattern", "State Machine"]
                db = "Local Memory / JSON Store with persistent snapshotting"
                api_style = "JSON-RPC / CLI Interface with typed event streams"
                test_strat = "Pytest deterministic unit test suite with mock LLM providers"
                sec_model = "Execution sandbox boundary + secret token redaction"
                rationale = "Autonomous AI agents require isolated tool execution boundaries and state persistence."
                conf = 0.95

            elif archetype == PlaybookArchetype.PYTHON_CLI:
                folder_struct = {
                    "cli": "cli/main.py",
                    "core": "core/engine.py",
                    "commands": "cli/commands/",
                    "tests": "tests/test_cli.py",
                }
                patterns = ["Command Pattern", "Plugin Architecture", "Argparse Dispatcher"]
                db = "None (Stateless) / Local SQLite"
                api_style = "CLI Arguments / Standard POSIX flags with JSON output"
                test_strat = "Pytest subprocess tests + CLI argument matrix tests"
                sec_model = "POSIX file permissions + input path traversal defense"
                rationale = "CLI utilities prioritize single-binary execution and zero external daemon dependencies."
                conf = 0.95

            elif archetype == PlaybookArchetype.MICROSERVICES or scale == "enterprise":
                folder_struct = {
                    "services": "services/microservices/",
                    "gateway": "services/gateway/",
                    "proto": "proto/contracts.proto",
                    "common": "common/messaging.py",
                    "tests": "tests/e2e/",
                }
                patterns = ["Event-Driven / CQRS", "API Gateway", "Saga Distributed Transaction"]
                db = "Distributed Event Store / PostgreSQL per service"
                api_style = "gRPC Protobuf internal + REST API Gateway external"
                test_strat = "Pytest contract tests + distributed integration test harness"
                sec_model = "mTLS / OAuth2 / JWT RBAC with distributed trace propagation"
                rationale = "Enterprise microservices require CQRS patterns and mTLS to enforce security boundaries."
                conf = 0.92

            else:
                folder_struct = {
                    "core": "core/app.py",
                    "models": "models/domain.py",
                    "tests": "tests/test_core.py",
                }
                patterns = ["Modular Architecture", "Repository Pattern"]
                db = "PostgreSQL"
                api_style = "RESTful JSON"
                test_strat = "Pytest"
                sec_model = "JWT / TLS"
                rationale = "Standard modular architecture with robust typing."
                conf = 0.90

            rec = ArchitectureRecommendation(
                recommendation_id=rec_id,
                project_name=proj_name,
                requirement_summary=req_text,
                archetype=archetype,
                recommended_folder_structure=folder_struct,
                recommended_structure=list(folder_struct.keys()),
                design_patterns=patterns,
                database_recommendation=db,
                database_choice=db,
                api_style=api_style,
                testing_strategy=test_strat,
                security_model=sec_model,
                confidence_score=conf,
                confidence=conf,
                rationale=rationale,
                historical_rationale=rationale,
                created_at=now,
            )

            self._recommendations[rec_id] = rec
            if self.auto_persist:
                self._persist_state()

            logger.info("Generated ArchitectureRecommendation %s for '%s' (%s, conf=%.2f)",
                        rec_id, proj_name, archetype.value, conf)
            return copy.deepcopy(rec)

    def incorporate_feedback(
        self,
        recommendation_id: str,
        success: bool = True,
        quality_score: float = 90.0,
    ) -> Optional[ArchitectureRecommendation]:
        """Updates recommendation confidence based on project outcome."""
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if not rec:
                return None
            if success:
                rec.confidence_score = min(1.0, round(rec.confidence_score + 0.03, 3))
            else:
                rec.confidence_score = max(0.5, round(rec.confidence_score - 0.08, 3))
            rec.confidence = rec.confidence_score
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(rec)

    def get_recommendation(self, recommendation_id: str) -> Optional[ArchitectureRecommendation]:
        """Retrieves a recommendation by ID."""
        with self._lock:
            r = self._recommendations.get(recommendation_id)
            return copy.deepcopy(r) if r else None

    def get_all_recommendations(self) -> List[ArchitectureRecommendation]:
        """Returns all stored architecture recommendations."""
        with self._lock:
            items = list(self._recommendations.values())
            items.sort(key=lambda x: x.created_at, reverse=True)
            return [copy.deepcopy(r) for r in items]

    def list_recommendations(self) -> List[ArchitectureRecommendation]:
        """Alias for get_all_recommendations."""
        return self.get_all_recommendations()

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            out_file = self.storage_dir / "architecture_recommendations.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._recommendations.values()], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist architecture recommendations: %s", e)

    def _load_state(self) -> None:
        out_file = self.storage_dir / "architecture_recommendations.json"
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        r = ArchitectureRecommendation.from_dict(item)
                        self._recommendations[r.recommendation_id] = r
            except Exception as e:
                logger.warning("Could not load architecture recommendations: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_recommendations": len(self._recommendations),
                "by_archetype": {
                    a.value: sum(1 for r in self._recommendations.values() if r.archetype == a)
                    for a in PlaybookArchetype
                },
            }
