"""
product_manager.py - Product Management Engine & Requirement Decomposition for AutoDev (v3.0)

Translates high-level business requirements into structured Epics, Features, User Stories,
Acceptance Criteria, and Engineering Task specifications with automated RICE prioritization.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    AcceptanceCriteria,
    Epic,
    PriorityLevel,
    ProductFeature,
    ProductVision,
    UserStory,
)

logger = logging.getLogger("AutoDev.Enterprise.Product")


class ProductManager:
    """
    Autonomous Product Management Engine.
    Handles product vision, backlog synthesis, RICE prioritization, and sprint backlog generation.
    """

    def __init__(self, vision: Optional[ProductVision] = None) -> None:
        self._lock = threading.RLock()
        self.vision = vision or ProductVision(
            vision_statement="AutoDev: Complete Autonomous AI Software Company executing world-class engineering.",
            target_market="Enterprise Software Companies & High-Scale Engineering Teams",
            value_proposition="100x developer productivity with verified quality and zero human bottlenecks.",
            key_differentiators=["Deterministic Execution", "100% Native Architecture", "Full-Lifecycle Autonomy"],
        )
        self._epics: Dict[str, Epic] = {}
        self._features: Dict[str, ProductFeature] = {}
        self._user_stories: Dict[str, UserStory] = {}
        self._backlog: List[str] = []  # List of story_ids in priority order

    def get_product_vision(self) -> ProductVision:
        with self._lock:
            return copy.deepcopy(self.vision)

    def set_vision(self, vision: ProductVision) -> None:
        with self._lock:
            self.vision = copy.deepcopy(vision)

    def update_product_vision(
        self,
        vision_statement: str,
        target_market: str,
        value_proposition: str,
        key_differentiators: List[str],
    ) -> ProductVision:
        with self._lock:
            self.vision = ProductVision(
                vision_statement=vision_statement,
                target_market=target_market,
                value_proposition=value_proposition,
                key_differentiators=list(key_differentiators),
                updated_at=time.time(),
            )
            return copy.deepcopy(self.vision)

    def create_epic(
        self,
        title: str,
        description: str,
        strategic_theme: str = "Core Platform",
        target_quarter: str = "Q1",
        estimated_roi_multiplier: float = 3.0,
    ) -> Epic:
        """Creates and tracks a new product epic."""
        with self._lock:
            e_id = f"EPIC-{int(time.time()*1000)}-{len(self._epics)+1:03d}"
            epic = Epic(
                epic_id=e_id,
                title=title,
                description=description,
                strategic_theme=strategic_theme,
                target_quarter=target_quarter,
                estimated_roi_multiplier=estimated_roi_multiplier,
            )
            self._epics[e_id] = epic
            logger.info("Created Epic %s: '%s' (%s)", e_id, title, target_quarter)
            return copy.deepcopy(epic)

    def create_feature(
        self,
        epic_id: str,
        name: str,
        description: str,
        business_value: float = 100.0,
        reach: int = 1000,
        impact: float = 2.0,
        confidence: float = 0.8,
        effort: float = 5.0,
        target_release: str = "v3.0.0",
        dependencies: Optional[List[str]] = None,
    ) -> ProductFeature:
        """Creates a feature within an Epic and computes its RICE score."""
        with self._lock:
            f_id = f"FEAT-{int(time.time()*1000)}-{len(self._features)+1:03d}"
            feat = ProductFeature(
                feature_id=f_id,
                epic_id=epic_id,
                name=name,
                description=description,
                business_value=business_value,
                reach=reach,
                impact=impact,
                confidence=confidence,
                effort=effort,
                target_release=target_release,
                dependencies=dependencies or [],
            )
            self._features[f_id] = feat
            if epic_id in self._epics:
                self._epics[epic_id].features.append(feat)
            logger.info("Created Feature %s ('%s', RICE=%.1f) under Epic %s", f_id, name, feat.rice_score, epic_id)
            return copy.deepcopy(feat)

    def create_user_story(
        self,
        feature_id: str,
        title: str,
        user_role: str,
        action: str,
        benefit: str,
        story_points: int = 3,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        criteria_specs: Optional[List[Tuple[str, str, str]]] = None,
    ) -> UserStory:
        """Creates an atomic user story with Gherkin acceptance criteria."""
        with self._lock:
            s_id = f"US-{int(time.time()*1000)}-{len(self._user_stories)+1:03d}"
            criteria: List[AcceptanceCriteria] = []
            
            if criteria_specs:
                for idx, (g, w, t) in enumerate(criteria_specs):
                    criteria.append(AcceptanceCriteria(
                        criterion_id=f"AC-{s_id}-{idx+1}",
                        given=g,
                        when=w,
                        then=t,
                    ))

            story = UserStory(
                story_id=s_id,
                feature_id=feature_id,
                title=title,
                user_role=user_role,
                action=action,
                benefit=benefit,
                story_points=story_points,
                priority=priority,
                acceptance_criteria=criteria,
            )

            self._user_stories[s_id] = story
            self._backlog.append(s_id)

            if feature_id in self._features:
                self._features[feature_id].user_stories.append(story)

            logger.debug("Created UserStory %s: '%s' (%d pts)", s_id, title, story_points)
            return copy.deepcopy(story)

    def add_acceptance_criterion(
        self,
        story_id: str,
        given: str,
        when: str,
        then: str,
    ) -> AcceptanceCriteria:
        """Adds a Gherkin acceptance criterion to an existing user story."""
        with self._lock:
            story = self._user_stories.get(story_id)
            if not story:
                raise KeyError(f"Story {story_id} not found")

            crit_id = f"AC-{story_id}-{len(story.acceptance_criteria) + 1}"
            crit = AcceptanceCriteria(criterion_id=crit_id, given=given, when=when, then=then)
            story.acceptance_criteria.append(crit)
            return copy.deepcopy(crit)

    def get_prioritized_backlog(self) -> List[UserStory]:
        """
        Sorts product backlog by parent feature RICE score descending and priority.
        """
        with self._lock:
            priority_weight = {
                PriorityLevel.CRITICAL: 1000.0,
                PriorityLevel.HIGH: 500.0,
                PriorityLevel.MEDIUM: 100.0,
                PriorityLevel.LOW: 10.0,
            }

            def story_sort_key(s_id: str) -> float:
                story = self._user_stories.get(s_id)
                if not story:
                    return 0.0
                feat = self._features.get(story.feature_id)
                rice = feat.rice_score if feat else 0.0
                p_weight = priority_weight.get(story.priority, 100.0)
                return rice + p_weight

            sorted_ids = sorted(self._user_stories.keys(), key=story_sort_key, reverse=True)
            return [copy.deepcopy(self._user_stories[sid]) for sid in sorted_ids]

    prioritize_backlog_rice = get_prioritized_backlog

    def get_epic(self, epic_id: str) -> Optional[Epic]:
        with self._lock:
            e = self._epics.get(epic_id)
            return copy.deepcopy(e) if e else None

    def get_feature(self, feature_id: str) -> Optional[ProductFeature]:
        with self._lock:
            f = self._features.get(feature_id)
            return copy.deepcopy(f) if f else None

    def get_user_story(self, story_id: str) -> Optional[UserStory]:
        with self._lock:
            s = self._user_stories.get(story_id)
            return copy.deepcopy(s) if s else None

    def list_epics(self) -> List[Epic]:
        with self._lock:
            return [copy.deepcopy(e) for e in self._epics.values()]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes ProductManager state."""
        with self._lock:
            return {
                "vision": self.vision.to_dict(),
                "total_epics": len(self._epics),
                "total_features": len(self._features),
                "total_user_stories": len(self._user_stories),
                "epics": [e.to_dict() for e in self._epics.values()],
            }
