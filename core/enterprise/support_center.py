"""
support_center.py - Customer Support & Incident Management for AutoDev (v3.0)

Handles customer-facing inquiries, bug reports, feature requests, incidents,
priority routing (P0-P3), SLA countdowns, CSAT scoring, root cause analysis (RCA),
and automatic generation of engineering tickets.
"""

from __future__ import annotations

import collections
import copy
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    SupportTicket,
    TeamType,
    TicketPriority,
    TicketType,
)

logger = logging.getLogger("AutoDev.Enterprise.Support")

# SLA deadlines in seconds by priority
SLA_SECONDS: Dict[TicketPriority, float] = {
    TicketPriority.P0_CRITICAL: 3600.0,      # 1 Hour
    TicketPriority.P1_HIGH: 14400.0,         # 4 Hours
    TicketPriority.P2_MEDIUM: 86400.0,       # 24 Hours
    TicketPriority.P3_LOW: 259200.0,         # 72 Hours
}


class SupportCenter:
    """
    Autonomous Customer Support & Incident Management Center.
    Triages incoming tickets, enforces SLAs, triggers engineering bugs, and measures CSAT.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tickets: Dict[str, SupportTicket] = {}
        self._rca_logs: Dict[str, Dict[str, Any]] = {}  # ticket_id -> RCA details
        self._on_engineering_task_created: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_engineering_task_hook(self, hook: Callable[[Dict[str, Any]], None]) -> None:
        """Sets a callback hook when an engineering ticket is auto-generated."""
        with self._lock:
            self._on_engineering_task_created = hook

    def submit_ticket(
        self,
        customer_id: str,
        ticket_type: TicketType,
        priority: TicketPriority,
        title: str,
        description: str,
        assigned_team: Optional[TeamType] = None,
    ) -> SupportTicket:
        """
        Submits a new customer support ticket, calculates SLA deadline, and auto-routes.
        """
        with self._lock:
            ticket_id = f"TICK-{int(time.time())}-{len(self._tickets) + 1:04d}"
            
            # Default intelligent routing based on ticket type and content
            if assigned_team is None:
                assigned_team = self._route_ticket_team(ticket_type, title, description)

            sla_duration = SLA_SECONDS.get(priority, 86400.0)
            now = time.time()
            deadline = now + sla_duration

            ticket = SupportTicket(
                ticket_id=ticket_id,
                customer_id=customer_id,
                ticket_type=ticket_type,
                priority=priority,
                title=title,
                description=description,
                status="OPEN",
                assigned_team=assigned_team,
                sla_deadline=deadline,
                created_at=now,
            )

            # Automatically convert bugs and critical incidents to engineering tasks
            if ticket_type in (TicketType.BUG_REPORT, TicketType.INCIDENT) or priority == TicketPriority.P0_CRITICAL:
                task_id = f"ENG-TASK-{ticket_id}"
                ticket.linked_engineering_task_id = task_id
                ticket.status = "IN_ENGINEERING"

                if self._on_engineering_task_created:
                    try:
                        self._on_engineering_task_created({
                            "task_id": task_id,
                            "ticket_id": ticket_id,
                            "title": f"Fix [{priority.value}]: {title}",
                            "team": assigned_team.value,
                            "description": description,
                        })
                    except Exception as e:
                        logger.warning(f"Failed to execute engineering task hook: {e}")

            self._tickets[ticket_id] = ticket
            logger.info(f"Created support ticket {ticket_id} [{priority.value}] assigned to {assigned_team.value}")
            return ticket

    def _route_ticket_team(self, ticket_type: TicketType, title: str, description: str) -> TeamType:
        """Determines best engineering or ops team based on text heuristics."""
        import re
        text = f"{title} {description}".lower()
        if "security" in text or "vulnerability" in text or "auth" in text or "jwt" in text:
            return TeamType.SECURITY_OPS
        elif "ui" in text or "frontend" in text or "button" in text or "css" in text or "react" in text:
            return TeamType.FRONTEND
        elif "mobile" in text or "ios" in text or "android" in text:
            return TeamType.MOBILE
        elif "database" in text or "postgres" in text or "sql" in text or "migration" in text:
            return TeamType.DATABASE
        elif "cluster" in text or "docker" in text or "k8s" in text or "server" in text or "infrastructure" in text:
            return TeamType.INFRASTRUCTURE
        elif "test" in text or "flaky" in text or "ci " in text or "regression" in text:
            return TeamType.QA_AUTOMATION
        elif "llm" in text or "embedding" in text or "agent" in text or re.search(r"\bai\b", text):
            return TeamType.AI_ML
        else:
            return TeamType.BACKEND

    def resolve_ticket(
        self,
        ticket_id: str,
        resolution_notes: str,
        rca: Optional[str] = None,
        csat_score: Optional[int] = None,
    ) -> SupportTicket:
        """Resolves a ticket and records root cause analysis and CSAT rating."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                raise KeyError(f"Ticket {ticket_id} not found")

            ticket.status = "RESOLVED"
            ticket.resolved_at = time.time()
            if csat_score is not None:
                ticket.csat_score = max(1, min(5, csat_score))

            if rca:
                self._rca_logs[ticket_id] = {
                    "ticket_id": ticket_id,
                    "resolution_notes": resolution_notes,
                    "rca": rca,
                    "resolved_at": ticket.resolved_at,
                }

            logger.info(f"Resolved ticket {ticket_id} (CSAT: {ticket.csat_score})")
            return ticket

    def record_csat(self, ticket_id: str, score: int) -> None:
        """Records customer satisfaction score (1 to 5) for a resolved ticket."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                raise KeyError(f"Ticket {ticket_id} not found")
            ticket.csat_score = max(1, min(5, score))

    def get_ticket(self, ticket_id: str) -> Optional[SupportTicket]:
        """Retrieves a single ticket by ID."""
        with self._lock:
            return copy.deepcopy(self._tickets.get(ticket_id))

    def list_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[TicketPriority] = None,
        assigned_team: Optional[TeamType] = None,
    ) -> List[SupportTicket]:
        """Filters support tickets by criteria."""
        with self._lock:
            res: List[SupportTicket] = []
            for t in self._tickets.values():
                if status and t.status != status:
                    continue
                if priority and t.priority != priority:
                    continue
                if assigned_team and t.assigned_team != assigned_team:
                    continue
                res.append(copy.deepcopy(t))
            return res

    def get_average_csat(self) -> float:
        """Calculates mean CSAT rating across scored tickets."""
        with self._lock:
            scores = [t.csat_score for t in self._tickets.values() if t.csat_score is not None]
            if not scores:
                return 5.0
            return round(sum(scores) / len(scores), 2)

    def get_sla_compliance_pct(self) -> float:
        """Calculates the percentage of resolved tickets resolved within SLA."""
        with self._lock:
            resolved = [t for t in self._tickets.values() if t.resolved_at is not None]
            if not resolved:
                return 100.0
            within_sla = sum(1 for t in resolved if t.resolved_at <= t.sla_deadline)
            return round((within_sla / len(resolved)) * 100.0, 2)

    def get_metrics(self) -> Dict[str, Any]:
        """Returns comprehensive support center operational metrics."""
        with self._lock:
            total = len(self._tickets)
            open_count = sum(1 for t in self._tickets.values() if t.status in ("OPEN", "TRIAGED", "IN_ENGINEERING"))
            resolved_count = sum(1 for t in self._tickets.values() if t.status in ("RESOLVED", "CLOSED"))
            p0_count = sum(1 for t in self._tickets.values() if t.priority == TicketPriority.P0_CRITICAL)

            return {
                "total_tickets": total,
                "open_tickets": open_count,
                "resolved_tickets": resolved_count,
                "p0_critical_tickets": p0_count,
                "avg_csat": self.get_average_csat(),
                "sla_compliance_pct": self.get_sla_compliance_pct(),
                "rca_count": len(self._rca_logs),
            }
