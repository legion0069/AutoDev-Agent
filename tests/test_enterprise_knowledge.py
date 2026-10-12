"""
test_enterprise_knowledge.py - Unit Tests for EnterpriseKnowledgeGraph (AutoDev Version 3.5)
"""

import pytest

from core.enterprise_knowledge import (
    EnterpriseKnowledgeGraph,
    KnowledgeCategory,
    KnowledgeEdge,
    KnowledgeNode,
    RelationshipType,
)


def test_knowledge_graph_initialization():
    kg = EnterpriseKnowledgeGraph()
    analytics = kg.get_knowledge_analytics()
    assert analytics["total_nodes"] == 0
    assert analytics["total_edges"] == 0
    assert analytics["total_reuses"] == 0


def test_add_knowledge_node():
    kg = EnterpriseKnowledgeGraph()
    node = kg.add_knowledge_node(
        category=KnowledgeCategory.ADR,
        title="ADR-001: Event Driven Architecture",
        content="Decided to utilize federated inboxes and zero-copy message passing.",
        company_id="COMP-A",
        author="Architect Agent",
        tags=["architecture", "adr", "federation"],
    )
    assert node.node_id.startswith("KNOW-")
    assert node.category == KnowledgeCategory.ADR
    assert node.company_id == "COMP-A"

    analytics = kg.get_knowledge_analytics()
    assert analytics["total_nodes"] == 1
    assert analytics["contributions_by_company"]["COMP-A"] == 1


def test_link_knowledge_nodes():
    kg = EnterpriseKnowledgeGraph()
    n1 = kg.add_knowledge_node(KnowledgeCategory.RESEARCH, "Neural Architecture Search", "Discovered fast network", "COMP-C", "AI Agent")
    n2 = kg.add_knowledge_node(KnowledgeCategory.ADR, "ADR-002: Adopt Fast Network", "Adopting research", "COMP-A", "Arch Agent")

    edge = kg.link_nodes(
        source_id=n2.node_id,
        target_id=n1.node_id,
        relationship=RelationshipType.IMPLEMENTS,
        description="Implements NAS algorithm in production",
    )
    assert edge is not None
    assert edge.relationship == RelationshipType.IMPLEMENTS

    related = kg.get_related_nodes(n2.node_id)
    assert len(related) == 1
    assert related[0][0].node_id == n1.node_id


def test_full_text_search():
    kg = EnterpriseKnowledgeGraph()
    n1 = kg.add_knowledge_node(KnowledgeCategory.API, "Payment Gateway API", "Process credit cards and wire transfers", "COMP-A", "Dev")
    n2 = kg.add_knowledge_node(KnowledgeCategory.BEST_PRACTICE, "Security Guidelines", "Never store raw payment tokens", "COMP-D", "Sec")
    n3 = kg.add_knowledge_node(KnowledgeCategory.RESEARCH, "Quantum Cryptography", "Post-quantum lattice signatures", "COMP-C", "Researcher")

    results = kg.search("payment")
    assert len(results) >= 2
    matched_ids = [n.node_id for n, score in results]
    assert n1.node_id in matched_ids
    assert n2.node_id in matched_ids
    assert n3.node_id not in matched_ids


def test_search_with_category_filter():
    kg = EnterpriseKnowledgeGraph()
    n1 = kg.add_knowledge_node(KnowledgeCategory.API, "Billing Service", "Invoicing API", "COMP-A", "Dev")
    n2 = kg.add_knowledge_node(KnowledgeCategory.RESEARCH, "Billing Optimization", "Machine learning cost forecast", "COMP-C", "Researcher")

    results = kg.search("billing", category=KnowledgeCategory.RESEARCH)
    assert len(results) == 1
    assert results[0][0].node_id == n2.node_id


def test_graph_path_finding_bfs():
    kg = EnterpriseKnowledgeGraph()
    n_a = kg.add_knowledge_node(KnowledgeCategory.RESEARCH, "Node A", "Content", "C1", "Dev")
    n_b = kg.add_knowledge_node(KnowledgeCategory.PATTERN, "Node B", "Content", "C1", "Dev")
    n_c = kg.add_knowledge_node(KnowledgeCategory.API, "Node C", "Content", "C1", "Dev")

    kg.link_nodes(n_a.node_id, n_b.node_id, RelationshipType.EXTENDS)
    kg.link_nodes(n_b.node_id, n_c.node_id, RelationshipType.IMPLEMENTS)

    path = kg.find_path(n_a.node_id, n_c.node_id)
    assert path == [n_a.node_id, n_b.node_id, n_c.node_id]


def test_knowledge_reuse_tracking():
    kg = EnterpriseKnowledgeGraph()
    n = kg.add_knowledge_node(KnowledgeCategory.BEST_PRACTICE, "Zero Trust Guidelines", "Verify every request", "COMP-D", "CISO")
    assert n.reuse_count == 0

    kg.record_reuse(n.node_id)
    kg.record_reuse(n.node_id)
    assert n.reuse_count == 2

    analytics = kg.get_knowledge_analytics()
    assert analytics["total_reuses"] == 2
    assert analytics["top_reused_nodes"][0]["node_id"] == n.node_id
