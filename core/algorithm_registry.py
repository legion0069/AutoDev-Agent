"""
core/algorithm_registry.py - Discovered Algorithms Repository & Lifecycle Management (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import enum
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


class AlgorithmAdoptionStatus(str, enum.Enum):
    """Institutional adoption status of an algorithm."""
    EXPERIMENTAL = "EXPERIMENTAL"      # Newly synthesized or discovered
    CANDIDATE = "CANDIDATE"            # Validated in sandbox experiments
    BENCHMARKED = "BENCHMARKED"        # Formally tested against regression baseline
    APPROVED = "APPROVED"              # Ratified by Chief Scientist & CTO
    PRODUCTION = "PRODUCTION"          # Integrated into active production systems
    DEPRECATED = "DEPRECATED"          # Superseded by superior algorithm
    RETIRED = "RETIRED"                # Preserved for historical archives only


class AlgorithmDomain(str, enum.Enum):
    """Domain categorization for algorithmic applications."""
    SYSTEMS = "SYSTEMS"
    MACHINE_LEARNING = "MACHINE_LEARNING"
    GRAPH = "GRAPH"
    OPTIMIZATION = "OPTIMIZATION"
    DISTRIBUTED = "DISTRIBUTED"
    SECURITY = "SECURITY"
    DATABASE = "DATABASE"
    REASONING = "REASONING"


@dataclass
class AlgorithmRecord:
    """Complete metadata and empirical record for an enterprise algorithm."""
    algorithm_id: str
    name: str
    domain: AlgorithmDomain
    version: str = "1.0.0"
    author: str = "PrincipalResearcher"
    creation_date: float = field(default_factory=time.time)
    description: str = ""
    specification: str = ""             # Mathematical spec or pseudocode
    time_complexity: str = "O(N)"
    space_complexity: str = "O(1)"
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    benchmark_history: List[Dict[str, Any]] = field(default_factory=list)
    success_rate: float = 100.0         # Empirical success rate [0.0 - 100.0]
    regression_risk: float = 0.05       # Estimated risk score [0.0 - 1.0]
    adoption_status: AlgorithmAdoptionStatus = AlgorithmAdoptionStatus.EXPERIMENTAL
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    status_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm_id": self.algorithm_id,
            "name": self.name,
            "domain": self.domain.value,
            "version": self.version,
            "author": self.author,
            "creation_date": self.creation_date,
            "description": self.description,
            "specification": self.specification,
            "time_complexity": self.time_complexity,
            "space_complexity": self.space_complexity,
            "performance_metrics": self.performance_metrics,
            "benchmark_history": self.benchmark_history[-10:],
            "success_rate": round(self.success_rate, 2),
            "regression_risk": round(self.regression_risk, 4),
            "adoption_status": self.adoption_status.value,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }


class AlgorithmRegistry:
    """
    Registry maintaining all discovered, benchmarked, and productionized algorithms
    across the enterprise research ecosystem.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._algorithms: Dict[str, AlgorithmRecord] = {}
        self._name_index: Dict[str, str] = {}  # name.lower() -> algorithm_id
        self._domain_index: Dict[str, Set[str]] = {}

    def register_algorithm(
        self,
        name: str,
        domain: AlgorithmDomain,
        description: str,
        specification: str,
        time_complexity: str = "O(N)",
        space_complexity: str = "O(1)",
        performance_metrics: Optional[Dict[str, float]] = None,
        author: str = "ResearchEngineer",
        adoption_status: AlgorithmAdoptionStatus = AlgorithmAdoptionStatus.EXPERIMENTAL,
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> AlgorithmRecord:
        """Registers a newly discovered or synthesized algorithm."""
        with self._lock:
            alg_id = f"ALG-{uuid.uuid4().hex[:8].upper()}"
            rec = AlgorithmRecord(
                algorithm_id=alg_id,
                name=name,
                domain=domain,
                version=version,
                author=author,
                description=description,
                specification=specification,
                time_complexity=time_complexity,
                space_complexity=space_complexity,
                performance_metrics=performance_metrics or {},
                adoption_status=adoption_status,
                tags=tags or [],
                status_history=[{
                    "timestamp": time.time(),
                    "status": adoption_status.value,
                    "rationale": "Initial registration",
                }],
            )

            self._algorithms[alg_id] = rec
            self._name_index[name.lower()] = alg_id
            self._domain_index.setdefault(domain.value, set()).add(alg_id)
            return rec

    def get_algorithm(self, algorithm_id: str) -> Optional[AlgorithmRecord]:
        with self._lock:
            return self._algorithms.get(algorithm_id)

    def get_by_name(self, name: str) -> Optional[AlgorithmRecord]:
        with self._lock:
            aid = self._name_index.get(name.lower())
            return self._algorithms.get(aid) if aid else None

    def update_status(
        self,
        algorithm_id: str,
        new_status: AlgorithmAdoptionStatus,
        rationale: str = "",
    ) -> bool:
        """Transitions algorithm adoption state across lifecycle gates."""
        with self._lock:
            rec = self._algorithms.get(algorithm_id)
            if not rec:
                return False

            rec.adoption_status = new_status
            rec.status_history.append({
                "timestamp": time.time(),
                "status": new_status.value,
                "rationale": rationale,
            })
            return True

    def record_benchmark(
        self,
        algorithm_id: str,
        metric_name: str,
        value: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Appends a new empirical benchmark data point to an algorithm's record."""
        with self._lock:
            rec = self._algorithms.get(algorithm_id)
            if not rec:
                return False

            rec.performance_metrics[metric_name] = value
            entry = {
                "timestamp": time.time(),
                "metric": metric_name,
                "value": value,
                "details": details or {},
            }
            rec.benchmark_history.append(entry)
            return True

    def compare_algorithms(self, id_a: str, id_b: str) -> Dict[str, Any]:
        """Provides side-by-side comparison of two algorithms."""
        with self._lock:
            rec_a = self._algorithms.get(id_a)
            rec_b = self._algorithms.get(id_b)
            if not rec_a or not rec_b:
                return {"error": "One or both algorithms not found"}

            all_metrics = set(rec_a.performance_metrics.keys()).union(set(rec_b.performance_metrics.keys()))
            comparisons = {}
            for m in all_metrics:
                val_a = rec_a.performance_metrics.get(m)
                val_b = rec_b.performance_metrics.get(m)
                delta = (val_b - val_a) if (val_a is not None and val_b is not None) else None
                comparisons[m] = {"a": val_a, "b": val_b, "delta_b_minus_a": delta}

            return {
                "algorithm_a": {"id": rec_a.algorithm_id, "name": rec_a.name, "status": rec_a.adoption_status.value},
                "algorithm_b": {"id": rec_b.algorithm_id, "name": rec_b.name, "status": rec_b.adoption_status.value},
                "metric_comparison": comparisons,
                "complexity_comparison": {
                    "time": {"a": rec_a.time_complexity, "b": rec_b.time_complexity},
                    "space": {"a": rec_a.space_complexity, "b": rec_b.space_complexity},
                },
            }

    def list_algorithms(
        self,
        domain: Optional[AlgorithmDomain] = None,
        status: Optional[AlgorithmAdoptionStatus] = None,
        tag: Optional[str] = None,
    ) -> List[AlgorithmRecord]:
        """Filters algorithms by domain, status, or tag."""
        with self._lock:
            results = list(self._algorithms.values())
            if domain:
                results = [r for r in results if r.domain == domain]
            if status:
                results = [r for r in results if r.adoption_status == status]
            if tag:
                t_lower = tag.lower()
                results = [r for r in results if any(t_lower == t.lower() for t in r.tags)]
            return results

    def recommend_algorithm(
        self,
        domain: AlgorithmDomain,
        target_metric: str = "LATENCY",
        lower_is_better: bool = True,
    ) -> Optional[AlgorithmRecord]:
        """Recommends the highest-performing approved or production algorithm in a domain."""
        with self._lock:
            candidates = [
                r for r in self._algorithms.values()
                if r.domain == domain and r.adoption_status in (AlgorithmAdoptionStatus.APPROVED, AlgorithmAdoptionStatus.PRODUCTION)
            ]
            if not candidates:
                # Fallback to candidate/benchmarked
                candidates = [r for r in self._algorithms.values() if r.domain == domain]

            if not candidates:
                return None

            def metric_key(r: AlgorithmRecord) -> float:
                val = r.performance_metrics.get(target_metric)
                if val is None:
                    return float('inf') if lower_is_better else -float('inf')
                return val

            candidates.sort(key=metric_key, reverse=not lower_is_better)
            return candidates[0]
