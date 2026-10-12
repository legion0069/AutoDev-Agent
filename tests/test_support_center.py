"""
test_support_center.py - Unit and Integration Tests for Customer Support & Incident Management (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import TeamType, TicketPriority, TicketType
from core.enterprise.support_center import SupportCenter


@pytest.fixture
def support():
    return SupportCenter()


class TestSupportCenter:
    def test_submit_ticket_auto_routing(self, support: SupportCenter):
        ticket = support.submit_ticket(
            customer_id="cust_123",
            ticket_type=TicketType.BUG_REPORT,
            priority=TicketPriority.P1_HIGH,
            title="Frontend UI button alignment broken",
            description="The checkout submit button is displaced in React view",
        )
        assert ticket.ticket_id.startswith("TICK-")
        assert ticket.assigned_team == TeamType.FRONTEND
        assert ticket.sla_deadline > ticket.created_at

    def test_bug_report_auto_generates_engineering_task(self, support: SupportCenter):
        captured_tasks = []
        support.set_engineering_task_hook(lambda t: captured_tasks.append(t))

        ticket = support.submit_ticket(
            customer_id="cust_456",
            ticket_type=TicketType.BUG_REPORT,
            priority=TicketPriority.P0_CRITICAL,
            title="Database deadlocks in transaction ledger",
            description="Critical SQL locking under high concurrency",
        )
        assert ticket.status == "IN_ENGINEERING"
        assert ticket.linked_engineering_task_id is not None
        assert len(captured_tasks) == 1
        assert captured_tasks[0]["ticket_id"] == ticket.ticket_id

    def test_resolve_ticket_and_csat(self, support: SupportCenter):
        ticket = support.submit_ticket(
            customer_id="cust_789",
            ticket_type=TicketType.INQUIRY,
            priority=TicketPriority.P3_LOW,
            title="API Rate limits question",
            description="What is the burst limit per second?",
        )
        resolved = support.resolve_ticket(
            ticket.ticket_id,
            resolution_notes="Sent documentation on burst token bucket rate limits",
            rca="User inquiry",
            csat_score=5,
        )
        assert resolved.status == "RESOLVED"
        assert resolved.csat_score == 5
        assert resolved.resolved_at is not None

    def test_get_average_csat_and_sla_compliance(self, support: SupportCenter):
        t1 = support.submit_ticket("c1", TicketType.INQUIRY, TicketPriority.P3_LOW, "Q1", "Desc")
        t2 = support.submit_ticket("c2", TicketType.INQUIRY, TicketPriority.P3_LOW, "Q2", "Desc")

        support.resolve_ticket(t1.ticket_id, "Res 1", csat_score=4)
        support.resolve_ticket(t2.ticket_id, "Res 2", csat_score=5)

        avg_csat = support.get_average_csat()
        assert avg_csat == 4.5
        assert support.get_sla_compliance_pct() == 100.0

    def test_support_metrics(self, support: SupportCenter):
        metrics = support.get_metrics()
        assert "total_tickets" in metrics
        assert "open_tickets" in metrics
        assert "resolved_tickets" in metrics
        assert "avg_csat" in metrics
        assert "sla_compliance_pct" in metrics
