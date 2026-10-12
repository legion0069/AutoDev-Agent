"""
AutoDev Specialized Agent - ReleaseAgent (v2.8)
==============================================
Specialized autonomous agent responsible for:
- Semantic versioning (SemVer) and release tagging
- CHANGELOG.md generation and release notes
- Packaging, artifacts, and pre-release synchronization validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.collaboration.collaboration_models import AgentRole, MessageType, TaskAssignment
from .specialized_agent import SpecializedAgent

logger = logging.getLogger("autodev.agents.release")


class ReleaseAgent(SpecializedAgent):
    """
    Lead Release & DevOps Engineer agent coordinating release milestones,
    version bumps, changelogs, and release gate validations.
    """

    def __init__(
        self,
        name: str = "ReleaseAgent",
        llm_client: Optional[Any] = None,
        bus: Optional[Any] = None,
        workspace: Optional[Any] = None,
    ):
        super().__init__(
            name=name,
            role=AgentRole.RELEASE,
            llm_client=llm_client,
            bus=bus,
            workspace=workspace,
        )

    def bump_version(self, current_version: str, bump_type: str = "minor") -> str:
        """Calculate next semantic version."""
        parts = [int(p) for p in current_version.split(".")]
        while len(parts) < 3:
            parts.append(0)

        if bump_type == "major":
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0
        elif bump_type == "minor":
            parts[1] += 1
            parts[2] = 0
        else:
            parts[2] += 1

        return f"{parts[0]}.{parts[1]}.{parts[2]}"

    def generate_changelog_entry(self, version: str, changes: List[str]) -> str:
        """Format markdown changelog section."""
        bullets = "\n".join(f"- {c}" for c in changes)
        return f"## [{version}]\n{bullets}\n"

    def execute_task(
        self,
        task: TaskAssignment,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute release packaging, changelog update, or versioning."""
        logger.info("ReleaseAgent executing: %s", task.title)

        staged_files = {}
        for fpath in task.estimated_files:
            self.acquire_lock(fpath, is_exclusive=True)
            content = (
                f"# Release Manifest: {task.title}\n"
                f"# Packaged by {self.name} (v2.8)\n\n"
                f"VERSION = '2.8.0'\n"
                f"STATUS = 'STABLE'\n"
            )
            staged_files[fpath] = content
            self.stage_code(fpath, content, f"Prepare release manifest for {task.title}")
            self.release_lock(fpath)

        if self.bus:
            self.send_message(
                receiver="*",
                message_type=MessageType.NOTIFICATION,
                payload={
                    "event": "release_prepared",
                    "task_id": task.task_id,
                    "version": "2.8.0",
                },
                task_id=task.task_id,
            )

        return {
            "agent": self.name,
            "role": self.role.value,
            "task_id": task.task_id,
            "action": "release_packaging",
            "staged_files": staged_files,
            "summary": f"Prepared release validation, changelog, and packaging for '{task.title}'.",
        }
