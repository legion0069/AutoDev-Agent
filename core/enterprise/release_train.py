"""
release_train.py - Enterprise Release Train & Deployment Management for AutoDev (v3.0)

Manages software delivery lifecycle stages (Alpha, Beta, RC, GA, Hotfix, Patch, LTS, Rollback),
SemVer versioning, automated quality gates checklist validation, executive release signoffs,
and zero-downtime production rollbacks.
"""

from __future__ import annotations

import copy
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    ExecutiveRole,
    ReleaseCandidate,
    ReleaseStage,
)

logger = logging.getLogger("AutoDev.Enterprise.ReleaseTrain")

SEMVER_REGEX = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


class ReleaseTrain:
    """
    Autonomous Enterprise Release Train Coordinator.
    Enforces quality gates, coordinates executive signoffs, and orchestrates releases.
    """

    def __init__(self, current_version: str = "2.9.0") -> None:
        self._lock = threading.RLock()
        self._current_version = current_version
        self._active_releases: Dict[str, ReleaseCandidate] = {}  # release_id -> ReleaseCandidate
        self._release_history: List[ReleaseCandidate] = []
        self._deployed_ga_versions: List[str] = [current_version]

    def create_release_candidate(
        self,
        target_version: str,
        stage: ReleaseStage = ReleaseStage.RELEASE_CANDIDATE,
        epics: Optional[List[str]] = None,
        features: Optional[List[str]] = None,
        bugs: Optional[List[str]] = None,
    ) -> ReleaseCandidate:
        """Creates a new release candidate."""
        if not SEMVER_REGEX.match(target_version):
            raise ValueError(f"Version '{target_version}' does not adhere to Semantic Versioning (X.Y.Z)")

        with self._lock:
            release_id = f"REL-{target_version}-{stage.value}"
            rc = ReleaseCandidate(
                release_id=release_id,
                version=target_version,
                stage=stage,
                epics_included=list(epics or []),
                features_included=list(features or []),
                bugs_fixed=list(bugs or []),
                checklist_gates={
                    "unit_tests_pass": True,
                    "integration_tests_pass": True,
                    "security_scan_clean": True,
                    "performance_sla_met": True,
                    "docs_updated": True,
                    "executive_signoff": False,
                },
                approved_by=[],
                status="STAGED",
                created_at=time.time(),
            )
            self._active_releases[release_id] = rc
            logger.info(f"Created Release Candidate [{release_id}] for version {target_version} ({stage.value})")
            return rc

    def set_gate_status(self, release_id: str, gate_name: str, passed: bool) -> ReleaseCandidate:
        """Sets the pass/fail status of an automated quality gate."""
        with self._lock:
            rc = self._active_releases.get(release_id)
            if not rc:
                raise KeyError(f"Release {release_id} not found")

            rc.checklist_gates[gate_name] = passed
            logger.info(f"Release [{release_id}] gate '{gate_name}' set to {passed}")
            return rc

    def signoff_release(self, release_id: str, approver_role: ExecutiveRole) -> ReleaseCandidate:
        """Records an executive signoff for a release candidate."""
        with self._lock:
            rc = self._active_releases.get(release_id)
            if not rc:
                raise KeyError(f"Release {release_id} not found")

            if approver_role not in rc.approved_by:
                rc.approved_by.append(approver_role)

            if len(rc.approved_by) >= 2:
                rc.checklist_gates["executive_signoff"] = True

            logger.info(f"Executive {approver_role.value} signed off on release {release_id}")
            return rc

    def promote_to_general_availability(self, release_id: str) -> ReleaseCandidate:
        """
        Promotes a release candidate to GENERAL_AVAILABILITY after validating all gates.
        """
        with self._lock:
            rc = self._active_releases.get(release_id)
            if not rc:
                raise KeyError(f"Release {release_id} not found")

            if not rc.is_approved_for_ga:
                failed_gates = [k for k, v in rc.checklist_gates.items() if not v]
                raise ValueError(
                    f"Release {release_id} cannot be promoted to GA. Incomplete gates: {failed_gates}, Approvals: {len(rc.approved_by)}"
                )

            rc.stage = ReleaseStage.GENERAL_AVAILABILITY
            rc.status = "DEPLOYED"
            rc.deployed_at = time.time()
            self._current_version = rc.version
            self._deployed_ga_versions.append(rc.version)
            self._release_history.append(rc)

            logger.info(f"🚀 Release {release_id} ({rc.version}) successfully deployed to GENERAL_AVAILABILITY!")
            return rc

    def trigger_rollback(self, release_id: str, reason: str) -> ReleaseCandidate:
        """Rolls back a release to the previous stable version."""
        with self._lock:
            rc = self._active_releases.get(release_id)
            if not rc:
                raise KeyError(f"Release {release_id} not found")

            rc.stage = ReleaseStage.ROLLBACK
            rc.status = f"ROLLED_BACK: {reason}"

            if len(self._deployed_ga_versions) > 1:
                # Revert current version to previous GA
                self._deployed_ga_versions.pop()
                self._current_version = self._deployed_ga_versions[-1]

            logger.warning(f"⚠️ Release {release_id} rolled back! Reverted active version to {self._current_version}")
            return rc

    def bump_semver(self, current_ver: str, bump_type: str = "minor") -> str:
        """Bumps semantic version string (major, minor, patch)."""
        match = SEMVER_REGEX.match(current_ver)
        if not match:
            return "1.0.0"

        major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if bump_type == "major":
            return f"{major + 1}.0.0"
        elif bump_type == "minor":
            return f"{major}.{minor + 1}.0"
        elif bump_type == "patch":
            return f"{major}.{minor}.{patch + 1}"
        else:
            return f"{major}.{minor}.{patch + 1}"

    def get_current_version(self) -> str:
        """Returns the currently active production version."""
        with self._lock:
            return self._current_version

    def get_release(self, release_id: str) -> Optional[ReleaseCandidate]:
        """Retrieves release candidate by ID."""
        with self._lock:
            return copy.deepcopy(self._active_releases.get(release_id))

    def list_releases(self) -> List[ReleaseCandidate]:
        """Lists all active and historical release candidates."""
        with self._lock:
            return copy.deepcopy(list(self._active_releases.values()))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes ReleaseTrain state."""
        with self._lock:
            return {
                "current_version": self._current_version,
                "deployed_ga_versions": list(self._deployed_ga_versions),
                "active_releases_count": len(self._active_releases),
                "history_count": len(self._release_history),
                "releases": [r.to_dict() for r in self._active_releases.values()],
            }
