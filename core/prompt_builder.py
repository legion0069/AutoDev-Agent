"""
prompt_builder.py - Engineering Prompt Synthesis Engine for AutoDev (v1.3)

Responsible for transforming project context (metadata, phases, directory tree,
existing codebase files), relevant engineering memory (ContextInjector),
and a target atomic Task into a production-grade, structured engineering prompt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.context_injector import ContextInjector
from core.memory_manager import MemoryManager


class PromptBuilder:
    """
    Constructs comprehensive, standardized engineering prompts for LLM code generation.
    Integrates the ContextInjector to inject only the most relevant historical engineering
    knowledge, architectural decisions, and bug lessons into the prompt.
    """

    def __init__(
        self,
        max_file_chars: int = 4000,
        context_injector: Optional[ContextInjector] = None,
        memory_manager: Optional[MemoryManager] = None,
    ) -> None:
        """
        Initializes the PromptBuilder.

        Args:
            max_file_chars: Maximum characters to include per source file before truncation.
            context_injector: Optional ContextInjector instance.
            memory_manager: Optional MemoryManager instance used to create a ContextInjector.
        """
        self.max_file_chars = max_file_chars
        if context_injector is not None:
            self.context_injector = context_injector
        elif memory_manager is not None:
            self.context_injector = ContextInjector(memory_manager=memory_manager)
        else:
            self.context_injector = ContextInjector(memory_manager=None)

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
            "CURRENT TASK TO IMPLEMENT\n"
            "================================================================================\n"
            f"Task ID            : {task_id}\n"
            f"Title              : {title}\n"
            f"Priority           : {priority}\n"
            f"Dependencies       : {deps_text}\n"
            f"Target Files       : {files_text}\n"
            f"Estimated Duration : {estimated_duration}\n\n"
            f"Task Specification:\n{description}"
        )

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
            f"RETRY & DEFECT REMEDIATION FEEDBACK (Attempt {attempt})\n"
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
            "EXISTING DIRECTORY STRUCTURE\n"
            "================================================================================\n"
            f"{tree_text}"
        )

    def build_files_section(self, project_files: Dict[str, str]) -> str:
        """
        Constructs the EXISTING SOURCE FILES section with safety truncation for large files.
        """
        if not project_files:
            files_text = "(No existing text source files in project workspace yet)"
        else:
            file_blocks: List[str] = []
            for file_path, content in sorted(project_files.items()):
                if len(content) > self.max_file_chars:
                    truncated = content[: self.max_file_chars]
                    rendered_content = f"{truncated}\n... [TRUNCATED: File exceeds {self.max_file_chars} characters] ..."
                else:
                    rendered_content = content

                file_blocks.append(
                    f"--- File: {file_path} ---\n{rendered_content}\n--- End of File ---"
                )
            files_text = "\n\n".join(file_blocks)

        return (
            "================================================================================\n"
            "EXISTING SOURCE FILES\n"
            "================================================================================\n"
            f"{files_text}"
        )

    def build_constraints_section(self) -> str:
        """
        Constructs the ENGINEERING CONSTRAINTS section.
        """
        return (
            "================================================================================\n"
            "ENGINEERING CONSTRAINTS\n"
            "================================================================================\n"
            "1. Architecture Integrity : Follow the established project layout, patterns, and conventions.\n"
            "2. Scoped Modifications   : Modify or create ONLY the files necessary for this specific task.\n"
            "3. Functional Continuity  : Preserve existing interfaces and functionality without regressions.\n"
            "4. SOLID Principles       : Write modular, single-responsibility, highly extensible code.\n"
            "5. Quality & Type Safety  : Write complete production-ready code with type annotations and docstrings.\n"
            "6. Strict Output Standard : Provide COMPLETE file contents (no placeholders, no ellipsis '...', no snippets).\n"
            "7. Technology Stack Rule  : Use only the specified stack and standard/configured libraries.\n"
            "8. Pure JSON Output       : Return ONLY a valid JSON object matching the required schema.\n"
            "9. No Markdown Enclosing  : Do NOT wrap the JSON in markdown fences (```json or ```). Return raw JSON only."
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
            "REQUIRED JSON OUTPUT FORMAT\n"
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
        Assembles all prompt sections into a unified engineering prompt string.

        Layout:
        1. System Role
        2. Project Information
        3. Technology Stack
        4. Current Development Phase
        5. Relevant Project Memory (injected if relevant memories exist)
        6. Current Task to Implement
        7. Retry & Defect Remediation Feedback (if retry attempt)
        8. Existing Directory Structure
        9. Existing Source Files
        10. Engineering Constraints
        11. Required JSON Output Format

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

        # Injected Relevant Project Memory
        memory_sec = self.build_memory_section(context, task)
        if memory_sec:
            sections.append(memory_sec)

        # Current Task
        sections.append(self.build_task_section(task))

        # Retry feedback if applicable
        feedback_sec = self.build_feedback_section(context)
        if feedback_sec:
            sections.append(feedback_sec)

        # Environment & Constraints
        sections.extend([
            self.build_directory_section(context.get("directory_tree", [])),
            self.build_files_section(context.get("project_files", {})),
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
