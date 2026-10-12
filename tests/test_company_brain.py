"""
test_company_brain.py - Unit and Integration Tests for Central Enterprise Knowledge Brain (v3.0)
"""

import pytest
from core.enterprise.company_brain import CompanyBrain
from core.enterprise.enterprise_models import DepartmentType, KnowledgeCategory


@pytest.fixture
def brain():
    return CompanyBrain()


class TestCompanyBrain:
    def test_seed_knowledge_initialized(self, brain: CompanyBrain):
        summary = brain.to_dict()
        assert summary["total_items"] >= 3
        assert summary["tags_count"] >= 5

    def test_store_and_search_knowledge(self, brain: CompanyBrain):
        item = brain.store_knowledge(
            title="ADR-002: FastCDC Content-Defined Chunking for CAS",
            category=KnowledgeCategory.ARCHITECTURE_ADR,
            content="FastCDC chunking optimizes CAS deduplication for large build artifacts.",
            tags=["cas", "fastcdc", "storage", "performance"],
            author="Rachel Green (DevOps)",
            department=DepartmentType.DEVOPS,
        )
        assert item.knowledge_id.startswith("KB-")
        assert item.version == 1

        # Search by keyword
        res_kw = brain.search_knowledge(query="FastCDC")
        assert len(res_kw) >= 1
        assert res_kw[0].title == item.title

        # Search by tag
        res_tag = brain.search_knowledge(tags=["cas"])
        assert len(res_tag) >= 1

        # Search by category
        res_cat = brain.search_knowledge(category=KnowledgeCategory.ARCHITECTURE_ADR)
        assert len(res_cat) >= 2

    def test_update_and_version_knowledge_item(self, brain: CompanyBrain):
        item = brain.store_knowledge(
            title="Deployment Runbook",
            category=KnowledgeCategory.ENGINEERING_STANDARDS,
            content="Initial deployment instructions",
            tags=["runbook", "deploy"],
            author="DevOps",
            department=DepartmentType.DEVOPS,
        )

        # Update
        updated = brain.store_knowledge(
            title="Deployment Runbook v2",
            category=KnowledgeCategory.ENGINEERING_STANDARDS,
            content="Updated multi-node cluster deployment runbook",
            tags=["runbook", "deploy", "cluster"],
            author="DevOps Lead",
            department=DepartmentType.DEVOPS,
            knowledge_id=item.knowledge_id,
        )
        assert updated.version == 2
        assert updated.title == "Deployment Runbook v2"

    def test_link_knowledge_entities(self, brain: CompanyBrain):
        k1 = brain.store_knowledge("Architecture Spec", KnowledgeCategory.ARCHITECTURE_ADR, "Spec", ["arch"], "CTO", DepartmentType.ARCHITECTURE)
        k2 = brain.store_knowledge("Postmortem Incident 101", KnowledgeCategory.POSTMORTEM, "Outage analysis", ["incident"], "DevOps", DepartmentType.DEVOPS)

        brain.link_knowledge(k1.knowledge_id, k2.knowledge_id)
        related = brain.get_related_knowledge(k1.knowledge_id)
        assert len(related) == 1
        assert related[0].knowledge_id == k2.knowledge_id
