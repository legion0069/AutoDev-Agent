"""
test_product_manager.py - Unit and Integration Tests for Product Management Engine (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import PriorityLevel
from core.enterprise.product_manager import ProductManager


@pytest.fixture
def pm():
    return ProductManager()


class TestProductManager:
    def test_default_vision_seeded(self, pm: ProductManager):
        vision = pm.get_product_vision()
        assert vision is not None
        assert "Autonomous AI Software Company" in vision.vision_statement
        assert len(vision.key_differentiators) >= 3

    def test_update_product_vision(self, pm: ProductManager):
        pm.update_product_vision(
            vision_statement="The definitive global AI software enterprise",
            target_market="Fortune 500 Enterprises",
            value_proposition="100x engineering velocity with zero human overhead",
            key_differentiators=["Deterministic Python Core", "Autonomous Executive Governance"],
        )
        v = pm.get_product_vision()
        assert v.target_market == "Fortune 500 Enterprises"
        assert len(v.key_differentiators) == 2

    def test_create_epic(self, pm: ProductManager):
        epic = pm.create_epic(
            title="Real-Time Telemetry & Observability",
            description="End-to-end distributed cluster observability platform",
            strategic_theme="Platform Reliability",
            target_quarter="Q2",
            estimated_roi_multiplier=5.0,
        )
        assert epic.epic_id.startswith("EPIC-")
        assert epic.title == "Real-Time Telemetry & Observability"
        assert epic.estimated_roi_multiplier == 5.0

    def test_create_feature_and_rice_scoring(self, pm: ProductManager):
        epic = pm.create_epic("Core Scale", "Scale cluster", "Scale")
        feat = pm.create_feature(
            epic_id=epic.epic_id,
            name="Distributed Cache Acceleration",
            description="Accelerate CAS caching across remote workers",
            reach=10000,
            impact=3.0,
            confidence=0.9,
            effort=5.0,
        )
        assert feat.feature_id.startswith("FEAT-")
        # RICE = (10000 * 3.0 * 0.9) / 5.0 = 27000 / 5.0 = 5400.0
        assert feat.rice_score == 5400.0

    def test_create_user_story_with_acceptance_criteria(self, pm: ProductManager):
        epic = pm.create_epic("Security Epics", "Security", "Security")
        feat = pm.create_feature(epic.epic_id, "Zero Trust RBAC", "Enforce RBAC")

        story = pm.create_user_story(
            feature_id=feat.feature_id,
            title="Enforce token signature on worker registration",
            user_role="Security Officer",
            action="verify ECDSA cryptographic signatures",
            benefit="prevent unauthorized node joins",
            story_points=5,
            priority=PriorityLevel.CRITICAL,
        )
        assert story.story_id.startswith("US-")

        crit = pm.add_acceptance_criterion(
            story_id=story.story_id,
            given="an unsigned worker join request",
            when="sent to MasterNode",
            then="the request is rejected with 401 Unauthorized",
        )
        assert crit.criterion_id.startswith("AC-")

        updated_story = pm.get_user_story(story.story_id)
        assert len(updated_story.acceptance_criteria) == 1
        assert updated_story.acceptance_criteria[0].given == "an unsigned worker join request"

    def test_get_prioritized_backlog(self, pm: ProductManager):
        epic = pm.create_epic("Backlog Epic", "Desc", "Theme")
        f_low = pm.create_feature(epic.epic_id, "Low Feat", "Low", reach=100, impact=1.0, confidence=0.5, effort=10.0)
        f_high = pm.create_feature(epic.epic_id, "High Feat", "High", reach=5000, impact=3.0, confidence=0.9, effort=2.0)

        s_low = pm.create_user_story(f_low.feature_id, "Low Story", "U", "A", "B", story_points=2, priority=PriorityLevel.LOW)
        s_high = pm.create_user_story(f_high.feature_id, "High Story", "U", "A", "B", story_points=8, priority=PriorityLevel.CRITICAL)

        backlog = pm.get_prioritized_backlog()
        assert len(backlog) >= 2
        # Highest RICE / Critical priority story should be ordered before low priority
        story_ids = [s.story_id for s in backlog]
        assert story_ids.index(s_high.story_id) < story_ids.index(s_low.story_id)

    def test_to_dict_export(self, pm: ProductManager):
        d = pm.to_dict()
        assert "vision" in d
        assert "total_epics" in d
        assert "total_features" in d
        assert "total_user_stories" in d
