"""
core/reproducibility_manager.py - Deterministic Experiment Replication & Integrity Auditing (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import hashlib
import json
import os
import platform
import random
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ExperimentRunManifest:
    """Complete cryptographic and environmental manifest of an experiment execution."""
    manifest_id: str
    experiment_id: str
    seed: int
    config: Dict[str, Any]
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    execution_logs: List[str]
    system_environment: Dict[str, str]
    code_hash: str
    artifacts_checksum: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "experiment_id": self.experiment_id,
            "seed": self.seed,
            "config": self.config,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "execution_logs": self.execution_logs[-20:],
            "system_environment": self.system_environment,
            "code_hash": self.code_hash,
            "artifacts_checksum": self.artifacts_checksum,
            "created_at": self.created_at,
        }


@dataclass
class ReplayResult:
    """Outcome of replaying an experiment from its recorded manifest."""
    manifest_id: str
    is_exact_match: bool
    numerical_diff_max: float
    output_checksum_matches: bool
    replay_time_sec: float
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "is_exact_match": self.is_exact_match,
            "numerical_diff_max": round(self.numerical_diff_max, 8),
            "output_checksum_matches": self.output_checksum_matches,
            "replay_time_sec": round(self.replay_time_sec, 4),
            "details": self.details,
        }


class ReproducibilityManager:
    """
    Manages deterministic experiment manifests, computes SHA-256 integrity checksums,
    and replays historical experiments to guarantee strict scientific reproducibility.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._manifests: Dict[str, ExperimentRunManifest] = {}

    @staticmethod
    def compute_sha256(data: Any) -> str:
        """Deterministic SHA-256 hash of arbitrary JSON-serializable structure."""
        serialized = json.dumps(data, sort_keys=True, default=str).encode('utf-8')
        return hashlib.sha256(serialized).hexdigest()

    def record_manifest(
        self,
        experiment_id: str,
        seed: int,
        config: Dict[str, Any],
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        execution_logs: Optional[List[str]] = None,
        code_snippet: str = "",
    ) -> ExperimentRunManifest:
        """Constructs and stores an immutable scientific manifest for an experiment run."""
        with self._lock:
            man_id = f"MAN-{uuid.uuid4().hex[:8].upper()}"
            env_info = {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            }

            code_hash = hashlib.sha256(code_snippet.encode('utf-8')).hexdigest()
            artifacts_data = {"inputs": inputs, "outputs": outputs, "config": config}
            artifacts_checksum = self.compute_sha256(artifacts_data)

            manifest = ExperimentRunManifest(
                manifest_id=man_id,
                experiment_id=experiment_id,
                seed=seed,
                config=config,
                inputs=inputs,
                outputs=outputs,
                execution_logs=execution_logs or [],
                system_environment=env_info,
                code_hash=code_hash,
                artifacts_checksum=artifacts_checksum,
            )

            self._manifests[man_id] = manifest
            return manifest

    def get_manifest(self, manifest_id: str) -> Optional[ExperimentRunManifest]:
        with self._lock:
            return self._manifests.get(manifest_id)

    def replay_experiment(
        self,
        manifest_id: str,
        target_fn: Callable[[Dict[str, Any], Dict[str, Any], int], Dict[str, Any]],
        tolerance: float = 1e-5,
    ) -> ReplayResult:
        """
        Re-executes the target function using the manifest's recorded seed, config, and inputs.
        Verifies outputs against historical records within tolerance.
        """
        with self._lock:
            man = self._manifests.get(manifest_id)
            if not man:
                raise ValueError(f"Manifest '{manifest_id}' not found")

            t0 = time.perf_counter()
            # Set random seed
            random.seed(man.seed)

            # Re-execute target function
            replayed_outputs = target_fn(man.config, man.inputs, man.seed)
            t_elapsed = time.perf_counter() - t0

            # Compute checksum of replayed outputs
            replayed_checksum = self.compute_sha256({
                "inputs": man.inputs,
                "outputs": replayed_outputs,
                "config": man.config,
            })
            checksum_matches = (replayed_checksum == man.artifacts_checksum)

            # Evaluate numerical differences across common keys
            max_diff = 0.0
            is_exact = True
            mismatched_keys = []

            for key, val in man.outputs.items():
                if key not in replayed_outputs:
                    is_exact = False
                    mismatched_keys.append(f"Missing key: {key}")
                    continue

                r_val = replayed_outputs[key]
                if isinstance(val, (int, float)) and isinstance(r_val, (int, float)):
                    diff = abs(val - r_val)
                    if diff > max_diff:
                        max_diff = diff
                    if diff > tolerance:
                        is_exact = False
                        mismatched_keys.append(f"{key}: recorded={val}, replayed={r_val}, diff={diff}")
                else:
                    if val != r_val:
                        is_exact = False
                        mismatched_keys.append(f"{key}: {val} != {r_val}")

            details = "Exact deterministic replay achieved." if is_exact else f"Mismatches detected: {'; '.join(mismatched_keys)}"

            return ReplayResult(
                manifest_id=man.manifest_id,
                is_exact_match=is_exact,
                numerical_diff_max=max_diff,
                output_checksum_matches=checksum_matches,
                replay_time_sec=t_elapsed,
                details=details,
            )
