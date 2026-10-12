"""
core.learning - Self-Evolving Intelligence Engine for AutoDev (v3.1)

Exposes autonomous learning, reflection, pattern discovery, prompt optimization,
execution analytics, architecture recommendations, playbooks, self-improvement planning,
knowledge evolution, and performance benchmarking.
"""

from core.learning.architecture_recommender import ArchitectureRecommendationEngine
from core.learning.execution_analytics import ExecutionAnalyticsEngine
from core.learning.knowledge_evolution import KnowledgeEvolutionEngine
from core.learning.learning_coordinator import LearningCoordinator, SelfEvolvingEngine
from core.learning.learning_engine import LearningEngine
from core.learning.learning_models import (
    ArchitectureRecommendation,
    EngineeringPattern,
    EngineeringPlaybook,
    ImprovementArea,
    ImprovementRoadmapItem,
    LearningEvent,
    LearningEventType,
    LearningKnowledge,
    LearningSession,
    LearningSnapshot,
    PatternCategory,
    PerformanceEvolutionRecord,
    PlaybookArchetype,
    PromptOptimizationRecord,
    ReflectionReport,
    ReflectionScope,
    SelfImprovementPlan,
)
from core.learning.pattern_miner import PatternMiningEngine
from core.learning.performance_evolution import PerformanceEvolutionEngine
from core.learning.playbook_engine import PlaybookEngine
from core.learning.prompt_optimizer import PromptOptimizationEngine
from core.learning.reflection_engine import ReflectionEngine
from core.learning.self_improvement_planner import SelfImprovementPlanner

__all__ = [
    # Subsystems
    "LearningEngine",
    "ReflectionEngine",
    "PatternMiningEngine",
    "PromptOptimizationEngine",
    "ExecutionAnalyticsEngine",
    "ArchitectureRecommendationEngine",
    "PlaybookEngine",
    "SelfImprovementPlanner",
    "KnowledgeEvolutionEngine",
    "PerformanceEvolutionEngine",
    "SelfEvolvingEngine",
    # Models & Enums
    "LearningEventType",
    "PatternCategory",
    "PlaybookArchetype",
    "ReflectionScope",
    "ImprovementArea",
    "LearningEvent",
    "LearningSession",
    "LearningSnapshot",
    "LearningKnowledge",
    "EngineeringPattern",
    "ReflectionReport",
    "PromptOptimizationRecord",
    "ArchitectureRecommendation",
    "EngineeringPlaybook",
    "ImprovementRoadmapItem",
    "SelfImprovementPlan",
    "PerformanceEvolutionRecord",
]
