"""
AutoDev Version 2.7 - Predictive Failure Prevention & Quality Intelligence Benchmark Suite
Tests latency, memory efficiency, throughput, and incremental caching speedups across large codebases.
"""

import os
import sys
import time
import json
import statistics
from typing import Dict, List, Tuple

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.complexity_analyzer import ComplexityAnalyzer
from core.dependency_health import DependencyHealthAnalyzer
from core.duplication_detector import DuplicationDetector
from core.predictive_quality_engine import PredictiveQualityEngine
from core.quality_gate import QualityGate
from core.quality_models import QualityGatePolicy
from core.risk_predictor import RiskPredictor


def generate_synthetic_repo(num_modules: int, funcs_per_module: int) -> Dict[str, str]:
    """Generates synthetic multi-module repository with realistic code structures."""
    repo = {}
    for m in range(num_modules):
        lines = [
            f"# Module {m}",
            "import math",
            f"from pkg.module_{(m + 1) % max(1, num_modules)} import helper_func_{m}" if num_modules > 1 else "",
            "",
            f"class ServiceEngine_{m}:",
            f"    def __init__(self):",
            f"        self.config_val = {m}",
            f"        self.state = 'active'",
            "",
            f"    def get_status_{m}(self):",
            f"        return self.state",
            "",
        ]
        for f in range(funcs_per_module):
            lines.append(f"""
def func_{m}_{f}(x, y, z):
    total = 0
    if x > 10:
        for i in range(y):
            if i % 2 == 0:
                total += i * {f}
            else:
                total -= i
    elif x < 0:
        total = -1
    else:
        total = y + z
    return total + {m}
""")
        repo[f"pkg/module_{m}.py"] = "\n".join(lines)
    return repo


def run_benchmarks() -> Dict[str, any]:
    print("=" * 80)
    print(" AUTODEV v2.7 - PREDICTIVE QUALITY INTELLIGENCE BENCHMARK SUITE")
    print("=" * 80)

    results = {}

    # Benchmark 1: Complexity Analyzer Throughput
    print("\n[1/5] Benchmarking AST Complexity Analyzer Throughput...")
    analyzer = ComplexityAnalyzer()
    repo_medium = generate_synthetic_repo(num_modules=50, funcs_per_module=20) # 1,000 functions
    total_loc = sum(len(c.splitlines()) for c in repo_medium.values())

    t0 = time.perf_counter()
    for path, code in repo_medium.items():
        analyzer.analyze_source(code, file_path=path)
    t_comp = time.perf_counter() - t0

    funcs_per_sec = 1000 / t_comp
    loc_per_sec = total_loc / t_comp
    print(f"  -> Processed 1,000 functions ({total_loc} LOC) in {t_comp:.4f}s")
    print(f"  -> Complexity Throughput: {funcs_per_sec:.1f} functions/sec | {loc_per_sec:.1f} LOC/sec")
    results["complexity_analyzer"] = {
        "functions_count": 1000,
        "loc_count": total_loc,
        "duration_sec": round(t_comp, 4),
        "funcs_per_sec": round(funcs_per_sec, 1),
        "loc_per_sec": round(loc_per_sec, 1),
    }

    # Benchmark 2: Dependency Health & Structural Graph Analysis
    print("\n[2/5] Benchmarking Dependency Health & Topological Cycles...")
    dep_analyzer = DependencyHealthAnalyzer()
    t0 = time.perf_counter()
    dep_health = dep_analyzer.analyze_dependencies(repo_medium)
    t_dep = time.perf_counter() - t0
    print(f"  -> Analyzed graph of 50 modules in {t_dep:.4f}s")
    print(f"  -> Detected Cycles: {len(dep_health.circular_dependency_cycles)} | Instability: {dep_health.instability:.2f}")
    results["dependency_health"] = {
        "modules_count": 50,
        "duration_sec": round(t_dep, 4),
        "cycles_found": len(dep_health.circular_dependency_cycles),
        "instability": dep_health.instability,
    }

    # Benchmark 3: Duplication Detector Sliding Window Throughput
    print("\n[3/5] Benchmarking Sliding Window Token/AST Duplication Detector...")
    dup_detector = DuplicationDetector(min_token_length=15, similarity_threshold=0.85)
    t0 = time.perf_counter()
    dup_blocks = dup_detector.detect_duplicates(repo_medium)
    t_dup = time.perf_counter() - t0
    print(f"  -> Scanned 50 files for clone blocks in {t_dup:.4f}s")
    print(f"  -> Duplicate Blocks Discovered: {len(dup_blocks)}")
    results["duplication_detector"] = {
        "files_scanned": 50,
        "duration_sec": round(t_dup, 4),
        "duplicate_blocks": len(dup_blocks),
    }

    # Benchmark 4: Incremental SHA-256 Caching Latency & Speedup
    print("\n[4/5] Benchmarking Incremental SHA-256 Caching (Scale: 100 Modules / 2,000 Functions)...")
    repo_large = generate_synthetic_repo(num_modules=100, funcs_per_module=20) # 2,000 functions
    engine = PredictiveQualityEngine(workspace_path=".")

    # Cold run
    t0 = time.perf_counter()
    res_cold = engine.assess_workspace(files_content=repo_large)
    t_cold = time.perf_counter() - t0

    # Warm run (identical content)
    t0 = time.perf_counter()
    res_warm = engine.assess_workspace(files_content=repo_large)
    t_warm = time.perf_counter() - t0

    speedup = t_cold / max(1e-6, t_warm)
    print(f"  -> Cold Analysis (2,000 symbols): {t_cold:.4f}s")
    print(f"  -> Warm Analysis (Cache Hit):     {t_warm:.4f}s")
    print(f"  -> Cache Acceleration:            {speedup:.2f}x speedup ({((t_cold - t_warm)/t_cold)*100:.1f}% reduction)")
    results["caching_performance"] = {
        "modules_count": 100,
        "functions_count": 2000,
        "cold_duration_sec": round(t_cold, 4),
        "warm_duration_sec": round(t_warm, 4),
        "speedup_factor": round(speedup, 2),
        "latency_reduction_pct": round(((t_cold - t_warm) / t_cold) * 100, 1),
    }

    # Benchmark 5: End-to-End Scalability Evaluation (10, 50, 100, 200 modules)
    print("\n[5/5] Multi-Scale End-to-End Pipeline Evaluation...")
    scales = [10, 50, 100, 200]
    scale_benchmarks = []
    for count in scales:
        sub_repo = generate_synthetic_repo(num_modules=count, funcs_per_module=15)
        eng = PredictiveQualityEngine(workspace_path=".")
        t0 = time.perf_counter()
        assessment = eng.assess_workspace(files_content=sub_repo)
        t_duration = time.perf_counter() - t0
        print(f"  -> {count:>3} Modules ({count * 15:>4} Funcs | {assessment.total_sloc:>5} SLOC): {t_duration:.4f}s | Gate: {assessment.gate_result.status.value}")
        scale_benchmarks.append({
            "modules": count,
            "functions": count * 15,
            "sloc": assessment.total_sloc,
            "duration_sec": round(t_duration, 4),
            "gate_status": assessment.gate_result.status.value,
            "maintainability_index": round(assessment.overall_maintainability_index, 1),
        })
    results["scalability_ladder"] = scale_benchmarks

    print("\n" + "=" * 80)
    print(" BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 80)
    return results


if __name__ == "__main__":
    benchmark_data = run_benchmarks()
    out_file = os.path.join(os.path.dirname(__file__), "benchmark_results_v27.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)
    print(f"\nSaved raw benchmark data to {out_file}")
