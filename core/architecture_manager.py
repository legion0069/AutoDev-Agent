"""
architecture_manager.py - Architecture Decision Record (ADR) Engine & Design Validator for AutoDev

Enables AutoDev to remember WHY architectural decisions were made, prevent architectural drift,
and validate that future code changes remain consistent with previous design decisions.
Operates completely offline and deterministically without external services.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task
    from core.code_context_retriever import ContextBundle
    from core.impact_analyzer import ImpactReport
    from core.memory_manager import MemoryEntry
    from core.repository_analyzer import RepositoryOverview
    from core.symbol_graph import SymbolGraph

# Configure module logger
logger = logging.getLogger("AutoDev.ArchitectureManager")


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class DecisionCategory(str, Enum):
    """Supported decision categories in the Architecture Decision Record (ADR) subsystem."""
    DATABASE = "DATABASE"
    API = "API"
    SECURITY = "SECURITY"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    PERFORMANCE = "PERFORMANCE"
    CACHING = "CACHING"
    ARCHITECTURE = "ARCHITECTURE"
    DEPENDENCY_INJECTION = "DEPENDENCY_INJECTION"
    ERROR_HANDLING = "ERROR_HANDLING"
    LOGGING = "LOGGING"
    TESTING = "TESTING"
    DEPLOYMENT = "DEPLOYMENT"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    BUILD_SYSTEM = "BUILD_SYSTEM"
    LLM = "LLM"
    PROMPT_ENGINEERING = "PROMPT_ENGINEERING"
    MEMORY = "MEMORY"
    CODE_STYLE = "CODE_STYLE"

    @classmethod
    def normalize(cls, category: Union[str, DecisionCategory]) -> str:
        if isinstance(category, cls):
            return category.value
        cat_str = str(category).strip().upper().replace(" ", "_")
        try:
            return cls[cat_str].value
        except KeyError:
            return cls.ARCHITECTURE.value


class DecisionStatus(str, Enum):
    """Lifecycle status of an Architectural Decision Record."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

    @classmethod
    def normalize(cls, status: Union[str, DecisionStatus]) -> str:
        if isinstance(status, cls):
            return status.value
        stat_str = str(status).strip().lower()
        for member in cls:
            if member.value == stat_str:
                return member.value
        return cls.PROPOSED.value


class ViolationSeverity(str, Enum):
    """Severity classification for architectural design violations."""
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class ArchitectureDecision:
    """
    Architecture Decision Record (ADR) dataclass capturing context, decision rationale,
    consequences, alternatives, and component linkages.
    """
    id: str
    title: str
    status: str = DecisionStatus.ACCEPTED.value
    date: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives: List[str] = field(default_factory=list)
    related_components: List[str] = field(default_factory=list)
    related_tasks: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: int = 1
    category: str = DecisionCategory.ARCHITECTURE.value

    def __post_init__(self) -> None:
        self.status = DecisionStatus.normalize(self.status)
        self.category = DecisionCategory.normalize(self.category)
        if not self.id:
            self.id = "ADR-000"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes ArchitectureDecision to a dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "date": self.date,
            "context": self.context,
            "decision": self.decision,
            "consequences": self.consequences,
            "alternatives": list(self.alternatives),
            "related_components": list(self.related_components),
            "related_tasks": list(self.related_tasks),
            "tags": list(self.tags),
            "version": self.version,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArchitectureDecision:
        """Constructs an ArchitectureDecision instance from dictionary data."""
        return cls(
            id=str(data.get("id", "ADR-000")),
            title=str(data.get("title", "")),
            status=str(data.get("status", DecisionStatus.ACCEPTED.value)),
            date=str(data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))),
            context=str(data.get("context", "")),
            decision=str(data.get("decision", "")),
            consequences=str(data.get("consequences", "")),
            alternatives=list(data.get("alternatives", [])),
            related_components=list(data.get("related_components", [])),
            related_tasks=list(data.get("related_tasks", [])),
            tags=list(data.get("tags", [])),
            version=int(data.get("version", 1)),
            category=str(data.get("category", DecisionCategory.ARCHITECTURE.value)),
        )

    def to_markdown(self) -> str:
        """Renders ADR in standard MADR / Markdown format."""
        alt_str = "\n".join(f"- {a}" for a in self.alternatives) if self.alternatives else "- None considered"
        comp_str = ", ".join(self.related_components) if self.related_components else "None"
        tags_str = ", ".join(self.tags) if self.tags else "None"
        tasks_str = ", ".join(self.related_tasks) if self.related_tasks else "None"

        return f"""# {self.id}: {self.title}

* **Status**: {self.status.capitalize()}
* **Category**: {self.category}
* **Date**: {self.date}
* **Version**: {self.version}
* **Related Components**: {comp_str}
* **Related Tasks**: {tasks_str}
* **Tags**: {tags_str}

## Context
{self.context or "No context recorded."}

## Decision
{self.decision or "No decision text recorded."}

## Consequences
{self.consequences or "No consequences recorded."}

## Considered Alternatives
{alt_str}
"""


@dataclass
class DesignViolation:
    """Represents a specific architectural violation or drift detected in code or task."""
    rule_name: str
    severity: str  # CRITICAL, ERROR, WARNING, INFO
    target: str
    target_file: str
    description: str
    recommendation: str
    adr_reference: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "severity": self.severity,
            "target": self.target,
            "target_file": self.target_file,
            "description": self.description,
            "recommendation": self.recommendation,
            "adr_reference": self.adr_reference,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DesignViolation:
        return cls(
            rule_name=str(data.get("rule_name", "")),
            severity=str(data.get("severity", ViolationSeverity.WARNING.value)),
            target=str(data.get("target", "")),
            target_file=str(data.get("target_file", "")),
            description=str(data.get("description", "")),
            recommendation=str(data.get("recommendation", "")),
            adr_reference=data.get("adr_reference"),
        )


@dataclass
class ValidationReport:
    """Comprehensive design and ADR compliance evaluation report."""
    violations: List[DesignViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 (Safe) to 100.0 (High Risk)
    summary: str = ""
    is_critical: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violations": [v.to_dict() for v in self.violations],
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "passed_checks": list(self.passed_checks),
            "risk_score": self.risk_score,
            "summary": self.summary,
            "is_critical": self.is_critical,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationReport:
        return cls(
            violations=[DesignViolation.from_dict(v) for v in data.get("violations", [])],
            warnings=list(data.get("warnings", [])),
            recommendations=list(data.get("recommendations", [])),
            passed_checks=list(data.get("passed_checks", [])),
            risk_score=float(data.get("risk_score", 0.0)),
            summary=str(data.get("summary", "")),
            is_critical=bool(data.get("is_critical", False)),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
        )


# =============================================================================
# DESIGN VALIDATOR ENGINE
# =============================================================================

class DesignValidator:
    """
    Deterministic Design Validator engine that checks proposed tasks, code snippets,
    and impact graphs against architectural rules, pattern constraints, and accepted ADRs.
    """

    SECRET_PATTERNS = [
        (re.compile(r"""(?i)(?:api_key|apikey|secret_key|app_secret|auth_token|bearer)\s*=\s*['"][a-zA-Z0-9_\-\.]{12,}['"]"""), "Hardcoded Secret/Token"),
        (re.compile(r"""(?i)(?:password|passwd|pwd)\s*=\s*['"][^'"]{6,}['"]"""), "Hardcoded Password"),
        (re.compile(r"""(?i)(?:AWS_SECRET_ACCESS_KEY|PRIVATE_KEY)\s*=\s*['"][^'"]+['"]"""), "Cloud/Private Key"),
    ]

    RAW_SQL_PATTERN = re.compile(r"""(?i)(?:cursor\.execute|sqlite3\.connect|psycopg2\.connect|db\.execute|session\.execute\(["']\s*(?:SELECT|INSERT|UPDATE|DELETE))\b""")
    IMPORT_PRESENTATION_PATTERN = re.compile(r"""(?m)^\s*(?:from|import)\s+.*(?:controller|view|api|route|cli|ui)""")
    IMPORT_UI_PATTERN = re.compile(r"""(?m)^\s*(?:from|import)\s+.*(?:controller|views|routes|endpoints)""")
    CONCRETION_PATTERN = re.compile(r"""(?:self\.\w+\s*=\s*(?:OpenAIProvider|GeminiProvider|AnthropicProvider|PostgresDatabase)\(\))""")
    SINGLETON_PATTERN = re.compile(r"""global\s+_(?:instance|state|db|client)\b""")
    CLASS_PATTERN = re.compile(r"""class\s+([A-Za-z0-9_]+)\b""")
    EXCEPT_PATTERN = re.compile(r"""except(?:\s+Exception)?\s*:\s*\n\s*pass\b""")
    LOGGING_PATTERN = re.compile(r"""(?:logger|logging)\.(?:info|debug|warning|error|exception)""")

    def __init__(self, architecture_manager: Optional[ArchitectureManager] = None) -> None:
        self.architecture_manager = architecture_manager

    def validate(
        self,
        task: Any,
        code_context: Optional[Union[Dict[str, Any], ContextBundle, str]] = None,
        impact_report: Optional[ImpactReport] = None,
        architecture_decisions: Optional[List[ArchitectureDecision]] = None,
        symbol_graph: Optional[SymbolGraph] = None,
        repository_overview: Optional[RepositoryOverview] = None,
    ) -> ValidationReport:
        """
        Executes all 13 deterministic architectural and design integrity validations.
        """
        task_title = str(getattr(task, "title", "") if hasattr(task, "title") else (task.get("title", "") if isinstance(task, dict) else str(task)))
        task_desc = str(getattr(task, "description", "") if hasattr(task, "description") else (task.get("description", "") if isinstance(task, dict) else ""))
        est_files = list(getattr(task, "estimated_files", []) if hasattr(task, "estimated_files") else (task.get("estimated_files", []) if isinstance(task, dict) else []))

        # Resolve ADR rule flags
        has_repo_adr = False
        has_basellm_rule = False
        if architecture_decisions is not None:
            accepted_adrs = [d for d in architecture_decisions if d.status == DecisionStatus.ACCEPTED.value]
            has_repo_adr = any(d.category == DecisionCategory.DATABASE.value or "repository" in d.title.lower() for d in accepted_adrs)
            has_basellm_rule = any("basellm" in d.decision.lower() for d in accepted_adrs)
        elif self.architecture_manager:
            if len(self.architecture_manager._cached_all) != len(self.architecture_manager._decisions):
                self.architecture_manager._rebuild_cache()
            has_repo_adr = self.architecture_manager._has_repo_rule
            has_basellm_rule = self.architecture_manager._has_basellm_rule

        # Extract file map and code contents from code_context
        file_contents: Dict[str, str] = self._extract_file_contents(code_context, est_files)

        violations: List[DesignViolation] = []
        warnings: List[str] = []
        recommendations: List[str] = []
        passed_checks: List[str] = []

        # 1. Repository Pattern Violations & Direct DB Access
        self._check_repository_pattern_and_direct_db(
            task_title, task_desc, file_contents, has_repo_adr, violations, passed_checks
        )

        # 2. Layer Violations & Service Calling UI Layer
        self._check_layer_violations_and_service_calling_ui(
            file_contents, symbol_graph, violations, passed_checks
        )

        # 3. Dependency Inversion Violations
        self._check_dependency_inversion(
            task_title, task_desc, file_contents, violations, passed_checks
        )

        # 4. Circular Dependency Introduction
        self._check_circular_dependencies(
            symbol_graph, est_files, violations, passed_checks
        )

        # 5. Singleton Misuse
        self._check_singleton_misuse(
            file_contents, violations, passed_checks
        )

        # 6. Duplicate Implementations
        self._check_duplicate_implementations(
            file_contents, symbol_graph, violations, passed_checks
        )

        # 7. Bypassed Interfaces
        self._check_bypassed_interfaces(
            task_title, task_desc, file_contents, has_basellm_rule, symbol_graph, violations, passed_checks
        )

        # 8. Hardcoded Secrets
        self._check_hardcoded_secrets(
            file_contents, violations, passed_checks
        )

        # 9. Incorrect Exception Propagation
        self._check_exception_propagation(
            file_contents, violations, passed_checks
        )

        # 10. Missing Logging
        self._check_missing_logging(
            file_contents, violations, passed_checks
        )

        # 11. Missing Tests
        self._check_missing_tests(
            est_files, file_contents, task_title, violations, passed_checks
        )

        # Compile warnings and recommendations from violations
        for v in violations:
            warnings.append(f"[{v.severity}] {v.rule_name} in {v.target_file}: {v.description}")
            if v.recommendation and v.recommendation not in recommendations:
                recommendations.append(v.recommendation)

        # Calculate risk score (0.0 to 100.0)
        risk_score = 0.0
        for v in violations:
            if v.severity == ViolationSeverity.CRITICAL.value:
                risk_score += 40.0
            elif v.severity == ViolationSeverity.ERROR.value:
                risk_score += 25.0
            elif v.severity == ViolationSeverity.WARNING.value:
                risk_score += 10.0
            elif v.severity == ViolationSeverity.INFO.value:
                risk_score += 3.0
        risk_score = min(100.0, round(risk_score, 1))

        is_critical = any(v.severity == ViolationSeverity.CRITICAL.value for v in violations) or risk_score >= 80.0

        summary = (
            f"Design Validation: {len(passed_checks)} checks passed, {len(violations)} violation(s) detected. "
            f"Risk Score: {risk_score}/100 ({'CRITICAL' if is_critical else 'NORMAL'})."
        )

        return ValidationReport(
            violations=violations,
            warnings=warnings,
            recommendations=recommendations,
            passed_checks=passed_checks,
            risk_score=risk_score,
            summary=summary,
            is_critical=is_critical,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # -------------------------------------------------------------------------
    # Internal Validation Check Methods
    # -------------------------------------------------------------------------

    def _extract_file_contents(
        self,
        code_context: Optional[Union[Dict[str, Any], ContextBundle, str]],
        est_files: List[str],
    ) -> Dict[str, str]:
        file_map: Dict[str, str] = {}
        if isinstance(code_context, dict):
            # Check for project_files or direct mapping
            p_files = code_context.get("project_files", code_context)
            if isinstance(p_files, dict):
                for k, v in p_files.items():
                    if isinstance(v, str):
                        file_map[k] = v
                    elif isinstance(v, dict) and "content" in v:
                        file_map[k] = str(v["content"])
            # Check for snippets in context_bundle
            bundle = code_context.get("context_bundle")
            if bundle and hasattr(bundle, "snippets"):
                for snip in bundle.snippets:
                    f_name = getattr(snip, "file_path", "snippet")
                    content = getattr(snip, "code", "")
                    file_map[f_name] = file_map.get(f_name, "") + "\n" + content
        elif hasattr(code_context, "snippets"):
            for snip in code_context.snippets:
                f_name = getattr(snip, "file_path", "snippet")
                content = getattr(snip, "code", "")
                file_map[f_name] = file_map.get(f_name, "") + "\n" + content
        elif isinstance(code_context, str):
            file_map["injected_code.py"] = code_context

        # Read missing estimated files from disk if available
        if est_files:
            for ef in est_files:
                if ef not in file_map and os.path.isfile(ef):
                    try:
                        with open(ef, "r", encoding="utf-8", errors="ignore") as f:
                            file_map[ef] = f.read()
                    except Exception:
                        pass

        return file_map

    def _check_repository_pattern_and_direct_db(
        self,
        title: str,
        desc: str,
        files: Dict[str, str],
        has_repo_adr: bool,
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_violation = False

        for f_path, content in files.items():
            fn = f_path.lower()
            if "service" in fn or "manager" in fn or "controller" in fn:
                if self.RAW_SQL_PATTERN.search(content):
                    found_violation = True
                    violations.append(DesignViolation(
                        rule_name="Repository Pattern Violation",
                        severity=ViolationSeverity.ERROR.value,
                        target=f_path,
                        target_file=f_path,
                        description=f"Direct database SQL execution detected in service/controller '{f_path}'.",
                        recommendation="Encapsulate SQL and database persistence inside a dedicated Repository class.",
                        adr_reference="ADR-DATABASE" if has_repo_adr else None,
                    ))

        if not found_violation:
            passed_checks.append("Repository Pattern & Database Isolation")

    def _check_layer_violations_and_service_calling_ui(
        self,
        files: Dict[str, str],
        symbol_graph: Optional[SymbolGraph],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_violation = False

        for f_path, content in files.items():
            fn = f_path.lower()
            if "model" in fn or "entity" in fn or "domain" in fn:
                match = self.IMPORT_PRESENTATION_PATTERN.search(content)
                if match:
                    found_violation = True
                    matched_line = match.group(0).strip()
                    line_idx = content[:match.start()].count('\n') + 1
                    violations.append(DesignViolation(
                        rule_name="Layer Violation (Domain -> Presentation)",
                        severity=ViolationSeverity.CRITICAL.value,
                        target=f"Line {line_idx}",
                        target_file=f_path,
                        description=f"Domain model '{f_path}' illegally imports presentation component: '{matched_line}'.",
                        recommendation="Invert dependency: presentation must depend on domain models, not vice-versa.",
                    ))

            if "service" in fn or "core" in fn:
                match = self.IMPORT_UI_PATTERN.search(content)
                if match:
                    found_violation = True
                    matched_line = match.group(0).strip()
                    line_idx = content[:match.start()].count('\n') + 1
                    violations.append(DesignViolation(
                        rule_name="Service Calling UI Layer Violation",
                        severity=ViolationSeverity.ERROR.value,
                        target=f"Line {line_idx}",
                        target_file=f_path,
                        description=f"Business service '{f_path}' depends on UI/Controller layer: '{matched_line}'.",
                        recommendation="Remove upward dependencies from business services into web/CLI controllers.",
                    ))

        if not found_violation:
            passed_checks.append("Layer Hierarchy & Upward Dependency Integrity")

    def _check_dependency_inversion(
        self,
        title: str,
        desc: str,
        files: Dict[str, str],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_violation = False
        for f_path, content in files.items():
            fn = f_path.lower()
            if "service" in fn or "agent" in fn:
                if self.CONCRETION_PATTERN.search(content):
                    found_violation = True
                    violations.append(DesignViolation(
                        rule_name="Dependency Inversion Violation",
                        severity=ViolationSeverity.WARNING.value,
                        target=f_path,
                        target_file=f_path,
                        description=f"Direct hardcoded instantiation of concretion in '{f_path}' without constructor injection.",
                        recommendation="Inject dependencies via constructor parameters accepting abstract base classes/interfaces.",
                    ))

        if not found_violation:
            passed_checks.append("Dependency Inversion & Injection")

    def _check_circular_dependencies(
        self,
        symbol_graph: Optional[SymbolGraph],
        est_files: List[str],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        if symbol_graph:
            cycles: List[List[str]] = []
            if hasattr(symbol_graph, "detect_cycles"):
                cycles = symbol_graph.detect_cycles()
            elif hasattr(symbol_graph, "file_dependency_graph") and symbol_graph.file_dependency_graph:
                adj = symbol_graph.file_dependency_graph
                visited: Set[str] = set()
                rec_stack: List[str] = []

                def dfs(node: str) -> None:
                    visited.add(node)
                    rec_stack.append(node)
                    for neighbor in sorted(list(adj.get(node, set()))):
                        if neighbor not in visited:
                            dfs(neighbor)
                        elif neighbor in rec_stack:
                            idx = rec_stack.index(neighbor)
                            cycles.append(rec_stack[idx:] + [neighbor])
                    rec_stack.pop()

                for node in sorted(list(adj.keys())):
                    if node not in visited:
                        dfs(node)

            active_cycles = [c for c in cycles if not est_files or any(f in est_files for f in c)]
            if active_cycles:
                violations.append(DesignViolation(
                    rule_name="Circular Dependency Introduction",
                    severity=ViolationSeverity.CRITICAL.value,
                    target=" -> ".join(active_cycles[0]),
                    target_file=active_cycles[0][0],
                    description=f"Circular dependency cycle detected: {' -> '.join(active_cycles[0])}.",
                    recommendation="Refactor circular dependency using dependency injection or mediator interfaces.",
                ))
                return

        passed_checks.append("Acyclic Dependency Graph")

    def _check_singleton_misuse(
        self,
        files: Dict[str, str],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_violation = False
        for f_path, content in files.items():
            if "__new__" in content and self.SINGLETON_PATTERN.search(content):
                found_violation = True
                violations.append(DesignViolation(
                    rule_name="Singleton Misuse & Mutable Global State",
                    severity=ViolationSeverity.WARNING.value,
                    target=f_path,
                    target_file=f_path,
                    description=f"Global mutable singleton pattern detected in '{f_path}'.",
                    recommendation="Use dependency injection container or explicit scoped context instead of global mutable singletons.",
                ))

        if not found_violation:
            passed_checks.append("Singleton & Global State Hygiene")

    def _check_duplicate_implementations(
        self,
        files: Dict[str, str],
        symbol_graph: Optional[SymbolGraph],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        if len(files) <= 1:
            passed_checks.append("Unique Implementation Namespaces")
            return

        class_declarations: Dict[str, List[str]] = {}
        for f_path, content in files.items():
            if "class " in content:
                classes = self.CLASS_PATTERN.findall(content)
                for c in classes:
                    class_declarations.setdefault(c, []).append(f_path)

        duplicate_found = False
        for cls_name, locations in class_declarations.items():
            if len(locations) > 1 and not any("test" in loc for loc in locations):
                duplicate_found = True
                violations.append(DesignViolation(
                    rule_name="Duplicate Implementation",
                    severity=ViolationSeverity.ERROR.value,
                    target=cls_name,
                    target_file=locations[0],
                    description=f"Duplicate class name '{cls_name}' declared across multiple non-test modules: {', '.join(locations)}.",
                    recommendation="Consolidate duplicate class definitions into a shared core module or namespace.",
                ))

        if not duplicate_found:
            passed_checks.append("Unique Implementation Namespaces")

    def _check_bypassed_interfaces(
        self,
        title: str,
        desc: str,
        files: Dict[str, str],
        has_basellm_rule: bool,
        symbol_graph: Optional[SymbolGraph],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_violation = False

        if has_basellm_rule:
            for f_path, content in files.items():
                if "provider" in f_path.lower() and "base" not in f_path.lower() and "test" not in f_path.lower():
                    if "class " in content and "BaseLLM" not in content and "abc" not in content:
                        found_violation = True
                        violations.append(DesignViolation(
                            rule_name="Bypassed Interface Contract",
                            severity=ViolationSeverity.ERROR.value,
                            target=f_path,
                            target_file=f_path,
                            description=f"Provider '{f_path}' does not inherit from mandatory abstract interface 'BaseLLM'.",
                            recommendation="Inherit from BaseLLM and implement all abstract methods.",
                        ))
                        break

        if not found_violation:
            passed_checks.append("Interface & Abstraction Conformance")

    def _check_hardcoded_secrets(
        self,
        files: Dict[str, str],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_violation = False
        for f_path, content in files.items():
            if "test" in f_path.lower():
                continue
            for pattern, sec_name in self.SECRET_PATTERNS:
                if pattern.search(content):
                    found_violation = True
                    violations.append(DesignViolation(
                        rule_name="Hardcoded Secret Detection",
                        severity=ViolationSeverity.CRITICAL.value,
                        target=sec_name,
                        target_file=f_path,
                        description=f"Potential {sec_name} found hardcoded in production file '{f_path}'.",
                        recommendation="Read credentials from environment variables or secure configuration vault.",
                    ))
                    break

        if not found_violation:
            passed_checks.append("Credentials & Secret Security")

    def _check_exception_propagation(
        self,
        files: Dict[str, str],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_violation = False
        for f_path, content in files.items():
            if "test" in f_path.lower():
                continue
            if self.EXCEPT_PATTERN.search(content):
                found_violation = True
                violations.append(DesignViolation(
                    rule_name="Incorrect Exception Propagation (Swallowed Exception)",
                    severity=ViolationSeverity.WARNING.value,
                    target=f_path,
                    target_file=f_path,
                    description=f"Bare exception swallowed with 'pass' in '{f_path}' without logging or re-raising.",
                    recommendation="Handle specific exception types and log errors before recovering or re-raising.",
                ))

        if not found_violation:
            passed_checks.append("Structured Exception Handling")

    def _check_missing_logging(
        self,
        files: Dict[str, str],
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        found_missing = False
        for f_path, content in files.items():
            fn = f_path.lower()
            if ("agent" in fn or "orchestrator" in fn or "engine" in fn) and "test" not in fn:
                if len(content) > 500 and not self.LOGGING_PATTERN.search(content):
                    found_missing = True
                    violations.append(DesignViolation(
                        rule_name="Missing Observability / Logging",
                        severity=ViolationSeverity.INFO.value,
                        target=f_path,
                        target_file=f_path,
                        description=f"Core subsystem file '{f_path}' has substantial logic but lacks structured logging.",
                        recommendation="Configure a module logger (logging.getLogger) and record operational telemetry.",
                    ))

        if not found_missing:
            passed_checks.append("Logging & Observability Telemetry")

    def _check_missing_tests(
        self,
        est_files: List[str],
        files: Dict[str, str],
        task_title: str,
        violations: List[DesignViolation],
        passed_checks: List[str],
    ) -> None:
        has_tests = any("test" in f.lower() for f in est_files) or any("test" in f.lower() for f in files.keys())
        has_code = any("test" not in f.lower() for f in est_files) or any("test" not in f.lower() for f in files.keys())

        if has_code and not has_tests and len(est_files) > 0:
            violations.append(DesignViolation(
                rule_name="Missing Test Coverage Requirement",
                severity=ViolationSeverity.WARNING.value,
                target="Test Suite",
                target_file="tests/",
                description=f"Task '{task_title}' creates/modifies application code without accompanying test files.",
                recommendation="Add unit or integration tests in tests/ to validate the new behavior.",
            ))
        else:
            passed_checks.append("Test Coverage Association")


# =============================================================================
# ARCHITECTURE MANAGER SUBSYSTEM
# =============================================================================

class ArchitectureManager:
    """
    Architecture Decision Record (ADR) Engine for AutoDev.
    Records, retrieves, searches, validates, and exports architectural decisions.
    All persistence operations use atomic file writing.
    """

    DEFAULT_PERSISTENCE_PATH = Path("memory/architecture_decisions.json")

    def __init__(
        self,
        persistence_path: Optional[Union[str, Path]] = None,
        auto_create: bool = True,
    ) -> None:
        """
        Initializes ArchitectureManager with configured persistence storage.
        """
        self.persistence_path = Path(persistence_path).resolve() if persistence_path else self.DEFAULT_PERSISTENCE_PATH.resolve()
        self.auto_create = auto_create
        self._decisions: Dict[str, ArchitectureDecision] = {}
        self._cached_all: List[ArchitectureDecision] = []
        self._cached_accepted: List[ArchitectureDecision] = []
        self._has_repo_rule: bool = False
        self._has_basellm_rule: bool = False
        self.validator = DesignValidator(architecture_manager=self)
        self._initialized = False
        self._load_initial_decisions()

    def _rebuild_cache(self) -> None:
        """Rebuilds internal lookup and filtering caches."""
        self._cached_all = list(self._decisions.values())
        self._cached_all.sort(key=lambda d: d.id)
        self._cached_accepted = [d for d in self._cached_all if d.status == DecisionStatus.ACCEPTED.value]
        self._has_repo_rule = any(d.category == DecisionCategory.DATABASE.value or "repository" in d.title.lower() for d in self._cached_accepted)
        self._has_basellm_rule = any("basellm" in d.decision.lower() for d in self._cached_accepted)

    # -------------------------------------------------------------------------
    # Core Decision CRUD API
    # -------------------------------------------------------------------------

    def record_decision(
        self,
        title: str,
        decision: str,
        context: str = "",
        consequences: str = "",
        alternatives: Optional[List[str]] = None,
        related_components: Optional[List[str]] = None,
        related_tasks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        category: Union[str, DecisionCategory] = DecisionCategory.ARCHITECTURE,
        status: Union[str, DecisionStatus] = DecisionStatus.ACCEPTED,
        decision_id: Optional[str] = None,
    ) -> ArchitectureDecision:
        """
        Creates and stores a new ArchitectureDecision, automatically generating an ID if omitted.
        """
        self._ensure_loaded()
        norm_status = DecisionStatus.normalize(status)
        norm_category = DecisionCategory.normalize(category)

        if not decision_id:
            decision_id = self._generate_next_id()
        elif decision_id in self._decisions:
            logger.info("Overwriting existing decision '%s'.", decision_id)

        adr = ArchitectureDecision(
            id=decision_id,
            title=title.strip(),
            status=norm_status,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            context=context.strip(),
            decision=decision.strip(),
            consequences=consequences.strip(),
            alternatives=list(alternatives or []),
            related_components=list(related_components or []),
            related_tasks=list(related_tasks or []),
            tags=list(tags or []),
            version=1,
            category=norm_category,
        )

        self._decisions[adr.id] = adr
        self._rebuild_cache()
        self.save_decisions()
        logger.info("Recorded Architecture Decision [%s]: '%s'", adr.id, adr.title)
        return adr

    def update_decision(
        self,
        decision_id: str,
        title: Optional[str] = None,
        status: Optional[Union[str, DecisionStatus]] = None,
        context: Optional[str] = None,
        decision: Optional[str] = None,
        consequences: Optional[str] = None,
        alternatives: Optional[List[str]] = None,
        related_components: Optional[List[str]] = None,
        related_tasks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        category: Optional[Union[str, DecisionCategory]] = None,
    ) -> ArchitectureDecision:
        """
        Updates an existing ArchitectureDecision and increments its version number.
        """
        self._ensure_loaded()
        if decision_id not in self._decisions:
            raise KeyError(f"Architecture Decision '{decision_id}' not found.")

        adr = self._decisions[decision_id]
        if title is not None:
            adr.title = title.strip()
        if status is not None:
            adr.status = DecisionStatus.normalize(status)
        if context is not None:
            adr.context = context.strip()
        if decision is not None:
            adr.decision = decision.strip()
        if consequences is not None:
            adr.consequences = consequences.strip()
        if alternatives is not None:
            adr.alternatives = list(alternatives)
        if related_components is not None:
            adr.related_components = list(related_components)
        if related_tasks is not None:
            adr.related_tasks = list(related_tasks)
        if tags is not None:
            adr.tags = list(tags)
        if category is not None:
            adr.category = DecisionCategory.normalize(category)

        adr.version += 1
        adr.date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._rebuild_cache()
        self.save_decisions()
        logger.info("Updated Architecture Decision [%s] to v%d.", adr.id, adr.version)
        return adr

    def get_decision(self, decision_id: str) -> Optional[ArchitectureDecision]:
        """Retrieves a single ADR by ID."""
        self._ensure_loaded()
        return self._decisions.get(decision_id)

    def list_decisions(
        self,
        status: Optional[Union[str, DecisionStatus]] = None,
        category: Optional[Union[str, DecisionCategory]] = None,
        tag: Optional[str] = None,
    ) -> List[ArchitectureDecision]:
        """Lists ADRs with optional status, category, or tag filtering."""
        self._ensure_loaded()
        if len(self._cached_all) != len(self._decisions):
            self._rebuild_cache()

        if status is None and category is None and tag is None:
            return list(self._cached_all)

        results = list(self._cached_all)

        if status:
            norm_status = DecisionStatus.normalize(status)
            results = [d for d in results if d.status == norm_status]

        if category:
            norm_cat = DecisionCategory.normalize(category)
            results = [d for d in results if d.category == norm_cat]

        if tag:
            norm_tag = tag.strip().lower()
            results = [d for d in results if any(t.lower() == norm_tag for t in d.tags)]

        return results

    # -------------------------------------------------------------------------
    # Search & Retrieval API
    # -------------------------------------------------------------------------

    def search(self, query: str) -> List[ArchitectureDecision]:
        """Searches decisions matching query tokens across title, decision, context, and tags."""
        self._ensure_loaded()
        if not query or not query.strip():
            return self.list_decisions()

        tokens = [t.lower() for t in query.split() if len(t) > 1]
        if not tokens:
            return []

        scored: List[Tuple[float, ArchitectureDecision]] = []
        for adr in self._decisions.values():
            score = 0.0
            t_low = adr.title.lower()
            tags_low = [t.lower() for t in adr.tags]

            for tok in tokens:
                if tok in t_low:
                    score += 5.0
                elif tok in tags_low:
                    score += 4.0
                elif tok in adr.decision.lower():
                    score += 2.0
                elif tok in adr.context.lower():
                    score += 1.0

            if score > 0.0:
                scored.append((score, adr))

        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [item[1] for item in scored]

    def search_by_component(self, component_name: str) -> List[ArchitectureDecision]:
        """Finds ADRs associated with a specific component or module file."""
        self._ensure_loaded()
        c_norm = component_name.strip().lower().replace("\\", "/")
        matches: List[ArchitectureDecision] = []

        for adr in self._decisions.values():
            for rc in adr.related_components:
                rc_norm = rc.strip().lower().replace("\\", "/")
                if c_norm in rc_norm or rc_norm in c_norm or Path(rc_norm).stem == Path(c_norm).stem:
                    matches.append(adr)
                    break

        matches.sort(key=lambda d: d.id)
        return matches

    def search_by_tag(self, tag: str) -> List[ArchitectureDecision]:
        """Finds ADRs having the specified tag."""
        return self.list_decisions(tag=tag)

    def search_relevant_for_task(
        self,
        task: Any,
        context: Optional[Dict[str, Any]] = None,
        limit: int = 5,
    ) -> List[ArchitectureDecision]:
        """
        Retrieves top relevant ADRs for a given task, considering title, technology,
        estimated files, affected modules, and priorities.
        """
        self._ensure_loaded()
        task_title = str(getattr(task, "title", "") if hasattr(task, "title") else str(task))
        task_desc = str(getattr(task, "description", "") if hasattr(task, "description") else "")
        est_files = list(getattr(task, "estimated_files", []) if hasattr(task, "estimated_files") else [])

        search_text = f"{task_title} {task_desc} {' '.join(est_files)}"
        if context:
            search_text += f" {context.get('project_name', '')} {context.get('technology_stack', '')}"

        results = self.search(search_text)
        if not results:
            results = [d for d in self._decisions.values() if d.status == DecisionStatus.ACCEPTED.value]

        return results[:limit]

    # -------------------------------------------------------------------------
    # Validation & Analysis API
    # -------------------------------------------------------------------------

    def validate_against_decisions(
        self,
        task: Any,
        code_context: Optional[Union[Dict[str, Any], ContextBundle, str]] = None,
        impact_report: Optional[ImpactReport] = None,
        symbol_graph: Optional[SymbolGraph] = None,
        repository_overview: Optional[RepositoryOverview] = None,
    ) -> ValidationReport:
        """
        Validates task and code changes against all recorded architectural decisions.
        """
        self._ensure_loaded()
        return self.validator.validate(
            task=task,
            code_context=code_context,
            impact_report=impact_report,
            architecture_decisions=list(self._decisions.values()),
            symbol_graph=symbol_graph,
            repository_overview=repository_overview,
        )

    # -------------------------------------------------------------------------
    # Automatic Memory Promotion API
    # -------------------------------------------------------------------------

    def promote_from_memory(
        self,
        memory_entry: Union[MemoryEntry, Dict[str, Any]],
        min_importance: float = 0.7,
        eligible_categories: Optional[Set[str]] = None,
    ) -> Optional[ArchitectureDecision]:
        """
        Promotes an accepted solution, design pattern, or major architectural improvement
        from MemoryManager into a formal ArchitectureDecision.
        """
        self._ensure_loaded()
        if eligible_categories is None:
            eligible_categories = {"ARCHITECTURE", "PATTERN", "DECISION", "OPTIMIZATION", "BUG"}

        m_dict = memory_entry.to_dict() if hasattr(memory_entry, "to_dict") else dict(memory_entry)
        category = str(m_dict.get("category", "")).upper()
        importance = float(m_dict.get("importance", 0.5))

        if category not in eligible_categories or importance < min_importance:
            return None

        title = str(m_dict.get("title", "Promoted Architecture Decision"))
        content = str(m_dict.get("content", ""))
        tags = list(m_dict.get("tags", []))
        files = list(m_dict.get("associated_files", []))

        # Check if already promoted
        for adr in self._decisions.values():
            if adr.title.lower() == title.lower():
                return adr

        cat_map = {
            "ARCHITECTURE": DecisionCategory.ARCHITECTURE,
            "PATTERN": DecisionCategory.ARCHITECTURE,
            "DECISION": DecisionCategory.ARCHITECTURE,
            "OPTIMIZATION": DecisionCategory.PERFORMANCE,
            "BUG": DecisionCategory.ERROR_HANDLING,
        }
        dec_cat = cat_map.get(category, DecisionCategory.ARCHITECTURE)

        adr = self.record_decision(
            title=title,
            decision=content,
            context=f"Automatically promoted from engineering memory record ({category}).",
            consequences="Maintains architectural consistency established in prior successful tasks.",
            related_components=files,
            tags=tags + ["promoted_from_memory"],
            category=dec_cat,
            status=DecisionStatus.ACCEPTED,
        )
        logger.info("Automatically promoted memory entry into ADR [%s]: '%s'", adr.id, adr.title)
        return adr

    # -------------------------------------------------------------------------
    # Markdown & JSON Export / Import
    # -------------------------------------------------------------------------

    def export_markdown(self, output_path: Optional[Union[str, Path]] = None) -> str:
        """Exports all recorded ADRs as formatted Markdown documentation."""
        self._ensure_loaded()
        adrs = self.list_decisions()
        lines = [
            "# Architecture Decision Records (ADRs)",
            "",
            f"> Auto-generated by AutoDev ArchitectureManager on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            f"> Total Decisions: **{len(adrs)}**",
            "",
            "## Table of Decisions",
            "",
            "| ID | Title | Category | Status | Date | Version |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for adr in adrs:
            lines.append(f"| `{adr.id}` | {adr.title} | {adr.category} | `{adr.status}` | {adr.date} | v{adr.version} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        for adr in adrs:
            lines.append(adr.to_markdown())
            lines.append("---")
            lines.append("")

        md_content = "\n".join(lines)
        if output_path:
            dest = Path(output_path).resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(md_content)

        return md_content

    def export_json(self, output_path: Optional[Union[str, Path]] = None) -> Path:
        """Exports ADRs to a JSON file."""
        return self.save_decisions(output_path)

    def import_json(self, input_path: Union[str, Path]) -> int:
        """Imports ADRs from an external JSON file, merging with existing records."""
        src = Path(input_path).resolve()
        if not src.is_file():
            raise FileNotFoundError(f"ADR JSON file not found at '{src}'.")

        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        items = data if isinstance(data, list) else data.get("decisions", [])
        for item in items:
            adr = ArchitectureDecision.from_dict(item)
            self._decisions[adr.id] = adr
            count += 1

        self._rebuild_cache()
        self.save_decisions()
        logger.info("Imported %d architecture decisions from '%s'.", count, src)
        return count

    def save_decisions(self, output_path: Optional[Union[str, Path]] = None) -> Path:
        """Atomically saves all ADRs to JSON file."""
        dest = Path(output_path).resolve() if output_path else self.persistence_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "decisions": [adr.to_dict() for adr in sorted(self._decisions.values(), key=lambda d: d.id)],
            "total_decisions": len(self._decisions),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        tmp_dest = dest.with_suffix(".tmp")
        with open(tmp_dest, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        shutil.move(str(tmp_dest), str(dest))
        return dest

    def load_decisions(self, input_path: Optional[Union[str, Path]] = None) -> Dict[str, ArchitectureDecision]:
        """Loads ADRs from persisted JSON file."""
        src = Path(input_path).resolve() if input_path else self.persistence_path
        if not src.is_file():
            if self.auto_create:
                self._decisions = {}
                self._rebuild_cache()
                self.save_decisions(src)
                return self._decisions
            raise FileNotFoundError(f"Architecture decisions file not found at '{src}'.")

        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)

            decisions: Dict[str, ArchitectureDecision] = {}
            items = data if isinstance(data, list) else data.get("decisions", [])
            for item in items:
                adr = ArchitectureDecision.from_dict(item)
                decisions[adr.id] = adr

            self._decisions = decisions
            self._initialized = True
            self._rebuild_cache()
            return self._decisions
        except Exception as err:
            logger.warning("Failed to parse architecture decisions JSON ('%s'). Initializing fresh storage.", err)
            self._decisions = {}
            self._rebuild_cache()
            return self._decisions

    # -------------------------------------------------------------------------
    # Summarization & Statistics API
    # -------------------------------------------------------------------------

    def generate_summary(self) -> str:
        """Produces a concise human-readable summary of recorded decisions."""
        self._ensure_loaded()
        adrs = list(self._decisions.values())
        accepted = [d for d in adrs if d.status == DecisionStatus.ACCEPTED.value]
        proposed = [d for d in adrs if d.status == DecisionStatus.PROPOSED.value]
        rejected = [d for d in adrs if d.status == DecisionStatus.REJECTED.value]
        deprecated = [d for d in adrs if d.status == DecisionStatus.DEPRECATED.value]

        lines = [
            f"Architecture Decisions: {len(adrs)} Total ({len(accepted)} Accepted, {len(proposed)} Proposed, {len(rejected)} Rejected, {len(deprecated)} Deprecated)",
        ]
        for adr in accepted[:5]:
            desc_snip = f": {adr.decision[:60]}" if adr.decision else ""
            lines.append(f"  • [{adr.id}] {adr.title} ({adr.category}){desc_snip}")

        return "\n".join(lines)

    def statistics(self) -> Dict[str, Any]:
        """Calculates quantitative telemetry on recorded architectural decisions."""
        self._ensure_loaded()
        adrs = list(self._decisions.values())
        by_status: Dict[str, int] = {}
        by_category: Dict[str, int] = {}

        for d in adrs:
            by_status[d.status] = by_status.get(d.status, 0) + 1
            by_category[d.category] = by_category.get(d.category, 0) + 1

        return {
            "total_decisions": len(adrs),
            "by_status": by_status,
            "by_category": by_category,
            "total_components_linked": len({c for d in adrs for c in d.related_components}),
            "total_tags": len({t for d in adrs for t in d.tags}),
        }

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._initialized:
            self._load_initial_decisions()

    def _load_initial_decisions(self) -> None:
        if self.persistence_path.is_file():
            self.load_decisions()
        else:
            self._decisions = {}
            self._initialized = True

    def _generate_next_id(self) -> str:
        existing_nums = []
        for did in self._decisions.keys():
            match = re.match(r"ADR-(\d+)", did)
            if match:
                existing_nums.append(int(match.group(1)))
        next_num = max(existing_nums, default=0) + 1
        return f"ADR-{next_num:03d}"
