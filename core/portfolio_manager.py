"""
portfolio_manager.py - Enterprise Portfolio Management System (AutoDev Version 3.5)

Manages multi-company project portfolios at enterprise scale:
- Tracks hundreds/thousands of concurrent strategic initiatives
- Evaluates ROI, Business Value, Risk, Strategic Alignment, Delivery Confidence
- Calculates Budget Variance, Schedule Variance, and Cost Performance Index (CPI)
- Automated portfolio rebalancing and priority ranking
- 100% Python Standard Library.
"""

from __future__ import annotations

import collections
import enum
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AutoDev.Federation.Portfolio")


class ProjectStatus(str, enum.Enum):
    """Lifecycle status of a portfolio project."""
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class PortfolioProject:
    """A strategic enterprise project spanning one or more companies."""
    project_id: str
    title: str
    lead_company_id: str
    participating_companies: List[str] = field(default_factory=list)
    strategic_theme: str = "Digital Transformation"
    estimated_roi: float = 3.5  # e.g., 3.5x return on investment
    business_value_score: float = 85.0  # 0 to 100
    strategic_alignment_score: float = 90.0  # 0 to 100
    risk_score: float = 20.0  # 0 (low risk) to 100 (high risk)
    allocated_budget_usd: float = 250000.0
    spent_budget_usd: float = 0.0
    planned_duration_days: float = 90.0
    actual_days_elapsed: float = 0.0
    delivery_confidence: float = 0.85  # 0.0 to 1.0
    status: ProjectStatus = ProjectStatus.PROPOSED
    milestones_total: int = 5
    milestones_completed: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def budget_variance_usd(self) -> float:
        """Positive indicates under budget, negative indicates cost overrun."""
        return self.allocated_budget_usd - self.spent_budget_usd

    @property
    def cost_performance_index(self) -> float:
        """Earned Value / Actual Cost ratio."""
        if self.spent_budget_usd <= 0:
            return 1.0
        earned_value = (self.milestones_completed / max(1, self.milestones_total)) * self.allocated_budget_usd
        return round(earned_value / self.spent_budget_usd, 2)

    @property
    def priority_score(self) -> float:
        """Composite priority score for portfolio ranking."""
        risk_factor = max(0.1, (100.0 - self.risk_score) / 100.0)
        return round((self.business_value_score * 0.4 + self.strategic_alignment_score * 0.4 + (self.estimated_roi * 10.0) * 0.2) * risk_factor, 2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if hasattr(self.status, "value") else self.status
        d["budget_variance_usd"] = self.budget_variance_usd
        d["cost_performance_index"] = self.cost_performance_index
        d["priority_score"] = self.priority_score
        return d


class PortfolioManager:
    """
    Coordinates global project portfolio across the enterprise federation.
    Tracks ROI, delivery risks, budgets, and strategic execution.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._projects: Dict[str, PortfolioProject] = {}

    def create_project(
        self,
        title: str,
        lead_company_id: str,
        participating_companies: Optional[List[str]] = None,
        strategic_theme: str = "Enterprise Scale",
        estimated_roi: float = 3.0,
        business_value: float = 80.0,
        strategic_alignment: float = 85.0,
        risk_score: float = 25.0,
        budget_usd: float = 200000.0,
        planned_duration_days: float = 60.0,
        milestones_total: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PortfolioProject:
        """Creates a new project in the enterprise portfolio."""
        with self._lock:
            pid = f"PRJ-{uuid.uuid4().hex[:8].upper()}"
            proj = PortfolioProject(
                project_id=pid,
                title=title,
                lead_company_id=lead_company_id,
                participating_companies=list(participating_companies or [lead_company_id]),
                strategic_theme=strategic_theme,
                estimated_roi=float(estimated_roi),
                business_value_score=float(business_value),
                strategic_alignment_score=float(strategic_alignment),
                risk_score=float(risk_score),
                allocated_budget_usd=float(budget_usd),
                planned_duration_days=float(planned_duration_days),
                milestones_total=max(1, int(milestones_total)),
                metadata=metadata or {},
            )
            self._projects[pid] = proj
            logger.info("Created portfolio project '%s': %s (Lead: %s)", pid, title, lead_company_id)
            return proj

    def update_progress(
        self,
        project_id: str,
        milestones_completed: Optional[int] = None,
        spent_budget_usd: Optional[float] = None,
        days_elapsed: Optional[float] = None,
        delivery_confidence: Optional[float] = None,
        status: Optional[ProjectStatus | str] = None,
    ) -> bool:
        """Updates delivery telemetry for an active project."""
        with self._lock:
            proj = self._projects.get(project_id)
            if not proj:
                return False

            if milestones_completed is not None:
                proj.milestones_completed = min(proj.milestones_total, max(0, milestones_completed))
                if proj.milestones_completed >= proj.milestones_total:
                    proj.status = ProjectStatus.COMPLETED
            if spent_budget_usd is not None:
                proj.spent_budget_usd = max(0.0, float(spent_budget_usd))
            if days_elapsed is not None:
                proj.actual_days_elapsed = max(0.0, float(days_elapsed))
            if delivery_confidence is not None:
                proj.delivery_confidence = max(0.0, min(1.0, float(delivery_confidence)))
            if status is not None:
                proj.status = ProjectStatus(status) if isinstance(status, str) else status

            # Auto-flag AT_RISK if confidence drops or budget heavily overrun
            if proj.delivery_confidence < 0.60 or proj.budget_variance_usd < -50000.0:
                if proj.status not in (ProjectStatus.COMPLETED, ProjectStatus.CANCELLED):
                    proj.status = ProjectStatus.AT_RISK

            return True

    def get_ranked_portfolio(self) -> List[PortfolioProject]:
        """Returns all projects ranked by priority score descending."""
        with self._lock:
            return sorted(self._projects.values(), key=lambda p: -p.priority_score)

    def get_portfolio_dashboard(self) -> Dict[str, Any]:
        """Synthesizes high-level executive dashboard across all portfolio projects."""
        with self._lock:
            total_projects = len(self._projects)
            if total_projects == 0:
                return {
                    "total_projects": 0,
                    "active_projects": 0,
                    "total_budget_usd": 0.0,
                    "total_spent_usd": 0.0,
                    "average_roi": 0.0,
                    "average_delivery_confidence": 1.0,
                    "portfolio_risk_index": 0.0,
                }

            total_budget = sum(p.allocated_budget_usd for p in self._projects.values())
            total_spent = sum(p.spent_budget_usd for p in self._projects.values())
            avg_roi = sum(p.estimated_roi for p in self._projects.values()) / total_projects
            avg_conf = sum(p.delivery_confidence for p in self._projects.values()) / total_projects
            avg_risk = sum(p.risk_score for p in self._projects.values()) / total_projects

            status_counts = collections.Counter(
                p.status.value if hasattr(p.status, "value") else str(p.status)
                for p in self._projects.values()
            )

            # Expected portfolio ROI value ($ return)
            expected_total_value = sum(p.allocated_budget_usd * p.estimated_roi for p in self._projects.values())

            return {
                "total_projects": total_projects,
                "active_projects": status_counts.get("ACTIVE", 0) + status_counts.get("ON_TRACK", 0) + status_counts.get("AT_RISK", 0),
                "status_breakdown": dict(status_counts),
                "total_allocated_budget_usd": round(total_budget, 2),
                "total_spent_budget_usd": round(total_spent, 2),
                "net_budget_variance_usd": round(total_budget - total_spent, 2),
                "expected_portfolio_return_usd": round(expected_total_value, 2),
                "average_roi_multiplier": round(avg_roi, 2),
                "average_delivery_confidence": round(avg_conf, 3),
                "portfolio_risk_index": round(avg_risk, 1),
                "top_strategic_projects": [
                    {"project_id": p.project_id, "title": p.title, "priority_score": p.priority_score, "lead": p.lead_company_id}
                    for p in self.get_ranked_portfolio()[:5]
                ],
            }
