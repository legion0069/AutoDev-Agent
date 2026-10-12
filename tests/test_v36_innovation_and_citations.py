"""
tests/test_v36_innovation_and_citations.py - Tests for InnovationGraph & CitationManager
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import unittest

from core.citation_manager import (
    CitationEntry,
    CitationFormat,
    CitationManager,
)
from core.innovation_graph import (
    InnovationEdgeType,
    InnovationGraph,
    InnovationNode,
    InnovationNodeType,
)


class TestInnovationGraph(unittest.TestCase):
    """Verifies node creation, edge relationships, lineage traversal, and Mermaid diagram export."""

    def setUp(self) -> None:
        self.graph = InnovationGraph()

    def test_add_nodes(self) -> None:
        n1 = self.graph.add_node(
            name="SequentialScan",
            node_type=InnovationNodeType.BASELINE,
            description="Baseline O(N) array search",
        )
        n2 = self.graph.add_node(
            name="BinarySearch",
            node_type=InnovationNodeType.ALGORITHM,
            description="O(log N) binary search over sorted array",
        )
        self.assertIsInstance(n1, InnovationNode)
        self.assertEqual(self.graph.total_nodes, 2)

    def test_add_edges_and_lineage(self) -> None:
        n1 = self.graph.add_node("Base", InnovationNodeType.BASELINE)
        n2 = self.graph.add_node("Improvement", InnovationNodeType.ALGORITHM)
        n3 = self.graph.add_node("OptimizedImprovement", InnovationNodeType.ALGORITHM)

        self.graph.add_edge(n1.node_id, n2.node_id, InnovationEdgeType.DERIVED_FROM)
        self.graph.add_edge(n2.node_id, n3.node_id, InnovationEdgeType.OPTIMIZES)

        lineage = self.graph.get_lineage(n3.node_id)
        self.assertEqual(len(lineage), 3)
        self.assertEqual(lineage[0].node_id, n1.node_id)

    def test_detect_cycles_acyclic(self) -> None:
        n1 = self.graph.add_node("A", InnovationNodeType.ALGORITHM)
        n2 = self.graph.add_node("B", InnovationNodeType.ALGORITHM)
        self.graph.add_edge(n1.node_id, n2.node_id, InnovationEdgeType.DERIVED_FROM)
        self.assertFalse(self.graph.has_cycles())

    def test_detect_cycles_cyclic(self) -> None:
        n1 = self.graph.add_node("A", InnovationNodeType.ALGORITHM)
        n2 = self.graph.add_node("B", InnovationNodeType.ALGORITHM)
        self.graph.add_edge(n1.node_id, n2.node_id, InnovationEdgeType.DERIVED_FROM)
        self.graph.add_edge(n2.node_id, n1.node_id, InnovationEdgeType.DERIVED_FROM)
        self.assertTrue(self.graph.has_cycles())

    def test_export_mermaid(self) -> None:
        n1 = self.graph.add_node("Node1", InnovationNodeType.BASELINE)
        n2 = self.graph.add_node("Node2", InnovationNodeType.ALGORITHM)
        self.graph.add_edge(n1.node_id, n2.node_id, InnovationEdgeType.SUPERSEDES)

        mermaid = self.graph.export_mermaid()
        self.assertIn("graph TD", mermaid)
        self.assertIn("Node1", mermaid)
        self.assertIn("SUPERSEDES", mermaid)


class TestCitationManager(unittest.TestCase):
    """Verifies citation registration, BibTeX parsing, APA formatting, and h-index computation."""

    def setUp(self) -> None:
        self.manager = CitationManager()

    def test_register_citation(self) -> None:
        entry = self.manager.register(
            key="shannon1948",
            title="A Mathematical Theory of Communication",
            authors=["Claude E. Shannon"],
            year=1948,
            venue="Bell System Technical Journal",
            volume="27",
            pages="379-423",
        )
        self.assertIsInstance(entry, CitationEntry)
        self.assertEqual(entry.key, "shannon1948")
        self.assertEqual(self.manager.total_citations, 1)

    def test_format_apa(self) -> None:
        entry = self.manager.register(
            key="turing1950",
            title="Computing Machinery and Intelligence",
            authors=["Alan M. Turing"],
            year=1950,
            venue="Mind",
        )
        formatted = self.manager.format_citation(entry.citation_id, CitationFormat.APA)
        self.assertIn("Turing", formatted)
        self.assertIn("(1950)", formatted)
        self.assertIn("Computing Machinery and Intelligence", formatted)

    def test_format_bibtex(self) -> None:
        entry = self.manager.register(
            key="knuth1974",
            title="Structured Programming with go to Statements",
            authors=["Donald E. Knuth"],
            year=1974,
            venue="ACM Computing Surveys",
        )
        bibtex = self.manager.format_citation(entry.citation_id, CitationFormat.BIBTEX)
        self.assertIn("@article{knuth1974", bibtex)
        self.assertIn("title={Structured Programming with go to Statements}", bibtex)

    def test_parse_bibtex_string(self) -> None:
        bibtex_str = """
@article{vaswani2017attention,
  author = {Vaswani, Ashish and Shazeer, Noam},
  title = {Attention Is All You Need},
  year = {2017},
  journal = {NeurIPS}
}
"""
        parsed = self.manager.import_bibtex(bibtex_str)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].key, "vaswani2017attention")
        self.assertEqual(parsed[0].title, "Attention Is All You Need")

    def test_h_index_calculation(self) -> None:
        # Citations: [10, 8, 5, 4, 3] => h-index = 4
        c1 = self.manager.register("p1", "Paper 1", ["Author"], 2020)
        c2 = self.manager.register("p2", "Paper 2", ["Author"], 2020)
        c3 = self.manager.register("p3", "Paper 3", ["Author"], 2020)
        c4 = self.manager.register("p4", "Paper 4", ["Author"], 2020)
        c5 = self.manager.register("p5", "Paper 5", ["Author"], 2020)

        self.manager.record_citations(c1.citation_id, 10)
        self.manager.record_citations(c2.citation_id, 8)
        self.manager.record_citations(c3.citation_id, 5)
        self.manager.record_citations(c4.citation_id, 4)
        self.manager.record_citations(c5.citation_id, 3)

        h_idx = self.manager.compute_h_index()
        self.assertEqual(h_idx, 4)


if __name__ == "__main__":
    unittest.main()
