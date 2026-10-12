"""
Tests for DistributedEngineeringCompany simulator, ceremonies, reports, and diagrams in AutoDev v3.3.
"""

import pytest
from core.multi_agent.engineering_company import DistributedEngineeringCompany
from core.multi_agent.work_queue import WorkItem


def test_engineering_company_roster_and_ceremonies():
    company = DistributedEngineeringCompany(deterministic_mode=True)
    # Check that standard corporate roles were registered
    assert company.registry.count >= 16
    assert company.registry.get_agent("agent_ceo") is not None
    assert company.registry.get_agent("agent_arch") is not None
    assert company.registry.get_agent("agent_qa") is not None

    # Standup
    standup = company.simulate_daily_standup()
    assert standup["attendees_count"] >= 16
    assert len(standup["updates"]) >= 16

    # Handoff
    task = WorkItem(task_id="t_handoff", title="Handoff Task")
    msg = company.simulate_handoff("agent_be", "agent_fe", task, "API payload ready")
    assert msg.sender == "agent_be"
    assert msg.receiver == "agent_fe"

    # Design Review
    des_prop = company.simulate_design_review("New Microservice Architecture", "spec_doc")
    assert des_prop.status == "APPROVED"

    # Code Review
    cr_prop = company.simulate_code_review("t_handoff", "diff", "agent_be")
    assert cr_prop.status == "APPROVED"

    # Retrospective & Release
    retro = company.simulate_retrospective()
    assert len(retro["takeaways"]) >= 4

    release = company.simulate_release_meeting("v3.3.0")
    assert release["status"] == "APPROVED"
    assert release["version"] == "v3.3.0"
    company.shutdown()


def test_all_10_engineering_reports():
    company = DistributedEngineeringCompany(deterministic_mode=True)
    task = WorkItem(task_id="t_sample", title="Sample Work Item")
    company.submit_and_execute_tasks([task])
    company.simulate_daily_standup()

    # Verify all 10 reports generate markdown strings with key headings
    r1 = company.generate_company_report()
    assert "Executive Company Report" in r1

    r2 = company.generate_engineering_report()
    assert "Engineering Subsystem Report" in r2

    r3 = company.generate_agent_performance_report()
    assert "Agent Performance & Efficiency Scorecard" in r3

    r4 = company.generate_communication_graph_report()
    assert "Inter-Agent Communication Matrix" in r4

    r5 = company.generate_task_timeline_report()
    assert "Task Timeline & Lifecycle Report" in r5

    r6 = company.generate_parallel_execution_timeline_report()
    assert "Parallel Execution Timeline" in r6

    r7 = company.generate_consensus_report()
    assert "Engineering Consensus & Ratification Report" in r7

    r8 = company.generate_conflict_resolution_report()
    assert "Conflict Resolution Audit" in r8

    r9 = company.generate_resource_utilization_report()
    assert "Distributed Resource & Lock Utilization Report" in r9

    r10 = company.generate_daily_engineering_report()
    assert "Daily Engineering Standup & Organizational Journal" in r10

    company.shutdown()


def test_all_6_mermaid_diagrams():
    company = DistributedEngineeringCompany(deterministic_mode=True)
    company.simulate_daily_standup()

    d1 = company.generate_company_hierarchy_diagram()
    assert "```mermaid" in d1 and "CEO (agent_ceo)" in d1

    d2 = company.generate_message_bus_diagram()
    assert "```mermaid" in d2 and "AgentMessageBus" in d2

    d3 = company.generate_parallel_execution_diagram()
    assert "```mermaid" in d3 and "ParallelExecutor" in d3

    d4 = company.generate_resource_scheduling_diagram()
    assert "```mermaid" in d4 and "sequenceDiagram" in d4

    d5 = company.generate_consensus_workflow_diagram()
    assert "```mermaid" in d5 and "stateDiagram-v2" in d5

    d6 = company.generate_communication_graph_diagram()
    assert "```mermaid" in d6

    company.shutdown()
