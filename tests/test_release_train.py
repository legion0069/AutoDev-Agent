"""
test_release_train.py - Unit and Integration Tests for Release Train & Deployment Management (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import ExecutiveRole, ReleaseStage
from core.enterprise.release_train import ReleaseTrain


@pytest.fixture
def rt():
    return ReleaseTrain(current_version="2.9.0")


class TestReleaseTrain:
    def test_current_version(self, rt: ReleaseTrain):
        assert rt.get_current_version() == "2.9.0"

    def test_semver_bumping(self, rt: ReleaseTrain):
        assert rt.bump_semver("2.9.0", "major") == "3.0.0"
        assert rt.bump_semver("2.9.0", "minor") == "2.10.0"
        assert rt.bump_semver("2.9.0", "patch") == "2.9.1"

    def test_create_release_candidate_invalid_version_raises(self, rt: ReleaseTrain):
        with pytest.raises(ValueError):
            rt.create_release_candidate("invalid_version_string")

    def test_full_release_lifecycle_promotion_to_ga(self, rt: ReleaseTrain):
        rc = rt.create_release_candidate(
            target_version="3.0.0",
            stage=ReleaseStage.RELEASE_CANDIDATE,
            epics=["EPIC-ENTERPRISE"],
            features=["Complete AI Company"],
        )
        assert rc.release_id == "REL-3.0.0-RELEASE_CANDIDATE"
        assert not rc.is_approved_for_ga

        # Complete gate signoffs
        rt.signoff_release(rc.release_id, ExecutiveRole.CTO)
        rt.signoff_release(rc.release_id, ExecutiveRole.VP_ENGINEERING)

        ga = rt.promote_to_general_availability(rc.release_id)
        assert ga.stage == ReleaseStage.GENERAL_AVAILABILITY
        assert ga.status == "DEPLOYED"
        assert rt.get_current_version() == "3.0.0"

    def test_premature_promotion_without_gates_raises_error(self, rt: ReleaseTrain):
        rc = rt.create_release_candidate("3.0.1")
        rt.set_gate_status(rc.release_id, "security_scan_clean", False)
        rt.signoff_release(rc.release_id, ExecutiveRole.CTO)
        rt.signoff_release(rc.release_id, ExecutiveRole.VP_ENGINEERING)

        with pytest.raises(ValueError):
            rt.promote_to_general_availability(rc.release_id)

    def test_production_rollback(self, rt: ReleaseTrain):
        rc = rt.create_release_candidate("3.0.0")
        rt.signoff_release(rc.release_id, ExecutiveRole.CTO)
        rt.signoff_release(rc.release_id, ExecutiveRole.VP_ENGINEERING)
        rt.promote_to_general_availability(rc.release_id)
        assert rt.get_current_version() == "3.0.0"

        # Trigger Rollback
        rolled_back = rt.trigger_rollback(rc.release_id, reason="High memory leak in worker daemon")
        assert rolled_back.stage == ReleaseStage.ROLLBACK
        assert "ROLLED_BACK" in rolled_back.status
        assert rt.get_current_version() == "2.9.0"
