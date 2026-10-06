"""
refactoring_planner.py - Refactoring Planner & Safe Code Modification Engine for AutoDev (v1.7)

Responsible for generating deterministic, multi-action refactoring execution plans (RefactoringPlan)
prior to code generation. Enables AutoDev to safely modify existing projects, detect breaking API changes,
track caller and inheritance safety rules, estimate line modifications, and ensure robust rollback preparedness.

100% deterministic, offline, and LLM-free.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.impact_analyzer import ImpactAnalyzer, ImpactReport, RiskLevel
from core.symbol_graph import Reference, Symbol, SymbolGraph, SymbolType, Visibility

logger = logging.getLogger("AutoDev.RefactoringPlanner")


# =============================================================================
# Action Types Enum
# =============================================================================

class ActionType(str, Enum):
    """Standardized refactoring and code modification action categories."""
    ADD_CLASS = "ADD_CLASS"
    ADD_METHOD = "ADD_METHOD"
    ADD_FUNCTION = "ADD_FUNCTION"
    MODIFY_FUNCTION = "MODIFY_FUNCTION"
    MODIFY_METHOD = "MODIFY_METHOD"
    MODIFY_CLASS = "MODIFY_CLASS"
    DELETE_FUNCTION = "DELETE_FUNCTION"
    DELETE_CLASS = "DELETE_CLASS"
    DELETE_FILE = "DELETE_FILE"
    CREATE_FILE = "CREATE_FILE"
    MOVE_SYMBOL = "MOVE_SYMBOL"
    RENAME_SYMBOL = "RENAME_SYMBOL"
    UPDATE_IMPORTS = "UPDATE_IMPORTS"
    ADD_TEST = "ADD_TEST"
    UPDATE_TEST = "UPDATE_TEST"
    UPDATE_DOCUMENTATION = "UPDATE_DOCUMENTATION"


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class ModificationAction:
    """
    Represents an atomic code modification or refactoring action to be performed.
    """
    action_type: Union[ActionType, str]
    target_symbol: str
    target_file: str
    reason: str
    priority: str = "HIGH"
    estimated_lines_changed: int = 15
    breaking_change: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.action_type, ActionType):
            self.action_type = self.action_type.value
        if isinstance(self.priority, str):
            self.priority = self.priority.upper()

    def to_dict(self) -> Dict[str, Any]:
        """Converts modification action to serializable dictionary."""
        return {
            "action_type": str(self.action_type),
            "target_symbol": self.target_symbol,
            "target_file": self.target_file,
            "reason": self.reason,
            "priority": self.priority,
            "estimated_lines_changed": self.estimated_lines_changed,
            "breaking_change": self.breaking_change,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModificationAction:
        """Instantiates modification action from dictionary."""
        return cls(
            action_type=data.get("action_type", ActionType.MODIFY_FUNCTION.value),
            target_symbol=data.get("target_symbol", ""),
            target_file=data.get("target_file", ""),
            reason=data.get("reason", ""),
            priority=data.get("priority", "HIGH"),
            estimated_lines_changed=int(data.get("estimated_lines_changed", 15)),
            breaking_change=bool(data.get("breaking_change", False)),
            notes=data.get("notes", ""),
        )


@dataclass
class RefactoringPlan:
    """
    Comprehensive, deterministic execution plan for safely refactoring or modifying code.
    """
    actions: List[ModificationAction] = field(default_factory=list)
    files_to_modify: List[str] = field(default_factory=list)
    files_to_create: List[str] = field(default_factory=list)
    files_to_delete: List[str] = field(default_factory=list)
    estimated_total_lines: int = 0
    breaking_changes: List[str] = field(default_factory=list)
    rollback_required: bool = False
    migration_required: bool = False
    risk_level: str = "LOW"
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts refactoring plan to serializable dictionary."""
        return {
            "actions": [a.to_dict() for a in self.actions],
            "files_to_modify": list(self.files_to_modify),
            "files_to_create": list(self.files_to_create),
            "files_to_delete": list(self.files_to_delete),
            "estimated_total_lines": self.estimated_total_lines,
            "breaking_changes": list(self.breaking_changes),
            "rollback_required": self.rollback_required,
            "migration_required": self.migration_required,
            "risk_level": self.risk_level,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RefactoringPlan:
        """Instantiates refactoring plan from dictionary."""
        raw_actions = data.get("actions", [])
        actions = [
            a if isinstance(a, ModificationAction) else ModificationAction.from_dict(a)
            for a in raw_actions
        ]
        return cls(
            actions=actions,
            files_to_modify=list(data.get("files_to_modify", [])),
            files_to_create=list(data.get("files_to_create", [])),
            files_to_delete=list(data.get("files_to_delete", [])),
            estimated_total_lines=int(data.get("estimated_total_lines", 0)),
            breaking_changes=list(data.get("breaking_changes", [])),
            rollback_required=bool(data.get("rollback_required", False)),
            migration_required=bool(data.get("migration_required", False)),
            risk_level=str(data.get("risk_level", "LOW")),
            summary=str(data.get("summary", "")),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serializes refactoring plan to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> RefactoringPlan:
        """Deserializes refactoring plan from JSON."""
        return cls.from_dict(json.loads(json_str))


# =============================================================================
# Refactoring Planner Subsystem
# =============================================================================

class RefactoringPlanner:
    """
    Deterministic Refactoring Planner and Safe Code Modification Engine.
    Analyzes existing codebase structures, predicts necessary modification actions,
    evaluates breaking API changes, and computes safety telemetry without LLM calls.
    """

    def __init__(
        self,
        symbol_graph: Optional[SymbolGraph] = None,
        impact_analyzer: Optional[ImpactAnalyzer] = None,
        project_root: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Initializes the RefactoringPlanner.

        Args:
            symbol_graph: Optional SymbolGraph containing project symbol metadata.
            impact_analyzer: Optional ImpactAnalyzer instance for blast radius estimation.
            project_root: Workspace root directory.
        """
        self.symbol_graph = symbol_graph
        self.impact_analyzer = impact_analyzer
        self.project_root = Path(project_root).resolve() if project_root else None

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def plan(
        self,
        task: Union[Task, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> RefactoringPlan:
        """
        Generates a comprehensive RefactoringPlan for the specified task.

        Args:
            task: Task object or task dictionary.
            context: Optional context dictionary containing project files and symbol graph.

        Returns:
            Deterministic RefactoringPlan instance.
        """
        ctx = context or {}

        # 1. Resolve SymbolGraph and ImpactReport
        graph = ctx.get("symbol_graph") or self.symbol_graph
        report: Optional[ImpactReport] = ctx.get("impact_report")
        if report is None:
            if self.impact_analyzer is not None:
                report = self.impact_analyzer.analyze(task, ctx)
            elif graph is not None:
                analyzer = ImpactAnalyzer(symbol_graph=graph)
                report = analyzer.analyze(task, ctx)

        # 2. Extract Task Attributes
        task_id = getattr(task, "id", None) or (task.get("id", "TASK") if isinstance(task, dict) else "TASK")
        task_title = getattr(task, "title", None) or (task.get("title", "") if isinstance(task, dict) else str(task))
        task_desc = getattr(task, "description", None) or (task.get("description", "") if isinstance(task, dict) else "")
        task_files = getattr(task, "estimated_files", None) or (task.get("estimated_files", []) if isinstance(task, dict) else [])

        logger.info("Generating Refactoring Plan for Task [%s]: '%s'...", task_id, task_title)

        # 3. Analyze Existing Code & Generate Modification Actions
        actions = self.analyze_existing_code(task=task, context=ctx)

        # 4. Determine Test Updates & Add to Actions
        test_actions = self.determine_test_updates(actions=actions, report=report, context=ctx)
        actions.extend(test_actions)

        # 5. Detect Breaking Changes & Safety Invariants
        breaking_changes, rollback_required, migration_required = self.detect_breaking_changes(
            actions=actions,
            graph=graph,
            report=report,
            task_desc=f"{task_title} {task_desc}",
        )

        # 6. Categorize Files
        files_to_modify: Set[str] = set()
        files_to_create: Set[str] = set()
        files_to_delete: Set[str] = set()

        for act in actions:
            if act.action_type == ActionType.CREATE_FILE.value:
                files_to_create.add(act.target_file)
            elif act.action_type == ActionType.DELETE_FILE.value:
                files_to_delete.add(act.target_file)
            elif act.action_type in {
                ActionType.MODIFY_FUNCTION.value,
                ActionType.MODIFY_METHOD.value,
                ActionType.MODIFY_CLASS.value,
                ActionType.ADD_METHOD.value,
                ActionType.ADD_FUNCTION.value,
                ActionType.ADD_CLASS.value,
                ActionType.DELETE_FUNCTION.value,
                ActionType.DELETE_CLASS.value,
                ActionType.MOVE_SYMBOL.value,
                ActionType.RENAME_SYMBOL.value,
                ActionType.UPDATE_IMPORTS.value,
                ActionType.UPDATE_TEST.value,
                ActionType.UPDATE_DOCUMENTATION.value,
            }:
                if act.target_file not in files_to_create:
                    files_to_modify.add(act.target_file)
            elif act.action_type == ActionType.ADD_TEST.value:
                # Check if test file exists in project
                if self._file_exists(act.target_file, ctx):
                    files_to_modify.add(act.target_file)
                else:
                    files_to_create.add(act.target_file)

        # Ensure mutually exclusive file partitions
        files_to_modify = files_to_modify - files_to_create - files_to_delete
        sorted_modify = sorted(files_to_modify)
        sorted_create = sorted(files_to_create)
        sorted_delete = sorted(files_to_delete)

        # 7. Compute Total Line Changes
        total_lines = sum(a.estimated_lines_changed for a in actions)

        # 8. Compute Risk Level
        risk_level = self._compute_risk_level(
            breaking_changes=breaking_changes,
            rollback_required=rollback_required,
            migration_required=migration_required,
            files_to_modify=sorted_modify,
            report=report,
            actions=actions,
        )

        # 9. Generate Deterministic Summary
        summary = self.generate_summary(
            actions=actions,
            files_to_modify=sorted_modify,
            files_to_create=sorted_create,
            files_to_delete=sorted_delete,
            breaking_changes=breaking_changes,
            total_lines=total_lines,
        )

        return RefactoringPlan(
            actions=actions,
            files_to_modify=sorted_modify,
            files_to_create=sorted_create,
            files_to_delete=sorted_delete,
            estimated_total_lines=total_lines,
            breaking_changes=breaking_changes,
            rollback_required=rollback_required,
            migration_required=migration_required,
            risk_level=risk_level,
            summary=summary,
        )

    def analyze_existing_code(
        self,
        task: Union[Task, Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[ModificationAction]:
        """
        Analyzes task intent, target files, and symbol graph to synthesize specific ModificationActions.

        Args:
            task: Task object or dict.
            context: Context dictionary containing project files and symbol graph.

        Returns:
            List of concrete ModificationAction instances.
        """
        actions: List[ModificationAction] = []
        graph: Optional[SymbolGraph] = context.get("symbol_graph") or self.symbol_graph
        project_files: Dict[str, Any] = context.get("project_files", {})

        task_title = getattr(task, "title", None) or (task.get("title", "") if isinstance(task, dict) else str(task))
        task_desc = getattr(task, "description", None) or (task.get("description", "") if isinstance(task, dict) else "")
        task_files = getattr(task, "estimated_files", None) or (task.get("estimated_files", []) if isinstance(task, dict) else [])
        full_task_text = f"{task_title} {task_desc}".lower()

        # Keywords inspection
        is_delete = any(k in full_task_text for k in ["delete", "remove", "deprecate", "drop", "purge"])
        is_rename = any(k in full_task_text for k in ["rename", "move symbol", "relocate symbol"])
        is_add_class = any(k in full_task_text for k in ["add class", "new class", "create class", "implement class"])
        is_add_method = any(k in full_task_text for k in ["add method", "new method", "create method"])
        is_add_func = any(k in full_task_text for k in ["add function", "new function", "create function", "helper function"])
        is_doc = any(k in full_task_text for k in ["readme", "documentation", "docstring", "api doc", "user guide"])

        processed_symbols: Set[str] = set()

        # 1. Process explicit target files
        for file_path in task_files:
            clean_file = file_path.replace("\\", "/").strip()
            if not clean_file:
                continue

            file_exists = self._file_exists(clean_file, context)

            if not file_exists:
                # File needs to be created
                action_type = ActionType.CREATE_FILE
                lines = self.estimate_line_changes(action_type, task_desc=full_task_text)
                actions.append(
                    ModificationAction(
                        action_type=action_type.value,
                        target_symbol=clean_file,
                        target_file=clean_file,
                        reason=f"Create new source file '{clean_file}' for task execution.",
                        priority="HIGH",
                        estimated_lines_changed=lines,
                        breaking_change=False,
                    )
                )
            else:
                # File exists -> identify affected symbols within the file
                file_symbols = self._get_symbols_in_file(graph, clean_file)

                matching_symbols: List[Symbol] = []
                for sym in file_symbols:
                    if sym.name.lower() in full_task_text:
                        matching_symbols.append(sym)

                if matching_symbols:
                    for sym in matching_symbols:
                        processed_symbols.add(sym.name)
                        act_type = self._resolve_symbol_action_type(
                            sym=sym,
                            is_delete=is_delete,
                            is_rename=is_rename,
                        )
                        lines = self.estimate_line_changes(act_type, target_symbol=sym, task_desc=full_task_text)
                        actions.append(
                            ModificationAction(
                                action_type=act_type.value,
                                target_symbol=sym.name,
                                target_file=clean_file,
                                reason=f"Targeted modification for symbol '{sym.name}' based on task requirements.",
                                priority="HIGH",
                                estimated_lines_changed=lines,
                                breaking_change=False,
                            )
                        )
                else:
                    # Fallback action on existing file
                    if is_delete and "file" in full_task_text:
                        act_type = ActionType.DELETE_FILE
                    elif is_add_class:
                        act_type = ActionType.ADD_CLASS
                    elif is_add_method:
                        act_type = ActionType.ADD_METHOD
                    elif is_add_func:
                        act_type = ActionType.ADD_FUNCTION
                    else:
                        act_type = ActionType.MODIFY_FUNCTION

                    lines = self.estimate_line_changes(act_type, task_desc=full_task_text)
                    actions.append(
                        ModificationAction(
                            action_type=act_type.value,
                            target_symbol=Path(clean_file).stem,
                            target_file=clean_file,
                            reason=f"Apply modifications to existing file '{clean_file}'.",
                            priority="HIGH",
                            estimated_lines_changed=lines,
                            breaking_change=False,
                        )
                    )

        # 2. Check for symbols referenced directly in task text if not already processed
        if graph:
            for sym_id, sym in graph.symbols.items():
                if (sym.name.lower() in full_task_text or sym.qualified_name.lower() in full_task_text) and sym.name not in processed_symbols:
                    processed_symbols.add(sym.name)
                    act_type = self._resolve_symbol_action_type(
                        sym=sym,
                        is_delete=is_delete,
                        is_rename=is_rename,
                    )
                    lines = self.estimate_line_changes(act_type, target_symbol=sym, task_desc=full_task_text)
                    actions.append(
                        ModificationAction(
                            action_type=act_type.value,
                            target_symbol=sym.name,
                            target_file=sym.file,
                            reason=f"Direct symbol match '{sym.name}' identified in task specification.",
                            priority="HIGH",
                            estimated_lines_changed=lines,
                            breaking_change=False,
                        )
                    )

        # 3. Check for import and documentation updates

        if is_rename or any(a.action_type in {ActionType.MOVE_SYMBOL.value, ActionType.RENAME_SYMBOL.value} for a in actions):
            actions.append(
                ModificationAction(
                    action_type=ActionType.UPDATE_IMPORTS.value,
                    target_symbol="imports",
                    target_file=actions[0].target_file if actions else "core/__init__.py",
                    reason="Update inter-module import references for renamed or moved symbols.",
                    priority="MEDIUM",
                    estimated_lines_changed=5,
                    breaking_change=False,
                )
            )

        if is_doc:
            doc_file = "README.md" if "README.md" in project_files or self._file_exists("README.md", context) else (task_files[0] if task_files else "README.md")
            actions.append(
                ModificationAction(
                    action_type=ActionType.UPDATE_DOCUMENTATION.value,
                    target_symbol="documentation",
                    target_file=doc_file,
                    reason="Update system documentation and usage guides.",
                    priority="LOW",
                    estimated_lines_changed=20,
                    breaking_change=False,
                )
            )

        # Fallback if no actions could be identified
        if not actions:
            target_f = task_files[0] if task_files else "src/main.py"
            if not self._file_exists(target_f, context):
                act_type = ActionType.CREATE_FILE
            else:
                act_type = ActionType.MODIFY_FUNCTION
            actions.append(
                ModificationAction(
                    action_type=act_type.value,
                    target_symbol=task_title or "main",
                    target_file=target_f,
                    reason=f"Execute task '{task_title}'.",
                    priority="HIGH",
                    estimated_lines_changed=15,
                    breaking_change=False,
                )
            )

        return actions


    def detect_breaking_changes(
        self,
        actions: List[ModificationAction],
        graph: Optional[SymbolGraph] = None,
        report: Optional[ImpactReport] = None,
        task_desc: str = "",
    ) -> Tuple[List[str], bool, bool]:
        """
        Detects potential breaking API changes, parameter modifications, and inheritance risks.

        Returns:
            Tuple of (breaking_changes_list, rollback_required, migration_required).
        """
        breaking_changes: List[str] = []
        rollback_required = False
        migration_required = False
        task_text = task_desc.lower()

        # 1. Database schema change detection
        schema_keywords = ["migration", "schema", "table", "column", "drop column", "alter table", "database migration"]
        if any(k in task_text for k in schema_keywords):
            migration_required = True
            breaking_changes.append("Database schema modification detected; database migration required.")

        # 2. Public API removal and signature change keywords
        sig_keywords = ["signature change", "parameter removal", "remove parameter", "change constructor", "modify interface"]
        if any(k in task_text for k in sig_keywords):
            breaking_changes.append(f"Interface / signature modification detected in task scope: '{task_desc[:60]}'.")
            rollback_required = True

        # 3. Analyze individual actions with SymbolGraph safety invariants
        for act in actions:
            sym_name = act.target_symbol
            sym: Optional[Symbol] = self._get_symbol(graph, sym_name)

            # A. Symbol Deletion
            if act.action_type in {ActionType.DELETE_FUNCTION.value, ActionType.DELETE_CLASS.value, ActionType.DELETE_FILE.value}:
                callers = self._get_callers(graph, sym_name)
                subclasses = self._get_subclasses(graph, sym_name)

                is_public = sym.visibility == Visibility.PUBLIC if sym else not sym_name.startswith("_")

                if is_public or callers or subclasses:
                    act.breaking_change = True
                    rollback_required = True
                    caller_count = len(callers)
                    subclass_count = len(subclasses)
                    msg = f"Deletion of public symbol '{sym_name}' in '{act.target_file}' (Callers: {caller_count}, Subclasses: {subclass_count})."
                    breaking_changes.append(msg)

            # B. Symbol Rename
            elif act.action_type == ActionType.RENAME_SYMBOL.value:
                callers = self._get_callers(graph, sym_name)
                is_public = sym.visibility == Visibility.PUBLIC if sym else not sym_name.startswith("_")
                if is_public or callers:
                    act.breaking_change = True
                    breaking_changes.append(f"Renaming exported symbol '{sym_name}' impacts external callers.")

            # C. Base Class / Interface Modification
            elif act.action_type in {ActionType.MODIFY_CLASS.value, ActionType.MODIFY_METHOD.value}:
                if graph and sym:
                    subclasses = self._get_subclasses(graph, sym_name)
                    if subclasses:
                        act.breaking_change = True
                        subclass_names = [getattr(s, "name", str(s)) for s in subclasses]
                        breaking_changes.append(f"Modifying base class / method '{sym_name}' affects derived classes: {subclass_names}.")

            # D. Filtered impact report breaking change risks
            if report and report.breaking_change_risks:
                action_targets = {a.target_symbol.lower() for a in actions} | {Path(a.target_file).stem.lower() for a in actions}
                for r in report.breaking_change_risks:
                    r_lower = r.lower()
                    if "low risk" in r_lower or "no breaking" in r_lower or "isolated" in r_lower:
                        continue
                    if any(t in r_lower for t in action_targets if len(t) > 3):
                        if r not in breaking_changes:
                            breaking_changes.append(r)
                if report.risk_level in {RiskLevel.CRITICAL, "CRITICAL"} and breaking_changes:
                    rollback_required = True

        return breaking_changes, rollback_required, migration_required



    def estimate_line_changes(
        self,
        action_type: Union[ActionType, str],
        target_symbol: Optional[Symbol] = None,
        task_desc: str = "",
    ) -> int:
        """
        Estimates the lines of code (LOC) modified or added for a given action type.

        Ranges:
        - new function: 10-25 lines (default: 18)
        - method update: 5-20 lines (default: 12)
        - class update: 20-100 lines (default: 40)
        - file creation: 30-250 lines (default: 80)
        - test update: 5-50 lines (default: 25)
        """
        act_val = action_type.value if isinstance(action_type, ActionType) else str(action_type)

        if act_val == ActionType.ADD_FUNCTION.value:
            return 18
        elif act_val == ActionType.MODIFY_FUNCTION.value:
            return 12
        elif act_val == ActionType.ADD_METHOD.value:
            return 14
        elif act_val == ActionType.MODIFY_METHOD.value:
            return 10
        elif act_val == ActionType.ADD_CLASS.value:
            return 55
        elif act_val == ActionType.MODIFY_CLASS.value:
            if target_symbol and target_symbol.line and target_symbol.end_line:
                span = target_symbol.end_line - target_symbol.line + 1
                return min(max(span // 2, 20), 100)
            return 40
        elif act_val == ActionType.CREATE_FILE.value:
            return 80
        elif act_val == ActionType.DELETE_FILE.value:
            return 0
        elif act_val in {ActionType.DELETE_FUNCTION.value, ActionType.DELETE_CLASS.value}:
            if target_symbol and target_symbol.line and target_symbol.end_line:
                return target_symbol.end_line - target_symbol.line + 1
            return 15
        elif act_val in {ActionType.MOVE_SYMBOL.value, ActionType.RENAME_SYMBOL.value}:
            return 15
        elif act_val == ActionType.UPDATE_IMPORTS.value:
            return 5
        elif act_val in {ActionType.ADD_TEST.value, ActionType.UPDATE_TEST.value}:
            return 25
        elif act_val == ActionType.UPDATE_DOCUMENTATION.value:
            return 20
        return 15

    def determine_test_updates(
        self,
        actions: List[ModificationAction],
        report: Optional[ImpactReport] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ModificationAction]:
        """
        Determines automated test updates or additions corresponding to modified code files.
        """
        test_actions: List[ModificationAction] = []
        ctx = context or {}
        seen_test_files: Set[str] = set()

        # 1. Inspect ImpactReport affected tests
        if report and report.affected_tests:
            for test_file in report.affected_tests:
                if test_file not in seen_test_files:
                    seen_test_files.add(test_file)
                    test_actions.append(
                        ModificationAction(
                            action_type=ActionType.UPDATE_TEST.value,
                            target_symbol=Path(test_file).stem,
                            target_file=test_file,
                            reason=f"Update affected regression test suite '{test_file}'.",
                            priority="MEDIUM",
                            estimated_lines_changed=self.estimate_line_changes(ActionType.UPDATE_TEST),
                            breaking_change=False,
                        )
                    )

        # 2. For modified source files, verify if corresponding test exists
        for act in actions:
            src_file = act.target_file
            if src_file.startswith("tests/") or "test_" in src_file:
                continue

            stem = Path(src_file).stem
            candidate_test = f"tests/test_{stem}.py"

            if candidate_test not in seen_test_files:
                seen_test_files.add(candidate_test)
                if self._file_exists(candidate_test, ctx):
                    test_actions.append(
                        ModificationAction(
                            action_type=ActionType.UPDATE_TEST.value,
                            target_symbol=f"test_{stem}",
                            target_file=candidate_test,
                            reason=f"Update existing test suite '{candidate_test}' for modified '{src_file}'.",
                            priority="MEDIUM",
                            estimated_lines_changed=self.estimate_line_changes(ActionType.UPDATE_TEST),
                            breaking_change=False,
                        )
                    )
                else:
                    test_actions.append(
                        ModificationAction(
                            action_type=ActionType.ADD_TEST.value,
                            target_symbol=f"test_{stem}",
                            target_file=candidate_test,
                            reason=f"Create new automated unit test file '{candidate_test}' for '{src_file}'.",
                            priority="MEDIUM",
                            estimated_lines_changed=self.estimate_line_changes(ActionType.ADD_TEST),
                            breaking_change=False,
                        )
                    )

        return test_actions

    def generate_summary(
        self,
        actions: List[ModificationAction],
        files_to_modify: List[str],
        files_to_create: List[str],
        files_to_delete: List[str],
        breaking_changes: List[str],
        total_lines: int,
    ) -> str:
        """
        Generates a human-readable deterministic summary of the refactoring plan.
        """
        mod_count = len(files_to_modify)
        create_count = len(files_to_create)
        del_count = len(files_to_delete)
        test_count = sum(
            1 for a in actions
            if a.action_type in {ActionType.ADD_TEST.value, ActionType.UPDATE_TEST.value}
        )

        if not breaking_changes:
            breaking_str = "introduces no breaking API changes"
        elif len(breaking_changes) == 1:
            breaking_str = "introduces 1 potential breaking API change"
        else:
            breaking_str = f"introduces {len(breaking_changes)} potential breaking API changes"

        del_clause = f", deletes {del_count} files" if del_count > 0 else ""

        return (
            f"This task modifies {mod_count} existing files, "
            f"creates {create_count} new files"
            f"{del_clause}, "
            f"updates {test_count} unit tests, "
            f"{breaking_str}, "
            f"estimated {total_lines} lines changed."
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _file_exists(self, file_path: str, context: Dict[str, Any]) -> bool:
        """Checks if a file exists in the workspace context or on disk."""
        project_files = context.get("project_files", {})
        norm_path = file_path.replace("\\", "/").strip()

        if norm_path in project_files:
            return True

        if "project_files" in context and not project_files:
            return False

        if self.project_root:
            target = (self.project_root / norm_path).resolve()
            return target.is_file()

        return False


    def _resolve_symbol_action_type(
        self,
        sym: Symbol,
        is_delete: bool,
        is_rename: bool,
    ) -> ActionType:
        """Determines the appropriate ActionType for a Symbol."""
        if is_delete:
            if sym.symbol_type == SymbolType.CLASS:
                return ActionType.DELETE_CLASS
            return ActionType.DELETE_FUNCTION

        if is_rename:
            return ActionType.RENAME_SYMBOL

        if sym.symbol_type == SymbolType.CLASS:
            return ActionType.MODIFY_CLASS
        elif sym.symbol_type in {SymbolType.METHOD, SymbolType.CONSTRUCTOR}:
            return ActionType.MODIFY_METHOD
        return ActionType.MODIFY_FUNCTION

    def _compute_risk_level(
        self,
        breaking_changes: List[str],
        rollback_required: bool,
        migration_required: bool,
        files_to_modify: List[str],
        report: Optional[ImpactReport],
        actions: List[ModificationAction],
    ) -> str:
        """Computes deterministic overall risk level."""
        if rollback_required or migration_required or len(breaking_changes) >= 2:
            return "CRITICAL"
        if breaking_changes:
            return "HIGH"
        if len(files_to_modify) >= 3 or (report and report.risk_level in {"HIGH", "CRITICAL"} and len(files_to_modify) > 0 and report.impact_score > 50):
            return "HIGH"
        if len(files_to_modify) >= 1 or (report and report.risk_level == "MEDIUM"):
            return "MEDIUM"
        return "LOW"


    def _get_symbols_in_file(self, graph: Optional[SymbolGraph], file_path: str) -> List[Symbol]:
        """Retrieves symbols declared in the specified file."""
        if not graph:
            return []
        if hasattr(graph, "find_file"):
            return graph.find_file(file_path)
        if hasattr(graph, "get_symbols_in_file"):
            return graph.get_symbols_in_file(file_path)
        norm = file_path.replace("\\", "/").strip()
        return [s for s in graph.symbols.values() if s.file == norm]

    def _get_symbol(self, graph: Optional[SymbolGraph], name_or_id: str) -> Optional[Symbol]:
        """Finds a symbol by id, qualified name, or short name."""
        if not graph:
            return None
        if hasattr(graph, "find_symbol"):
            return graph.find_symbol(name_or_id)
        if hasattr(graph, "get_symbol"):
            return graph.get_symbol(name_or_id)
        if name_or_id in graph.symbols:
            return graph.symbols[name_or_id]
        for s in graph.symbols.values():
            if s.name == name_or_id or s.qualified_name == name_or_id:
                return s
        return None

    def _get_callers(self, graph: Optional[SymbolGraph], name_or_id: str) -> List[Any]:
        """Finds callers of a symbol."""
        if not graph:
            return []
        if hasattr(graph, "find_callers"):
            return graph.find_callers(name_or_id)
        if hasattr(graph, "get_callers"):
            return graph.get_callers(name_or_id)
        return []

    def _get_subclasses(self, graph: Optional[SymbolGraph], name_or_id: str) -> List[Any]:
        """Finds subclasses inheriting from a class."""
        if not graph:
            return []
        if hasattr(graph, "find_subclasses"):
            return graph.find_subclasses(name_or_id)
        if hasattr(graph, "get_subclasses"):
            return graph.get_subclasses(name_or_id)
        return []

