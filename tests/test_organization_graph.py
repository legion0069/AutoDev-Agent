"""
test_organization_graph.py - Unit and Integration Tests for Organization Graph (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import DepartmentType, ExecutiveRole, TeamType
from core.enterprise.organization_graph import EdgeRelation, OrgEdge, OrganizationGraph, OrgNode


@pytest.fixture
def org_graph():
    return OrganizationGraph()


class TestOrganizationGraph:
    def test_bootstrap_hierarchy(self, org_graph: OrganizationGraph):
        nodes = org_graph.list_nodes()
        assert len(nodes) >= 12
        node_ids = {n.node_id for n in nodes}
        assert "emp_ceo" in node_ids
        assert "emp_cto" in node_ids
        assert "emp_vpeng" in node_ids
        assert "emp_vpprod" in node_ids
        assert "emp_cfo" in node_ids

    def test_find_escalation_path(self, org_graph: OrganizationGraph):
        # Backend lead reports to VP Eng, who reports to CEO
        path = org_graph.find_escalation_path("lead_backend", "emp_ceo")
        assert path is not None
        assert path[0] == "lead_backend"
        assert path[-1] == "emp_ceo"
        assert "emp_vpeng" in path

    def test_get_direct_reports(self, org_graph: OrganizationGraph):
        reports = org_graph.get_direct_reports("emp_ceo")
        report_ids = {r.node_id for r in reports}
        assert "emp_cto" in report_ids
        assert "emp_vpeng" in report_ids
        assert "emp_vpprod" in report_ids
        assert "emp_cfo" in report_ids

    def test_calculate_span_of_control(self, org_graph: OrganizationGraph):
        span = org_graph.calculate_span_of_control("emp_ceo")
        assert span >= 4

    def test_add_custom_node_and_edge(self, org_graph: OrganizationGraph):
        new_node = OrgNode(
            node_id="emp_sec_analyst_01",
            name="Bob Martin",
            title="Senior Security Analyst",
            department=DepartmentType.SECURITY,
            team=TeamType.SECURITY_OPS,
        )
        org_graph.add_node(new_node)
        org_graph.add_edge("emp_sec_analyst_01", "lead_sec", EdgeRelation.REPORTS_TO)

        path = org_graph.find_escalation_path("emp_sec_analyst_01", "emp_cto")
        assert path is not None
        assert "emp_sec_analyst_01" in path
        assert "lead_sec" in path

    def test_generate_mermaid_org_chart(self, org_graph: OrganizationGraph):
        mermaid = org_graph.generate_mermaid_org_chart()
        assert "graph TD" in mermaid
        assert "emp_ceo" in mermaid
        assert "emp_cto" in mermaid
        assert "-->|REPORTS_TO|" in mermaid

    def test_list_nodes_by_department(self, org_graph: OrganizationGraph):
        eng_nodes = org_graph.list_nodes(department=DepartmentType.ENGINEERING)
        assert len(eng_nodes) >= 3
        for n in eng_nodes:
            assert n.department == DepartmentType.ENGINEERING
