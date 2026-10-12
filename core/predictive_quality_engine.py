"""
AutoDev Predictive Quality Engine (v2.7)
Master engine coordinating pre-code-generation quality intelligence,
deterministic complexity analysis, code duplication detection, dependency health,
predictive risk modeling, memory-based historical learning, and quality gate enforcement.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from core.complexity_analyzer import ComplexityAnalyzer
from core.dependency_health import DependencyHealthAnalyzer
from core.duplication_detector import DuplicationDetector
from core.quality_gate import QualityGate
from core.quality_models import (
    ComplexityMetrics,
    DependencyHealthMetrics,
    DuplicationBlock,
    PredictiveRiskScores,
    QualityAssessmentResult,
    QualityGatePolicy,
    QualityGateResult,
    QualityGateStatus,
    QualityIssue,
    QualityRiskCategory,
    QualitySeverity,
)
from core.quality_report import QualityReportGenerator
from core.quality_rules import DEFAULT_QUALITY_RULES, QualityRule
from core.risk_predictor import RiskPredictor

logger = logging.getLogger(__name__)


class PredictiveQualityEngine:
    """Master engine delivering pre-generation quality intelligence and failure prevention."""

    def __init__(
        self,
        workspace_path: str,
        gate_policy: Optional[QualityGatePolicy] = None,
        memory_manager: Optional[Any] = None,
        rules: Optional[List[QualityRule]] = None,
    ):
        self.workspace_path = os.path.realpath(os.path.abspath(workspace_path))
        self.gate_policy = gate_policy or QualityGatePolicy()
        self.memory_manager = memory_manager
        self.rules = rules or list(DEFAULT_QUALITY_RULES)

        self.complexity_analyzer = ComplexityAnalyzer()
        self.duplication_detector = DuplicationDetector()
        self.dependency_analyzer = DependencyHealthAnalyzer(self.workspace_path)
        self.risk_predictor = RiskPredictor()
        self.quality_gate = QualityGate(self.gate_policy)

        # In-memory cache for incremental analysis: file_path -> (sha256, ComplexityMetrics)
        self._file_cache: Dict[str, Tuple[str, ComplexityMetrics]] = {}
        self._ws_dup_cache: Dict[str, Tuple[List[DuplicationBlock], float]] = {}
        self._ws_dep_cache: Dict[str, Dict[str, DependencyHealthMetrics]] = {}

    def assess_workspace(
        self,
        files_content: Optional[Dict[str, str]] = None,
        task_id: Optional[str] = None,
        project_id: str = "default_project",
        impact_summary: Optional[Dict[str, Any]] = None,
        modified_files: Optional[List[str]] = None,
    ) -> QualityAssessmentResult:
        """
        Executes full pre-generation quality assessment pipeline over workspace or specified files.
        """
        start_time = time.perf_counter()

        # 1. Gather files content
        files = files_content or self._load_workspace_python_files()
        if not files:
            # Empty workspace fallback
            return QualityAssessmentResult(
                project_id=project_id,
                task_id=task_id,
            )

        # 2. Complexity Analysis (with incremental caching)
        file_complexities: Dict[str, ComplexityMetrics] = {}
        total_loc = 0
        total_sloc = 0
        sum_mi = 0.0
        max_cyclomatic = 1
        max_cognitive = 0
        max_nesting = 0
        max_call_chain = 0

        file_hashes: List[str] = []
        for rel_path, code_str in files.items():
            content_hash = hashlib.sha256(code_str.encode("utf-8")).hexdigest()
            file_hashes.append(f"{rel_path}:{content_hash}")
            if rel_path in self._file_cache and self._file_cache[rel_path][0] == content_hash:
                metrics = self._file_cache[rel_path][1]
            else:
                metrics = self.complexity_analyzer.analyze_source(code_str, file_path=rel_path)
                self._file_cache[rel_path] = (content_hash, metrics)

            file_complexities[rel_path] = metrics
            total_loc += metrics.loc
            total_sloc += metrics.sloc
            sum_mi += metrics.maintainability_index
            max_cyclomatic = max(max_cyclomatic, metrics.cyclomatic_complexity)
            max_cognitive = max(max_cognitive, metrics.cognitive_complexity)
            max_nesting = max(max_nesting, metrics.max_nesting_depth)
            max_call_chain = max(max_call_chain, metrics.longest_call_chain)

        avg_mi = round(sum_mi / len(files), 2) if files else 100.0

        complexity_summary = ComplexityMetrics(
            cyclomatic_complexity=max_cyclomatic,
            cognitive_complexity=max_cognitive,
            max_nesting_depth=max_nesting,
            longest_call_chain=max_call_chain,
            loc=total_loc,
            sloc=total_sloc,
            maintainability_index=avg_mi,
        )

        ws_hash = hashlib.sha256(";".join(sorted(file_hashes)).encode("utf-8")).hexdigest()

        # 3. Duplication Detection (with workspace-level cache)
        if ws_hash in self._ws_dup_cache:
            duplications, dup_percentage = self._ws_dup_cache[ws_hash]
        else:
            duplications, dup_percentage = self.duplication_detector.scan_files(files)
            self._ws_dup_cache[ws_hash] = (duplications, dup_percentage)

        # 4. Dependency Health Analysis (with workspace-level cache)
        if ws_hash in self._ws_dep_cache:
            dep_health_map = self._ws_dep_cache[ws_hash]
        else:
            dep_health_map = self.dependency_analyzer.analyze_workspace(files)
            self._ws_dep_cache[ws_hash] = dep_health_map
        # Select aggregate/worst metrics
        aggregate_dep_health = self._aggregate_dependency_health(dep_health_map)

        # 5. Query Historical Engineering Memory for Known Defect Patterns
        historical_patterns: List[str] = []
        historical_defect_count = 0
        if self.memory_manager:
            historical_patterns = self._query_historical_memories(modified_files or list(files.keys()))
            historical_defect_count = len(historical_patterns)

        # 6. Evaluate Declarative Quality Rules
        issues: List[QualityIssue] = []
        for rule in self.rules:
            context = {
                "workspace_path": self.workspace_path,
                "files_content": files,
                "file_complexities": file_complexities,
                "dependency_health": dep_health_map,
                "duplications": duplications,
            }
            # Per-file rule evaluation where applicable
            for rel_path, code_str in files.items():
                file_ctx = dict(context)
                file_ctx["file_path"] = rel_path
                file_ctx["source_code"] = code_str
                issues.extend(rule.evaluate(file_ctx))

        # Deduplicate issues by (rule_id, location)
        unique_issues: List[QualityIssue] = []
        seen_issue_keys: Set[str] = set()
        for issue in issues:
            loc_key = f"{issue.location.file_path}:{issue.location.start_line}" if issue.location else "ws"
            key = f"{issue.rule_id}:{loc_key}"
            if key not in seen_issue_keys:
                seen_issue_keys.add(key)
                unique_issues.append(issue)

        total_debt = sum(i.technical_debt_minutes for i in unique_issues)

        # 7. Predictive Risk Scores
        risk_scores = self.risk_predictor.predict_risks(
            complexity=complexity_summary,
            dependency_health=aggregate_dep_health,
            issues=unique_issues,
            impact_summary=impact_summary,
            historical_defects_count=historical_defect_count,
            modified_files=modified_files or list(files.keys()),
        )

        # 8. Quality Gate Evaluation
        gate_result = self.quality_gate.evaluate(
            complexity=complexity_summary,
            dependency_health=aggregate_dep_health,
            risk_scores=risk_scores,
            issues=unique_issues,
            duplication_percentage=dup_percentage,
        )

        # 9. Generate Heatmap Data (file_path -> risk_score)
        heatmap_data: Dict[str, float] = {}
        for f, m in file_complexities.items():
            f_issues = [i for i in unique_issues if i.location and i.location.file_path == f]
            f_score = min(
                1.0,
                (m.cyclomatic_complexity / 30.0) * 0.4
                + (1.0 - (m.maintainability_index / 100.0)) * 0.3
                + (len(f_issues) * 0.15),
            )
            heatmap_data[f] = round(f_score, 2)

        assessment = QualityAssessmentResult(
            project_id=project_id,
            task_id=task_id,
            analyzed_files_count=len(files),
            total_loc=total_loc,
            total_sloc=total_sloc,
            overall_maintainability_index=avg_mi,
            total_technical_debt_minutes=total_debt,
            complexity_summary=complexity_summary,
            dependency_health=aggregate_dep_health,
            duplications=duplications,
            duplication_percentage=dup_percentage,
            issues=unique_issues,
            risk_scores=risk_scores,
            gate_result=gate_result,
            historical_patterns_found=historical_patterns,
            heatmap_data=heatmap_data,
        )

        return assessment

    def assess_code(
        self,
        code_str: str,
        file_path: str = "snippet.py",
        task_id: Optional[str] = None,
        project_id: str = "snippet_project",
    ) -> QualityAssessmentResult:
        """Assesses a single source code snippet."""
        files = {file_path: code_str}
        return self.assess_workspace(files_content=files, task_id=task_id, project_id=project_id)

    def _load_workspace_python_files(self) -> Dict[str, str]:
        """Loads all Python source files in the workspace (excluding tests, venv, git)."""
        files: Dict[str, str] = {}
        for root, dirs, filenames in os.walk(self.workspace_path):
            # Prune hidden and virtual environment directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("venv", "env", "node_modules", "__pycache__", "build", "dist")
            ]
            for fname in filenames:
                if fname.endswith(".py"):
                    abs_p = os.path.join(root, fname)
                    rel_p = os.path.relpath(abs_p, self.workspace_path).replace("\\", "/")
                    try:
                        with open(abs_p, "r", encoding="utf-8", errors="replace") as f:
                            files[rel_p] = f.read()
                    except Exception as e:
                        logger.warning(f"Could not read {abs_p}: {e}")
        return files

    def _aggregate_dependency_health(
        self, dep_map: Dict[str, DependencyHealthMetrics]
    ) -> DependencyHealthMetrics:
        """Aggregates per-module dependency metrics into workspace-wide metric container."""
        if not dep_map:
            return DependencyHealthMetrics()

        all_cycles = []
        has_cycles = False
        max_ca = 0
        max_ce = 0
        max_instability = 0.0
        max_distance = 0.0
        is_god = False
        is_hub = False
        max_lcom4 = 1
        max_dit = 0

        for m, h in dep_map.items():
            if h.has_circular_dependencies:
                has_cycles = True
                all_cycles.extend(h.circular_dependency_cycles)
            max_ca = max(max_ca, h.afferent_coupling)
            max_ce = max(max_ce, h.efferent_coupling)
            max_instability = max(max_instability, h.instability)
            max_distance = max(max_distance, h.distance_main_sequence)
            if h.is_god_object:
                is_god = True
            if h.is_hub_module:
                is_hub = True
            max_lcom4 = max(max_lcom4, h.lack_of_cohesion_lcom4)
            max_dit = max(max_dit, h.depth_of_inheritance)

        return DependencyHealthMetrics(
            afferent_coupling=max_ca,
            efferent_coupling=max_ce,
            instability=max_instability,
            abstractness=0.0,
            distance_main_sequence=max_distance,
            has_circular_dependencies=has_cycles,
            circular_dependency_cycles=all_cycles,
            is_god_object=is_god,
            is_hub_module=is_hub,
            depth_of_inheritance=max_dit,
            lack_of_cohesion_lcom4=max_lcom4,
        )

    def _query_historical_memories(self, file_paths: Sequence[str]) -> List[str]:
        """Queries MemoryManager for past recorded defects, bugs, and failed repairs."""
        if not self.memory_manager:
            return []

        patterns: List[str] = []
        try:
            for f in file_paths:
                results = self.memory_manager.search(query=f, limit=3)
                for res in results:
                    entry = getattr(res, "entry", res)
                    desc = getattr(entry, "content", getattr(entry, "description", str(entry)))
                    patterns.append(f"Historic defect pattern for {f}: {desc[:100]}")
        except Exception as e:
            logger.debug(f"Memory search failed: {e}")
        return patterns
