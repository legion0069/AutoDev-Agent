"""
prompt_builder.py - Engineering Prompt Synthesis Engine for AutoDev (v1.5)

Responsible for transforming project context (metadata, phases, directory tree,
existing codebase files), relevant engineering memory (ContextInjector),
code-aware symbol context (CodeContextRetriever), and blast-radius risk analysis
(ImpactAnalyzer) into a production-grade, structured engineering prompt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.change_planner import (
    BreakingChange,
    ChangeClassification,
    ChangePlan,
    ChangePlanner,
    FileChange,
    MigrationStep,
    NecessityRank,
    RefactoringStep,
    RefactoringType,
    SymbolChange,
    ValidationRule,
)
from core.code_context_retriever import (
    CodeContextResult,
    CodeContextRetriever,
    CodeSnippet,
    ContextBundle,
    RelevantFile,
    RelevantSymbol,
)
from core.context_injector import ContextInjector
from core.impact_analyzer import ImpactAnalyzer, ImpactReport, RiskLevel
from core.memory_manager import MemoryManager
from core.refactoring_planner import (
    ActionType,
    ModificationAction,
    RefactoringPlan,
    RefactoringPlanner,
)
from core.repository_analyzer import (
    ArchitectureLayer,
    ArchitectureMetrics,
    CircularDependency,
    Hotspot,
    ModuleSummary,
    RepositoryAnalysis,
    RepositoryAnalyzer,
    RepositoryOverview,
)
from core.symbol_graph import SymbolGraph


class PromptBuilder:
    """
    Constructs comprehensive, standardized engineering prompts for LLM code generation.
    Integrates ContextInjector (historical engineering memory), CodeContextRetriever
    (minimal relevant code slices), ImpactAnalyzer (blast radius & breaking change risks),
    RefactoringPlanner (safe modification execution plan), RepositoryAnalyzer
    (repository architecture intelligence), and ChangePlanner (semantic change blueprint).
    """

    def __init__(
        self,
        max_file_chars: int = 4000,
        context_injector: Optional[ContextInjector] = None,
        memory_manager: Optional[MemoryManager] = None,
        code_context_retriever: Optional[CodeContextRetriever] = None,
        impact_analyzer: Optional[ImpactAnalyzer] = None,
        refactoring_planner: Optional[RefactoringPlanner] = None,
        repository_analyzer: Optional[RepositoryAnalyzer] = None,
        change_planner: Optional[ChangePlanner] = None,
        symbol_graph: Optional[SymbolGraph] = None,
    ) -> None:
        """
        Initializes the PromptBuilder.

        Args:
            max_file_chars: Maximum characters to include per source file before truncation.
            context_injector: Optional ContextInjector instance.
            memory_manager: Optional MemoryManager instance used to create a ContextInjector.
            code_context_retriever: Optional CodeContextRetriever instance.
            impact_analyzer: Optional ImpactAnalyzer instance.
            refactoring_planner: Optional RefactoringPlanner instance.
            repository_analyzer: Optional RepositoryAnalyzer instance.
            change_planner: Optional ChangePlanner instance.
            symbol_graph: Optional SymbolGraph instance used to construct subsystems.
        """
        self.max_file_chars = max_file_chars

        # Memory Context Injector
        if context_injector is not None:
            self.context_injector = context_injector
        elif memory_manager is not None:
            self.context_injector = ContextInjector(memory_manager=memory_manager)
        else:
            self.context_injector = ContextInjector(memory_manager=None)

        # Code Context Retriever
        if code_context_retriever is not None:
            self.code_context_retriever = code_context_retriever
        elif symbol_graph is not None:
            self.code_context_retriever = CodeContextRetriever(symbol_graph=symbol_graph)
        else:
            self.code_context_retriever = None

        # Impact Analyzer
        if impact_analyzer is not None:
            self.impact_analyzer = impact_analyzer
        elif symbol_graph is not None:
            self.impact_analyzer = ImpactAnalyzer(symbol_graph=symbol_graph)
        else:
            self.impact_analyzer = None

        # Refactoring Planner
        if refactoring_planner is not None:
            self.refactoring_planner = refactoring_planner
        elif symbol_graph is not None:
            self.refactoring_planner = RefactoringPlanner(symbol_graph=symbol_graph)
        else:
            self.refactoring_planner = None

        # Repository Analyzer (v1.7)
        if repository_analyzer is not None:
            self.repository_analyzer = repository_analyzer
        elif symbol_graph is not None:
            self.repository_analyzer = RepositoryAnalyzer(symbol_graph=symbol_graph)
        else:
            self.repository_analyzer = None

        # Change Planner (v1.8)
        if change_planner is not None:
            self.change_planner = change_planner
        elif symbol_graph is not None:
            self.change_planner = ChangePlanner(symbol_graph=symbol_graph)
        else:
            self.change_planner = None



    # -------------------------------------------------------------------------
    # Section Builders
    # -------------------------------------------------------------------------

    def build_system_section(self) -> str:
        """
        Constructs the SYSTEM ROLE definition.
        """
        return (
            "================================================================================\n"
            "1. SYSTEM ROLE\n"
            "================================================================================\n"
            "You are an Elite Principal Software Engineer and autonomous core developer in the\n"
            "AutoDev system. Your objective is to implement clean, production-ready, highly robust\n"
            "software modules that precisely fulfill the assigned engineering task while strictly\n"
            "adhering to existing architectural patterns, project memory, and constraints."
        )

    def build_project_section(self, context: Dict[str, Any]) -> str:
        """
        Constructs the PROJECT INFORMATION & GOALS section.
        """
        project_name = context.get("project_name", "Untitled Project")
        description = context.get("description", "No description provided.")

        return (
            "================================================================================\n"
            "2. PROJECT INFORMATION\n"
            "================================================================================\n"
            f"Project Name : {project_name}\n"
            f"Description  : {description}"
        )

    def build_technology_section(self, context: Dict[str, Any]) -> str:
        """
        Constructs the TECHNOLOGY STACK specification section.
        """
        tech_stack = context.get("technology_stack", "Standard Library")

        return (
            "================================================================================\n"
            "3. TECHNOLOGY STACK\n"
            "================================================================================\n"
            f"Mandatory Stack & Tooling: {tech_stack}\n\n"
            "You must use only idiomatic patterns and approved libraries within this stack."
        )

    def build_phase_section(self, context: Dict[str, Any]) -> str:
        """
        Constructs the CURRENT DEVELOPMENT PHASE context section.
        """
        current_day = context.get("current_day", 1)
        current_phase = context.get("current_phase", {}) or {}
        phase_name = current_phase.get("phase_name", f"Day {current_day} Phase")
        goals = current_phase.get("goals", [])
        deliverables = current_phase.get("deliverables", [])
        testing_focus = current_phase.get("testing_focus", "N/A")

        goals_text = "\n".join(f"  - {g}" for g in goals) if goals else "  - (Standard phase goals)"
        deliv_text = "\n".join(f"  + {d}" for d in deliverables) if deliverables else "  + (Standard deliverables)"

        return (
            "================================================================================\n"
            "4. CURRENT DEVELOPMENT PHASE\n"
            "================================================================================\n"
            f"Day Index     : Day {current_day}\n"
            f"Phase Name    : {phase_name}\n"
            f"Testing Focus : {testing_focus}\n\n"
            f"Phase Goals:\n{goals_text}\n\n"
            f"Phase Deliverables:\n{deliv_text}"
        )

    def build_architecture_section(
        self,
        context: Dict[str, Any],
        task: Optional[Union[Task, Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        Constructs the PROJECT ARCHITECTURE section detailing detected patterns,
        layers, module responsibilities, entry points, hotspots, and circular dependencies.
        """
        overview: Optional[RepositoryOverview] = None

        if "repository_analysis" in context and isinstance(context["repository_analysis"], RepositoryOverview):
            overview = context["repository_analysis"]
        elif "repository_overview" in context and isinstance(context["repository_overview"], RepositoryOverview):
            overview = context["repository_overview"]
        elif "repository_analyzer" in context and hasattr(context["repository_analyzer"], "analyze"):
            overview = context["repository_analyzer"].analyze(
                symbol_graph=context.get("symbol_graph"),
                project_files=context.get("project_files"),
            )
        elif self.repository_analyzer is not None:
            overview = self.repository_analyzer.analyze(
                symbol_graph=context.get("symbol_graph"),
                project_files=context.get("project_files"),
            )
        elif "symbol_graph" in context and context["symbol_graph"] is not None:
            analyzer = RepositoryAnalyzer(symbol_graph=context["symbol_graph"])
            overview = analyzer.analyze(
                symbol_graph=context["symbol_graph"],
                project_files=context.get("project_files"),
            )

        if not overview or overview.total_modules == 0:
            return None

        lines: List[str] = [
            "================================================================================",
            "PROJECT ARCHITECTURE",
            "================================================================================",
        ]

        if overview.detected_architectures:
            top_arch = overview.detected_architectures[0]
            lines.append(f"Primary Architecture : {top_arch.pattern_name} (Confidence: {top_arch.confidence:.2f})")
            if len(overview.detected_architectures) > 1:
                other_archs = [f"{a.pattern_name} ({a.confidence:.2f})" for a in overview.detected_architectures[1:3]]
                lines.append(f"Associated Patterns  : {', '.join(other_archs)}")

        if overview.architecture_layers:
            lines.append("\nDetected Layers:")
            for layer in overview.architecture_layers:
                if layer.modules:
                    mod_sample = ", ".join(layer.modules[:4])
                    if len(layer.modules) > 4:
                        mod_sample += f" (+{len(layer.modules) - 4} more)"
                    lines.append(f"- {layer.name}: {mod_sample}")

        if overview.module_summaries:
            lines.append("\nKey Module Responsibilities:")
            target_files = []
            if task:
                if hasattr(task, "estimated_files"):
                    target_files = getattr(task, "estimated_files", []) or []
                elif isinstance(task, dict):
                    target_files = task.get("estimated_files", []) or []

            shown_mods = 0
            for tf in target_files:
                if tf in overview.module_summaries and shown_mods < 4:
                    ms = overview.module_summaries[tf]
                    lines.append(f"- `{tf}`: {ms.purpose or ', '.join(ms.responsibilities[:1])}")
                    shown_mods += 1

            for mod_path, ms in list(overview.module_summaries.items()):
                if mod_path not in target_files and shown_mods < 4:
                    lines.append(f"- `{mod_path}`: {ms.purpose or ', '.join(ms.responsibilities[:1])}")
                    shown_mods += 1

        if overview.entry_points:
            lines.append("\nImportant Entry Points:")
            for ep in overview.entry_points[:4]:
                lines.append(f"- {ep}")

        if overview.hotspots:
            lines.append("\nRepository Hotspots:")
            for h in overview.hotspots[:3]:
                lines.append(f"- [{h.category.upper()}] {h.target}: {h.description}")

        if overview.circular_dependencies:
            lines.append("\nCircular Dependencies:")
            for c in overview.circular_dependencies[:3]:
                lines.append(f"- [WARNING - {c.severity}] {' -> '.join(c.cycle)}")

        if overview.public_apis:
            lines.append("\nPublic APIs:")
            for api in overview.public_apis[:4]:
                lines.append(f"- {api}")

        return "\n".join(lines)

    def build_memory_section(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
        max_tokens: int = 2500,
    ) -> Optional[str]:
        """
        Constructs the RELEVANT PROJECT MEMORY section using ContextInjector.
        Returns None if no relevant memories are available.
        """
        injector = context.get("context_injector") or self.context_injector
        if not injector:
            return None

        memory_block = injector.build_prompt_context(
            context=context,
            task=task,
            max_tokens=max_tokens,
        )
        if memory_block and memory_block.strip():
            return memory_block
        return None


    def build_task_section(self, task: Union[Task, Dict[str, Any]]) -> str:
        """
        Constructs the specific CURRENT TASK execution section.
        """
        if hasattr(task, "id") and hasattr(task, "title"):
            task_id = str(getattr(task, "id", "UNKNOWN-TASK"))
            title = str(getattr(task, "title", ""))
            description = str(getattr(task, "description", ""))
            priority = getattr(task, "priority", 1)
            dependencies = getattr(task, "dependencies", [])
            estimated_files = getattr(task, "estimated_files", [])
            estimated_duration = getattr(task, "estimated_duration", "N/A")
        elif isinstance(task, dict):
            task_id = task.get("id", "UNKNOWN-TASK")
            title = task.get("title", "")
            description = task.get("description", "")
            priority = task.get("priority", 1)
            dependencies = task.get("dependencies", [])
            estimated_files = task.get("estimated_files", [])
            estimated_duration = task.get("estimated_duration", "N/A")
        else:
            task_id = "UNKNOWN-TASK"
            title = str(task)
            description = ""
            priority = 1
            dependencies = []
            estimated_files = []
            estimated_duration = "N/A"

        deps_text = ", ".join(dependencies) if dependencies else "None (Independent)"
        files_text = ", ".join(estimated_files) if estimated_files else "To be determined by task scope"

        return (
            "================================================================================\n"
            "6. CURRENT TASK TO IMPLEMENT\n"
            "================================================================================\n"
            f"Task ID            : {task_id}\n"
            f"Title              : {title}\n"
            f"Priority           : {priority}\n"
            f"Dependencies       : {deps_text}\n"
            f"Target Files       : {files_text}\n"
            f"Estimated Duration : {estimated_duration}\n\n"
            f"Task Specification:\n{description}"
        )

    def build_impact_section(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
    ) -> Optional[str]:
        """
        Constructs the CODE IMPACT ANALYSIS section.
        Omitted if no impact data or graph is available.
        """
        report: Optional[ImpactReport] = None

        if "impact_report" in context and isinstance(context["impact_report"], ImpactReport):
            report = context["impact_report"]
        elif "impact_analyzer" in context and hasattr(context["impact_analyzer"], "analyze"):
            report = context["impact_analyzer"].analyze(task, context)
        elif "impact_analyzer" in context and hasattr(context["impact_analyzer"], "analyze_task"):
            report = context["impact_analyzer"].analyze_task(task)
        elif self.impact_analyzer is not None:
            report = self.impact_analyzer.analyze(task, context)
        elif "symbol_graph" in context and context["symbol_graph"] is not None:
            analyzer = ImpactAnalyzer(symbol_graph=context["symbol_graph"])
            report = analyzer.analyze(task, context)

        if not report:
            return None

        # If zero impact score and no affected elements, omit cleanly
        if (
            report.impact_score == 0.0
            and not report.affected_files
            and not report.affected_symbols
            and not report.breaking_change_risks
            and not report.summary
        ):
            return None

        lines: List[str] = [
            "================================================================================",
            "7. CODE IMPACT ANALYSIS",
            "================================================================================",
            f"Target                  : {report.target or 'Current Task'}",
            f"Risk Level              : {report.risk_level} (Impact Score: {report.impact_score:.1f}/100, Confidence: {report.confidence:.2f})",
            f"Estimated Scope         : {report.estimated_change_scope}",
            f"Affected Files          : {', '.join(report.affected_files) if report.affected_files else 'None'}",
            f"Affected Symbols        : {', '.join(report.affected_symbols) if report.affected_symbols else 'None'}",
            f"Affected Tests          : {', '.join(report.affected_tests) if report.affected_tests else 'None'}",
            f"Callers                 : {', '.join(report.callers) if report.callers else 'None'}",
            f"Callees                 : {', '.join(report.callees) if report.callees else 'None'}",
            f"Dependencies            : {', '.join(report.dependencies) if report.dependencies else 'None'}",
            f"Dependents              : {', '.join(report.dependents) if report.dependents else 'None'}",
            f"Inheritance Chain       : {', '.join(report.inheritance_chain) if report.inheritance_chain else 'None'}",
        ]

        if report.summary:
            lines.append(f"\nSummary:\n{report.summary}")

        if report.breaking_change_risks:
            lines.append("\nPotential Breaking Changes:")
            for r in report.breaking_change_risks:
                lines.append(f"  - {r}")

        if report.recommended_validation:
            lines.append("\nRecommended Validation:")
            for v in report.recommended_validation:
                lines.append(f"  * {v}")

        return "\n".join(lines)

    def build_refactoring_section(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
    ) -> Optional[str]:
        """
        Constructs the SAFE REFACTORING PLAN section detailing exact files to modify/create/delete
        and granular modification actions with breaking change analysis.
        """
        plan: Optional[RefactoringPlan] = None

        if "refactoring_plan" in context and isinstance(context["refactoring_plan"], RefactoringPlan):
            plan = context["refactoring_plan"]
        elif "refactoring_planner" in context and hasattr(context["refactoring_planner"], "plan"):
            plan = context["refactoring_planner"].plan(task, context)
        elif self.refactoring_planner is not None:
            plan = self.refactoring_planner.plan(task, context)
        elif "symbol_graph" in context and context["symbol_graph"] is not None:
            planner = RefactoringPlanner(symbol_graph=context["symbol_graph"])
            plan = planner.plan(task, context)

        if not plan or not plan.actions:
            return None

        lines: List[str] = [
            "================================================================================",
            "SAFE REFACTORING PLAN",
            "================================================================================",
        ]

        if plan.summary:
            lines.append(f"Summary:\n{plan.summary}\n")

        if plan.files_to_modify:
            lines.append("Files To Modify\n---------------")
            for f in plan.files_to_modify:
                lines.append(f)
            lines.append("")

        if plan.files_to_create:
            lines.append("Files To Create\n---------------")
            for f in plan.files_to_create:
                lines.append(f)
            lines.append("")

        if plan.files_to_delete:
            lines.append("Files To Delete\n---------------")
            for f in plan.files_to_delete:
                lines.append(f)
            lines.append("")

        if plan.actions:
            lines.append("Actions\n--------")
            for act in plan.actions:
                lines.append(str(act.action_type))
                sym_str = str(act.target_symbol)
                sym_display = f"{sym_str}()" if act.action_type in {"MODIFY_FUNCTION", "MODIFY_METHOD", "ADD_FUNCTION", "ADD_METHOD", "DELETE_FUNCTION"} and not sym_str.endswith("()") else sym_str
                lines.append(sym_display)
                lines.append("")
                lines.append(f"Reason:\n{act.reason}")
                lines.append("")
                lines.append(f"Priority:\n{act.priority}")
                lines.append("")
                lines.append(f"Estimated Change:\n{act.estimated_lines_changed} LOC")
                lines.append("")
                breaking_text = "Yes" if act.breaking_change else "No"
                lines.append(f"Breaking:\n{breaking_text}")
                if act.notes:
                    lines.append(f"\nNotes:\n{act.notes}")
                lines.append("--------------------------------------------------------------------------------")

        if plan.breaking_changes:
            lines.append("\nBreaking Changes & Safety Invariants:")
            for bc in plan.breaking_changes:
                lines.append(f"  ! {bc}")
            if plan.rollback_required:
                lines.append("  * Rollback Preparedness: REQUIRED")
            if plan.migration_required:
                lines.append("  * Database Migration: REQUIRED")

        return "\n".join(lines)

    def build_change_plan_section(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
    ) -> Optional[str]:
        """
        Constructs the CHANGE PLAN section detailing files to modify, create, avoid,
        refactoring steps, breaking changes, migration steps, and execution order.
        """
        plan: Optional[ChangePlan] = None

        if "change_plan" in context and isinstance(context["change_plan"], ChangePlan):
            plan = context["change_plan"]
        elif "change_planner" in context and hasattr(context["change_planner"], "plan"):
            plan = context["change_planner"].plan(
                task=task,
                context=context,
                symbol_graph=context.get("symbol_graph"),
                repository_overview=context.get("repository_analysis"),
                impact_report=context.get("impact_report"),
            )
        elif self.change_planner is not None:
            plan = self.change_planner.plan(
                task=task,
                context=context,
                symbol_graph=context.get("symbol_graph"),
                repository_overview=context.get("repository_analysis"),
                impact_report=context.get("impact_report"),
            )
        elif "symbol_graph" in context and context["symbol_graph"] is not None:
            planner = ChangePlanner(symbol_graph=context["symbol_graph"])
            plan = planner.plan(
                task=task,
                context=context,
                symbol_graph=context["symbol_graph"],
                repository_overview=context.get("repository_analysis"),
                impact_report=context.get("impact_report"),
            )

        if not plan:
            return None

        lines: List[str] = [
            "================================================================================",
            "CHANGE PLAN",
            "================================================================================",
            f"Classification : {plan.change_classification} (Risk: {plan.risk_level} | Estimated LOC: {plan.estimated_total_lines})",
        ]

        if plan.summary:
            lines.append(f"Summary        : {plan.summary}\n")

        if plan.files_to_modify:
            lines.append("Files to Modify:")
            for f in plan.files_to_modify:
                fc = next((x for x in plan.file_changes if x.file_path == f), None)
                reason_str = f" - {fc.reason}" if fc else ""
                lines.append(f"- {f}{reason_str}")

        if plan.files_to_create:
            lines.append("\nFiles to Create:")
            for f in plan.files_to_create:
                fc = next((x for x in plan.file_changes if x.file_path == f), None)
                reason_str = f" - {fc.reason}" if fc else ""
                lines.append(f"- {f}{reason_str}")

        if plan.files_to_avoid:
            avoid_sample = ", ".join(plan.files_to_avoid[:5])
            if len(plan.files_to_avoid) > 5:
                avoid_sample += f" (+{len(plan.files_to_avoid) - 5} more)"
            lines.append(f"\nFiles to Avoid (Protected from unnecessary edits):\n- {avoid_sample}")

        if plan.refactoring_steps:
            lines.append("\nRefactoring Strategy:")
            for r in plan.refactoring_steps:
                lines.append(f"- [{r.refactoring_type}] {r.target} in `{r.target_file}`: {r.description} (Rationale: {r.rationale})")

        if plan.breaking_changes:
            lines.append("\nBreaking Changes & Mitigations:")
            for b in plan.breaking_changes:
                lines.append(f"- [{b.change_category}] {b.target}: {b.description} (Impact: {b.impact_level})")
                lines.append(f"  Mitigation: {b.mitigation_strategy}")

        if plan.migration_steps:
            lines.append("\nMigration Steps:")
            for m in plan.migration_steps:
                lines.append(f"- [{m.migration_type}] `{m.target_file}`: {m.description}")
                lines.append(f"  Action: {m.sql_or_code_action}")
                lines.append(f"  Rollback: {m.rollback_instruction}")

        if plan.execution_order:
            lines.append("\nExecution Order:")
            for idx, step_file in enumerate(plan.execution_order, start=1):
                lines.append(f"{idx}. `{step_file}`")

        return "\n".join(lines)


    def build_code_context_section(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
        max_tokens: int = 6000,
    ) -> Optional[str]:
        """
        Constructs the RELEVANT CODE CONTEXT section containing focused symbols and file slices.
        Omitted if no relevant code is retrieved.
        """
        result: Optional[Any] = None

        if "context_bundle" in context:
            result = context["context_bundle"]
        elif "code_context_result" in context:
            result = context["code_context_result"]
        elif "code_context_retriever" in context and hasattr(context["code_context_retriever"], "retrieve"):
            result = context["code_context_retriever"].retrieve(
                task=task,
                impact_report=context.get("impact_report"),
                context=context,
                max_tokens=max_tokens,
            )
        elif self.code_context_retriever is not None:
            result = self.code_context_retriever.retrieve(
                task=task,
                impact_report=context.get("impact_report"),
                context=context,
                max_tokens=max_tokens,
            )
        elif "symbol_graph" in context and context["symbol_graph"] is not None:
            retriever = CodeContextRetriever(graph=context["symbol_graph"])
            result = retriever.retrieve(
                task=task,
                impact_report=context.get("impact_report"),
                context=context,
                max_tokens=max_tokens,
            )

        if not result:
            return None

        snippets = getattr(result, "snippets", [])
        relevant_files = getattr(result, "relevant_files", [])

        if not snippets and not relevant_files and not getattr(result, "relevant_symbols", []):
            return None

        lines: List[str] = [
            "================================================================================",
            "8. RELEVANT CODE CONTEXT",
            "================================================================================",
        ]
        if hasattr(result, "summary") and result.summary:
            lines.append(f"Summary: {result.summary}\n")

        if snippets:
            for s in snippets:
                lines.append(f"File   : {s.file}")
                lines.append(f"Lines  : {s.start_line}-{s.end_line}")
                lines.append(f"Reason : {s.reason}")
                lines.append(f"Symbol : {s.symbol}")
                lines.append(f"```{s.language}")
                lines.append(s.content.rstrip())
                lines.append("```")
                lines.append("--------------------------------------------------------------------------------")
        elif relevant_files:
            for file_item in relevant_files:
                f_path = getattr(file_item, "path", getattr(file_item, "file", ""))
                f_syms = getattr(file_item, "symbols", [])
                lines.append(f"FILE: {f_path}")
                if f_syms:
                    lines.append(f"SYMBOL: {', '.join(f_syms) if isinstance(f_syms, list) else f_syms}")
                lines.append(f"RELATIONSHIP: {getattr(file_item, 'relationship', getattr(file_item, 'reason', 'direct_target'))}")
                lines.append("")
                lines.append(getattr(file_item, "content", ""))
                lines.append("--------------------------------------------------------------------------------")

        return "\n".join(lines)

    def build_feedback_section(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Constructs the SELF-HEALING RETRY FEEDBACK section if prior attempt feedback exists.
        """
        feedback = context.get("retry_feedback")
        if not feedback:
            return None

        attempt = feedback.get("attempt", 2)
        review_info = feedback.get("previous_review", {})
        test_info = feedback.get("previous_tests")

        feedback_parts: List[str] = [
            "================================================================================\n"
            f"9. RETRY & DEFECT REMEDIATION FEEDBACK (Attempt {attempt})\n"
            "================================================================================"
        ]

        if review_info:
            score = review_info.get("score", 0)
            summary = review_info.get("summary", "Review completed with issues.")
            feedback_parts.append(f"Previous Code Quality Score : {score}/100")
            feedback_parts.append(f"Reviewer Summary            : {summary}")

            issues = review_info.get("issues", [])
            if issues:
                feedback_parts.append("\nDetected Issues to Fix:")
                for idx, iss in enumerate(issues, start=1):
                    if isinstance(iss, dict):
                        sev = iss.get("severity", "ISSUE")
                        loc = f"{iss.get('file', 'unknown')}:{iss.get('line') or '?'}"
                        desc = iss.get("description", "")
                        rec = iss.get("recommendation", "")
                        feedback_parts.append(f"  {idx}. [{sev}] ({loc}) {desc}")
                        if rec:
                            feedback_parts.append(f"     Fix: {rec}")

            recs = review_info.get("recommendations", [])
            if recs:
                feedback_parts.append("\nRecommendations:")
                for r in recs:
                    feedback_parts.append(f"  * {r}")

        if test_info:
            passed = test_info.get("passed", 0)
            failed = test_info.get("failed", 0)
            stderr = test_info.get("stderr", "")
            stdout = test_info.get("stdout", "")
            feedback_parts.append(f"\nAutomated Test Results : {passed} passed, {failed} failed")
            if stderr or stdout:
                preview = (stderr or stdout)[:600]
                feedback_parts.append(f"Test Error Output:\n{preview}")

        feedback_parts.append(
            "\nREMEDIATION INSTRUCTION:\n"
            "Improve and fix the implementation to resolve all identified issues and test failures above.\n"
            "Do NOT restart from scratch; preserve working architecture and correct the specific defects."
        )

        return "\n".join(feedback_parts)

    def build_directory_section(self, directory_tree: List[str]) -> str:
        """
        Constructs the EXISTING DIRECTORY STRUCTURE section.
        """
        if not directory_tree:
            tree_text = "(Empty workspace - Initial project setup required)"
        else:
            tree_text = "\n".join(f"  {entry}" for entry in directory_tree)

        return (
            "================================================================================\n"
            "10. EXISTING DIRECTORY STRUCTURE\n"
            "================================================================================\n"
            f"{tree_text}"
        )

    def build_files_section(
        self,
        project_files: Dict[str, str],
        excluded_files: Optional[Set[str]] = None,
        has_code_context: bool = False,
    ) -> str:
        """
        Constructs the EXISTING / ADDITIONAL SOURCE FILES section with safety truncation.
        """
        section_title = "11. ADDITIONAL PROJECT FILES" if has_code_context else "11. EXISTING SOURCE FILES"

        if not project_files:
            files_text = "(No existing text source files in project workspace yet)"
        else:
            file_blocks: List[str] = []
            for file_path, content in sorted(project_files.items()):
                if excluded_files and file_path in excluded_files:
                    continue

                if len(content) > self.max_file_chars:
                    truncated = content[: self.max_file_chars]
                    rendered_content = f"{truncated}\n... [TRUNCATED: File exceeds {self.max_file_chars} characters] ..."
                else:
                    rendered_content = content

                file_blocks.append(
                    f"--- File: {file_path} ---\n{rendered_content}\n--- End of File ---"
                )

            if not file_blocks:
                files_text = "(All relevant source files provided in RELEVANT CODE CONTEXT above)"
            else:
                files_text = "\n\n".join(file_blocks)

        return (
            "================================================================================\n"
            f"{section_title}\n"
            "================================================================================\n"
            f"{files_text}"
        )

    def build_constraints_section(self) -> str:
        """
        Constructs the ENGINEERING CONSTRAINTS section.
        """
        return (
            "================================================================================\n"
            "12. ENGINEERING CONSTRAINTS\n"
            "================================================================================\n"
            "1. Architecture Integrity : Follow the established project layout, patterns, and conventions.\n"
            "2. Scoped Modifications   : Modify or create ONLY the files necessary for this specific task.\n"
            "3. Functional Continuity  : Preserve existing interfaces and functionality without regressions.\n"
            "4. Impact Inspection      : Inspect impact information before changing public APIs; preserve compatibility.\n"
            "5. Dependent Updates      : Update dependent code and tests when interfaces or behavior change.\n"
            "6. Context Discipline     : Do not invent files or symbols not present in context unless necessary.\n"
            "7. SOLID Principles       : Write modular, single-responsibility, highly extensible code.\n"
            "8. Quality & Type Safety  : Write complete production-ready code with type annotations and docstrings.\n"
            "9. Strict Output Standard : Provide COMPLETE file contents (no placeholders, no ellipsis '...', no snippets).\n"
            "10. Technology Stack Rule : Use only the specified stack and standard/configured libraries.\n"
            "11. Pure JSON Output      : Return ONLY a valid JSON object matching the required schema.\n"
            "12. No Markdown Enclosing : Do NOT wrap the JSON in markdown fences (```json or ```). Return raw JSON only."
        )

    def build_output_schema_section(self) -> str:
        """
        Constructs the REQUIRED JSON OUTPUT FORMAT section.
        """
        schema_example = {
            "summary": "Concise high-level summary of code implementation and changes made",
            "files": [
                {
                    "path": "relative/path/to/target_file.py",
                    "content": "# Full source code for the file goes here\n",
                }
            ],
            "explanation": "Detailed engineering explanation of design decisions, implementation details, and verification steps",
        }

        rendered_schema = json.dumps(schema_example, indent=2)

        return (
            "================================================================================\n"
            "13. REQUIRED JSON OUTPUT FORMAT\n"
            "================================================================================\n"
            "You MUST respond with a single, strictly valid JSON object matching this schema:\n\n"
            f"{rendered_schema}\n\n"
            "Critical: Ensure all special characters and newlines in file contents are properly escaped as valid JSON strings."
        )

    # -------------------------------------------------------------------------
    # Master Build Method
    # -------------------------------------------------------------------------

    def build(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
    ) -> str:
        """
        Assembles all prompt sections into a unified 13-section engineering prompt.

        Layout (v1.5):
        1. SYSTEM ROLE
        2. PROJECT INFORMATION
        3. TECHNOLOGY STACK
        4. CURRENT DEVELOPMENT PHASE
        5. RELEVANT PROJECT MEMORY (if available)
        6. CURRENT TASK TO IMPLEMENT
        7. CODE IMPACT ANALYSIS (if available)
        8. RELEVANT CODE CONTEXT (if available)
        9. RETRY & DEFECT REMEDIATION FEEDBACK (if retry attempt)
        10. EXISTING DIRECTORY STRUCTURE
        11. ADDITIONAL / EXISTING SOURCE FILES
        12. ENGINEERING CONSTRAINTS
        13. REQUIRED JSON OUTPUT FORMAT

        Args:
            context: Context dictionary produced by ContextBuilder.
            task: Task object or dictionary produced by TaskPlannerAgent.

        Returns:
            Complete, standardized prompt string ready for LLM inference.
        """
        sections: List[str] = [
            self.build_system_section(),
            self.build_project_section(context),
            self.build_technology_section(context),
            self.build_phase_section(context),
        ]

        # Project Architecture Intelligence (v1.7)
        arch_sec = self.build_architecture_section(context, task)
        if arch_sec:
            sections.append(arch_sec)

        # 5. Injected Relevant Project Memory
        memory_sec = self.build_memory_section(context, task)
        if memory_sec:
            sections.append(memory_sec)


        # 6. Current Task
        sections.append(self.build_task_section(task))

        # 7. Code Impact Analysis
        impact_sec = self.build_impact_section(context, task)
        if impact_sec:
            sections.append(impact_sec)

        # Safe Refactoring Plan (v1.7)
        refactoring_sec = self.build_refactoring_section(context, task)
        if refactoring_sec:
            sections.append(refactoring_sec)

        # Semantic Change Plan (v1.8)
        change_plan_sec = self.build_change_plan_section(context, task)
        if change_plan_sec:
            sections.append(change_plan_sec)


        # 8. Relevant Code Context
        code_context_sec = self.build_code_context_section(context, task)
        excluded_files: Set[str] = set()
        has_code_context = False

        if code_context_sec:
            sections.append(code_context_sec)
            has_code_context = True
            # Extract excluded files if code context result was stored
            result_obj = context.get("code_context_result")
            if result_obj and hasattr(result_obj, "relevant_files"):
                excluded_files = {f.path for f in result_obj.relevant_files}

        # 9. Retry feedback if applicable
        feedback_sec = self.build_feedback_section(context)
        if feedback_sec:
            sections.append(feedback_sec)

        # 10. Existing Directory Structure
        sections.append(self.build_directory_section(context.get("directory_tree", [])))

        # 11. Additional / Existing Source Files
        sections.append(
            self.build_files_section(
                context.get("project_files", {}),
                excluded_files=excluded_files if has_code_context else None,
                has_code_context=has_code_context,
            )
        )

        # 12. Engineering Constraints & 13. Output Schema
        sections.extend([
            self.build_constraints_section(),
            self.build_output_schema_section(),
        ])

        return "\n\n".join(sections)


if __name__ == "__main__":
    from agents.task_planner_agent import TaskPlannerAgent
    from core.context_builder import build_context

    # 1. Load context
    ctx = build_context()

    # 2. Extract active tasks
    planner = TaskPlannerAgent()
    tasks = planner.execute(ctx)

    # 3. Select first task
    sample_task = tasks[0] if tasks else Task(
        id="DEMO-TASK01",
        title="Initialize core project scaffold",
        description="Scaffold basic project architecture and dependencies.",
    )

    # 4. Synthesize prompt
    builder = PromptBuilder()
    prompt = builder.build(context=ctx, task=sample_task)

    print("===================== GENERATED ENGINEERING PROMPT =====================")
    print(prompt)
    print("========================================================================")
    print(f"\nPrompt Total Length: {len(prompt)} characters.")
