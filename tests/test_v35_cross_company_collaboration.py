"""
test_v35_cross_company_collaboration.py - Cross-Company Collaboration & Ecosystem Simulation Tests (AutoDev Version 3.5)
"""

import pytest

from core.enterprise_federation import EnterpriseFederation
from core.orchestrator import Orchestrator


def test_federation_initialization_and_bootstrap():
    fed = EnterpriseFederation(auto_bootstrap_default_companies=True)
    summary = fed.registry.get_registry_summary()
    assert summary["total_companies"] == 8
    assert summary["active_companies"] == 8

    # Verify baseline companies exist
    for cid in ["COMP-A-BACKEND", "COMP-B-FRONTEND", "COMP-C-AI", "COMP-D-SECURITY",
                "COMP-E-CLOUD", "COMP-F-QA", "COMP-G-DEVOPS", "COMP-H-DOCS"]:
        assert fed.get_company(cid) is not None
        prof = fed.registry.get_company(cid)
        assert prof is not None
        assert prof.status.value == "ACTIVE"


def test_execute_cross_company_ai_collaboration_pipeline():
    fed = EnterpriseFederation()

    workflow_result = fed.execute_cross_company_ai_collaboration(
        algorithm_name="NeuralSublinearRouting-v1",
        expected_business_impact_usd=7500000.0,
    )

    assert workflow_result["overall_status"] == "COLLABORATION_PIPELINE_SUCCESS"
    assert "1_ai_research_discovery" in workflow_result
    assert "2_backend_implementation" in workflow_result
    assert "3_qa_validation" in workflow_result
    assert "4_security_audit" in workflow_result
    assert "5_devops_deployment" in workflow_result
    assert "6_documentation_published" in workflow_result
    assert "7_portfolio_impact" in workflow_result

    # Step 1: AI Research node published
    ai_step = workflow_result["1_ai_research_discovery"]
    assert ai_step["status"] == "DISCOVERED_AND_PUBLISHED"

    # Step 2: Backend implementation verified
    be_step = workflow_result["2_backend_implementation"]
    assert be_step["status"] == "IMPLEMENTATION_COMPLETE"

    # Step 3: QA tests passed
    qa_step = workflow_result["3_qa_validation"]
    assert qa_step["pass_rate_pct"] == 100.0

    # Step 4: Security cleared
    sec_step = workflow_result["4_security_audit"]
    assert sec_step["status"] == "SECURITY_CLEARED"
    assert sec_step["compliance_score"] == 100.0

    # Step 5: DevOps deployed
    dev_step = workflow_result["5_devops_deployment"]
    assert dev_step["status"] == "DEPLOYED_PRODUCTION"

    # Step 6: Docs published
    doc_step = workflow_result["6_documentation_published"]
    assert doc_step["status"] == "MANUALS_AND_API_PUBLISHED"

    # Step 7: Portfolio realized
    port_step = workflow_result["7_portfolio_impact"]
    assert port_step["net_value_usd"] == 7500000.0
    assert port_step["calculated_roi"] == 30.0  # 7.5M / 250k


def test_simulate_ecosystem_discrete_cycles():
    fed = EnterpriseFederation()

    sim_res = fed.simulate_ecosystem(
        num_cycles=4,
        messages_per_cycle=20,
        trade_resources=True,
    )

    assert sim_res["cycles_executed"] == 4
    assert sim_res["total_messages_routed"] == 80  # 4 * 20
    assert sim_res["trades_attempted"] == 4
    assert sim_res["total_companies_active"] == 8
    assert sim_res["message_throughput_per_sec"] > 0


def test_global_dashboard_telemetry():
    fed = EnterpriseFederation()
    fed.execute_cross_company_ai_collaboration()

    dashboard = fed.get_global_dashboard()
    assert dashboard.total_companies == 8
    assert dashboard.active_companies == 8
    assert dashboard.total_projects >= 1
    assert dashboard.enterprise_health_score >= 90.0
    assert dashboard.enterprise_security_score == 100.0
    assert dashboard.innovation_score > 0
    assert len(dashboard.company_breakdown) == 8


def test_orchestrator_integration_v35():
    fed = EnterpriseFederation()
    orchestrator = Orchestrator(enterprise_federation=fed)

    # Simulate via orchestrator
    sim_out = orchestrator.simulate_enterprise_federation(num_cycles=2, messages_per_cycle=10)
    assert sim_out["cycles_executed"] == 2
    assert sim_out["total_messages_routed"] == 20

    # Execute workflow via orchestrator
    collab_out = orchestrator.execute_cross_company_collaboration("AttentionOptimization-v3")
    assert collab_out["overall_status"] == "COLLABORATION_PIPELINE_SUCCESS"

    # Query global dashboard
    dash_dict = orchestrator.query_global_dashboard()
    assert dash_dict["total_companies"] == 8
    assert "company_breakdown" in dash_dict
