"""
pattern_miner.py - Autonomous Engineering Pattern Mining Engine for AutoDev (v3.1)

Mines historical project execution, learning events, error logs, and repository structures to
automatically discover repeated architectures, recurring bugs, verified fixes, file layouts, and API styles.
Synthesizes reusable Engineering Patterns with confidence, quality scores, and usage tracking.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.learning.learning_models import (
    EngineeringPattern,
    LearningEvent,
    LearningEventType,
    PatternCategory,
)

logger = logging.getLogger("AutoDev.Learning.PatternMiner")


class PatternMiningEngine:
    """
    Autonomous Pattern Mining Engine.
    Discovers, clusters, scores, and maintains reusable engineering patterns mined from historical memory.
    """

    def __init__(self, storage_dir: Optional[str] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/learning")
        self.auto_persist = auto_persist
        self._patterns: Dict[str, EngineeringPattern] = {}

        # Default standard patterns
        self._init_default_patterns()

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create pattern miner storage directory: %s", e)

    def _init_default_patterns(self) -> None:
        """Initializes baseline foundational engineering patterns."""
        defaults = [
            (
                "PAT-ARCH-CLEAN-01",
                "Clean Layered Hexagonal Architecture",
                PatternCategory.ARCHITECTURE,
                "Decouples presentation controllers, application use-cases, domain entities, and infrastructure adapters.",
                ["Multi-module project", "Complex business rules", "Testability requirement"],
                {"layers": ["domain", "application", "infrastructure", "interfaces"], "core": "domain/core.py"},
                95.0,
                0.95,
                ["clean_architecture", "hexagonal", "ddd"],
            ),
            (
                "PAT-ARCH-REPOSVC-02",
                "Repository-Service Pattern",
                PatternCategory.ARCHITECTURE,
                "Separates data persistence operations behind repository interfaces used by business domain services.",
                ["Database backed", "CRUD workflows", "Unit testable"],
                {"components": ["models", "repositories", "services", "controllers"], "core": "services.py"},
                92.0,
                0.90,
                ["repository", "service", "orm"],
            ),
            (
                "PAT-BUG-MUTEX-01",
                "Reentrant Lock Partitioning for Nested Calls",
                PatternCategory.CONCURRENCY,
                "Replaces simple threading.Lock with threading.RLock when methods acquire locks while calling internal helpers.",
                ["Deadlock under self-invocation", "Recursive method calls"],
                {"fix_strategy": "Use threading.RLock() instead of threading.Lock()"},
                98.0,
                0.98,
                ["concurrency", "deadlock", "rlock"],
            ),
            (
                "PAT-BUG-IMPORTS-02",
                "Circular Import Safe Shim and Lazy Ingestion",
                PatternCategory.BUG_FIX,
                "Resolves cyclic dependencies using deferred local imports within method bodies or dedicated typing TYPE_CHECKING blocks.",
                ["ImportError: cannot import name", "Circular dependency cycles"],
                {"fix_strategy": "Move import into method body or use TYPE_CHECKING"},
                94.0,
                0.92,
                ["imports", "cycles", "tarjan"],
            ),
            (
                "PAT-API-REST-01",
                "RESTful Resource-Oriented API Structure",
                PatternCategory.API_DESIGN,
                "Standard JSON API envelopes with plural resource paths, status codes, and uniform error schemas.",
                ["Web service", "REST API", "HTTP client consumption"],
                {"envelope": {"data": {}, "status": "SUCCESS", "error": None}},
                90.0,
                0.90,
                ["rest", "json", "api_design"],
            ),
            (
                "PAT-LAYOUT-CLI-01",
                "Standard Python CLI Package Layout",
                PatternCategory.FILE_LAYOUT,
                "Scaffolding featuring src/package, tests, cli entrypoint, and config.",
                ["Command line tool", "Python utility"],
                {"core": "pkg/core.py", "tests": "tests/test_cli.py", "structure": ["pkg/__init__.py", "pkg/cli.py", "pkg/core.py", "tests/"]},
                91.0,
                0.91,
                ["layout", "cli", "scaffold"],
            ),
        ]

        for p_id, name, cat, desc, conds, tmpl, qual, conf, tags in defaults:
            self._patterns[p_id] = EngineeringPattern(
                id=p_id,
                pattern_id=p_id,
                name=name,
                category=cat,
                description=desc,
                applicable_scenarios=conds,
                context_conditions=conds,
                structure_template=tmpl,
                template_structure=tmpl,
                usage_count=5,
                confidence=conf,
                quality_score=qual,
                success_rate=1.0,
                tags=tags,
                historical_instances=["genesis_baseline"],
            )

    def register_pattern(
        self,
        pattern: Optional[Union[EngineeringPattern, str]] = None,
        name: str = "",
        category: PatternCategory = PatternCategory.ARCHITECTURE,
        description: str = "",
        solution: str = "",
        structure_template: Optional[Dict[str, Any]] = None,
        applicable_scenarios: Optional[List[str]] = None,
        confidence: float = 0.85,
        quality_score: float = 90.0,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> EngineeringPattern:
        """Registers or updates a discovered engineering pattern."""
        with self._lock:
            if isinstance(pattern, EngineeringPattern):
                pat = pattern
            else:
                p_name = name or (pattern if isinstance(pattern, str) else "")
                p_desc = description or solution or kwargs.get("sol", "")
                p_id = f"PAT-{int(time.time() * 1000)}-{len(self._patterns)+1}"
                tmpl = structure_template or kwargs.get("template_structure", {})
                scenarios = applicable_scenarios or kwargs.get("context_conditions", [])
                pat = EngineeringPattern(
                    id=p_id,
                    pattern_id=p_id,
                    name=p_name,
                    category=category,
                    description=p_desc,
                    solution=solution or p_desc,
                    structure_template=tmpl,
                    template_structure=tmpl,
                    applicable_scenarios=scenarios,
                    context_conditions=scenarios,
                    usage_count=0,
                    confidence=confidence,
                    quality_score=quality_score,
                    success_rate=1.0,
                    tags=list(tags or []),
                )

            self._patterns[pat.id] = pat
            if pat.pattern_id:
                self._patterns[pat.pattern_id] = pat
            if self.auto_persist:
                self._persist_state()
            logger.info("Registered EngineeringPattern %s ('%s', confidence=%.2f)",
                        pat.id, pat.name, pat.confidence)
            return copy.deepcopy(pat)

    def record_pattern_usage(self, pattern_id: str, success: bool = True) -> Optional[EngineeringPattern]:
        """Tracks usage of a pattern and updates its success rate and confidence."""
        with self._lock:
            p = self._patterns.get(pattern_id)
            if not p:
                # Check by name or alias
                for item in self._patterns.values():
                    if item.id == pattern_id or item.pattern_id == pattern_id or item.name == pattern_id:
                        p = item
                        break
            if not p:
                return None
            
            # Calculate total past successes from previous usage and success rate
            past_successes = round(p.usage_count * p.success_rate)
            p.usage_count += 1
            if success:
                past_successes += 1
            p.success_rate = round(past_successes / max(1, p.usage_count), 2)
            p.last_used = time.time()
            
            if success:
                p.confidence = min(1.0, round(p.confidence + 0.02, 3))
            else:
                p.confidence = max(0.5, round(p.confidence - 0.02, 3))
            
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(p)

    def mine_patterns(self, events: List[LearningEvent]) -> List[EngineeringPattern]:
        """Alias for mine_patterns_from_events."""
        return self.mine_patterns_from_events(events)

    def mine_patterns_from_events(self, events: List[LearningEvent]) -> List[EngineeringPattern]:
        """
        Mines recurring patterns from a stream of learning events (e.g. recurring bug fixes).
        """
        with self._lock:
            new_patterns: List[EngineeringPattern] = []
            
            # 1. Cluster BUG_FIXED events by root cause or solution similarity
            bug_events = [e for e in events if e.category in (LearningEventType.BUG_FIXED, LearningEventType.REVIEW_FAILURE) and (e.root_cause or e.solution or e.summary)]
            
            root_cause_groups: Dict[str, List[LearningEvent]] = defaultdict(list)
            for e in bug_events:
                rc_lower = (e.root_cause + " " + e.summary + " " + e.solution).lower()
                if "leak" in rc_lower or "context manager" in rc_lower or "with" in rc_lower:
                    root_cause_groups["resource_leak_context_manager"].append(e)
                elif "deadlock" in rc_lower or "lock" in rc_lower or "mutex" in rc_lower:
                    root_cause_groups["concurrency_lock"].append(e)
                elif "import" in rc_lower or "circular" in rc_lower:
                    root_cause_groups["circular_import"].append(e)
                elif "none" in rc_lower or "attribute" in rc_lower or "null" in rc_lower:
                    root_cause_groups["null_pointer_attribute"].append(e)
                elif "type" in rc_lower or "cast" in rc_lower:
                    root_cause_groups["type_coercion"].append(e)
                elif "timeout" in rc_lower or "socket" in rc_lower or "connection" in rc_lower:
                    root_cause_groups["connection_timeout"].append(e)
                else:
                    root_cause_groups["generic_defect"].append(e)

            for group_key, group_events in root_cause_groups.items():
                if len(group_events) >= 1:
                    p_id = f"PAT-MINED-BUG-{group_key.upper()}-{len(self._patterns)+1}"
                    first = group_events[0]
                    pat = EngineeringPattern(
                        id=p_id,
                        pattern_id=p_id,
                        name=f"Automated Pattern for {group_key.replace('_', ' ').title()}",
                        category=PatternCategory.BUG_FIX,
                        description=f"Discovered pattern resolving recurring {group_key} issues across {len(group_events)} tasks.",
                        solution=first.solution or "Apply standard validation guard",
                        context_conditions=[f"Root cause: {first.root_cause}"],
                        applicable_scenarios=[f"Root cause: {first.root_cause}"],
                        template_structure={"solution_template": first.solution},
                        structure_template={"solution_template": first.solution},
                        usage_count=len(group_events),
                        confidence=min(0.95, 0.70 + (len(group_events) * 0.05)),
                        quality_score=90.0,
                        success_rate=1.0,
                        tags=["mined", group_key, "auto_healed"],
                        historical_instances=[e.id for e in group_events],
                    )
                    self._patterns[p_id] = pat
                    new_patterns.append(pat)

            if self.auto_persist and new_patterns:
                self._persist_state()

            logger.info("Mined %d new engineering patterns from %d events", len(new_patterns), len(events))
            return [copy.deepcopy(p) for p in new_patterns]

    def mine_file_layout_patterns(
        self,
        name_or_files: Union[str, List[Any]],
        files_or_type: Union[List[str], str] = "python_app",
    ) -> Union[EngineeringPattern, List[EngineeringPattern]]:
        """
        Extracts structural file layout pattern from a successful repository structure.
        Supports single file list or list of file lists.
        """
        with self._lock:
            # Check if input is a list of file sets
            if isinstance(name_or_files, list) and len(name_or_files) > 0 and isinstance(name_or_files[0], list):
                extracted_list: List[EngineeringPattern] = []
                for idx, file_subset in enumerate(name_or_files):
                    pat = self.mine_file_layout_patterns(
                        name_or_files=f"Discovered Layout {idx+1}",
                        files_or_type=file_subset,
                    )
                    if isinstance(pat, EngineeringPattern):
                        extracted_list.append(pat)
                return extracted_list

            if isinstance(name_or_files, str):
                name = name_or_files
                project_files = files_or_type if isinstance(files_or_type, list) else []
            else:
                project_files = name_or_files
                name = files_or_type if isinstance(files_or_type, str) else "Discovered Layout"

            p_id = f"PAT-LAYOUT-{len(self._patterns)+1}"
            
            dirs = sorted(list(set(str(Path(f).parent).replace("\\", "/") for f in project_files if f)))
            sample_files = [str(f).replace("\\", "/") for f in project_files[:15]]
            
            tmpl: Dict[str, Any] = {"directories": dirs, "sample_files": sample_files}
            for d in dirs:
                if d and d != ".":
                    parts = d.split("/")
                    tmpl[parts[0]] = d

            pattern = EngineeringPattern(
                id=p_id,
                pattern_id=p_id,
                name=name,
                category=PatternCategory.FILE_LAYOUT,
                description=f"Standard structural file and directory scaffold for {name}.",
                applicable_scenarios=[f"Layout: {name}"],
                context_conditions=[f"Layout: {name}"],
                structure_template=tmpl,
                template_structure=tmpl,
                usage_count=1,
                confidence=0.88,
                quality_score=92.0,
                success_rate=1.0,
                tags=["mined_layout", name.lower().replace(" ", "_")],
                historical_instances=["project_extraction"],
            )
            self._patterns[p_id] = pattern
            if self.auto_persist:
                self._persist_state()
            return copy.deepcopy(pattern)

    def query_patterns(
        self,
        category: Optional[Union[PatternCategory, str]] = None,
        min_confidence: float = 0.0,
        min_quality: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> List[EngineeringPattern]:
        """Queries patterns with filtering."""
        with self._lock:
            cat_val = None
            if category:
                if isinstance(category, Enum):
                    cat_val = category.value
                else:
                    cat_val = str(category)

            results: List[EngineeringPattern] = []
            seen_ids: Set[str] = set()
            for p in self._patterns.values():
                if p.id in seen_ids:
                    continue
                seen_ids.add(p.id)
                if cat_val:
                    p_cat_val = p.category.value if isinstance(p.category, Enum) else str(p.category)
                    if p_cat_val != cat_val:
                        continue
                if p.confidence < min_confidence:
                    continue
                if p.quality_score < min_quality:
                    continue
                if tags and not any(t.lower() in [x.lower() for x in p.tags] for t in tags):
                    continue
                results.append(p)
            results.sort(key=lambda x: (x.confidence, x.quality_score), reverse=True)
            return [copy.deepcopy(p) for p in results]

    def get_all_patterns(self) -> List[EngineeringPattern]:
        """Returns all registered engineering patterns."""
        with self._lock:
            unique_patterns: Dict[str, EngineeringPattern] = {}
            for p in self._patterns.values():
                unique_patterns[p.id] = p
            return [copy.deepcopy(p) for p in unique_patterns.values()]

    def list_patterns(self, category: Optional[Union[PatternCategory, str]] = None) -> List[EngineeringPattern]:
        """Lists patterns with optional category filter."""
        return self.query_patterns(category=category)

    def get_pattern(self, pattern_id: str) -> Optional[EngineeringPattern]:
        """Retrieves an engineering pattern by ID or name."""
        with self._lock:
            if pattern_id in self._patterns:
                return copy.deepcopy(self._patterns[pattern_id])
            for p in self._patterns.values():
                if p.id == pattern_id or p.pattern_id == pattern_id or p.name == pattern_id:
                    return copy.deepcopy(p)
            return None

    def get_top_patterns(self, limit: int = 10) -> List[EngineeringPattern]:
        """Returns the highest-confidence, most heavily used patterns."""
        with self._lock:
            items = sorted(
                self.get_all_patterns(),
                key=lambda x: (x.confidence * x.success_rate * x.quality_score, x.usage_count),
                reverse=True,
            )
            return [copy.deepcopy(x) for x in items[:limit]]

    def _persist_state(self) -> None:
        try:
            self._ensure_storage()
            out_file = self.storage_dir / "patterns.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump([p.to_dict() for p in self.get_all_patterns()], f, indent=2)
        except Exception as e:
            logger.error("Failed to persist patterns: %s", e)

    def _load_state(self) -> None:
        out_file = self.storage_dir / "patterns.json"
        if out_file.exists():
            try:
                with open(out_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        p = EngineeringPattern.from_dict(item)
                        self._patterns[p.id] = p
                        if p.pattern_id:
                            self._patterns[p.pattern_id] = p
            except Exception as e:
                logger.warning("Could not load patterns: %s", e)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            all_pats = self.get_all_patterns()
            by_cat = {
                cat.value: sum(1 for p in all_pats if p.category == cat)
                for cat in PatternCategory
            }
            return {
                "total_patterns": len(all_pats),
                "by_category": by_cat,
                "patterns_by_category": by_cat,
                "top_pattern_ids": [p.id for p in self.get_top_patterns(5)],
                "patterns": [p.to_dict() for p in all_pats],
            }
