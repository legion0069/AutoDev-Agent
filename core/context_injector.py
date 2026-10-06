"""
context_injector.py - Engineering Context Injection Engine for AutoDev (v1.3)

Analyzes the active Task and Project Context, queries the MemoryManager,
ranks retrieved memories using deterministic semantic scoring, removes duplicates,
enforces strict token budgeting, and formats structured knowledge for PromptBuilder.
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if TYPE_CHECKING:
    from agents.task_planner_agent import Task

from core.architecture_manager import ArchitectureDecision, ArchitectureManager
from core.memory_manager import MemoryCategory, MemoryEntry, MemoryManager

# Configure module logger
logger = logging.getLogger("AutoDev.ContextInjector")


@dataclass
class ScoredMemory:
    """
    Internal container associating a MemoryEntry with its computed relevance score.
    """
    entry: MemoryEntry
    score: float
    relevance_breakdown: Dict[str, float] = field(default_factory=dict)


class ContextInjector:
    """
    Context Injection Engine responsible for selecting, ranking, deduplicating,
    and formatting relevant long-term engineering memories and architectural decisions for LLM prompts.
    """

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        architecture_manager: Optional[ArchitectureManager] = None,
        max_tokens: int = 2500,
        max_memories: int = 10,
    ) -> None:
        """
        Initializes the ContextInjector.

        Args:
            memory_manager: MemoryManager instance. If None, instantiates default MemoryManager.
            architecture_manager: Optional ArchitectureManager instance.
            max_tokens: Default maximum token budget for the injected prompt memory block.
            max_memories: Maximum number of memories to retrieve and inject.
        """
        self.memory_manager = memory_manager or MemoryManager(auto_create=True)
        self.architecture_manager = architecture_manager
        self.max_tokens = max_tokens
        self.max_memories = max_memories

    # -------------------------------------------------------------------------
    # Architectural Decisions Retrieval API
    # -------------------------------------------------------------------------

    def retrieve_relevant_decisions(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
        max_decisions: Optional[int] = None,
        architecture_manager: Optional[ArchitectureManager] = None,
    ) -> List[ArchitectureDecision]:
        """
        Retrieves Architecture Decision Records relevant to task title, technology,
        estimated files, affected modules, and priority.
        """
        mgr = architecture_manager or self.architecture_manager or context.get("architecture_manager")
        if not mgr:
            return []

        limit = max_decisions or 5
        return mgr.search_relevant_for_task(task, context, limit=limit)

    def retrieve_engineering_decision(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
        decision_engine: Optional[Any] = None,
    ) -> Optional[Any]:
        """
        Retrieves precomputed engineering decision or delegates to EngineeringDecisionEngine.
        """
        if "decision_report" in context:
            return context["decision_report"]
        if "engineering_decision" in context:
            return context["engineering_decision"]

        engine = decision_engine or context.get("decision_engine")
        if engine and hasattr(engine, "decide"):
            try:
                return engine.decide(
                    task=task,
                    impact_report=context.get("impact_report"),
                    code_context=context.get("context_bundle") or context.get("project_files"),
                    symbol_graph=context.get("symbol_graph"),
                    repository_overview=context.get("repository_analysis"),
                    architecture_decisions=context.get("architecture_decisions"),
                )
            except Exception as err:
                logger.warning("EngineeringDecisionEngine error in ContextInjector: %s", err)

        return None

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def retrieve_relevant_memories(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
        max_memories: Optional[int] = None,
    ) -> List[MemoryEntry]:
        """
        Extracts search signals from context and task, queries the MemoryManager,
        ranks results, removes duplicates, and returns the top relevant MemoryEntry objects.

        Args:
            context: Project context dictionary produced by ContextBuilder.
            task: Current atomic Task object or dictionary.
            max_memories: Maximum number of memories to retrieve (defaults to self.max_memories).

        Returns:
            List of unique, highly-relevant MemoryEntry instances.
        """
        limit = max_memories if max_memories is not None else self.max_memories
        all_entries = list(self.memory_manager.load_memory().values())
        if not all_entries:
            return []

        # 1. Rank all candidate memories against task & context
        ranked_scored = self.rank_memories(all_entries, task=task, context=context)

        # 2. Extract MemoryEntry objects preserving rank order
        ranked_entries = [sm.entry for sm in ranked_scored if sm.score > 0.0]

        # If zero score matches exist, fallback to top memories by importance & recency
        if not ranked_entries:
            fallback = sorted(
                all_entries,
                key=lambda e: (e.importance, e.timestamp),
                reverse=True,
            )
            ranked_entries = fallback

        # 3. Deduplicate memories (highest-ranked survives)
        deduped = self.remove_duplicates(ranked_entries)

        return deduped[:limit]

    def rank_memories(
        self,
        memories: List[MemoryEntry],
        task: Union[Task, Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[ScoredMemory]:
        """
        Ranks candidate memories using a deterministic multi-factor weighted scoring model.

        Weights:
        - Task Similarity (Title & Description): 30%
        - Target Files Overlap: 20%
        - Tags Overlap: 20%
        - Importance Weighting: 15%
        - Recency Boost: 10%
        - Category Relevance Bonus: 5%

        Args:
            memories: List of MemoryEntry candidates.
            task: Current target task.
            context: Project context dictionary.

        Returns:
            List of ScoredMemory instances sorted descending by score.
        """
        if not memories:
            return []

        # Parse task attributes
        task_id, task_title, task_desc, target_files, priority = self._extract_task_signals(task)

        # Parse context attributes
        tech_stack = str(context.get("technology_stack", "")).lower()
        project_name = str(context.get("project_name", "")).lower()
        phase_name = str(context.get("current_phase", {}).get("phase_name", "")).lower()

        # Tokenize signals
        title_tokens = set(self._tokenize(task_title))
        desc_tokens = set(self._tokenize(task_desc))
        combined_task_tokens = title_tokens | desc_tokens
        tech_tokens = set(self._tokenize(tech_stack))
        file_tokens = set(self._tokenize(" ".join(target_files)))

        # Find timestamp extremes for recency calculation
        timestamps = []
        for m in memories:
            try:
                dt = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00"))
                timestamps.append(dt.timestamp())
            except Exception:
                pass
        max_ts = max(timestamps) if timestamps else 1.0
        min_ts = min(timestamps) if timestamps else 0.0
        ts_range = max(max_ts - min_ts, 1.0)

        scored_list: List[ScoredMemory] = []

        for m in memories:
            score, breakdown = self._score_single_memory(
                entry=m,
                task_id=task_id,
                task_title=task_title,
                task_desc=task_desc,
                combined_task_tokens=combined_task_tokens,
                title_tokens=title_tokens,
                desc_tokens=desc_tokens,
                target_files=target_files,
                file_tokens=file_tokens,
                tech_tokens=tech_tokens,
                priority=priority,
                max_ts=max_ts,
                ts_range=ts_range,
            )
            scored_list.append(ScoredMemory(entry=m, score=score, relevance_breakdown=breakdown))

        # Sort descending by score, then by importance, then by timestamp
        scored_list.sort(
            key=lambda sm: (sm.score, sm.entry.importance, sm.entry.timestamp),
            reverse=True,
        )

        return scored_list

    def remove_duplicates(self, memories: List[MemoryEntry]) -> List[MemoryEntry]:
        """
        Deduplicates a list of MemoryEntry items. If two memories share the same
        ID, normalized title, or normalized content, only the highest-ranked (first encountered)
        entry is retained.

        Args:
            memories: List of MemoryEntry objects ordered by relevance rank.

        Returns:
            Deduplicated list of MemoryEntry objects.
        """
        seen_ids: Set[str] = set()
        seen_titles: Set[str] = set()
        seen_contents: Set[str] = set()
        unique_memories: List[MemoryEntry] = []

        for entry in memories:
            norm_id = entry.id.strip().lower()
            norm_title = self._normalize_for_dedup(entry.title)
            norm_content = self._normalize_for_dedup(entry.content)

            if norm_id in seen_ids or norm_title in seen_titles or norm_content in seen_contents:
                logger.debug(f"Deduplicated redundant memory '{entry.id}' ({entry.title})")
                continue

            seen_ids.add(norm_id)
            seen_titles.add(norm_title)
            seen_contents.add(norm_content)
            unique_memories.append(entry)

        return unique_memories

    def build_prompt_context(
        self,
        context: Dict[str, Any],
        task: Union[Task, Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Executes end-to-end memory retrieval, ranking, deduplication, categorization,
        and token budgeting to generate a clean, structured markdown block for PromptBuilder.

        Args:
            context: Project context dictionary.
            task: Current target task.
            max_tokens: Token budget limit (defaults to self.max_tokens).

        Returns:
            Clean markdown string formatted for prompt injection, or empty string if no memories.
        """
        token_limit = max_tokens if max_tokens is not None else self.max_tokens
        memories = self.retrieve_relevant_memories(context=context, task=task, max_memories=self.max_memories)
        if not memories:
            return ""

        # Group memories by domain section
        categorized_blocks = self._group_memories_by_category(memories)
        if not any(categorized_blocks.values()):
            return ""

        # Assemble markdown string under token budget constraints
        rendered_block = self._assemble_prompt_sections(categorized_blocks, token_limit=token_limit)
        return rendered_block

    # -------------------------------------------------------------------------
    # Scoring Algorithm Internals
    # -------------------------------------------------------------------------

    def _score_single_memory(
        self,
        entry: MemoryEntry,
        task_id: str,
        task_title: str,
        task_desc: str,
        combined_task_tokens: Set[str],
        title_tokens: Set[str],
        desc_tokens: Set[str],
        target_files: List[str],
        file_tokens: Set[str],
        tech_tokens: Set[str],
        priority: int,
        max_ts: float,
        ts_range: float,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Computes weighted relevance score combining all relevance dimensions.
        """
        breakdown: Dict[str, float] = {}

        # 1. Task Similarity (Weight: 30%)
        # Matches against entry title and content
        entry_title_tokens = set(self._tokenize(entry.title))
        entry_content_tokens = set(self._tokenize(entry.content))
        entry_all_tokens = entry_title_tokens | entry_content_tokens

        sim_score = 0.0
        if combined_task_tokens and entry_all_tokens:
            overlap = len(combined_task_tokens & entry_all_tokens) / len(combined_task_tokens)
            sim_score += overlap * 0.70

        # Exact title substring match
        if task_title and task_title.lower() in entry.title.lower():
            sim_score += 0.30
        elif task_title and task_title.lower() in entry.content.lower():
            sim_score += 0.15

        task_sim_contrib = min(sim_score, 1.0) * 30.0
        breakdown["task_similarity"] = task_sim_contrib

        # 2. Target Files Overlap (Weight: 20%)
        file_score = 0.0
        if target_files:
            # Check if any target file path is mentioned in entry title, content, or tags
            entry_text_lower = f"{entry.title} {entry.content} {' '.join(entry.tags)}".lower()
            for tf in target_files:
                tf_clean = tf.strip().lower()
                tf_name = Path(tf_clean).name
                if tf_clean in entry_text_lower or (tf_name and tf_name in entry_text_lower):
                    file_score += 0.60
            if file_tokens:
                token_overlap = len(file_tokens & entry_all_tokens) / len(file_tokens)
                file_score += token_overlap * 0.40

        file_contrib = min(file_score, 1.0) * 20.0
        breakdown["target_files"] = file_contrib

        # 3. Tags & Technology Overlap (Weight: 20%)
        tag_score = 0.0
        if entry.tags:
            entry_tag_set = set(entry.tags)
            matched_tags = len(entry_tag_set & combined_task_tokens)
            matched_tech = len(entry_tag_set & tech_tokens)
            total_tag_matches = matched_tags + matched_tech
            tag_score += min(total_tag_matches / max(len(entry.tags), 1), 1.0) * 0.80
            if matched_tech > 0:
                tag_score += 0.20

        tag_contrib = min(tag_score, 1.0) * 20.0
        breakdown["tags_and_tech"] = tag_contrib

        # 4. Importance (Weight: 15%)
        # Importance scaled from 0-10 -> 0.0 to 1.0
        norm_importance = min(max(entry.importance, 0), 10) / 10.0
        importance_contrib = norm_importance * 15.0
        breakdown["importance"] = importance_contrib

        # 5. Recency (Weight: 10%)
        recency_val = 0.0
        try:
            dt = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
            ts = dt.timestamp()
            recency_val = max(0.0, (ts - (max_ts - ts_range)) / ts_range)
        except Exception:
            recency_val = 0.5
        recency_contrib = recency_val * 10.0
        breakdown["recency"] = recency_contrib

        # 6. Category Bonus (Weight: 5%)
        # High impact categories receive bonus
        cat_bonus = 0.0
        if entry.category in (MemoryCategory.ARCHITECTURE, MemoryCategory.DECISION):
            cat_bonus = 1.0
        elif entry.category in (MemoryCategory.BUG, MemoryCategory.LESSON):
            cat_bonus = 0.85
        elif entry.category in (MemoryCategory.REVIEW, MemoryCategory.PATTERN):
            cat_bonus = 0.70
        else:
            cat_bonus = 0.50

        # Related task ID direct match bonus (+5 bonus points)
        if task_id and any(task_id.lower() == rt.lower() for rt in entry.related_tasks):
            cat_bonus += 1.0

        cat_contrib = min(cat_bonus, 2.0) * 5.0
        breakdown["category_bonus"] = cat_contrib

        total_score = round(
            task_sim_contrib + file_contrib + tag_contrib + importance_contrib + recency_contrib + cat_contrib,
            4,
        )
        return total_score, breakdown

    # -------------------------------------------------------------------------
    # Formatting & Token Budgeting Internals
    # -------------------------------------------------------------------------

    def _group_memories_by_category(self, memories: List[MemoryEntry]) -> Dict[str, List[MemoryEntry]]:
        """
        Organizes memories into structured domain categories.
        """
        groups: Dict[str, List[MemoryEntry]] = {
            "Architecture Decisions": [],
            "Common Bugs & Pitfalls": [],
            "Implementation Lessons & Patterns": [],
            "Reviewer Directives & Quality Feedback": [],
            "Testing Notes": [],
            "Unresolved Engineering TODOs": [],
        }

        for entry in memories:
            if entry.category in (MemoryCategory.ARCHITECTURE, MemoryCategory.DECISION):
                groups["Architecture Decisions"].append(entry)
            elif entry.category == MemoryCategory.BUG:
                groups["Common Bugs & Pitfalls"].append(entry)
            elif entry.category in (MemoryCategory.IMPLEMENTATION, MemoryCategory.LESSON, MemoryCategory.PATTERN, MemoryCategory.OPTIMIZATION):
                groups["Implementation Lessons & Patterns"].append(entry)
            elif entry.category == MemoryCategory.REVIEW:
                groups["Reviewer Directives & Quality Feedback"].append(entry)
            elif entry.category == MemoryCategory.TESTING:
                groups["Testing Notes"].append(entry)
            elif entry.category == MemoryCategory.TODO:
                groups["Unresolved Engineering TODOs"].append(entry)

        return groups

    def _assemble_prompt_sections(
        self,
        categorized_blocks: Dict[str, List[MemoryEntry]],
        token_limit: int,
    ) -> str:
        """
        Renders markdown sections while strictly enforcing token budget.
        Higher ranked memories survive truncation.
        """
        header = (
            "================================================================================\n"
            "PROJECT MEMORY & RELEVANT ENGINEERING CONTEXT\n"
            "================================================================================"
        )

        section_strings: List[str] = []
        current_tokens = self._estimate_tokens(header)
        total_memories_added = 0

        for title, entries in categorized_blocks.items():
            if not entries:
                continue

            entry_lines: List[str] = []
            for entry in entries:
                bullet = f"- [{entry.id}] {entry.title}: {entry.content}"
                bullet_tokens = self._estimate_tokens(bullet)

                if current_tokens + bullet_tokens > token_limit:
                    if total_memories_added == 0:
                        # Ensure the highest-ranked memory always survives
                        max_chars = max(30, int((token_limit - current_tokens) * 3.8))
                        truncated_content = entry.content[:max_chars]
                        bullet = f"- [{entry.id}] {entry.title}: {truncated_content}..."
                        entry_lines.append(bullet)
                        current_tokens += self._estimate_tokens(bullet)
                        total_memories_added += 1
                    logger.debug(f"Memory budget reached ({current_tokens}/{token_limit} tokens). Truncating further entries.")
                    break

                entry_lines.append(bullet)
                current_tokens += bullet_tokens
                total_memories_added += 1

            if entry_lines:
                sec_md = f"### {title}\n" + "\n".join(entry_lines)
                section_strings.append(sec_md)

        if not section_strings:
            return ""

        body = "\n\n".join(section_strings)
        return f"{header}\n{body}\n================================================================================"

    # -------------------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------------------

    def _extract_task_signals(self, task: Union[Task, Dict[str, Any]]) -> Tuple[str, str, str, List[str], int]:
        """Extracts standardized attributes from Task object or dict."""
        if hasattr(task, "id") and hasattr(task, "title"):
            return (
                str(getattr(task, "id", "UNKNOWN-TASK")),
                str(getattr(task, "title", "")),
                str(getattr(task, "description", "")),
                list(getattr(task, "estimated_files", [])),
                int(getattr(task, "priority", 1)),
            )
        if isinstance(task, dict):
            return (
                str(task.get("id", "UNKNOWN-TASK")),
                str(task.get("title", "")),
                str(task.get("description", "")),
                list(task.get("estimated_files", [])),
                int(task.get("priority", 1)),
            )
        return ("UNKNOWN-TASK", str(task), "", [], 1)

    def _tokenize(self, text: str) -> List[str]:
        """Extracts normalized alphanumeric word tokens."""
        return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 1]

    def _normalize_for_dedup(self, text: str) -> str:
        """Normalizes string for duplicate detection."""
        return re.sub(r"\s+", " ", text.strip().lower())

    def retrieve_technical_debt_context(self, context: Dict[str, Any]) -> str:
        """Extracts and formats technical debt summary from context."""
        report = context.get("refactoring_report") or context.get("technical_debt_report")
        if not report:
            return ""
        if hasattr(report, "summary") and report.summary:
            return report.summary
        if isinstance(report, dict):
            return report.get("summary", "")
        return ""

    def _estimate_tokens(self, text: str) -> int:
        """Deterministic token estimator (~3.8 chars per token)."""
        if not text:
            return 0
        return max(1, int(len(text) / 3.8))
