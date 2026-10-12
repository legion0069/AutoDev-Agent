"""
organization.py - Autonomous AI Organization Framework (AutoDev Version 3.4)

Master Autonomous AI Software Company Architecture:
Instead of one orchestrator... an entire autonomous software company!

Organization Hierarchy:
CEO
 ↓
CTO
 ↓
Engineering Manager
 ↓
16 Specialized AI Departments:
- Architecture Team
- Backend Team
- Frontend Team
- AI Team
- DevOps Team
- QA Team
- Security Team
- Documentation Team
- Release Manager
- Customer Feedback Team
- Business Analyst
- Product Manager
- Finance & Cost Estimator
- Compliance Team
- Operations Team

Subsystems Integrated:
1. Communication Bus (Event-driven prioritized messaging, correlation IDs, thread tracking)
2. Department Infrastructure (Roles, authority levels, capacities, health/performance scores)
3. Organization State (Persistent memory, searchable history, SHA-256 audit log)
4. Decision Engine (Consensus, weighted votes, evidence ranking, executive veto)
5. Conflict Resolver (Resource, task, architecture, merge, priority, ownership & security disputes)
6. Meeting Engine (Daily Standup, Sprint Planning, Reviews, Architecture, Security, Release, Retro)
7. Organization Metrics (Velocity, lead time, cycle time, utilization, defect rate, security score)
8. Simulation Mode (Full autonomous end-to-end software delivery pipeline)

100% Python Standard Library.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.conflict_resolver import ConflictResolver
from core.decision_engine import DecisionDomain, DecisionEngine
from core.department import Department, DepartmentAuthorityLevel, DepartmentRole
from core.meeting_manager import MeetingManager, MeetingType
from core.organization_metrics import OrganizationMetricsCalculator, OrganizationMetricsDashboard
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.Organization")


class EnterpriseOrganization:
    """
    Enterprise-scale Autonomous AI Software Company.
    Orchestrates 16+ specialized AI departments collaborating via structured messaging,
    autonomous meetings, consensus decisions, and automated conflict resolution.
    """

    def __init__(
        self,
        company_name: str = "AutoDev Autonomous Technologies Inc.",
        storage_dir: Optional[str | Path] = None,
        auto_persist: bool = True,
        initial_budget_usd: float = 500000.0,
    ) -> None:
        self._lock = threading.RLock()
        self.company_name = company_name
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/organization")
        self.initial_budget_usd = float(initial_budget_usd)
        self.auto_persist = auto_persist

        # 1. Core Enterprise Subsystems
        self.bus = CommunicationBus()
        self.state = OrganizationState(storage_dir=self.storage_dir, auto_persist=self.auto_persist)
        self.decision_engine = DecisionEngine(state=self.state)
        self.conflict_resolver = ConflictResolver(bus=self.bus)
        self.meeting_manager = MeetingManager(bus=self.bus, state=self.state)
        self.metrics_calculator = OrganizationMetricsCalculator()

        # 2. Departments Registry
        self.departments: Dict[str, Department] = {}
        self._init_departments()

        # 3. Agents Registry (Specialized AI department heads / teams)
        self.agents: Dict[str, Any] = {}
        self._init_agents()

        # Audit company initialization
        self.state.record_audit_event(
            actor="SYSTEM",
            action="INITIALIZE_ORGANIZATION",
            details={
                "company_name": self.company_name,
                "departments_count": len(self.departments),
                "budget_usd": self.initial_budget_usd,
            },
        )
        logger.info("EnterpriseOrganization '%s' initialized with %d departments.", self.company_name, len(self.departments))

    def _init_departments(self) -> None:
        """Initializes all 16 departments with hierarchical authority and budgets."""
        dept_configs = [
            # Executive & Management
            ("CEO", DepartmentRole.EXECUTIVE, DepartmentAuthorityLevel.EXECUTIVE, 100000.0, 10, 5, 2),
            ("CTO", DepartmentRole.EXECUTIVE, DepartmentAuthorityLevel.EXECUTIVE, 80000.0, 9, 8, 3),
            ("EngineeringManager", DepartmentRole.ENGINEERING_MANAGEMENT, DepartmentAuthorityLevel.MANAGERIAL, 50000.0, 8, 15, 4),
            ("ProductManager", DepartmentRole.PRODUCT_MANAGEMENT, DepartmentAuthorityLevel.MANAGERIAL, 40000.0, 8, 12, 3),
            ("BusinessAnalyst", DepartmentRole.BUSINESS_ANALYSIS, DepartmentAuthorityLevel.SPECIALIST, 30000.0, 7, 10, 3),

            # Engineering Core
            ("Architecture", DepartmentRole.ARCHITECTURE, DepartmentAuthorityLevel.DIRECTOR, 45000.0, 8, 8, 3),
            ("Backend", DepartmentRole.BACKEND, DepartmentAuthorityLevel.SPECIALIST, 60000.0, 7, 20, 6),
            ("Frontend", DepartmentRole.FRONTEND, DepartmentAuthorityLevel.SPECIALIST, 45000.0, 6, 15, 5),
            ("QA", DepartmentRole.QA, DepartmentAuthorityLevel.SPECIALIST, 35000.0, 7, 15, 4),
            ("Security", DepartmentRole.SECURITY, DepartmentAuthorityLevel.DIRECTOR, 40000.0, 9, 10, 3),
            ("DevOps", DepartmentRole.DEVOPS, DepartmentAuthorityLevel.SPECIALIST, 35000.0, 8, 12, 3),
            ("ReleaseManager", DepartmentRole.RELEASE_MANAGEMENT, DepartmentAuthorityLevel.MANAGERIAL, 30000.0, 8, 8, 2),

            # Operations, Governance & Business
            ("Documentation", DepartmentRole.DOCUMENTATION, DepartmentAuthorityLevel.OPERATIONAL, 20000.0, 5, 10, 2),
            ("CustomerFeedback", DepartmentRole.CUSTOMER_FEEDBACK, DepartmentAuthorityLevel.SPECIALIST, 25000.0, 6, 10, 3),
            ("Finance", DepartmentRole.FINANCE, DepartmentAuthorityLevel.MANAGERIAL, 30000.0, 8, 8, 2),
            ("Compliance", DepartmentRole.COMPLIANCE, DepartmentAuthorityLevel.DIRECTOR, 35000.0, 9, 8, 2),
            ("Operations", DepartmentRole.OPERATIONS, DepartmentAuthorityLevel.SPECIALIST, 30000.0, 8, 12, 3),
        ]

        for name, role, authority, budget, priority, capacity, headcount in dept_configs:
            dept = Department(
                name=name,
                role=role,
                authority=authority,
                bus=self.bus,
                budget=budget,
                priority=priority,
                capacity=capacity,
                headcount=headcount,
                dependencies=["CTO", "EngineeringManager"] if role in (DepartmentRole.BACKEND, DepartmentRole.FRONTEND) else [],
            )
            self.departments[name] = dept

    def _init_agents(self) -> None:
        """Instantiates and registers the 17 specialized AI agents."""
        try:
            from agents.ceo_agent import CEOAgent
            from agents.cto_agent import CTOAgent
            from agents.engineering_manager import EngineeringManagerAgent
            from agents.architect_agent import ArchitectAgent
            from agents.backend_team import BackendTeamAgent
            from agents.frontend_team import FrontendTeamAgent
            from agents.qa_manager import QAManagerAgent
            from agents.security_manager import SecurityManagerAgent
            from agents.devops_manager import DevOpsManagerAgent
            from agents.release_manager import ReleaseManagerAgent
            from agents.product_manager import ProductManagerAgent
            from agents.business_analyst import BusinessAnalystAgent
            from agents.documentation_manager import DocumentationManagerAgent
            from agents.customer_feedback_manager import CustomerFeedbackManagerAgent
            from agents.finance_manager import FinanceManagerAgent
            from agents.compliance_manager import ComplianceManagerAgent
            from agents.operations_manager import OperationsManagerAgent

            self.agents["CEO"] = CEOAgent(bus=self.bus, state=self.state)
            self.agents["CTO"] = CTOAgent(bus=self.bus, state=self.state)
            self.agents["EngineeringManager"] = EngineeringManagerAgent(bus=self.bus, state=self.state)
            self.agents["Architecture"] = ArchitectAgent(bus=self.bus, state=self.state)
            self.agents["Backend"] = BackendTeamAgent(bus=self.bus, state=self.state)
            self.agents["Frontend"] = FrontendTeamAgent(bus=self.bus, state=self.state)
            self.agents["QA"] = QAManagerAgent(bus=self.bus, state=self.state)
            self.agents["Security"] = SecurityManagerAgent(bus=self.bus, state=self.state)
            self.agents["DevOps"] = DevOpsManagerAgent(bus=self.bus, state=self.state)
            self.agents["ReleaseManager"] = ReleaseManagerAgent(bus=self.bus, state=self.state)
            self.agents["ProductManager"] = ProductManagerAgent(bus=self.bus, state=self.state)
            self.agents["BusinessAnalyst"] = BusinessAnalystAgent(bus=self.bus, state=self.state)
            self.agents["Documentation"] = DocumentationManagerAgent(bus=self.bus, state=self.state)
            self.agents["CustomerFeedback"] = CustomerFeedbackManagerAgent(bus=self.bus, state=self.state)
            self.agents["Finance"] = FinanceManagerAgent(bus=self.bus, state=self.state)
            self.agents["Compliance"] = ComplianceManagerAgent(bus=self.bus, state=self.state)
            self.agents["Operations"] = OperationsManagerAgent(bus=self.bus, state=self.state)
        except Exception as e:
            logger.debug("Agents lazy load note: %s", e)

    def get_department(self, name: str) -> Optional[Department]:
        """Retrieves department by name."""
        return self.departments.get(name)

    def get_agent(self, name: str) -> Optional[Any]:
        """Retrieves specialized agent by department name."""
        return self.agents.get(name)

    # -------------------------------------------------------------------------
    # Autonomous Company Simulation Lifecycle
    # -------------------------------------------------------------------------

    def simulate_company_workflow(
        self,
        customer_request: str = "Build a high-performance transactional payments API with JWT authentication and audit trails.",
        target_version: str = "3.4.0",
    ) -> Dict[str, Any]:
        """
        Simulates an entire autonomous software company lifecycle:
        1. Customer submits feature request
        2. Business Analyst decomposes to Epics, Stories, Acceptance Criteria, ROI
        3. Product Manager prioritizes into roadmap & sprint goal
        4. CEO reviews and grants executive budget approval
        5. CTO validates technology architecture & security standards
        6. Engineering Manager estimates capacity and assigns tasks
        7. Architect designs ADR & component interfaces
        8. Backend develops core implementation
        9. Frontend develops user interface components
        10. QA tests with regression & integration suites
        11. Security audits code, secrets, and OWASP policies
        12. DevOps prepares deployment plans & environment validations
        13. Release Manager collects approvals and triggers release
        14. Documentation Manager generates manuals and changelog
        15. Customer Feedback records delivery and updates CSAT
        16. Operations confirms health metrics and closes loop
        """
        with self._lock:
            start_time = time.time()
            stage_results: Dict[str, Any] = {}

            # Step 1: Customer Feedback ingestion
            req_id = self.state.record_customer_request({
                "title": "Customer Feature Request",
                "description": customer_request,
                "source": "Enterprise Client Portal",
                "status": "INGESTED",
            })
            stage_results["1_customer_ingestion"] = {"request_id": req_id, "status": "INGESTED"}

            # Step 2: Business Analyst Analysis
            ba_agent = self.get_agent("BusinessAnalyst")
            if ba_agent and hasattr(ba_agent, "analyze_customer_request"):
                ba_output = ba_agent.analyze_customer_request(customer_request)
            else:
                ba_output = {
                    "epic": "High-Performance Transactional Payments API",
                    "user_stories": [
                        "US-1: Tokenized Payment Gateway Endpoint",
                        "US-2: Idempotent Transaction Ledger",
                        "US-3: HMAC Audit Event Egress",
                    ],
                    "acceptance_criteria": [
                        "Given valid payment payload When POST /v1/payments Then return 201 Created",
                        "Given duplicate idempotency key When repeated Then return 200 with cached ledger ID",
                    ],
                    "estimated_roi": 3.8,
                    "business_risks": ["PCI-DSS compliance exposure", "Transient database lock contention"],
                }
            stage_results["2_business_analysis"] = ba_output

            # Step 3: Product Manager Prioritization
            pm_agent = self.get_agent("ProductManager")
            if pm_agent and hasattr(pm_agent, "define_sprint_goal"):
                pm_output = pm_agent.define_sprint_goal(ba_output["user_stories"])
            else:
                pm_output = {
                    "sprint_goal": "Deliver Production-Ready Payments API with Idempotency and Audit Logging",
                    "priority_tier": "CRITICAL_P0",
                    "customer_value_score": 94.5,
                    "target_milestone": "Q4-Payments-GA",
                }
            stage_results["3_product_management"] = pm_output

            # Step 4: CEO Strategic & Budget Approval
            ceo_agent = self.get_agent("CEO")
            if ceo_agent and hasattr(ceo_agent, "approve_budget"):
                ceo_approved, ceo_rationale = ceo_agent.approve_budget(25000.0, "EngineeringCore")
            else:
                ceo_approved = True
                ceo_rationale = "Strategic alignment verified. Approved $25,000 engineering allocation."
            stage_results["4_ceo_approval"] = {"approved": ceo_approved, "rationale": ceo_rationale}

            # Step 5: CTO Architecture & Tech Validation
            cto_agent = self.get_agent("CTO")
            if cto_agent and hasattr(cto_agent, "validate_technology_stack"):
                cto_validation = cto_agent.validate_technology_stack(["Python Standard Library", "FastAPI / Standard HTTP", "SQLite / PostgreSQL"])
            else:
                cto_validation = {
                    "approved": True,
                    "tech_stack": ["Python 3.12 Standard Library", "Deterministic Transaction Ledger"],
                    "governance_score": 96.0,
                }
            stage_results["5_cto_validation"] = cto_validation

            # Step 6: Engineering Manager Task Allocation
            em_agent = self.get_agent("EngineeringManager")
            if em_agent and hasattr(em_agent, "plan_sprint_allocation"):
                em_plan = em_agent.plan_sprint_allocation(ba_output["user_stories"], ["Backend", "Frontend", "QA"])
            else:
                em_plan = {
                    "allocated_tasks": {
                        "TASK-BE-01": {"team": "Backend", "title": "Implement Payment Processing Pipeline", "effort_h": 8.0},
                        "TASK-FE-01": {"team": "Frontend", "title": "Implement Payment Dashboard Widget", "effort_h": 6.0},
                        "TASK-QA-01": {"team": "QA", "title": "Build Integration Test Matrix", "effort_h": 4.0},
                    },
                    "team_capacity_healthy": True,
                }
            stage_results["6_engineering_allocation"] = em_plan

            # Step 7: Architecture Design & ADR
            arch_agent = self.get_agent("Architecture")
            if arch_agent and hasattr(arch_agent, "generate_adr"):
                adr_record = arch_agent.generate_adr(
                    title="Clean Layered Architecture for Payments API",
                    context="Scalable payment ledger with strict ACID idempotency and audit logs.",
                    decision="Adopt Domain-Driven Design with transactional outbox and zero external dependencies.",
                    consequences="Maximized reliability and deterministic testing with Python standard library.",
                )
            else:
                adr_record = {
                    "adr_id": "ADR-042",
                    "title": "Clean Layered Architecture for Payments API",
                    "decision": "Domain-Driven Design with Transactional Ledger",
                    "status": "RATIFIED",
                }
            self.state.record_architecture_decision(adr_record)
            stage_results["7_architecture_design"] = adr_record

            # Step 8: Backend Team Development
            be_agent = self.get_agent("Backend")
            if be_agent and hasattr(be_agent, "develop_endpoint"):
                be_output = be_agent.develop_endpoint({"path": "/v1/payments", "methods": ["POST", "GET"]})
            else:
                be_output = {
                    "endpoints_created": ["POST /v1/payments", "GET /v1/payments/{id}"],
                    "models_created": ["PaymentRequest", "PaymentResponse", "TransactionLedgerEntry"],
                    "status": "DEVELOPMENT_COMPLETE",
                }
            self.departments["Backend"].complete_task("TASK-BE-01", cost=2500.0)
            stage_results["8_backend_development"] = be_output

            # Step 9: Frontend Team Development
            fe_agent = self.get_agent("Frontend")
            if fe_agent and hasattr(fe_agent, "develop_component"):
                fe_output = fe_agent.develop_component({"name": "PaymentHistoryWidget"})
            else:
                fe_output = {
                    "components_created": ["PaymentModal", "TransactionStreamTable"],
                    "status": "UI_DEVELOPMENT_COMPLETE",
                }
            self.departments["Frontend"].complete_task("TASK-FE-01", cost=1800.0)
            stage_results["9_frontend_development"] = fe_output

            # Step 10: QA Testing & Quality Gates
            qa_agent = self.get_agent("QA")
            if qa_agent and hasattr(qa_agent, "evaluate_quality_gate"):
                qa_output = qa_agent.evaluate_quality_gate({"passed": 42, "failed": 0}, coverage_pct=94.5)
            else:
                qa_output = {
                    "tests_executed": 42,
                    "tests_passed": 42,
                    "test_coverage_pct": 94.5,
                    "quality_gate_status": "PASSED",
                }
            self.departments["QA"].complete_task("TASK-QA-01", cost=1200.0)
            stage_results["10_qa_verification"] = qa_output

            # Step 11: Security Audit
            sec_agent = self.get_agent("Security")
            if sec_agent and hasattr(sec_agent, "audit_code_security"):
                sec_output = sec_agent.audit_code_security(["def process_payment(req): pass"])
            else:
                sec_output = {
                    "vulnerabilities_found": 0,
                    "critical_cves": 0,
                    "secrets_detected": 0,
                    "security_score": 98.0,
                    "security_gate_status": "APPROVED",
                }
            stage_results["11_security_audit"] = sec_output

            # Step 12: DevOps Infrastructure & Deployment Readiness
            devops_agent = self.get_agent("DevOps")
            if devops_agent and hasattr(devops_agent, "generate_deployment_plan"):
                devops_output = devops_agent.generate_deployment_plan({"service": "PaymentsAPI", "version": target_version})
            else:
                devops_output = {
                    "deployment_strategy": "ROLLING_ZERO_DOWNTIME",
                    "health_check_endpoint": "/healthz",
                    "rollback_ready": True,
                    "infrastructure_status": "HEALTHY",
                }
            stage_results["12_devops_readiness"] = devops_output

            # Step 13: Release Management
            rel_agent = self.get_agent("ReleaseManager")
            if rel_agent and hasattr(rel_agent, "execute_release"):
                rel_output = rel_agent.execute_release(target_version)
            else:
                rel_output = {
                    "version": target_version,
                    "approvals": ["CEO", "CTO", "QA", "Security"],
                    "release_status": "DEPLOYED_TO_PRODUCTION",
                    "release_notes": f"AutoDev Version {target_version} Payments API GA Release",
                }
            self.state.record_release(rel_output)
            stage_results["13_release_execution"] = rel_output

            # Step 14: Documentation Generation
            doc_agent = self.get_agent("Documentation")
            if doc_agent and hasattr(doc_agent, "generate_api_documentation"):
                doc_output = doc_agent.generate_api_documentation(be_output.get("endpoints_created", []))
            else:
                doc_output = {
                    "manuals_generated": ["Payments API Developer Guide", "OpenAPI Specification"],
                    "changelog_updated": True,
                }
            stage_results["14_documentation"] = doc_output

            # Step 15: Customer Feedback & Satisfaction
            fb_agent = self.get_agent("CustomerFeedback")
            if fb_agent and hasattr(fb_agent, "ingest_feedback"):
                fb_output = fb_agent.ingest_feedback({
                    "csat_score": 95.0,
                    "feedback": "Feature delivered ahead of schedule with zero defect leakage.",
                })
            else:
                fb_output = {
                    "csat_score": 95.0,
                    "customer_sentiment": "HIGHLY_SATISFIED",
                    "roadmap_feedback_loop": "CLOSED",
                }
            stage_results["15_customer_feedback"] = fb_output

            # Step 16: Operations Closing Verification
            ops_agent = self.get_agent("Operations")
            if ops_agent and hasattr(ops_agent, "monitor_slas"):
                ops_output = ops_agent.monitor_slas({"uptime_pct": 99.99, "latency_p95_ms": 42.0})
            else:
                ops_output = {
                    "uptime_pct": 99.99,
                    "latency_p95_ms": 42.0,
                    "sla_status": "MET",
                }
            stage_results["16_operations"] = ops_output

            duration = round(time.time() - start_time, 3)

            # Generate organizational metrics dashboard
            dashboard = self.metrics_calculator.calculate_dashboard(
                departments=self.departments,
                releases_count=1,
                incidents_count=0,
                completed_tasks_count=3,
                failed_tasks_count=0,
                lead_time_hours=12.0,
                cycle_time_hours=3.5,
                security_findings_count=0,
                critical_cves_count=0,
            )

            # Record final audit event
            self.state.record_audit_event(
                actor="EnterpriseOrganization",
                action="COMPLETE_COMPANY_SIMULATION",
                details={
                    "version": target_version,
                    "duration_s": duration,
                    "stages_completed": len(stage_results),
                    "confidence": dashboard.delivery_confidence,
                },
            )

            return {
                "organization": self.company_name,
                "target_version": target_version,
                "simulation_status": "SUCCESS",
                "execution_duration_s": duration,
                "stages": stage_results,
                "metrics_dashboard": dashboard.to_dict(),
            }

    # -------------------------------------------------------------------------
    # Autonomous Corporate Meetings
    # -------------------------------------------------------------------------

    def conduct_corporate_meeting(
        self,
        meeting_type: MeetingType | str,
        title: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Conducts an autonomous corporate meeting across attendee departments."""
        mtype = MeetingType(meeting_type) if isinstance(meeting_type, str) else meeting_type
        all_attendees = attendees or list(self.departments.keys())[:8]

        # Gather real department reports
        dept_reports = {
            name: self.departments[name].get_status_report()
            for name in all_attendees
            if name in self.departments
        }

        default_title = f"{mtype.value.replace('_', ' ').title()} Session"
        minutes = self.meeting_manager.schedule_and_conduct_meeting(
            meeting_type=mtype,
            title=title or default_title,
            host="EngineeringManager" if mtype == MeetingType.DAILY_STANDUP else "CEO",
            attendees=all_attendees,
            department_reports=dept_reports,
        )
        return minutes.to_dict()

    def conduct_all_standard_meetings(self) -> List[Dict[str, Any]]:
        """Conducts the full suite of standard corporate meetings."""
        meeting_types = [
            MeetingType.DAILY_STANDUP,
            MeetingType.SPRINT_PLANNING,
            MeetingType.ARCHITECTURE_REVIEW,
            MeetingType.SECURITY_REVIEW,
            MeetingType.RELEASE_MEETING,
            MeetingType.SPRINT_REVIEW,
            MeetingType.RETROSPECTIVE,
            MeetingType.EXECUTIVE_REVIEW,
        ]
        return [self.conduct_corporate_meeting(mt) for mt in meeting_types]

    # -------------------------------------------------------------------------
    # Decision & Dispute Management
    # -------------------------------------------------------------------------

    def resolve_departmental_dispute(
        self,
        title: str,
        domain: DecisionDomain | str,
        options: List[str],
        voter_preferences: Dict[str, str],
        evidence_dict: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Creates a decision proposal, records votes, and determines winning choice."""
        pid = self.decision_engine.create_proposal(
            title=title,
            domain=domain,
            options=options,
            proposer=list(voter_preferences.keys())[0] if voter_preferences else "EngineeringManager",
        )
        evidence_map = evidence_dict or {}

        for voter, choice in voter_preferences.items():
            ev = evidence_map.get(voter, [f"Standard operational recommendation from {voter}"])
            self.decision_engine.cast_vote(
                proposal_id=pid,
                voter=voter,
                chosen_option=choice,
                confidence=0.92,
                evidence=ev,
            )

        return self.decision_engine.evaluate_decision(pid)

    # -------------------------------------------------------------------------
    # Organization Telemetry & Dashboard
    # -------------------------------------------------------------------------

    def get_organization_dashboard(self) -> Dict[str, Any]:
        """Synthesizes high-level corporate KPI dashboard."""
        dashboard = self.metrics_calculator.calculate_dashboard(
            departments=self.departments,
            releases_count=len(self.state.release_history) or 1,
            incidents_count=len(self.state.incidents),
            customer_requests_count=len(self.state.customer_requests),
            completed_tasks_count=sum(len(d.completed_tasks) for d in self.departments.values()),
            failed_tasks_count=sum(len(d.failed_tasks) for d in self.departments.values()),
        )
        return dashboard.to_dict()

    def get_organization_summary(self) -> Dict[str, Any]:
        """Returns structural hierarchy and department telemetry overview."""
        with self._lock:
            return {
                "company_name": self.company_name,
                "departments": {
                    name: dept.get_status_report()
                    for name, dept in self.departments.items()
                },
                "total_budget": sum(d.budget for d in self.departments.values()),
                "total_spent": sum(d.spent_budget for d in self.departments.values()),
                "total_headcount": sum(d.headcount for d in self.departments.values()),
                "bus_telemetry": self.bus.get_bus_telemetry(),
                "memory_summary": self.state.export_full_memory_dump(),
            }

    # Convenient alias
    run_simulation_cycle = simulate_company_workflow


# Backwards compatibility alias
Organization = EnterpriseOrganization
