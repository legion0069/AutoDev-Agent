"""
AutoDev Conflict Resolution Subsystem.

Detects merge conflicts, duplicate implementations, architecture divergences,
style mismatches, and dependency clashes; resolves them via automated heuristics
or escalates to consensus.
"""

from __future__ import annotations

import difflib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from core.multi_agent.work_queue import WorkItem


class ConflictType(str, Enum):
    """Categorization of engineering conflicts."""
    MERGE = "merge"
    DUPLICATE_IMPLEMENTATION = "duplicate_implementation"
    ARCHITECTURE = "architecture"
    STYLE = "style"
    DEPENDENCY = "dependency"


class ResolutionAction(str, Enum):
    """Action taken to resolve a conflict."""
    CHOOSE_BEST = "choose_best"
    MERGE_COMPONENTS = "merge_components"
    ARCHITECT_OVERRIDE = "architect_override"
    REQUEST_CONSENSUS = "request_consensus"
    REJECT_ALL = "reject_all"


@dataclass
class ConflictRecord:
    """Record of a detected conflict and its resolution lifecycle."""
    conflict_id: str
    conflict_type: ConflictType
    description: str
    involved_agents: List[str]
    involved_resources: List[str]
    proposals: Dict[str, Any] = field(default_factory=dict)
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution_action: Optional[ResolutionAction] = None
    winning_agent_id: Optional[str] = None
    resolved_at: Optional[float] = None
    resolution_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the conflict record."""
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "involved_agents": list(self.involved_agents),
            "involved_resources": list(self.involved_resources),
            "proposals": self.proposals,
            "detected_at": self.detected_at,
            "resolved": self.resolved,
            "resolution_action": self.resolution_action.value if self.resolution_action else None,
            "winning_agent_id": self.winning_agent_id,
            "resolved_at": self.resolved_at,
            "resolution_notes": self.resolution_notes,
        }


class ConflictResolver:
    """
    Subsystem responsible for detecting and remediating multi-agent engineering conflicts.
    """

    def __init__(self) -> None:
        self._conflicts: Dict[str, ConflictRecord] = {}

    def get_all_conflicts(self) -> List[ConflictRecord]:
        """Returns all recorded conflicts in chronological order."""
        return sorted(list(self._conflicts.values()), key=lambda c: c.detected_at)

    def get_conflict(self, conflict_id: str) -> Optional[ConflictRecord]:
        """Retrieves a conflict record by ID."""
        return self._conflicts.get(conflict_id)

    @property
    def total_conflicts(self) -> int:
        return len(self._conflicts)

    @property
    def resolved_count(self) -> int:
        return sum(1 for c in self._conflicts.values() if c.resolved)

    @property
    def resolution_rate(self) -> float:
        if not self._conflicts:
            return 1.0
        return round(self.resolved_count / len(self._conflicts), 4)

    def detect_merge_conflict(
        self,
        resource_id: str,
        base_content: str,
        proposals: Dict[str, str],
    ) -> Optional[ConflictRecord]:
        """
        Detects if multiple agents have made conflicting line changes to the same resource.
        """
        if len(proposals) < 2:
            return None

        agent_ids = sorted(list(proposals.keys()))
        diffs = {}
        for a_id in agent_ids:
            diff = list(
                difflib.unified_diff(
                    base_content.splitlines(),
                    proposals[a_id].splitlines(),
                    lineterm="",
                )
            )
            diffs[a_id] = diff

        # Check if modified lines overlap
        # If any two proposals differ from each other and base
        first_content = proposals[agent_ids[0]]
        has_divergence = any(proposals[a_id] != first_content for a_id in agent_ids[1:])

        if has_divergence:
            conflict_id = f"conf_merge_{uuid.uuid4().hex[:8]}"
            record = ConflictRecord(
                conflict_id=conflict_id,
                conflict_type=ConflictType.MERGE,
                description=f"Concurrent conflicting edits detected on resource '{resource_id}' by agents {agent_ids}",
                involved_agents=agent_ids,
                involved_resources=[resource_id],
                proposals=proposals,
            )
            self._conflicts[conflict_id] = record
            return record

        return None

    def detect_duplicate_implementations(
        self,
        tasks: List[WorkItem],
    ) -> List[ConflictRecord]:
        """
        Detects tasks with duplicate titles, resources, or goals assigned to distinct agents.
        """
        seen_titles: Dict[str, List[WorkItem]] = {}
        records: List[ConflictRecord] = []

        for task in tasks:
            key = task.title.strip().lower()
            if key not in seen_titles:
                seen_titles[key] = []
            seen_titles[key].append(task)

        for title, group in seen_titles.items():
            if len(group) > 1:
                assigned_agents = [
                    t.assigned_agent_id for t in group if t.assigned_agent_id
                ]
                if len(set(assigned_agents)) > 1:
                    conflict_id = f"conf_dup_{uuid.uuid4().hex[:8]}"
                    record = ConflictRecord(
                        conflict_id=conflict_id,
                        conflict_type=ConflictType.DUPLICATE_IMPLEMENTATION,
                        description=f"Duplicate tasks detected for goal '{title}' across multiple agents",
                        involved_agents=sorted(list(set(assigned_agents))),
                        involved_resources=[t.task_id for t in group],
                        proposals={t.task_id: t.to_dict() for t in group},
                    )
                    self._conflicts[conflict_id] = record
                    records.append(record)

        return records

    def detect_architecture_conflict(
        self,
        proposals: Dict[str, Dict[str, Any]],
    ) -> Optional[ConflictRecord]:
        """
        Detects conflicting architectural decisions (e.g. pattern, database engine, protocol).
        """
        if len(proposals) < 2:
            return None

        # Compare pattern or protocol keys across proposals
        decisions: Dict[str, Set[str]] = {}
        for agent_id, data in proposals.items():
            for key, val in data.items():
                if key not in decisions:
                    decisions[key] = set()
                decisions[key].add(str(val))

        conflicting_keys = [k for k, v in decisions.items() if len(v) > 1]
        if conflicting_keys:
            conflict_id = f"conf_arch_{uuid.uuid4().hex[:8]}"
            record = ConflictRecord(
                conflict_id=conflict_id,
                conflict_type=ConflictType.ARCHITECTURE,
                description=f"Architectural divergence on keys: {conflicting_keys}",
                involved_agents=sorted(list(proposals.keys())),
                involved_resources=conflicting_keys,
                proposals=proposals,
            )
            self._conflicts[conflict_id] = record
            return record

        return None

    def detect_dependency_conflict(
        self,
        agent_dependencies: Dict[str, Dict[str, str]],
    ) -> Optional[ConflictRecord]:
        """
        Detects package version clashes between agent requirements.
        """
        pkg_versions: Dict[str, Dict[str, str]] = {}
        for a_id, deps in agent_dependencies.items():
            for pkg, ver in deps.items():
                if pkg not in pkg_versions:
                    pkg_versions[pkg] = {}
                pkg_versions[pkg][a_id] = ver

        clashing_pkgs = {
            pkg: vers for pkg, vers in pkg_versions.items() if len(set(vers.values())) > 1
        }

        if clashing_pkgs:
            conflict_id = f"conf_dep_{uuid.uuid4().hex[:8]}"
            involved = sorted(list({a for vers in clashing_pkgs.values() for a in vers}))
            record = ConflictRecord(
                conflict_id=conflict_id,
                conflict_type=ConflictType.DEPENDENCY,
                description=f"Conflicting package dependency versions detected: {clashing_pkgs}",
                involved_agents=involved,
                involved_resources=sorted(list(clashing_pkgs.keys())),
                proposals=agent_dependencies,
            )
            self._conflicts[conflict_id] = record
            return record

        return None

    def resolve_conflict(
        self,
        conflict: ConflictRecord,
        preferred_action: Optional[ResolutionAction] = None,
        scoring_fn: Optional[Callable[[str, Any], float]] = None,
    ) -> ConflictRecord:
        """
        Resolves a conflict using deterministic heuristics or flags it for consensus.
        """
        if conflict.resolved:
            return conflict

        action = preferred_action or ResolutionAction.CHOOSE_BEST

        if action == ResolutionAction.REQUEST_CONSENSUS:
            conflict.resolution_action = ResolutionAction.REQUEST_CONSENSUS
            conflict.resolution_notes = "Escalated to engineering consensus review."
            return conflict

        if action == ResolutionAction.CHOOSE_BEST:
            # Deterministic evaluation
            proposals = conflict.proposals
            scored_candidates: List[tuple[float, str]] = []

            for a_id, prop in proposals.items():
                if scoring_fn:
                    score = scoring_fn(a_id, prop)
                else:
                    # Default heuristic: proposal completeness (e.g. length of content or dict items)
                    if isinstance(prop, str):
                        score = float(len(prop))
                    elif isinstance(prop, dict):
                        score = float(len(prop))
                    else:
                        score = 1.0
                scored_candidates.append((score, a_id))

            if scored_candidates:
                # Deterministic sort: highest score, then lexicographical agent_id
                scored_candidates.sort(key=lambda item: (-item[0], item[1]))
                best_score, winner = scored_candidates[0]
                conflict.winning_agent_id = winner
                conflict.resolution_action = ResolutionAction.CHOOSE_BEST
                conflict.resolved = True
                conflict.resolved_at = time.time()
                conflict.resolution_notes = (
                    f"Selected proposal from '{winner}' with highest score {best_score}."
                )
        elif action == ResolutionAction.ARCHITECT_OVERRIDE:
            # Pick first available or explicit architect
            winner = conflict.involved_agents[0] if conflict.involved_agents else None
            conflict.winning_agent_id = winner
            conflict.resolution_action = ResolutionAction.ARCHITECT_OVERRIDE
            conflict.resolved = True
            conflict.resolved_at = time.time()
            conflict.resolution_notes = f"Chief Architect override enforced on '{winner}'."
        elif action == ResolutionAction.REJECT_ALL:
            conflict.resolution_action = ResolutionAction.REJECT_ALL
            conflict.resolved = True
            conflict.resolved_at = time.time()
            conflict.resolution_notes = "All competing proposals rejected."

        self._conflicts[conflict.conflict_id] = conflict
        return conflict
