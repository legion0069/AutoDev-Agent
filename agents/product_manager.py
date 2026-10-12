"""
product_manager.py - Product Manager Agent (AutoDev Version 3.4)

Directs product roadmap, sprint goals, and customer value:
- Product Roadmap and strategic release milestones
- Sprint Goal definition and backlog prioritization
- Customer Value Score and Business Impact estimation
- Feature dependency mapping and delivery sequencing
- Customer requirement intake and satisfaction alignment
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.ProductManager")


class ProductManagerAgent:
    """
    Autonomous Product Manager AI Agent.
    """

    def __init__(
        self,
        name: str = "ProductManager",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 3  # Managerial Product
        self.roadmap_milestones: List[Dict[str, Any]] = []

        if self.bus:
            self.bus.register_entity(self.name)

    def prioritize_backlog(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ranks backlog features by RICE-inspired Customer Value Score:
        Score = (Reach * Impact * Confidence) / Effort
        """
        scored_features = []
        for feat in features:
            reach = feat.get("reach", 10.0)
            impact = feat.get("impact", 3.0)  # 1 to 5
            conf = feat.get("confidence", 0.8)
            effort = max(1.0, feat.get("effort_days", 2.0))

            score = round((reach * impact * conf) / effort, 2)
            item = dict(feat)
            item["customer_value_score"] = score
            scored_features.append(item)

        scored_features.sort(key=lambda x: -x["customer_value_score"])
        return scored_features

    def define_sprint_goal(self, selected_features: List[str]) -> Dict[str, Any]:
        """Formulates a concise, measurable sprint goal."""
        joined = ", ".join(selected_features[:3])
        goal = f"Deliver production-ready capability for: {joined}"

        result = {
            "sprint_goal": goal,
            "features_committed": selected_features,
            "target_completion_days": 14,
            "customer_value_score": 92.5,
            "timestamp": time.time(),
        }

        logger.info("Sprint Goal defined: '%s'", goal)
        return result

    def update_roadmap(self, quarter: str, milestones: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Updates official quarterly product roadmap."""
        self.roadmap_milestones.extend(milestones)
        if self.state:
            self.state.update_roadmap(quarter, milestones)

        return {
            "quarter": quarter,
            "milestones_count": len(milestones),
            "status": "ROADMAP_UPDATED",
        }
