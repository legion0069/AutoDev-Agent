"""
change_planner.py - Semantic Refactoring & Change Planning Engine for AutoDev (v1.8)

Computes optimal, deterministic, offline modification plans before code generation occurs.
Analyzes tasks, SymbolGraph, RepositoryAnalyzer, and ImpactAnalyzer to determine:
- Minimal file change sets (files to modify, create, delete, and avoid)
- Granular symbol changes and signatures
- Semantic refactoring strategies (Rename, Extract Method/Class, Move, Repository/Service Extraction, Patterns)
- Breaking changes across APIs, signatures, inheritance, schemas, REST endpoints, and CLI commands
- Database and configuration migration steps with rollback instructions
- Change dependency graphs, topological execution order, and rollback order
- Architectural consistency and layer violation validation rules
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.impact_analyzer import ImpactAnalyzer, ImpactReport
from core.repository_analyzer import (
    ArchitectureLayer,
    ArchitectureMetrics,
    Hotspot,
    ModuleSummary,
    RepositoryAnalyzer,
    RepositoryOverview,
)
from core.symbol_graph import Dependency, Symbol, SymbolGraph, SymbolType, Visibility

logger = logging.getLogger("AutoDev.ChangePlanner")


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ChangeClassification(str, Enum):
    FEATURE = "Feature"
    BUG_FIX = "Bug Fix"
    REFACTOR = "Refactor"
    OPTIMIZATION = "Optimization"
    SECURITY_PATCH = "Security Patch"
    DOCUMENTATION = "Documentation"
    CONFIGURATION = "Configuration"
    TEST = "Test"
    BUILD = "Build"
    INFRASTRUCTURE = "Infrastructure"


class RefactoringType(str, Enum):
    RENAME = "Rename"
    EXTRACT_METHOD = "Extract Method"
    EXTRACT_CLASS = "Extract Class"
    MOVE_METHOD = "Move Method"
    MOVE_CLASS = "Move Class"
    INLINE_METHOD = "Inline Method"
    INLINE_VARIABLE = "Inline Variable"
    SPLIT_MODULE = "Split Module"
    MERGE_MODULE = "Merge Module"
    DEPENDENCY_INJECTION = "Dependency Injection"
    REPOSITORY_EXTRACTION = "Repository Extraction"
    SERVICE_EXTRACTION = "Service Extraction"
    FACTORY_EXTRACTION = "Factory Extraction"
    STRATEGY_PATTERN = "Strategy Pattern"
    ADAPTER_PATTERN = "Adapter Pattern"
    FACADE = "Facade"
    OBSERVER = "Observer"
    DECORATOR = "Decorator"


class NecessityRank(str, Enum):
    PRIMARY_TARGET = "PRIMARY_TARGET"
    DIRECT_DEPENDENCY = "DIRECT_DEPENDENCY"
    DOWNSTREAM_AFFECTED = "DOWNSTREAM_AFFECTED"
    TEST_VALIDATION = "TEST_VALIDATION"
    PROTECTED = "PROTECTED"


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class FileChange:
    """Represents a planned change to a specific file with necessity ranking."""
    file_path: str
    change_type: str  # MODIFY, CREATE, DELETE, RENAME, NO_CHANGE
    necessity_rank: str  # PRIMARY_TARGET, DIRECT_DEPENDENCY, DOWNSTREAM_AFFECTED, TEST_VALIDATION, PROTECTED
    reason: str
    estimated_loc: int = 15
    symbols_affected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "necessity_rank": self.necessity_rank,
            "reason": self.reason,
            "estimated_loc": self.estimated_loc,
            "symbols_affected": list(self.symbols_affected),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileChange:
        return cls(
            file_path=data.get("file_path", ""),
            change_type=data.get("change_type", "MODIFY"),
            necessity_rank=data.get("necessity_rank", NecessityRank.PRIMARY_TARGET),
            reason=data.get("reason", ""),
            estimated_loc=int(data.get("estimated_loc", 15)),
            symbols_affected=list(data.get("symbols_affected", [])),
        )


@dataclass
class SymbolChange:
    """Represents a planned modification, addition, or removal of a code symbol."""
    symbol_name: str
    file_path: str
    change_type: str  # ADD, MODIFY, DELETE, RENAME, MOVE, SIGNATURE_CHANGE
    old_signature: Optional[str] = None
    new_signature: Optional[str] = None
    reason: str = ""
    is_breaking: bool = False
    callers_affected: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_name": self.symbol_name,
            "file_path": self.file_path,
            "change_type": self.change_type,
            "old_signature": self.old_signature,
            "new_signature": self.new_signature,
            "reason": self.reason,
            "is_breaking": self.is_breaking,
            "callers_affected": list(self.callers_affected),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SymbolChange:
        return cls(
            symbol_name=data.get("symbol_name", ""),
            file_path=data.get("file_path", ""),
            change_type=data.get("change_type", "MODIFY"),
            old_signature=data.get("old_signature"),
            new_signature=data.get("new_signature"),
            reason=data.get("reason", ""),
            is_breaking=bool(data.get("is_breaking", False)),
            callers_affected=list(data.get("callers_affected", [])),
        )


@dataclass
class RefactoringStep:
    """Represents a high-level semantic refactoring operation."""
    refactoring_type: str
    target: str
    target_file: str
    description: str
    rationale: str
    source_location: Optional[str] = None
    destination_location: Optional[str] = None
    priority: str = "HIGH"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "refactoring_type": self.refactoring_type,
            "target": self.target,
            "target_file": self.target_file,
            "description": self.description,
            "rationale": self.rationale,
            "source_location": self.source_location,
            "destination_location": self.destination_location,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RefactoringStep:
        return cls(
            refactoring_type=data.get("refactoring_type", RefactoringType.RENAME),
            target=data.get("target", ""),
            target_file=data.get("target_file", ""),
            description=data.get("description", ""),
            rationale=data.get("rationale", ""),
            source_location=data.get("source_location"),
            destination_location=data.get("destination_location"),
            priority=data.get("priority", "HIGH"),
        )


@dataclass
class BreakingChange:
    """Details a breaking change, affected API surface, and mitigation strategy."""
    change_category: str  # PUBLIC_API, SIGNATURE_CHANGE, INHERITANCE_CHANGE, REMOVED_EXPORT, DELETED_FILE, CONFIG_CHANGE, SCHEMA_CHANGE, DATABASE_MIGRATION, REST_ENDPOINT, CLI_CHANGE
    target: str
    target_file: str
    description: str
    impact_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    mitigation_strategy: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_category": self.change_category,
            "target": self.target,
            "target_file": self.target_file,
            "description": self.description,
            "impact_level": self.impact_level,
            "mitigation_strategy": self.mitigation_strategy,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BreakingChange:
        return cls(
            change_category=data.get("change_category", "PUBLIC_API"),
            target=data.get("target", ""),
            target_file=data.get("target_file", ""),
            description=data.get("description", ""),
            impact_level=data.get("impact_level", "HIGH"),
            mitigation_strategy=data.get("mitigation_strategy", ""),
        )


@dataclass
class MigrationStep:
    """Represents a database, schema, or configuration migration step with rollback instructions."""
    migration_type: str  # DATABASE_SCHEMA, CONFIG_MIGRATION, API_VERSIONING, DATA_TRANSFORMATION, DEPENDENCY_UPGRADE
    target_file: str
    description: str
    sql_or_code_action: str
    rollback_instruction: str
    is_reversible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "migration_type": self.migration_type,
            "target_file": self.target_file,
            "description": self.description,
            "sql_or_code_action": self.sql_or_code_action,
            "rollback_instruction": self.rollback_instruction,
            "is_reversible": self.is_reversible,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MigrationStep:
        return cls(
            migration_type=data.get("migration_type", "DATABASE_SCHEMA"),
            target_file=data.get("target_file", ""),
            description=data.get("description", ""),
            sql_or_code_action=data.get("sql_or_code_action", ""),
            rollback_instruction=data.get("rollback_instruction", ""),
            is_reversible=bool(data.get("is_reversible", True)),
        )


@dataclass
class ValidationRule:
    """Architectural and dependency safety validation rule outcome."""
    rule_name: str
    passed: bool
    severity: str  # ERROR, WARNING, INFO
    description: str
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "passed": self.passed,
            "severity": self.severity,
            "description": self.description,
            "recommendation": self.recommendation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationRule:
        return cls(
            rule_name=data.get("rule_name", ""),
            passed=bool(data.get("passed", True)),
            severity=data.get("severity", "INFO"),
            description=data.get("description", ""),
            recommendation=data.get("recommendation", ""),
        )


@dataclass
class ChangePlan:
    """
    Comprehensive, deterministic modification blueprint generated before code synthesis.
    """
    task_id: str = "TASK-00"
    task_title: str = ""
    change_classification: str = ChangeClassification.FEATURE
    files_to_modify: List[str] = field(default_factory=list)
    files_to_create: List[str] = field(default_factory=list)
    files_to_delete: List[str] = field(default_factory=list)
    files_to_avoid: List[str] = field(default_factory=list)
    file_changes: List[FileChange] = field(default_factory=list)
    symbol_changes: List[SymbolChange] = field(default_factory=list)
    refactoring_steps: List[RefactoringStep] = field(default_factory=list)
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    migration_steps: List[MigrationStep] = field(default_factory=list)
    test_updates: List[Dict[str, Any]] = field(default_factory=list)
    config_updates: List[Dict[str, Any]] = field(default_factory=list)
    dependency_updates: List[Dict[str, Any]] = field(default_factory=list)
    doc_updates: List[Dict[str, Any]] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)
    rollback_order: List[str] = field(default_factory=list)
    validation_rules: List[ValidationRule] = field(default_factory=list)
    estimated_total_lines: int = 0
    risk_level: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_title": self.task_title,
            "change_classification": self.change_classification,
            "files_to_modify": list(self.files_to_modify),
            "files_to_create": list(self.files_to_create),
            "files_to_delete": list(self.files_to_delete),
            "files_to_avoid": list(self.files_to_avoid),
            "file_changes": [f.to_dict() for f in self.file_changes],
            "symbol_changes": [s.to_dict() for s in self.symbol_changes],
            "refactoring_steps": [r.to_dict() for r in self.refactoring_steps],
            "breaking_changes": [b.to_dict() for b in self.breaking_changes],
            "migration_steps": [m.to_dict() for m in self.migration_steps],
            "test_updates": list(self.test_updates),
            "config_updates": list(self.config_updates),
            "dependency_updates": list(self.dependency_updates),
            "doc_updates": list(self.doc_updates),
            "execution_order": list(self.execution_order),
            "rollback_order": list(self.rollback_order),
            "validation_rules": [v.to_dict() for v in self.validation_rules],
            "estimated_total_lines": self.estimated_total_lines,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChangePlan:
        return cls(
            task_id=data.get("task_id", "TASK-00"),
            task_title=data.get("task_title", ""),
            change_classification=data.get("change_classification", ChangeClassification.FEATURE),
            files_to_modify=list(data.get("files_to_modify", [])),
            files_to_create=list(data.get("files_to_create", [])),
            files_to_delete=list(data.get("files_to_delete", [])),
            files_to_avoid=list(data.get("files_to_avoid", [])),
            file_changes=[FileChange.from_dict(f) for f in data.get("file_changes", [])],
            symbol_changes=[SymbolChange.from_dict(s) for s in data.get("symbol_changes", [])],
            refactoring_steps=[RefactoringStep.from_dict(r) for r in data.get("refactoring_steps", [])],
            breaking_changes=[BreakingChange.from_dict(b) for b in data.get("breaking_changes", [])],
            migration_steps=[MigrationStep.from_dict(m) for m in data.get("migration_steps", [])],
            test_updates=list(data.get("test_updates", [])),
            config_updates=list(data.get("config_updates", [])),
            dependency_updates=list(data.get("dependency_updates", [])),
            doc_updates=list(data.get("doc_updates", [])),
            execution_order=list(data.get("execution_order", [])),
            rollback_order=list(data.get("rollback_order", [])),
            validation_rules=[ValidationRule.from_dict(v) for v in data.get("validation_rules", [])],
            estimated_total_lines=int(data.get("estimated_total_lines", 0)),
            risk_level=data.get("risk_level", "LOW"),
            summary=data.get("summary", ""),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


# =============================================================================
# CHANGE PLANNER ENGINE
# =============================================================================

class ChangePlanner:
    """
    Deterministic offline change planner that computes optimal code modifications,
    semantic refactoring strategies, breaking change detection, and topological ordering.
    """

    DEFAULT_OUTPUT_PATH = Path("memory/change_plan.json")

    DATABASE_KEYWORDS = {
        "migration", "schema", "table", "column", "foreign key", "alter table",
        "create table", "drop column", "add column", "database", "sqlalchemy", "prisma", "orm",
    }

    REST_API_KEYWORDS = {
        "endpoint", "route", "router", "get", "post", "put", "delete", "patch", "api", "controller",
    }

    CLI_KEYWORDS = {
        "cli", "command", "flag", "argument", "click", "argparse", "typer", "options",
    }

    def __init__(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        repository_analyzer: Optional[RepositoryAnalyzer] = None,
        impact_analyzer: Optional[ImpactAnalyzer] = None,
        output_path: Union[str, Path] = DEFAULT_OUTPUT_PATH,
    ) -> None:
        """
        Initializes ChangePlanner with static code intelligence instances.
        """
        self.symbol_graph = symbol_graph
        self.repository_analyzer = repository_analyzer
        self.impact_analyzer = impact_analyzer
        self.output_path = Path(output_path).resolve()

    # -------------------------------------------------------------------------
    # Main Planning API
    # -------------------------------------------------------------------------

    def plan(
        self,
        task: Any,
        context: Optional[Dict[str, Any]] = None,
        symbol_graph: Optional[SymbolGraph] = None,
        repository_overview: Optional[RepositoryOverview] = None,
        impact_report: Optional[ImpactReport] = None,
    ) -> ChangePlan:
        """
        Generates a comprehensive, deterministic ChangePlan for the given task.
        """
        ctx = context or {}
        graph = symbol_graph or self.symbol_graph or ctx.get("symbol_graph") or SymbolGraph()
        overview = repository_overview or ctx.get("repository_analysis") or ctx.get("repository_overview")
        impact = impact_report or ctx.get("impact_report")

        if overview is None and graph.files:
            analyzer = self.repository_analyzer or RepositoryAnalyzer(symbol_graph=graph)
            overview = analyzer.analyze(symbol_graph=graph, project_files=ctx.get("project_files"))

        task_id = str(getattr(task, "id", "TASK-00") if hasattr(task, "id") else ctx.get("task_id", "TASK-00"))
        task_title = str(getattr(task, "title", "") if hasattr(task, "title") else ctx.get("task_title", str(task)))
        task_desc = str(getattr(task, "description", "") if hasattr(task, "description") else "")
        est_files = list(getattr(task, "estimated_files", []) if hasattr(task, "estimated_files") else [])

        # 1. Change Classification
        classification = self._classify_change(task_title, task_desc, est_files)

        # 2. Minimal Change Set Computation
        file_changes, files_to_modify, files_to_create, files_to_delete, files_to_avoid = self.compute_change_set(
            task=task,
            graph=graph,
            context=ctx,
            overview=overview,
            impact=impact,
        )

        # 3. Symbol Changes
        symbol_changes = self._compute_symbol_changes(task_title, task_desc, file_changes, graph)

        # 4. Semantic Refactoring Strategy
        refactoring_steps = self._detect_refactoring_steps(task_title, task_desc, file_changes, symbol_changes, graph, overview)

        # 5. Breaking Change Analysis
        breaking_changes = self.detect_breaking_changes(
            task=task,
            file_changes=file_changes,
            symbol_changes=symbol_changes,
            graph=graph,
            overview=overview,
        )

        # 6. Database & Configuration Migrations
        migration_steps, config_updates = self._compute_migrations(task_title, task_desc, file_changes, breaking_changes)

        # 7. Test, Dependency & Doc Updates
        test_updates, dependency_updates, doc_updates = self._compute_auxiliary_updates(
            task_title, task_desc, file_changes, symbol_changes, graph, overview
        )

        # 8. Dependency Graph & Topological Ordering
        execution_order, rollback_order = self.build_execution_order(
            file_changes=file_changes,
            refactoring_steps=refactoring_steps,
            graph=graph,
            overview=overview,
        )

        # 9. Architectural & Safety Validation
        validation_rules = self.validate_plan(
            file_changes=file_changes,
            symbol_changes=symbol_changes,
            breaking_changes=breaking_changes,
            graph=graph,
            overview=overview,
        )

        # 10. Line Estimation & Risk Scoring
        total_loc = sum(fc.estimated_loc for fc in file_changes if fc.change_type != "NO_CHANGE")
        risk_level = self._compute_risk_level(breaking_changes, migration_steps, file_changes, validation_rules)

        # 11. Deterministic Summary Generation
        summary = self._generate_plan_summary(
            task_id=task_id,
            classification=classification,
            files_to_modify=files_to_modify,
            files_to_create=files_to_create,
            files_to_delete=files_to_delete,
            breaking_changes=breaking_changes,
            total_loc=total_loc,
            risk_level=risk_level,
        )

        plan = ChangePlan(
            task_id=task_id,
            task_title=task_title,
            change_classification=classification,
            files_to_modify=files_to_modify,
            files_to_create=files_to_create,
            files_to_delete=files_to_delete,
            files_to_avoid=files_to_avoid,
            file_changes=file_changes,
            symbol_changes=symbol_changes,
            refactoring_steps=refactoring_steps,
            breaking_changes=breaking_changes,
            migration_steps=migration_steps,
            test_updates=test_updates,
            config_updates=config_updates,
            dependency_updates=dependency_updates,
            doc_updates=doc_updates,
            execution_order=execution_order,
            rollback_order=rollback_order,
            validation_rules=validation_rules,
            estimated_total_lines=total_loc,
            risk_level=risk_level,
            summary=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return plan

    # -------------------------------------------------------------------------
    # Core Algorithms
    # -------------------------------------------------------------------------

    def compute_change_set(
        self,
        task: Any,
        graph: SymbolGraph,
        context: Dict[str, Any],
        overview: Optional[RepositoryOverview] = None,
        impact: Optional[ImpactReport] = None,
    ) -> Tuple[List[FileChange], List[str], List[str], List[str], List[str]]:
        """
        Computes the minimal valid modification set and classifies files into
        modify, create, delete, and avoid (protected).
        """
        task_title = str(getattr(task, "title", "") if hasattr(task, "title") else str(task))
        task_desc = str(getattr(task, "description", "") if hasattr(task, "description") else "")
        est_files = list(getattr(task, "estimated_files", []) if hasattr(task, "estimated_files") else [])

        known_files: Set[str] = set()
        if graph and graph.files:
            known_files.update(f.replace("\\", "/") for f in graph.files.keys())
        if "project_files" in context and context["project_files"]:
            known_files.update(f.replace("\\", "/") for f in context["project_files"].keys())
        if overview and overview.module_summaries:
            known_files.update(f.replace("\\", "/") for f in overview.module_summaries.keys())

        # Match targets from task
        primary_targets: Set[str] = set()
        for ef in est_files:
            primary_targets.add(ef.replace("\\", "/"))

        # Regex scan for file paths in task text
        scanned_paths = re.findall(r"[\w/\.-]+\.(?:py|java|js|ts|tsx|jsx|json|yaml|yml|sql|toml)", f"{task_title} {task_desc}")
        for sp in scanned_paths:
            sp_norm = sp.replace("\\", "/")
            if not sp_norm.startswith(("http://", "https://")):
                primary_targets.add(sp_norm)

        # Match symbols in graph
        for sym_name, sym in graph.symbols.items():
            if sym_name.lower() in task_title.lower() or sym_name.lower() in task_desc.lower():
                if sym.file:
                    primary_targets.add(sym.file.replace("\\", "/"))

        # Fallback if no targets found
        if not primary_targets and known_files:
            primary_targets.add(sorted(list(known_files))[0])

        files_to_modify: Set[str] = set()
        files_to_create: Set[str] = set()
        files_to_delete: Set[str] = set()
        file_changes: List[FileChange] = []

        # Classify primary targets
        for pt in sorted(list(primary_targets)):
            is_delete = any(k in f"{task_title} {task_desc}".lower() for k in [f"delete {pt}", f"remove {pt}", f"drop {pt}"])
            if is_delete:
                files_to_delete.add(pt)
                file_changes.append(FileChange(
                    file_path=pt,
                    change_type="DELETE",
                    necessity_rank=NecessityRank.PRIMARY_TARGET,
                    reason=f"File '{pt}' marked for deletion per task specification.",
                    estimated_loc=0,
                ))
            elif pt in known_files or self._file_exists_on_disk(pt, context):
                files_to_modify.add(pt)
                file_changes.append(FileChange(
                    file_path=pt,
                    change_type="MODIFY",
                    necessity_rank=NecessityRank.PRIMARY_TARGET,
                    reason=f"Primary implementation target for task '{task_title}'.",
                    estimated_loc=self._estimate_loc_for_file(pt, graph, context),
                ))
            else:
                files_to_create.add(pt)
                file_changes.append(FileChange(
                    file_path=pt,
                    change_type="CREATE",
                    necessity_rank=NecessityRank.PRIMARY_TARGET,
                    reason=f"New module required to fulfill task '{task_title}'.",
                    estimated_loc=40,
                ))

        # Check for downstream affected files via ImpactReport or Graph
        downstream_files: Set[str] = set()
        if impact and impact.affected_files:
            for af in impact.affected_files:
                af_norm = af.replace("\\", "/")
                if af_norm not in primary_targets and af_norm in known_files:
                    downstream_files.add(af_norm)

        for df in sorted(list(downstream_files))[:3]:
            files_to_modify.add(df)
            file_changes.append(FileChange(
                file_path=df,
                change_type="MODIFY",
                necessity_rank=NecessityRank.DOWNSTREAM_AFFECTED,
                reason=f"Downstream dependency affected by changes to primary targets.",
                estimated_loc=10,
            ))

        # Check for associated test files
        for target_f in list(primary_targets):
            stem = Path(target_f).stem
            test_candidates = [
                f"tests/test_{stem}.py",
                f"test_{stem}.py",
                f"tests/{stem}_test.py",
                f"tests/test_{stem}.ts",
            ]
            for tc in test_candidates:
                if tc not in primary_targets and tc not in downstream_files:
                    if tc in known_files or self._file_exists_on_disk(tc, context):
                        files_to_modify.add(tc)
                        file_changes.append(FileChange(
                            file_path=tc,
                            change_type="MODIFY",
                            necessity_rank=NecessityRank.TEST_VALIDATION,
                            reason=f"Update existing test suite to validate changes in '{target_f}'.",
                            estimated_loc=20,
                        ))
                        break
                    elif not any(tc_item.file_path == tc for tc_item in file_changes):
                        files_to_create.add(tc)
                        file_changes.append(FileChange(
                            file_path=tc,
                            change_type="CREATE",
                            necessity_rank=NecessityRank.TEST_VALIDATION,
                            reason=f"Create dedicated test suite for '{target_f}'.",
                            estimated_loc=25,
                        ))
                        break

        # Compute protected files to avoid
        changed_set = files_to_modify | files_to_create | files_to_delete
        files_to_avoid = sorted([f for f in known_files if f not in changed_set])

        return (
            file_changes,
            sorted(list(files_to_modify)),
            sorted(list(files_to_create)),
            sorted(list(files_to_delete)),
            files_to_avoid,
        )

    def detect_breaking_changes(
        self,
        task: Any,
        file_changes: List[FileChange],
        symbol_changes: List[SymbolChange],
        graph: SymbolGraph,
        overview: Optional[RepositoryOverview] = None,
    ) -> List[BreakingChange]:
        """
        Detects breaking changes across public APIs, signatures, inheritance, schemas, and routes.
        """
        task_text = f"{getattr(task, 'title', '')} {getattr(task, 'description', '')}".lower()
        breaking: List[BreakingChange] = []

        # 1. Deleted Files with Dependents
        for fc in file_changes:
            if fc.change_type == "DELETE":
                dependents = graph.file_reverse_dependencies.get(fc.file_path, set())
                if dependents:
                    breaking.append(BreakingChange(
                        change_category="DELETED_FILE",
                        target=fc.file_path,
                        target_file=fc.file_path,
                        description=f"Deletion of file '{fc.file_path}' breaks {len(dependents)} dependent module(s): {', '.join(sorted(list(dependents))[:3])}.",
                        impact_level="CRITICAL",
                        mitigation_strategy="Update all import sites or provide backward-compatible re-export module aliases.",
                    ))

        # 2. Public Symbol Modifications or Deletions with Callers
        for sc in symbol_changes:
            if sc.is_breaking or sc.change_type in ("DELETE", "RENAME", "SIGNATURE_CHANGE"):
                sym = graph.find_symbol(sc.symbol_name) if hasattr(graph, "find_symbol") else graph.symbols.get(sc.symbol_name)
                callers = sc.callers_affected or (graph.find_callers(sc.symbol_name) if hasattr(graph, "find_callers") else list(graph.reverse_call_graph.get(sc.symbol_name, [])))

                if sc.change_type == "DELETE":
                    breaking.append(BreakingChange(
                        change_category="PUBLIC_API",
                        target=sc.symbol_name,
                        target_file=sc.file_path,
                        description=f"Public symbol '{sc.symbol_name}' deleted with {len(callers)} active caller(s).",
                        impact_level="CRITICAL" if callers else "HIGH",
                        mitigation_strategy="Deprecate symbol with a warning before removal or update all call sites.",
                    ))
                elif sc.change_type == "SIGNATURE_CHANGE" or "signature" in sc.reason.lower():
                    breaking.append(BreakingChange(
                        change_category="SIGNATURE_CHANGE",
                        target=sc.symbol_name,
                        target_file=sc.file_path,
                        description=f"Signature change for '{sc.symbol_name}' breaks existing invocation contracts.",
                        impact_level="HIGH",
                        mitigation_strategy="Use default parameter values or overload functions to preserve signature compatibility.",
                    ))
                elif sc.change_type == "RENAME":
                    breaking.append(BreakingChange(
                        change_category="REMOVED_EXPORT",
                        target=sc.symbol_name,
                        target_file=sc.file_path,
                        description=f"Renaming '{sc.symbol_name}' invalidates downstream import references.",
                        impact_level="MEDIUM",
                        mitigation_strategy="Export a compatibility alias (e.g. old_name = new_name) during transition.",
                    ))

        # 3. Base Class & Inheritance Breaking Changes
        for sc in symbol_changes:
            subclasses = graph.find_subclasses(sc.symbol_name) if hasattr(graph, "find_subclasses") else list(graph.subclass_graph.get(sc.symbol_name, []))
            if subclasses and sc.change_type in ("MODIFY", "DELETE", "SIGNATURE_CHANGE"):
                subclass_names = [s.name if hasattr(s, "name") else str(s) for s in subclasses]
                breaking.append(BreakingChange(
                    change_category="INHERITANCE_CHANGE",
                    target=sc.symbol_name,
                    target_file=sc.file_path,
                    description=f"Base class '{sc.symbol_name}' modification affects {len(subclasses)} subclass(es): {', '.join(subclass_names[:3])}.",
                    impact_level="HIGH",
                    mitigation_strategy="Ensure abstract method contracts remain consistent across all derived classes.",
                ))

        # 4. Database Schema & Migration Breaking Changes
        if any(k in task_text for k in self.DATABASE_KEYWORDS):
            target_file = next((fc.file_path for fc in file_changes if "model" in fc.file_path or "schema" in fc.file_path or "db" in fc.file_path), "database/schema.sql")
            breaking.append(BreakingChange(
                change_category="DATABASE_MIGRATION",
                target="Database Schema",
                target_file=target_file,
                description="Database schema or table structure modified, requiring an explicit migration script.",
                impact_level="HIGH",
                mitigation_strategy="Generate reversible database migration script with forward and rollback SQL.",
            ))

        # 5. REST API & CLI Breaking Changes
        if any(k in task_text for k in self.REST_API_KEYWORDS) and any(k in task_text for k in ["change", "modify", "remove", "update"]):
            breaking.append(BreakingChange(
                change_category="REST_ENDPOINT",
                target="API Route Contract",
                target_file=next((fc.file_path for fc in file_changes if "controller" in fc.file_path or "api" in fc.file_path or "route" in fc.file_path), "api/routes.py"),
                description="REST endpoint contract or request/response schema altered.",
                impact_level="MEDIUM",
                mitigation_strategy="Support API versioning (e.g. /v2/) to avoid breaking legacy consumers.",
            ))

        if any(k in task_text for k in self.CLI_KEYWORDS) and any(k in task_text for k in ["argument", "flag", "command", "option"]):
            breaking.append(BreakingChange(
                change_category="CLI_CHANGE",
                target="CLI Interface",
                target_file=next((fc.file_path for fc in file_changes if "cli" in fc.file_path or "main" in fc.file_path), "cli.py"),
                description="Command line interface argument structure changed.",
                impact_level="MEDIUM",
                mitigation_strategy="Maintain backward-compatible aliases for legacy flags and commands.",
            ))

        return breaking

    def build_execution_order(
        self,
        file_changes: List[FileChange],
        refactoring_steps: List[RefactoringStep],
        graph: SymbolGraph,
        overview: Optional[RepositoryOverview] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Constructs a dependency-ordered execution graph and computes topological execution
        order (dependencies first) and rollback order (reverse).
        """
        target_files = [fc.file_path for fc in file_changes if fc.change_type != "DELETE"]

        # Build dependency adjacency list restricted to target files
        adj: Dict[str, Set[str]] = defaultdict(set)
        in_degree: Dict[str, int] = {f: 0 for f in target_files}

        for f in target_files:
            deps = graph.file_dependency_graph.get(f, set())
            for d in deps:
                if d in target_files and d != f:
                    # d must be executed before f
                    adj[d].add(f)
                    in_degree[f] = in_degree.get(f, 0) + 1

        # Kahn's topological sort
        queue = deque([f for f in target_files if in_degree[f] == 0])
        ordered: List[str] = []

        while queue:
            node = queue.popleft()
            ordered.append(node)
            for neighbor in sorted(list(adj.get(node, set()))):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If cycles exist or remaining nodes, append them sorted
        remaining = [f for f in target_files if f not in ordered]
        ordered.extend(sorted(remaining))

        # Categorize by architectural layer if available
        def layer_priority(f_path: str) -> int:
            fn = f_path.lower()
            if any(k in fn for k in ["model", "schema", "entity", "db", "sql"]):
                return 1
            elif any(k in fn for k in ["repo", "repository", "dao"]):
                return 2
            elif any(k in fn for k in ["service", "manager", "engine", "core", "agent"]):
                return 3
            elif any(k in fn for k in ["controller", "api", "route", "endpoint", "cli", "main"]):
                return 4
            elif any(k in fn for k in ["test", "spec", "mock"]):
                return 5
            return 6

        # Secondary stable sort by layer priority
        ordered.sort(key=layer_priority)

        # Deletions happen last in execution order
        for fc in file_changes:
            if fc.change_type == "DELETE" and fc.file_path not in ordered:
                ordered.append(fc.file_path)

        rollback_order = list(reversed(ordered))
        return ordered, rollback_order

    def validate_plan(
        self,
        file_changes: List[FileChange],
        symbol_changes: List[SymbolChange],
        breaking_changes: List[BreakingChange],
        graph: SymbolGraph,
        overview: Optional[RepositoryOverview] = None,
    ) -> List[ValidationRule]:
        """
        Validates the change plan for architectural integrity, layer violations, and dependency safety.
        """
        rules: List[ValidationRule] = []

        # Rule 1: Acyclic Change Dependencies
        change_files = {fc.file_path for fc in file_changes}
        cycles = graph.detect_cycles() if hasattr(graph, "detect_cycles") else []
        active_cycles = [c for c in cycles if any(f in change_files for f in c)]
        if active_cycles:
            rules.append(ValidationRule(
                rule_name="Acyclic Modification Flow",
                passed=False,
                severity="WARNING",
                description=f"Circular dependency involves modified files: {' -> '.join(active_cycles[0])}.",
                recommendation="Break cycle using dependency inversion, interfaces, or mediator patterns.",
            ))
        else:
            rules.append(ValidationRule(
                rule_name="Acyclic Modification Flow",
                passed=True,
                severity="INFO",
                description="Change execution order is completely acyclic and safely serializable.",
            ))

        # Rule 2: Architecture Layer Consistency
        has_layer_violation = False
        for fc in file_changes:
            fn = fc.file_path.lower()
            if "model" in fn or "entity" in fn:
                # Domain/Model should not import Controller/UI
                deps = graph.file_dependency_graph.get(fc.file_path, set())
                for d in deps:
                    dn = d.lower()
                    if "controller" in dn or "api" in dn or "views" in dn:
                        has_layer_violation = True
                        rules.append(ValidationRule(
                            rule_name="Layer Hierarchy Integrity",
                            passed=False,
                            severity="ERROR",
                            description=f"Layer violation: Data/Model file '{fc.file_path}' depends on presentation layer '{d}'.",
                            recommendation="Remove upward dependency; presentation layer should depend on domain models, not vice versa.",
                        ))
                        break

        if not has_layer_violation:
            rules.append(ValidationRule(
                rule_name="Layer Hierarchy Integrity",
                passed=True,
                severity="INFO",
                description="All planned modifications strictly preserve layered architectural boundaries.",
            ))

        # Rule 3: Public API Safety
        critical_breaking = [b for b in breaking_changes if b.impact_level == "CRITICAL"]
        if critical_breaking:
            rules.append(ValidationRule(
                rule_name="Public API Safety",
                passed=False,
                severity="WARNING",
                description=f"Plan contains {len(critical_breaking)} critical breaking API change(s).",
                recommendation="Apply recommended mitigations and provide backward-compatible shims.",
            ))
        else:
            rules.append(ValidationRule(
                rule_name="Public API Safety",
                passed=True,
                severity="INFO",
                description="No unmitigated critical breaking API changes detected.",
            ))

        # Rule 4: Test Coverage Validation
        has_tests = any("test" in fc.file_path.lower() for fc in file_changes)
        if not has_tests and len(file_changes) > 1:
            rules.append(ValidationRule(
                rule_name="Test Suite Verification",
                passed=False,
                severity="WARNING",
                description="Plan modifies functional code but does not include test updates.",
                recommendation="Add unit or integration tests to validate modified functionality.",
            ))
        else:
            rules.append(ValidationRule(
                rule_name="Test Suite Verification",
                passed=True,
                severity="INFO",
                description="Plan includes dedicated test files for continuous validation.",
            ))

        return rules

    # -------------------------------------------------------------------------
    # JSON Export & Import
    # -------------------------------------------------------------------------

    def export(
        self,
        plan: ChangePlan,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Exports ChangePlan as formatted JSON to memory/change_plan.json.
        """
        dest = Path(output_path).resolve() if output_path else self.output_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest.with_suffix(".tmp")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(plan.to_dict(), f, indent=2)

        shutil.move(str(tmp_path), str(dest))
        logger.info("Saved change plan to '%s'.", dest)
        return dest

    # Backward compatibility alias
    save_plan = export

    def load_plan(self, input_path: Optional[Union[str, Path]] = None) -> ChangePlan:
        """
        Loads ChangePlan from a persisted JSON file.
        """
        src = Path(input_path).resolve() if input_path else self.output_path
        if not src.is_file():
            raise FileNotFoundError(f"Change plan not found at '{src}'.")

        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ChangePlan.from_dict(data)

    # -------------------------------------------------------------------------
    # Statistics API
    # -------------------------------------------------------------------------

    def statistics(self, plan: ChangePlan) -> Dict[str, Any]:
        """
        Calculates metric telemetry and aggregated breakdown for a ChangePlan.
        """
        return {
            "task_id": plan.task_id,
            "change_classification": plan.change_classification,
            "total_files_modified": len(plan.files_to_modify),
            "total_files_created": len(plan.files_to_create),
            "total_files_deleted": len(plan.files_to_delete),
            "total_files_avoided": len(plan.files_to_avoid),
            "total_symbol_changes": len(plan.symbol_changes),
            "total_refactoring_steps": len(plan.refactoring_steps),
            "total_breaking_changes": len(plan.breaking_changes),
            "total_migration_steps": len(plan.migration_steps),
            "estimated_total_lines": plan.estimated_total_lines,
            "risk_level": plan.risk_level,
            "validation_passed": all(v.passed for v in plan.validation_rules),
        }

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _classify_change(self, title: str, desc: str, files: List[str]) -> str:
        text = f"{title} {desc} {' '.join(files)}".lower()

        if any(k in text for k in ["security", "vulnerability", "cve", "sanitize", "xss", "csrf", "sqli", "injection"]):
            return ChangeClassification.SECURITY_PATCH
        elif any(k in text for k in ["fix", "bug", "issue", "defect", "patch", "error", "crash", "fault"]):
            return ChangeClassification.BUG_FIX
        elif any(k in text for k in ["refactor", "cleanup", "extract", "restructure", "simplify", "split", "merge"]):
            return ChangeClassification.REFACTOR
        elif any(k in text for k in ["optimize", "performance", "perf", "speed", "cache", "latency", "memory"]):
            return ChangeClassification.OPTIMIZATION
        elif any(k in text for k in ["doc", "readme", "comment", "documentation", "guide"]):
            return ChangeClassification.DOCUMENTATION
        elif any(k in text for k in ["config", "settings", "env", ".env", "yaml", "toml", "ini"]):
            return ChangeClassification.CONFIGURATION
        elif any(k in text for k in ["test", "coverage", "pytest", "mock", "assert", "unit test"]):
            return ChangeClassification.TEST
        elif any(k in text for k in ["docker", "dockerfile", "makefile", "build", "pipeline", "ci", "cd"]):
            return ChangeClassification.BUILD
        elif any(k in text for k in ["infra", "infrastructure", "deploy", "serverless", "kubernetes", "k8s"]):
            return ChangeClassification.INFRASTRUCTURE

        return ChangeClassification.FEATURE

    def _compute_symbol_changes(
        self,
        title: str,
        desc: str,
        file_changes: List[FileChange],
        graph: SymbolGraph,
    ) -> List[SymbolChange]:
        text = f"{title} {desc}".lower()
        changes: List[SymbolChange] = []
        seen_symbols: Set[str] = set()

        for fc in file_changes:
            symbols_in_file = [s for s in graph.symbols.values() if s.file == fc.file_path or s.file.replace("\\", "/") == fc.file_path]
            for s in symbols_in_file:
                if s.name in seen_symbols:
                    continue

                is_mentioned = s.name.lower() in text or s.qualified_name.lower() in text
                if is_mentioned or fc.necessity_rank == NecessityRank.PRIMARY_TARGET:
                    change_type = "MODIFY"
                    if "rename" in text:
                        change_type = "RENAME"
                    elif "delete" in text or "remove" in text:
                        change_type = "DELETE"
                    elif "signature" in text or "param" in text:
                        change_type = "SIGNATURE_CHANGE"

                    callers = graph.find_callers(s.name) if hasattr(graph, "find_callers") else list(graph.reverse_call_graph.get(s.name, []))
                    is_breaking = (len(callers) > 0 and change_type in ("DELETE", "RENAME", "SIGNATURE_CHANGE"))

                    changes.append(SymbolChange(
                        symbol_name=s.name,
                        file_path=fc.file_path,
                        change_type=change_type,
                        old_signature=s.signature or f"{s.name}()",
                        new_signature=s.signature or f"{s.name}()",
                        reason=f"Modified symbol '{s.name}' to fulfill task specification.",
                        is_breaking=is_breaking,
                        callers_affected=callers,
                    ))
                    seen_symbols.add(s.name)

        return changes

    def _detect_refactoring_steps(
        self,
        title: str,
        desc: str,
        file_changes: List[FileChange],
        symbol_changes: List[SymbolChange],
        graph: SymbolGraph,
        overview: Optional[RepositoryOverview],
    ) -> List[RefactoringStep]:
        text = f"{title} {desc}".lower()
        steps: List[RefactoringStep] = []

        # 1. Rename
        if "rename" in text:
            target_name = next((sc.symbol_name for sc in symbol_changes), "Symbol")
            target_file = next((fc.file_path for fc in file_changes), "module.py")
            steps.append(RefactoringStep(
                refactoring_type=RefactoringType.RENAME,
                target=target_name,
                target_file=target_file,
                description=f"Rename symbol '{target_name}' across file and call sites.",
                rationale="Improves naming consistency and clarity per requirements.",
            ))

        # 2. Extract Method / Class
        if "extract method" in text or "extract function" in text:
            target_file = next((fc.file_path for fc in file_changes), "module.py")
            steps.append(RefactoringStep(
                refactoring_type=RefactoringType.EXTRACT_METHOD,
                target="Extracted Helper Method",
                target_file=target_file,
                description="Extract cohesive logic block into an isolated helper method.",
                rationale="Reduces cyclomatic complexity and enhances testability.",
            ))
        elif "extract class" in text or "extract service" in text:
            target_file = next((fc.file_path for fc in file_changes), "service.py")
            steps.append(RefactoringStep(
                refactoring_type=RefactoringType.EXTRACT_CLASS,
                target="Extracted Service / Entity Class",
                target_file=target_file,
                description="Extract distinct responsibility cluster into a dedicated class.",
                rationale="Enforces Single Responsibility Principle (SRP).",
            ))

        # 3. Repository / Service Extraction
        if any(k in text for k in ["repo", "repository", "dao"]) and any(fc.change_type == "CREATE" for fc in file_changes):
            target_file = next((fc.file_path for fc in file_changes if "repo" in fc.file_path), "repositories/repository.py")
            steps.append(RefactoringStep(
                refactoring_type=RefactoringType.REPOSITORY_EXTRACTION,
                target="Data Persistence Layer",
                target_file=target_file,
                description=f"Isolate data access queries into dedicated repository '{target_file}'.",
                rationale="Decouples business logic from storage mechanics.",
            ))

        if any(k in text for k in ["service", "usecase"]) and any(fc.change_type == "CREATE" for fc in file_changes):
            target_file = next((fc.file_path for fc in file_changes if "service" in fc.file_path), "services/service.py")
            steps.append(RefactoringStep(
                refactoring_type=RefactoringType.SERVICE_EXTRACTION,
                target="Domain Service Layer",
                target_file=target_file,
                description=f"Extract orchestration workflows into dedicated service '{target_file}'.",
                rationale="Encapsulates core domain business transactions.",
            ))

        # 4. Dependency Injection
        if any(k in text for k in ["dependency injection", "inject", "ioc", "provider"]):
            target_file = next((fc.file_path for fc in file_changes), "container.py")
            steps.append(RefactoringStep(
                refactoring_type=RefactoringType.DEPENDENCY_INJECTION,
                target="Constructor Inversion",
                target_file=target_file,
                description="Refactor hard-coded instantiations to accept dependencies via constructor.",
                rationale="Improves unit test mockability and loose coupling.",
            ))

        return steps

    def _compute_migrations(
        self,
        title: str,
        desc: str,
        file_changes: List[FileChange],
        breaking_changes: List[BreakingChange],
    ) -> Tuple[List[MigrationStep], List[Dict[str, Any]]]:
        text = f"{title} {desc}".lower()
        migrations: List[MigrationStep] = []
        config_updates: List[Dict[str, Any]] = []

        # Database Migrations
        if any(k in text for k in self.DATABASE_KEYWORDS) or any(b.change_category == "DATABASE_MIGRATION" for b in breaking_changes):
            target_file = next((fc.file_path for fc in file_changes if "model" in fc.file_path or "schema" in fc.file_path or "sql" in fc.file_path), "migrations/001_update_schema.sql")
            migrations.append(MigrationStep(
                migration_type="DATABASE_SCHEMA",
                target_file=target_file,
                description="Database schema migration step required for new entity structures.",
                sql_or_code_action="ALTER TABLE entities ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;",
                rollback_instruction="ALTER TABLE entities DROP COLUMN IF EXISTS updated_at;",
                is_reversible=True,
            ))

        # Configuration Updates
        if any(k in text for k in ["config", "setting", "env", "secret"]):
            config_file = next((fc.file_path for fc in file_changes if "config" in fc.file_path or "setting" in fc.file_path or ".env" in fc.file_path), "config.py")
            config_updates.append({
                "config_file": config_file,
                "key": "FEATURE_FLAGS",
                "value": "enabled",
                "reason": "Enable new feature flag configuration required for task implementation.",
            })

        return migrations, config_updates

    def _compute_auxiliary_updates(
        self,
        title: str,
        desc: str,
        file_changes: List[FileChange],
        symbol_changes: List[SymbolChange],
        graph: SymbolGraph,
        overview: Optional[RepositoryOverview],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        test_updates: List[Dict[str, Any]] = []
        dependency_updates: List[Dict[str, Any]] = []
        doc_updates: List[Dict[str, Any]] = []

        for fc in file_changes:
            if "test" in fc.file_path.lower():
                test_updates.append({
                    "test_file": fc.file_path,
                    "target_module": fc.file_path.replace("tests/test_", "").replace("test_", "").replace(".py", ".py"),
                    "action": "UPDATE" if fc.change_type == "MODIFY" else "CREATE",
                    "reason": fc.reason,
                })

        for sc in symbol_changes:
            if sc.is_breaking or sc.change_type in ("ADD", "MODIFY"):
                doc_updates.append({
                    "doc_file": "README.md",
                    "section": "Public API Documentation",
                    "target_symbol": sc.symbol_name,
                    "reason": f"Document updated signature and behavior for '{sc.symbol_name}'.",
                })

        return test_updates, dependency_updates, doc_updates

    def _compute_risk_level(
        self,
        breaking: List[BreakingChange],
        migrations: List[MigrationStep],
        file_changes: List[FileChange],
        validations: List[ValidationRule],
    ) -> str:
        if any(b.impact_level == "CRITICAL" for b in breaking) or any(v.severity == "ERROR" and not v.passed for v in validations):
            return "CRITICAL"
        elif any(b.impact_level == "HIGH" for b in breaking) or migrations or len(file_changes) >= 5:
            return "HIGH"
        elif len(file_changes) >= 3 or breaking:
            return "MEDIUM"
        return "LOW"

    def _file_exists_on_disk(self, file_path: str, context: Dict[str, Any]) -> bool:
        if "project_files" in context and file_path in context["project_files"]:
            return True
        p = Path(file_path)
        return p.is_file()

    def _estimate_loc_for_file(self, file_path: str, graph: SymbolGraph, context: Dict[str, Any]) -> int:
        if "project_files" in context and file_path in context["project_files"]:
            return min(40, max(10, len(context["project_files"][file_path].splitlines()) // 4))
        symbols = [s for s in graph.symbols.values() if s.file == file_path or s.file.replace("\\", "/") == file_path]
        return min(50, max(10, len(symbols) * 8))

    def _generate_plan_summary(
        self,
        task_id: str,
        classification: str,
        files_to_modify: List[str],
        files_to_create: List[str],
        files_to_delete: List[str],
        breaking_changes: List[BreakingChange],
        total_loc: int,
        risk_level: str,
    ) -> str:
        breaking_str = f"{len(breaking_changes)} breaking change(s)" if breaking_changes else "no breaking API changes"
        return (
            f"Task [{task_id}] classified as {classification}. Modifies {len(files_to_modify)} file(s), "
            f"creates {len(files_to_create)} file(s), deletes {len(files_to_delete)} file(s), "
            f"introduces {breaking_str}, with estimated {total_loc} lines changed (Risk: {risk_level})."
        )


if __name__ == "__main__":
    planner = ChangePlanner()
    task_mock = type("MockTask", (), {"id": "TASK-DEMO", "title": "Refactor UserService to use UserRepository", "description": "Extract DB logic", "estimated_files": ["services/user_service.py"]})()
    p = planner.plan(task_mock)
    print("===================== SEMANTIC CHANGE PLAN =====================")
    print(json.dumps(p.to_dict(), indent=2))
