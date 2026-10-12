"""
executive_engine.py - Executive Decision Engine & C-Suite Governance for AutoDev (v3.0)

Coordinates C-suite executives, strategic business goals, multi-signoff decision matrices,
budget authorizations, risk assessments, and executive veto policies.
"""

from __future__ import annotations

import copy
import hashlib
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    DecisionStatus,
    DepartmentType,
    ExecutiveDecision,
    ExecutiveProfile,
    ExecutiveRole,
    StrategicGoal,
)

logger = logging.getLogger("AutoDev.Enterprise.Executive")


class ExecutiveDecisionEngine:
    """
    Authoritative Executive Decision Engine orchestrating C-suite decisions,
    budget signoffs, strategic goal alignment, and corporate governance.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executives: Dict[ExecutiveRole, ExecutiveProfile] = {}
        self._decisions: Dict[str, ExecutiveDecision] = {}
        self._strategic_goals: Dict[str, StrategicGoal] = {}
        self._decision_audit_log: List[Dict[str, Any]] = []
        
        self._init_default_c_suite()

    def _init_default_c_suite(self) -> None:
        """Initializes the complete standard C-suite and executive director profiles."""
        exec_specs = [
            (ExecutiveRole.CEO, "Chief Executive Officer", "Elena Rostova", DepartmentType.EXECUTIVE, 
             ["Corporate Strategy", "Company Vision", "Investor Relations"], ["ALL"], 5000000.0, 0.7),
            (ExecutiveRole.CTO, "Chief Technology Officer", "Marcus Vance", DepartmentType.ARCHITECTURE,
             ["Tech Architecture", "Technology Strategy", "Platform Evolution"], ["ARCHITECTURE", "TECHNOLOGY", "SECURITY"], 2000000.0, 0.6),
            (ExecutiveRole.VP_PRODUCT, "VP of Product Management", "Sarah Chen", DepartmentType.PRODUCT,
             ["Product Vision", "Roadmap Prioritization", "Market Fit"], ["PRODUCT_ROADMAP", "FEATURE_SCOPE"], 1000000.0, 0.65),
            (ExecutiveRole.VP_ENGINEERING, "VP of Engineering", "David Kim", DepartmentType.ENGINEERING,
             ["Engineering Execution", "Team Scaling", "Delivery Velocity"], ["ENGINEERING_HIRES", "TECH_STACK"], 1500000.0, 0.5),
            (ExecutiveRole.DIRECTOR_ENGINEERING, "Director of Engineering", "Alex Rivera", DepartmentType.ENGINEERING,
             ["Sprint Delivery", "Code Quality", "Engineering Operations"], ["SPRINT_PLANNING", "WORKLOAD"], 500000.0, 0.5),
            (ExecutiveRole.DIRECTOR_QA, "Director of Quality Assurance", "Priya Sharma", DepartmentType.QA,
             ["Test Automation", "Release Quality Gates", "Defect Prevention"], ["RELEASE_GATE", "TEST_STRATEGY"], 300000.0, 0.2),
            (ExecutiveRole.DIRECTOR_SECURITY, "Director of Information Security", "Viktor Stone", DepartmentType.SECURITY,
             ["Cybersecurity", "Compliance Auditing", "Threat Modeling"], ["SECURITY_VETO", "COMPLIANCE"], 500000.0, 0.1),
            (ExecutiveRole.DIRECTOR_PLATFORM, "Director of Platform Engineering", "Liam O'Connor", DepartmentType.ENGINEERING,
             ["Core Services", "Developer Platform", "Internal Tooling"], ["PLATFORM_STANDARDS"], 400000.0, 0.4),
            (ExecutiveRole.DIRECTOR_DEVOPS, "Director of DevOps & SRE", "Rachel Green", DepartmentType.DEVOPS,
             ["Infrastructure Reliability", "CI/CD Pipelines", "Incident Response"], ["DEPLOYMENT_APPROVAL"], 500000.0, 0.3),
            (ExecutiveRole.DIRECTOR_DOCUMENTATION, "Director of Technical Documentation", "Arthur Pendelton", DepartmentType.DOCUMENTATION,
             ["Developer Docs", "API Specifications", "User Guides"], ["DOC_STANDARDS"], 150000.0, 0.6),
            (ExecutiveRole.DIRECTOR_CUSTOMER_SUCCESS, "Director of Customer Success", "Maya Lin", DepartmentType.CUSTOMER_SUPPORT,
             ["Customer Satisfaction", "Support Escalations", "CSAT KPIs"], ["SUPPORT_SLA"], 300000.0, 0.5),
            (ExecutiveRole.DIRECTOR_ANALYTICS, "Director of Business Analytics", "Dr. Jonathan Hayes", DepartmentType.ANALYTICS,
             ["Product Analytics", "DORA Metrics", "Business Intelligence"], ["ANALYTICS_STANDARDS"], 250000.0, 0.7),
            (ExecutiveRole.DIRECTOR_FINANCE, "Director of Finance", "Hannah Abbott", DepartmentType.FINANCE,
             ["Budget Allocation", "Cost Optimization", "Financial Forecasting"], ["BUDGET_APPROVAL", "FINANCE_VETO"], 3000000.0, 0.2),
            (ExecutiveRole.DIRECTOR_HR, "Director of Human Resources", "Carlos Mendez", DepartmentType.HR,
             ["Headcount Planning", "Hiring Execution", "Performance Reviews"], ["COMPENSATION", "PROMOTIONS"], 400000.0, 0.4),
            (ExecutiveRole.LEGAL_COUNSEL, "General Legal Counsel", "Evelyn Cross", DepartmentType.LEGAL,
             ["Regulatory Compliance", "IP Protection", "Vendor Contracts"], ["LEGAL_VETO", "POLICY_APPROVAL"], 500000.0, 0.1),
        ]

        for role, title, name, dept, resps, auths, budget, risk in exec_specs:
            self._executives[role] = ExecutiveProfile(
                role=role,
                title=title,
                name=name,
                department=dept,
                responsibilities=resps,
                decision_authority=auths,
                budget_authority_usd=budget,
                risk_tolerance=risk,
                strategic_priorities=[f"Excellence in {dept.value}"],
                kpis={"strategic_delivery_rate": 95.0, "budget_adherence": 98.0},
            )

    def get_executive(self, role: ExecutiveRole) -> Optional[ExecutiveProfile]:
        """Retrieves an executive profile."""
        with self._lock:
            return copy.deepcopy(self._executives.get(role))

    def list_executives(self) -> List[ExecutiveProfile]:
        """Lists all registered executives."""
        with self._lock:
            return [copy.deepcopy(e) for e in self._executives.values()]

    def update_executive_kpis(self, role: ExecutiveRole, kpis: Dict[str, float]) -> Optional[ExecutiveProfile]:
        """Updates KPI telemetry for an executive."""
        with self._lock:
            exec_profile = self._executives.get(role)
            if not exec_profile:
                return None
            exec_profile.kpis.update(kpis)
            return copy.deepcopy(exec_profile)

    def create_strategic_goal(
        self,
        goal_id: str,
        title: str,
        description: str,
        target_quarter: str = "Q1",
        target_year: int = 2026,
        owner_role: ExecutiveRole = ExecutiveRole.CEO,
        target_metric: str = "ARR_USD",
        target_value: float = 1000000.0,
    ) -> StrategicGoal:
        """Registers a new corporate strategic goal."""
        with self._lock:
            goal = StrategicGoal(
                goal_id=goal_id,
                title=title,
                description=description,
                target_quarter=target_quarter,
                target_year=target_year,
                owner_role=owner_role,
                target_metric=target_metric,
                target_value=target_value,
                current_value=0.0,
            )
            self._strategic_goals[goal_id] = goal
            logger.info("Strategic Goal recorded: %s (Target: %s %s)", title, target_value, target_metric)
            return copy.deepcopy(goal)

    def set_strategic_goal(self, goal: StrategicGoal) -> None:
        """Registers or updates a corporate strategic goal object."""
        with self._lock:
            self._strategic_goals[goal.goal_id] = copy.deepcopy(goal)

    def get_strategic_goal(self, goal_id: str) -> Optional[StrategicGoal]:
        """Retrieves a single strategic goal by ID."""
        with self._lock:
            return copy.deepcopy(self._strategic_goals.get(goal_id))

    def update_strategic_goal_progress(self, goal_id: str, current_value: float) -> Optional[StrategicGoal]:
        """Updates progress on a corporate strategic goal."""
        with self._lock:
            goal = self._strategic_goals.get(goal_id)
            if not goal:
                return None
            goal.current_value = current_value
            if goal.current_value >= goal.target_value:
                goal.status = "COMPLETED"
            return copy.deepcopy(goal)

    def list_strategic_goals(self) -> List[StrategicGoal]:
        """Returns all strategic corporate goals."""
        with self._lock:
            return [copy.deepcopy(g) for g in self._strategic_goals.values()]

    def propose_decision(
        self,
        title: str,
        description: str,
        proposer: Optional[ExecutiveRole] = None,
        required_signoffs: Optional[List[ExecutiveRole]] = None,
        proposer_role: Optional[ExecutiveRole] = None,
        budget_impact_usd: float = 0.0,
        risk_score: float = 15.0,
        strategic_alignment_score: float = 90.0,
    ) -> ExecutiveDecision:
        """
        Submits an executive proposal into the corporate decision pipeline.
        Automatically determines required signoffs based on budget thresholds and domains.
        """
        actual_proposer = proposer_role or proposer or ExecutiveRole.CEO
        with self._lock:
            d_id = f"DEC-{int(time.time()*1000)}-{len(self._decisions)+1:03d}"
            
            # Default signoffs based on proposal impact
            signoffs = set(required_signoffs or [actual_proposer])
            exec_profile = self._executives.get(actual_proposer)
            if exec_profile and budget_impact_usd > exec_profile.budget_authority_usd:
                signoffs.add(ExecutiveRole.DIRECTOR_FINANCE)
                signoffs.add(ExecutiveRole.CEO)
            elif budget_impact_usd > 100000.0:
                signoffs.add(ExecutiveRole.DIRECTOR_FINANCE)
            if budget_impact_usd > 500000.0:
                signoffs.add(ExecutiveRole.CEO)
            if risk_score > 50.0:
                signoffs.add(ExecutiveRole.DIRECTOR_SECURITY)
                signoffs.add(ExecutiveRole.LEGAL_COUNSEL)

            init_status = DecisionStatus.PROPOSED
            decision = ExecutiveDecision(
                decision_id=d_id,
                title=title,
                description=description,
                proposer_role=actual_proposer,
                required_signoffs=list(signoffs),
                signoffs_received={actual_proposer.value: True},
                budget_impact_usd=budget_impact_usd,
                risk_score=risk_score,
                strategic_alignment_score=strategic_alignment_score,
                status=init_status,
                audit_trail=[{
                    "action": "PROPOSED",
                    "role": actual_proposer.value,
                    "timestamp": time.time(),
                    "note": "Decision proposed",
                }]
            )

            self._decisions[d_id] = decision
            logger.info("Executive proposal %s submitted by %s: '%s'", d_id, actual_proposer.value, title)
            return copy.deepcopy(decision)

    def signoff_decision(
        self,
        decision_id: str,
        role: Optional[ExecutiveRole] = None,
        approved: bool = True,
        notes: str = "",
        voter_role: Optional[ExecutiveRole] = None,
    ) -> ExecutiveDecision:
        """Records an executive signoff or rejection on a proposed decision."""
        actual_role = role or voter_role or ExecutiveRole.CEO
        with self._lock:
            dec = self._decisions.get(decision_id)
            if not dec:
                raise ValueError(f"Decision {decision_id} not found")

            now = time.time()
            dec.signoffs_received[actual_role.value] = approved
            
            dec.audit_trail.append({
                "action": "SIGN_OFF" if approved else "REJECT",
                "role": actual_role.value,
                "approved": approved,
                "notes": notes,
                "timestamp": now,
            })

            if not approved:
                dec.status = DecisionStatus.REJECTED
                dec.decided_at = now
                return copy.deepcopy(dec)

            # Check if all required signoffs are satisfied
            all_signed = all(
                dec.signoffs_received.get(req.value, False)
                for req in dec.required_signoffs
            )

            if all_signed:
                dec.status = DecisionStatus.APPROVED
                dec.decided_at = now
                logger.info("Decision %s fully APPROVED by required C-suite consensus", decision_id)
            else:
                dec.status = DecisionStatus.IN_REVIEW

            return copy.deepcopy(dec)

    vote_on_decision = signoff_decision

    def veto_decision(
        self,
        decision_id: str,
        veto_role: ExecutiveRole,
        reason: str,
    ) -> ExecutiveDecision:
        """Executes an authoritative veto by an authorized executive (Security, Legal, Finance, CEO)."""
        with self._lock:
            dec = self._decisions.get(decision_id)
            if not dec:
                raise ValueError(f"Decision {decision_id} not found")

            now = time.time()
            dec.status = DecisionStatus.VETOED
            dec.veto_role = veto_role
            dec.decided_at = now
            dec.audit_trail.append({
                "action": "VETO",
                "role": veto_role.value,
                "notes": reason,
                "timestamp": now,
            })
            logger.warning("Decision %s VETOED by %s: %s", decision_id, veto_role.value, reason)
            return copy.deepcopy(dec)

    def get_decision(self, decision_id: str) -> Optional[ExecutiveDecision]:
        """Retrieves a single decision by ID."""
        with self._lock:
            return copy.deepcopy(self._decisions.get(decision_id))

    def list_decisions(self, status: Optional[DecisionStatus] = None) -> List[ExecutiveDecision]:
        """Lists decisions, optionally filtered by status."""
        with self._lock:
            if status is None:
                return [copy.deepcopy(d) for d in self._decisions.values()]
            return [copy.deepcopy(d) for d in self._decisions.values() if d.status == status]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes executive engine state."""
        with self._lock:
            return {
                "executives": {r.value: e.to_dict() for r, e in self._executives.items()},
                "decisions": {k: d.to_dict() for k, d in self._decisions.items()},
                "strategic_goals": {k: g.to_dict() for k, g in self._strategic_goals.items()},
                "total_decisions": len(self._decisions),
            }
