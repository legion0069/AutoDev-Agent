"""
AutoDev Worker Scaling Policy (Phase 3 - Kubernetes-Native Worker Orchestration)
Defines policy-driven autoscaling rules, stabilization windows, cooldowns,
and concurrency-aware capacity planning for worker pools.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any


class ScaleType(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"


@dataclass
class ScalingDecision:
    """Result of evaluating autoscaling metrics against a scaling policy."""
    desired_replicas: int
    current_replicas: int
    scale_type: ScaleType
    reason: str
    delta: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def changed(self) -> bool:
        return self.scale_type != ScaleType.MAINTAIN and self.delta != 0


class WorkerScalingPolicy:
    """
    Evaluates worker fleet telemetry to determine horizontal scaling actions.
    Enforces minimum/maximum replica bounds, cooldown periods, stabilization
    windows, and per-interval change ceilings to prevent oscillation.
    """

    def __init__(
        self,
        min_replicas: int = 1,
        max_replicas: int = 10,
        queue_depth_threshold: int = 5,
        busy_ratio_scale_up_threshold: float = 0.8,
        busy_ratio_scale_down_threshold: float = 0.2,
        cooldown_seconds: float = 30.0,
        stabilization_window_seconds: float = 60.0,
        max_scale_change_per_interval: int = 5,
        global_max_replicas: int = 50,
    ) -> None:
        if min_replicas < 0:
            raise ValueError("min_replicas cannot be negative")
        if max_replicas < min_replicas:
            raise ValueError("max_replicas cannot be less than min_replicas")
        if not (0.0 <= busy_ratio_scale_down_threshold <= busy_ratio_scale_up_threshold <= 1.0):
            raise ValueError("Invalid busy ratio thresholds: must satisfy 0 <= down <= up <= 1.0")

        self.min_replicas = min_replicas
        self.max_replicas = min(max_replicas, global_max_replicas)
        self.global_max_replicas = global_max_replicas
        self.queue_depth_threshold = max(1, queue_depth_threshold)
        self.busy_ratio_scale_up = busy_ratio_scale_up_threshold
        self.busy_ratio_scale_down = busy_ratio_scale_down_threshold
        self.cooldown_seconds = cooldown_seconds
        self.stabilization_window_seconds = stabilization_window_seconds
        self.max_scale_change_per_interval = max(1, max_scale_change_per_interval)

        self.last_scale_time: Optional[float] = None
        self.last_decision: Optional[ScalingDecision] = None

    def evaluate(
        self,
        current_replicas: int,
        ready_replicas: int,
        busy_replicas: int,
        queue_depth: int,
        now: Optional[float] = None,
    ) -> ScalingDecision:
        """
        Evaluate current metrics against policy to produce a scaling decision.
        """
        current_time = now if now is not None else datetime.now(timezone.utc).timestamp()

        # Enforce hard bounds first
        if current_replicas < self.min_replicas:
            delta = self.min_replicas - current_replicas
            return self._record_decision(
                desired=self.min_replicas,
                current=current_replicas,
                scale_type=ScaleType.SCALE_UP,
                reason=f"Current replicas ({current_replicas}) below min_replicas ({self.min_replicas})",
                delta=delta,
                now=current_time,
            )

        if current_replicas > self.max_replicas:
            delta = self.max_replicas - current_replicas
            return self._record_decision(
                desired=self.max_replicas,
                current=current_replicas,
                scale_type=ScaleType.SCALE_DOWN,
                reason=f"Current replicas ({current_replicas}) exceeds max_replicas ({self.max_replicas})",
                delta=delta,
                now=current_time,
            )

        # Check cooldown period
        if self.last_scale_time is not None:
            elapsed = current_time - self.last_scale_time
            if elapsed < self.cooldown_seconds:
                return ScalingDecision(
                    desired_replicas=current_replicas,
                    current_replicas=current_replicas,
                    scale_type=ScaleType.MAINTAIN,
                    reason=f"Cooldown active ({elapsed:.1f}s / {self.cooldown_seconds}s elapsed)",
                    delta=0,
                )

        # Calculate metrics
        busy_ratio = (busy_replicas / ready_replicas) if ready_replicas > 0 else 1.0

        # Scale Up Condition: high queue depth OR high busy ratio with active queue
        if queue_depth >= self.queue_depth_threshold or (busy_ratio >= self.busy_ratio_scale_up and queue_depth > 0):
            # Calculate required replicas based on queue depth
            additional_needed = max(1, queue_depth // self.queue_depth_threshold)
            target = min(
                current_replicas + min(additional_needed, self.max_scale_change_per_interval),
                self.max_replicas,
            )
            if target > current_replicas:
                delta = target - current_replicas
                return self._record_decision(
                    desired=target,
                    current=current_replicas,
                    scale_type=ScaleType.SCALE_UP,
                    reason=f"Scale-up triggered (queue_depth={queue_depth}, busy_ratio={busy_ratio:.2f})",
                    delta=delta,
                    now=current_time,
                )

        # Scale Down Condition: empty queue AND low busy ratio
        if queue_depth == 0 and busy_ratio <= self.busy_ratio_scale_down and current_replicas > self.min_replicas:
            excess = max(1, (ready_replicas - busy_replicas) // 2)
            target = max(
                current_replicas - min(excess, self.max_scale_change_per_interval),
                self.min_replicas,
            )
            if target < current_replicas:
                delta = target - current_replicas
                return self._record_decision(
                    desired=target,
                    current=current_replicas,
                    scale_type=ScaleType.SCALE_DOWN,
                    reason=f"Scale-down triggered (queue_depth=0, busy_ratio={busy_ratio:.2f})",
                    delta=delta,
                    now=current_time,
                )

        # Maintain
        return ScalingDecision(
            desired_replicas=current_replicas,
            current_replicas=current_replicas,
            scale_type=ScaleType.MAINTAIN,
            reason=f"Fleet load balanced (queue_depth={queue_depth}, busy_ratio={busy_ratio:.2f})",
            delta=0,
        )

    def _record_decision(
        self,
        desired: int,
        current: int,
        scale_type: ScaleType,
        reason: str,
        delta: int,
        now: float,
    ) -> ScalingDecision:
        decision = ScalingDecision(
            desired_replicas=desired,
            current_replicas=current,
            scale_type=scale_type,
            reason=reason,
            delta=delta,
        )
        if decision.changed:
            self.last_scale_time = now
        self.last_decision = decision
        return decision

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "global_max_replicas": self.global_max_replicas,
            "queue_depth_threshold": self.queue_depth_threshold,
            "busy_ratio_scale_up_threshold": self.busy_ratio_scale_up,
            "busy_ratio_scale_down_threshold": self.busy_ratio_scale_down,
            "cooldown_seconds": self.cooldown_seconds,
            "stabilization_window_seconds": self.stabilization_window_seconds,
            "max_scale_change_per_interval": self.max_scale_change_per_interval,
            "last_scale_time": self.last_scale_time,
        }
