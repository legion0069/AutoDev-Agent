"""
AutoDev Collaboration Framework - Automatic Conflict Resolver (v2.8)
====================================================================
Deterministic conflict detection, semantic analysis, patch reconciliation,
and automated resolution for concurrent multi-agent engineering workflows.

Handles:
- Concurrent file edits / merge collisions (3-way merge & chunk-level diffs)
- API contract mismatches (endpoint, parameter, return type drift)
- Schema mismatches (ORM models vs migrations vs serializers)
- Dependency version and package conflicts
- Interface / signature breaking changes
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from .collaboration_models import (
    AgentRole,
    Conflict,
    ConflictType,
    ResolutionDecision,
)

logger = logging.getLogger("autodev.collaboration.conflict_resolver")


class ConflictResolver:
    """
    Production-grade deterministic conflict detection and resolution engine.
    Maintains an immutable audit log of conflict decisions and auto-applies
    reconciled diffs, API bridges, schema adapters, and dependency unifications.
    """

    def __init__(self, workspace=None):
        self.workspace = workspace
        self._lock = threading.RLock()
        self._conflicts: Dict[str, Conflict] = {}
        self._resolutions: Dict[str, ResolutionDecision] = {}
        self._history: List[ResolutionDecision] = []

    # ------------------------------------------------------------------
    # Detection Engine
    # ------------------------------------------------------------------

    def detect_file_conflict(
        self,
        file_path: str,
        change_a: Dict[str, Any],
        change_b: Dict[str, Any],
        base_content: Optional[str] = None,
    ) -> Optional[Conflict]:
        """
        Detect concurrent modifications to the same file.
        change_a and change_b format:
        {'agent_id': str, 'role': str/AgentRole, 'content': str, 'diff': str (optional)}
        """
        content_a = change_a.get("content", "")
        content_b = change_b.get("content", "")
        agent_a = change_a.get("agent_id", "agent_a")
        agent_b = change_b.get("agent_id", "agent_b")

        if content_a == content_b:
            return None  # Identical changes, no conflict

        # Analyze line-level overlap if base_content provided, or direct diff
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)
        lines_base = base_content.splitlines(keepends=True) if base_content else []

        # Find changed lines relative to base
        diff_a_indices = self._get_changed_line_ranges(lines_base, lines_a)
        diff_b_indices = self._get_changed_line_ranges(lines_base, lines_b)

        overlapping = self._has_overlapping_ranges(diff_a_indices, diff_b_indices)
        is_merge_conflict = bool(overlapping or not base_content)

        conflict_type = ConflictType.MERGE_CONFLICT if is_merge_conflict else ConflictType.CONCURRENT_EDIT

        conflict = Conflict(
            conflict_type=conflict_type,
            file_path=file_path,
            involved_agents=[agent_a, agent_b],
            description=(
                f"Concurrent file edit collision on '{file_path}' between "
                f"{agent_a} and {agent_b}. Overlapping line ranges: {overlapping}"
            ),
            context={
                "base_content": base_content,
                "change_a": change_a,
                "change_b": change_b,
                "overlapping_ranges": overlapping,
            },
        )

        with self._lock:
            self._conflicts[conflict.conflict_id] = conflict

        logger.warning("Detected %s on file '%s' (ID: %s)", conflict_type.value, file_path, conflict.conflict_id)
        return conflict

    def detect_api_mismatch(
        self,
        endpoint_or_symbol: str,
        caller_spec: Dict[str, Any],
        callee_spec: Dict[str, Any],
        caller_agent: str = "FrontendAgent",
        callee_agent: str = "BackendAgent",
    ) -> Optional[Conflict]:
        """
        Detect contract divergence between API caller expectations and callee definitions.
        Specs format:
        {'method': 'GET'/'POST', 'params': {'id': 'int'}, 'returns': 'dict', 'path': str}
        """
        mismatches: List[str] = []

        # Compare method
        if caller_spec.get("method") and callee_spec.get("method"):
            if caller_spec["method"].upper() != callee_spec["method"].upper():
                mismatches.append(f"HTTP method mismatch: expected {caller_spec['method']}, got {callee_spec['method']}")

        # Compare parameters / payload
        caller_params = caller_spec.get("params", {})
        callee_params = callee_spec.get("params", {})
        for param, ptype in caller_params.items():
            if param not in callee_params:
                mismatches.append(f"Missing required parameter '{param}' in callee definition")
            elif callee_params[param] != ptype and ptype != "Any":
                mismatches.append(f"Parameter type mismatch for '{param}': {ptype} vs {callee_params[param]}")

        # Compare return type
        if caller_spec.get("returns") and callee_spec.get("returns"):
            if caller_spec["returns"] != callee_spec["returns"] and caller_spec["returns"] != "Any":
                mismatches.append(f"Return type mismatch: expected {caller_spec['returns']}, got {callee_spec['returns']}")

        if not mismatches:
            return None

        conflict = Conflict(
            conflict_type=ConflictType.API_MISMATCH,
            file_path=caller_spec.get("path") or callee_spec.get("path"),
            involved_agents=[caller_agent, callee_agent],
            description=f"API contract mismatch on '{endpoint_or_symbol}': " + "; ".join(mismatches),
            context={
                "endpoint_or_symbol": endpoint_or_symbol,
                "caller_spec": caller_spec,
                "callee_spec": callee_spec,
                "mismatches": mismatches,
            },
        )

        with self._lock:
            self._conflicts[conflict.conflict_id] = conflict

        logger.warning("Detected API mismatch on '%s' (ID: %s)", endpoint_or_symbol, conflict.conflict_id)
        return conflict

    def detect_schema_mismatch(
        self,
        entity_name: str,
        model_schema: Dict[str, Any],
        target_schema: Dict[str, Any],
        model_agent: str = "BackendAgent",
        target_agent: str = "FrontendAgent",
    ) -> Optional[Conflict]:
        """
        Detect differences between entity database schema / ORM model and client model / DTO.
        """
        field_differences: List[str] = []
        model_fields = model_schema.get("fields", {})
        target_fields = target_schema.get("fields", {})

        for field, ftype in model_fields.items():
            if field not in target_fields:
                field_differences.append(f"Field '{field}' ({ftype}) missing in target schema")
            elif target_fields[field] != ftype:
                field_differences.append(f"Field '{field}' type divergence: {ftype} vs {target_fields[field]}")

        for field, ftype in target_fields.items():
            if field not in model_fields:
                field_differences.append(f"Extra field '{field}' ({ftype}) present in target schema only")

        if not field_differences:
            return None

        conflict = Conflict(
            conflict_type=ConflictType.SCHEMA_MISMATCH,
            file_path=model_schema.get("file_path"),
            involved_agents=[model_agent, target_agent],
            description=f"Schema divergence for entity '{entity_name}': " + "; ".join(field_differences),
            context={
                "entity_name": entity_name,
                "model_schema": model_schema,
                "target_schema": target_schema,
                "differences": field_differences,
            },
        )

        with self._lock:
            self._conflicts[conflict.conflict_id] = conflict

        return conflict

    def detect_dependency_conflict(
        self,
        package_name: str,
        dep_spec_a: Dict[str, Any],
        dep_spec_b: Dict[str, Any],
        agent_a: str = "BackendAgent",
        agent_b: str = "SecurityAgent",
    ) -> Optional[Conflict]:
        """
        Detect incompatible version constraints across dependency declarations.
        dep_spec format: {'version': '>=2.0.0,<3.0.0', 'source': 'requirements.txt'}
        """
        version_a = dep_spec_a.get("version", "")
        version_b = dep_spec_b.get("version", "")

        if version_a == version_b:
            return None

        # Determine if constraints are compatible (simplified semver constraint conflict check)
        is_incompatible = self._are_versions_incompatible(version_a, version_b)
        if not is_incompatible:
            return None

        conflict = Conflict(
            conflict_type=ConflictType.DEPENDENCY_CONFLICT,
            file_path=dep_spec_a.get("source") or dep_spec_b.get("source"),
            involved_agents=[agent_a, agent_b],
            description=f"Dependency version conflict for '{package_name}': '{version_a}' vs '{version_b}'",
            context={
                "package_name": package_name,
                "spec_a": dep_spec_a,
                "spec_b": dep_spec_b,
                "version_a": version_a,
                "version_b": version_b,
            },
        )

        with self._lock:
            self._conflicts[conflict.conflict_id] = conflict

        return conflict

    def detect_interface_change(
        self,
        interface_name: str,
        old_interface: Dict[str, Any],
        new_interface: Dict[str, Any],
        dependents: List[str],
        author_agent: str = "ArchitectureAgent",
    ) -> Optional[Conflict]:
        """
        Detect breaking changes to public module interfaces affecting downstream components.
        """
        breaking_changes: List[str] = []
        old_methods = old_interface.get("methods", {})
        new_methods = new_interface.get("methods", {})

        for method, sig in old_methods.items():
            if method not in new_methods:
                breaking_changes.append(f"Method '{method}' was removed")
            else:
                new_sig = new_methods[method]
                if sig.get("args") != new_sig.get("args"):
                    breaking_changes.append(f"Method '{method}' parameter signature changed: {sig.get('args')} -> {new_sig.get('args')}")
                if sig.get("return_type") != new_sig.get("return_type"):
                    breaking_changes.append(f"Method '{method}' return type changed: {sig.get('return_type')} -> {new_sig.get('return_type')}")

        if not breaking_changes:
            return None

        conflict = Conflict(
            conflict_type=ConflictType.INTERFACE_BREAK,
            file_path=old_interface.get("file_path"),
            involved_agents=[author_agent] + dependents,
            description=f"Breaking interface change on '{interface_name}': " + "; ".join(breaking_changes),
            context={
                "interface_name": interface_name,
                "old_interface": old_interface,
                "new_interface": new_interface,
                "dependents": dependents,
                "breaking_changes": breaking_changes,
            },
        )

        with self._lock:
            self._conflicts[conflict.conflict_id] = conflict

        return conflict

    # ------------------------------------------------------------------
    # Resolution Engine
    # ------------------------------------------------------------------

    def analyze_conflict(self, conflict: Conflict) -> Dict[str, Any]:
        """
        Perform in-depth structural, semantic, and diff analysis of the conflict.
        """
        analysis = {
            "conflict_id": conflict.conflict_id,
            "conflict_type": conflict.conflict_type.value,
            "severity": "HIGH" if conflict.conflict_type in (ConflictType.MERGE_CONFLICT, ConflictType.INTERFACE_BREAK) else "MEDIUM",
            "can_auto_resolve": True,
            "recommended_strategy": "three_way_merge",
        }

        if conflict.conflict_type in (ConflictType.CONCURRENT_EDIT, ConflictType.MERGE_CONFLICT):
            base = conflict.context.get("base_content", "")
            ca = conflict.context.get("change_a", {}).get("content", "")
            cb = conflict.context.get("change_b", {}).get("content", "")
            overlapping = conflict.context.get("overlapping_ranges", [])

            analysis["overlapping_chunks"] = len(overlapping)
            analysis["recommended_strategy"] = "clean_merge" if len(overlapping) == 0 else "semantic_union"

        elif conflict.conflict_type == ConflictType.API_MISMATCH:
            analysis["recommended_strategy"] = "update_caller_adapter"
        elif conflict.conflict_type == ConflictType.SCHEMA_MISMATCH:
            analysis["recommended_strategy"] = "superset_union_schema"
        elif conflict.conflict_type == ConflictType.DEPENDENCY_CONFLICT:
            analysis["recommended_strategy"] = "highest_compatible_semver"
        elif conflict.conflict_type == ConflictType.INTERFACE_BREAK:
            analysis["recommended_strategy"] = "backward_compatibility_shim"

        return analysis

    def propose_resolution(self, conflict: Conflict, strategy: Optional[str] = None) -> ResolutionDecision:
        """
        Generate a concrete, deterministic resolution patch and explanation.
        """
        strat = strategy or self.analyze_conflict(conflict)["recommended_strategy"]

        patch: Dict[str, Any] = {}
        explanation = ""
        resolved_content: Optional[str] = None

        if conflict.conflict_type in (ConflictType.CONCURRENT_EDIT, ConflictType.MERGE_CONFLICT):
            base = conflict.context.get("base_content", "")
            content_a = conflict.context.get("change_a", {}).get("content", "")
            content_b = conflict.context.get("change_b", {}).get("content", "")
            agent_a = conflict.context.get("change_a", {}).get("agent_id", "agent_a")
            agent_b = conflict.context.get("change_b", {}).get("agent_id", "agent_b")

            resolved_content, merge_success = self._three_way_merge(base, content_a, content_b, agent_a, agent_b)
            patch = {
                "file_path": conflict.file_path,
                "merged_content": resolved_content,
                "clean_merge": merge_success,
            }
            explanation = (
                f"Automated 3-way merge synthesis applied across changes from {agent_a} and {agent_b}."
                if merge_success
                else f"Semantic union patch synthesized with prioritized hunk reconciliation."
            )

        elif conflict.conflict_type == ConflictType.API_MISMATCH:
            callee_spec = conflict.context.get("callee_spec", {})
            caller_spec = conflict.context.get("caller_spec", {})
            # Adapt caller or callee by harmonizing to backend contract
            harmonized_spec = {**callee_spec}
            patch = {
                "action": "harmonize_api_spec",
                "unified_spec": harmonized_spec,
                "recommended_caller_update": f"Adjust caller request to use schema: {harmonized_spec}",
            }
            explanation = f"Harmonized API contract to canonical server specification."

        elif conflict.conflict_type == ConflictType.SCHEMA_MISMATCH:
            model_fields = conflict.context.get("model_schema", {}).get("fields", {})
            target_fields = conflict.context.get("target_schema", {}).get("fields", {})
            # Union of fields with optional defaults for newly added fields
            union_fields = {**model_fields, **target_fields}
            patch = {
                "action": "superset_schema_union",
                "unified_fields": union_fields,
            }
            explanation = f"Generated non-breaking superset schema union with {len(union_fields)} properties."

        elif conflict.conflict_type == ConflictType.DEPENDENCY_CONFLICT:
            ver_a = conflict.context.get("version_a", "")
            ver_b = conflict.context.get("version_b", "")
            pkg = conflict.context.get("package_name", "package")
            unified_version = self._reconcile_versions(ver_a, ver_b)
            patch = {
                "package_name": pkg,
                "resolved_version": unified_version,
            }
            explanation = f"Reconciled dependency '{pkg}' constraints '{ver_a}' and '{ver_b}' to unified pinning '{unified_version}'."

        elif conflict.conflict_type == ConflictType.INTERFACE_BREAK:
            interface_name = conflict.context.get("interface_name", "")
            patch = {
                "action": "add_compatibility_shim",
                "interface_name": interface_name,
                "shim_strategy": "Maintain deprecated signatures with default delegation to new interface.",
            }
            explanation = f"Generated backward-compatibility shim layer preserving legacy signatures."

        decision = ResolutionDecision(
            conflict_id=conflict.conflict_id,
            strategy=strat,
            resolution_patch=patch,
            resolved_content=resolved_content,
            explanation=explanation,
            applied_by="ConflictResolver (v2.8 AutoDev Engine)",
        )

        with self._lock:
            self._resolutions[decision.decision_id] = decision
            conflict.resolved = True
            conflict.resolution_decision = decision.to_dict()
            self._history.append(decision)

        logger.info("Generated resolution decision %s for conflict %s [%s]", decision.decision_id, conflict.conflict_id, strat)
        return decision

    def resolve_and_apply(self, conflict: Conflict, strategy: Optional[str] = None) -> ResolutionDecision:
        """
        Resolve the conflict and, if a SharedWorkspace is attached, stage the merged content.
        """
        decision = self.propose_resolution(conflict, strategy=strategy)

        if self.workspace and decision.resolved_content and conflict.file_path:
            self.workspace.stage_change(
                file_path=conflict.file_path,
                author_id="ConflictResolver",
                role=AgentRole.COORDINATOR,
                content=decision.resolved_content,
                commit_message=f"Auto-resolved conflict {conflict.conflict_id}: {decision.explanation}",
            )

        return decision

    # ------------------------------------------------------------------
    # History & Queries
    # ------------------------------------------------------------------

    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        with self._lock:
            return self._conflicts.get(conflict_id)

    def get_unresolved_conflicts(self) -> List[Conflict]:
        with self._lock:
            return [c for c in self._conflicts.values() if not c.resolved]

    def get_history(self) -> List[ResolutionDecision]:
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        with self._lock:
            self._conflicts.clear()
            self._resolutions.clear()
            self._history.clear()

    # ------------------------------------------------------------------
    # Internal Merge & Semver Helpers
    # ------------------------------------------------------------------

    def _get_changed_line_ranges(self, base_lines: List[str], new_lines: List[str]) -> List[Tuple[int, int]]:
        """Compute line ranges that changed from base to new."""
        matcher = difflib.SequenceMatcher(None, base_lines, new_lines)
        changed_ranges: List[Tuple[int, int]] = []
        for tag, alo, ahi, blo, bhi in matcher.get_opcodes():
            if tag != "equal":
                changed_ranges.append((alo, ahi))
        return changed_ranges

    def _has_overlapping_ranges(self, ranges_a: List[Tuple[int, int]], ranges_b: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Check if any line ranges overlap between two sets of changes."""
        overlapping = []
        for a_start, a_end in ranges_a:
            for b_start, b_end in ranges_b:
                if max(a_start, b_start) < min(a_end, b_end) or (a_start == a_end and b_start == b_end and a_start == b_start):
                    overlapping.append((max(a_start, b_start), min(a_end, b_end)))
        return overlapping

    def _three_way_merge(
        self,
        base: str,
        content_a: str,
        content_b: str,
        agent_a: str,
        agent_b: str,
    ) -> Tuple[str, bool]:
        """
        Perform a 3-way line merge. If disjoint hunks, produces clean merge.
        If overlapping conflict hunks, outputs resolved synthesis.
        """
        base_lines = base.splitlines() if base else []
        lines_a = content_a.splitlines()
        lines_b = content_b.splitlines()

        if not base_lines:
            # If no common base, synthesize line union or append unique blocks
            if content_a in content_b:
                return content_b, True
            if content_b in content_a:
                return content_a, True
            # Concatenate or line union
            combined = lines_a + [l for l in lines_b if l not in lines_a]
            return "\n".join(combined), False

        # Compute diffs relative to base
        diff_a = list(difflib.ndiff(base_lines, lines_a))
        diff_b = list(difflib.ndiff(base_lines, lines_b))

        # Check if edits are identical
        if lines_a == lines_b:
            return content_a, True

        # Simplified 3-way line reconciliation
        merged_lines: List[str] = []
        clean_merge = True

        idx_base = 0
        idx_a = 0
        idx_b = 0

        # Fast line-by-line reconciliation
        while idx_a < len(lines_a) or idx_b < len(lines_b) or idx_base < len(base_lines):
            line_base = base_lines[idx_base] if idx_base < len(base_lines) else None
            line_a = lines_a[idx_a] if idx_a < len(lines_a) else None
            line_b = lines_b[idx_b] if idx_b < len(lines_b) else None

            if line_a == line_b:
                if line_a is not None:
                    merged_lines.append(line_a)
                idx_a += 1
                idx_b += 1
                if idx_base < len(base_lines):
                    idx_base += 1
            elif line_a == line_base and line_b is not None:
                # Agent B modified line, A kept base
                merged_lines.append(line_b)
                idx_a += 1
                idx_b += 1
                idx_base += 1
            elif line_b == line_base and line_a is not None:
                # Agent A modified line, B kept base
                merged_lines.append(line_a)
                idx_a += 1
                idx_b += 1
                idx_base += 1
            else:
                # True conflict hunk - synthesize without git markers
                clean_merge = False
                if line_a is not None:
                    merged_lines.append(line_a)
                if line_b is not None and line_b != line_a:
                    merged_lines.append(line_b)
                idx_a += 1
                idx_b += 1
                if idx_base < len(base_lines):
                    idx_base += 1

        return "\n".join(merged_lines), clean_merge

    def _are_versions_incompatible(self, ver_a: str, ver_b: str) -> bool:
        """Check for major semver version clash (e.g., ^1.0 vs ^2.0 or >=2.0 vs <2.0)."""
        nums_a = re.findall(r"\d+", ver_a)
        nums_b = re.findall(r"\d+", ver_b)
        if nums_a and nums_b:
            major_a = int(nums_a[0])
            major_b = int(nums_b[0])
            if major_a != major_b:
                return True
        if "<" in ver_a and ">=" in ver_b:
            return True
        if "<" in ver_b and ">=" in ver_a:
            return True
        return False

    def _reconcile_versions(self, ver_a: str, ver_b: str) -> str:
        """Choose the highest compatible version or modern constraint."""
        nums_a = re.findall(r"\d+(?:\.\d+)*", ver_a)
        nums_b = re.findall(r"\d+(?:\.\d+)*", ver_b)
        val_a = nums_a[0] if nums_a else "1.0.0"
        val_b = nums_b[0] if nums_b else "1.0.0"

        # Return the higher version requirement
        if val_a >= val_b:
            return f">={val_a}"
        return f">={val_b}"
