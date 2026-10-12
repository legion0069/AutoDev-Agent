"""
Tests for Orchestrator integration with Distributed Company Mode in AutoDev v3.3.
"""

from pathlib import Path
import pytest
from core.orchestrator import Orchestrator
from core.multi_agent.work_queue import WorkItem


def test_orchestrator_company_mode_execution(tmp_path: Path):
    plan_file = tmp_path / "project_plan.json"
    plan_file.write_text('{"total_days": 1, "phases": [{"day": 1, "name": "Init"}]}', encoding="utf-8")
    state_file = tmp_path / "state.json"
    state_file.write_text('{"current_day": 1, "completed_tasks": []}', encoding="utf-8")

    orch = Orchestrator(
        project_dir=tmp_path,
        plan_path=plan_file,
        state_path=state_file,
    )

    # Validate multi_agent_company property
    assert orch.multi_agent_company is not None
    assert orch.multi_agent_company.registry.count >= 16

    # Test custom tasks via execute_company
    custom_tasks = [
        WorkItem(task_id="orch_task_1", title="Build Core Schema", priority=80),
        WorkItem(task_id="orch_task_2", title="Expose API Route", priority=70, dependencies={"orch_task_1"}),
    ]

    result = orch.execute_company(tasks=custom_tasks, simulate_ceremonies=True)
    assert result["mode"] == "distributed_company"
    assert result["tasks_executed"] == 2
    assert result["completed_tasks"] == 2
    assert result["standup"] is not None
    assert result["design_review"] is not None
    assert result["code_review"] is not None
    assert len(result["reports"]) == 10

    # Test run_company alias
    alias_res = orch.run_company(tasks=custom_tasks, simulate_ceremonies=False)
    assert alias_res["tasks_executed"] == 2

    orch.multi_agent_company.shutdown()
