"""
learning_models.py - Domain Models and Data Contracts for Self-Evolving Intelligence (v3.1)

Defines dataclasses, enumerations, DTOs, and serialization schemas for autonomous learning,
reflection, pattern mining, prompt optimization, execution analytics, architecture recommendations,
engineering playbooks, self-improvement planning, knowledge evolution, and performance evolution.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ---------------------------------------------------------------------------
# 1. Learning & Reflection Enums
# ---------------------------------------------------------------------------

class LearningEventType(str, Enum):
    BUG_FIXED = "BUG_FIXED"
    PATTERN_DISCOVERED = "PATTERN_DISCOVERED"
    REVIEW_FAILURE = "REVIEW_FAILURE"
    ARCHITECTURE_SUCCESS = "ARCHITECTURE_SUCCESS"
    PERFORMANCE_IMPROVEMENT = "PERFORMANCE_IMPROVEMENT"
    TEST_STRATEGY = "TEST_STRATEGY"
    REFACTOR_SUCCESS = "REFACTOR_SUCCESS"
    DEPLOYMENT_FAILURE = "DEPLOYMENT_FAILURE"
    PROMPT_TUNED = "PROMPT_TUNED"
    PLAYBOOK_CREATED = "PLAYBOOK_CREATED"
    CODE_SMELL_RESOLVED = "CODE_SMELL_RESOLVED"
    CONCURRENCY_FIXED = "CONCURRENCY_FIXED"
    SECURITY_VULNERABILITY_PATCHED = "SECURITY_VULNERABILITY_PATCHED"
    API_CONTRACT_STABILIZED = "API_CONTRACT_STABILIZED"


class PatternCategory(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    ARCHITECTURAL = "ARCHITECTURE"
    BUG_FIX = "BUG_FIX"
    FILE_LAYOUT = "FILE_LAYOUT"
    API_DESIGN = "API_DESIGN"
    TESTING = "TESTING"
    TEST_PATTERN = "TESTING"
    PROMPT_TEMPLATE = "PROMPT_TEMPLATE"
    REFACTORING = "REFACTORING"
    CONCURRENCY = "CONCURRENCY"
    SECURITY = "SECURITY"
    CODING_CONVENTION = "CODING_CONVENTION"
    PERFORMANCE = "PERFORMANCE"


class PlaybookArchetype(str, Enum):
    REST_API = "REST_API"
    SPRING_BOOT = "SPRING_BOOT"
    PYTHON_CLI = "PYTHON_CLI"
    AI_AGENT = "AI_AGENT"
    WEB_DASHBOARD = "WEB_DASHBOARD"
    MICROSERVICES = "MICROSERVICES"
    AUTHENTICATION = "AUTHENTICATION"
    CRUD_APPLICATION = "CRUD_APPLICATION"
    CRUD = "CRUD_APPLICATION"
    EVENT_STREAMING = "EVENT_STREAMING"
    EVENT_DRIVEN = "EVENT_STREAMING"
    DISTRIBUTED_WORKER = "DISTRIBUTED_WORKER"
    LLM_INTEGRATION = "AI_AGENT"


class ReflectionScope(str, Enum):
    TASK = "TASK"
    SPRINT = "SPRINT"
    RELEASE = "RELEASE"
    MONTHLY = "MONTHLY"
    PROJECT = "PROJECT"


class ImprovementArea(str, Enum):
    RETRY_ENGINE = "RETRY_ENGINE"
    PLANNING = "PLANNING"
    PROMPT_ENGINEERING = "PROMPT_ENGINEERING"
    PROMPT_SYNTHESIS = "PROMPT_ENGINEERING"
    PROMPTS = "PROMPT_ENGINEERING"
    TESTING_STRATEGY = "TESTING_STRATEGY"
    TEST_COVERAGE = "TESTING_STRATEGY"
    TESTING = "TESTING_STRATEGY"
    ORCHESTRATION = "ORCHESTRATION"
    ARCHITECTURE_MODELING = "ARCHITECTURE_MODELING"
    ARCHITECTURE = "ARCHITECTURE_MODELING"
    MEMORY_MANAGEMENT = "MEMORY_MANAGEMENT"
    SECURITY_GOVERNANCE = "SECURITY_GOVERNANCE"
    CODE_QUALITY = "CODE_QUALITY"
    PERFORMANCE_EFFICIENCY = "PERFORMANCE_EFFICIENCY"
    PERFORMANCE = "PERFORMANCE_EFFICIENCY"
    RELIABILITY = "RETRY_ENGINE"


# ---------------------------------------------------------------------------
# 2. Learning Core Data Contracts
# ---------------------------------------------------------------------------

@dataclass
class LearningEvent:
    """Represents a discrete learning event generated from execution outcomes."""
    id: str = field(default_factory=lambda: f"EVT-{int(time.time() * 1000)}")
    event_id: str = ""
    timestamp: float = field(default_factory=time.time)
    project: str = "default_project"
    project_id: str = ""
    task: str = "task_0"
    task_id: str = ""
    category: LearningEventType = LearningEventType.BUG_FIXED
    confidence: float = 0.85          # 0.0 - 1.0
    importance: float = 75.0          # 0.0 - 100.0
    summary: str = ""
    affected_files: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    root_cause: str = ""
    solution: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.event_id:
            self.id = self.event_id
        elif self.id:
            self.event_id = self.id
        if self.task_id:
            self.task = self.task_id
        elif self.task:
            self.task_id = self.task
        if self.project_id:
            self.project = self.project_id
        elif self.project:
            self.project_id = self.project
        if not self.files and self.affected_files:
            self.files = list(self.affected_files)
        elif not self.affected_files and self.files:
            self.affected_files = list(self.files)
        if not self.key_metrics and self.metrics:
            self.key_metrics = dict(self.metrics)
        elif not self.metrics and self.key_metrics:
            self.metrics = dict(self.key_metrics)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, Enum) else str(self.category)
        d["id"] = self.id
        d["event_id"] = self.event_id or self.id
        d["task"] = self.task
        d["task_id"] = self.task_id or self.task
        d["project"] = self.project
        d["project_id"] = self.project_id or self.project
        d["affected_files"] = self.affected_files or self.files
        d["files"] = self.files or self.affected_files
        d["metrics"] = self.metrics or self.key_metrics
        d["key_metrics"] = self.key_metrics or self.metrics
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LearningEvent:
        d = dict(data)
        if isinstance(d.get("category"), str):
            d["category"] = LearningEventType(d["category"])
        if "id" in d and "event_id" not in d:
            d["event_id"] = d["id"]
        if "event_id" in d and "id" not in d:
            d["id"] = d["event_id"]
        if "task" in d and "task_id" not in d:
            d["task_id"] = d["task"]
        if "task_id" in d and "task" not in d:
            d["task"] = d["task_id"]
        if "files" in d and "affected_files" not in d:
            d["affected_files"] = d["files"]
        if "affected_files" in d and "files" not in d:
            d["files"] = d["affected_files"]
        if "key_metrics" in d and "metrics" not in d:
            d["metrics"] = d["key_metrics"]
        if "metrics" in d and "key_metrics" not in d:
            d["key_metrics"] = d["metrics"]
        return cls(**d)

    @classmethod
    def from_json(cls, json_str: str) -> LearningEvent:
        return cls.from_dict(json.loads(json_str))


@dataclass
class LearningSession:
    """Tracks a learning session spanning tasks or project iterations."""
    session_id: str = field(default_factory=lambda: f"SESS-{int(time.time() * 1000)}")
    id: str = ""
    project: str = "default_project"
    project_id: str = ""
    events: List[Any] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    events_count: int = 0
    patterns_discovered: int = 0
    reflections_count: int = 0
    status: str = "ACTIVE"
    summary: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id:
            self.session_id = self.id
        elif self.session_id:
            self.id = self.session_id
        if self.project_id:
            self.project = self.project_id
        elif self.project:
            self.project_id = self.project
        if self.events and not self.events_count:
            self.events_count = len(self.events)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id or self.session_id
        d["session_id"] = self.session_id or self.id
        d["project"] = self.project
        d["project_id"] = self.project_id or self.project
        d["events"] = [e.to_dict() if isinstance(e, LearningEvent) else e for e in self.events]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LearningSession:
        d = dict(data)
        if "events" in d and isinstance(d["events"], list):
            d["events"] = [
                LearningEvent.from_dict(e) if isinstance(e, dict) else e
                for e in d["events"]
            ]
        if "id" in d and "session_id" not in d:
            d["session_id"] = d["id"]
        if "session_id" in d and "id" not in d:
            d["id"] = d["session_id"]
        if "project" in d and "project_id" not in d:
            d["project_id"] = d["project"]
        if "project_id" in d and "project" not in d:
            d["project"] = d["project_id"]
        return cls(**d)


@dataclass
class LearningSnapshot:
    """Point-in-time snapshot of collective learned intelligence."""
    snapshot_id: str = field(default_factory=lambda: f"SNAP-{int(time.time() * 1000)}")
    id: str = ""
    project: str = "default_project"
    timestamp: float = field(default_factory=time.time)
    total_events: int = 0
    total_patterns: int = 0
    total_reflections: int = 0
    active_playbooks: int = 0
    average_confidence: float = 0.0
    categories_count: Dict[str, int] = field(default_factory=dict)
    events_by_category: Dict[str, int] = field(default_factory=dict)
    events: List[Any] = field(default_factory=list)
    key_learnings: List[str] = field(default_factory=list)
    summary_stats: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id:
            self.snapshot_id = self.id
        elif self.snapshot_id:
            self.id = self.snapshot_id
        if not self.events_by_category and self.categories_count:
            self.events_by_category = dict(self.categories_count)
        elif not self.categories_count and self.events_by_category:
            self.categories_count = dict(self.events_by_category)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id or self.snapshot_id
        d["snapshot_id"] = self.snapshot_id or self.id
        d["events_by_category"] = self.events_by_category or self.categories_count
        d["categories_count"] = self.categories_count or self.events_by_category
        d["events"] = [e.to_dict() if isinstance(e, LearningEvent) else e for e in self.events]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LearningSnapshot:
        d = dict(data)
        if "events" in d and isinstance(d["events"], list):
            d["events"] = [
                LearningEvent.from_dict(e) if isinstance(e, dict) else e
                for e in d["events"]
            ]
        if "id" in d and "snapshot_id" not in d:
            d["snapshot_id"] = d["id"]
        if "snapshot_id" in d and "id" not in d:
            d["id"] = d["snapshot_id"]
        if "events_by_category" in d and "categories_count" not in d:
            d["categories_count"] = d["events_by_category"]
        if "categories_count" in d and "events_by_category" not in d:
            d["events_by_category"] = d["categories_count"]
        return cls(**d)


@dataclass
class LearningKnowledge:
    """Distilled institutional knowledge item generated from aggregated learning events."""
    knowledge_id: str = field(default_factory=lambda: f"KNW-{int(time.time() * 1000)}")
    id: str = ""
    domain: str = "General"
    category: str = ""
    topic: str = ""
    title: str = ""
    summary: str = ""
    content: str = ""
    details: str = ""
    evidence_events: List[str] = field(default_factory=list)
    source_events: List[str] = field(default_factory=list)
    confidence: float = 0.85
    utility_score: float = 50.0       # 0.0 - 100.0
    promoted: bool = False
    usage_count: int = 0
    status: str = "ACTIVE"
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    last_applied: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.id:
            self.knowledge_id = self.id
        elif self.knowledge_id:
            self.id = self.knowledge_id
        if not self.category and self.domain:
            self.category = self.domain
        elif not self.domain and self.category:
            self.domain = self.category
        if not self.title and self.topic:
            self.title = self.topic
        elif not self.topic and self.title:
            self.topic = self.title
        if not self.content and self.summary:
            self.content = self.summary
        elif not self.summary and self.content:
            self.summary = self.content
        if not self.source_events and self.evidence_events:
            self.source_events = list(self.evidence_events)
        elif not self.evidence_events and self.source_events:
            self.evidence_events = list(self.source_events)
        if not self.last_applied and self.last_accessed:
            self.last_applied = self.last_accessed

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id or self.knowledge_id
        d["knowledge_id"] = self.knowledge_id or self.id
        d["category"] = self.category or self.domain
        d["domain"] = self.domain or self.category
        d["title"] = self.title or self.topic
        d["topic"] = self.topic or self.title
        d["content"] = self.content or self.summary
        d["summary"] = self.summary or self.content
        d["status"] = self.status
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LearningKnowledge:
        d = dict(data)
        if "id" in d and "knowledge_id" not in d:
            d["knowledge_id"] = d["id"]
        if "knowledge_id" in d and "id" not in d:
            d["id"] = d["knowledge_id"]
        if "category" in d and "domain" not in d:
            d["domain"] = d["category"]
        if "domain" in d and "category" not in d:
            d["category"] = d["domain"]
        if "title" in d and "topic" not in d:
            d["topic"] = d["title"]
        if "topic" in d and "title" not in d:
            d["title"] = d["topic"]
        if "content" in d and "summary" not in d:
            d["summary"] = d["content"]
        if "summary" in d and "content" not in d:
            d["content"] = d["summary"]
        if "source_events" in d and "evidence_events" not in d:
            d["evidence_events"] = d["source_events"]
        if "evidence_events" in d and "source_events" not in d:
            d["source_events"] = d["evidence_events"]
        return cls(**d)


# ---------------------------------------------------------------------------
# 3. Pattern Mining Data Contracts
# ---------------------------------------------------------------------------

@dataclass
class EngineeringPattern:
    """Reusable discovered engineering pattern mined from historical codebase executions."""
    id: str = field(default_factory=lambda: f"PAT-{int(time.time() * 1000)}")
    pattern_id: str = ""
    name: str = ""
    pattern_name: str = ""
    category: PatternCategory = PatternCategory.ARCHITECTURE
    description: str = ""
    solution: str = ""
    structure_template: Dict[str, Any] = field(default_factory=dict)
    template_structure: Dict[str, Any] = field(default_factory=dict)
    applicable_scenarios: List[str] = field(default_factory=list)
    context_conditions: List[str] = field(default_factory=list)
    usage_count: int = 1
    confidence: float = 0.80          # 0.0 - 1.0
    quality_score: float = 90.0       # 0.0 - 100.0
    success_rate: float = 1.0         # 0.0 - 1.0
    last_used: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    historical_instances: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.pattern_id:
            self.id = self.pattern_id
        elif self.id:
            self.pattern_id = self.id
        if self.pattern_name:
            self.name = self.pattern_name
        elif self.name:
            self.pattern_name = self.name
        if not self.solution and self.description:
            self.solution = self.description
        elif not self.description and self.solution:
            self.description = self.solution
        if not self.template_structure and self.structure_template:
            self.template_structure = dict(self.structure_template)
        elif not self.structure_template and self.template_structure:
            self.structure_template = dict(self.template_structure)
        if not self.context_conditions and self.applicable_scenarios:
            self.context_conditions = list(self.applicable_scenarios)
        elif not self.applicable_scenarios and self.context_conditions:
            self.applicable_scenarios = list(self.context_conditions)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, Enum) else str(self.category)
        d["id"] = self.id
        d["pattern_id"] = self.pattern_id or self.id
        d["name"] = self.name
        d["pattern_name"] = self.pattern_name or self.name
        d["solution"] = self.solution or self.description
        d["structure_template"] = self.structure_template
        d["template_structure"] = self.template_structure or self.structure_template
        d["applicable_scenarios"] = self.applicable_scenarios
        d["context_conditions"] = self.context_conditions or self.applicable_scenarios
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EngineeringPattern:
        d = dict(data)
        if isinstance(d.get("category"), str):
            cat_str = d["category"]
            if cat_str in ("TEST_PATTERN", "TESTING"):
                d["category"] = PatternCategory.TESTING
            elif cat_str in ("ARCHITECTURAL", "ARCHITECTURE"):
                d["category"] = PatternCategory.ARCHITECTURE
            else:
                try:
                    d["category"] = PatternCategory(cat_str)
                except Exception:
                    d["category"] = PatternCategory.ARCHITECTURE
        if "id" in d and "pattern_id" not in d:
            d["pattern_id"] = d["id"]
        if "pattern_id" in d and "id" not in d:
            d["id"] = d["pattern_id"]
        if "name" in d and "pattern_name" not in d:
            d["pattern_name"] = d["name"]
        if "pattern_name" in d and "name" not in d:
            d["name"] = d["pattern_name"]
        if "structure_template" in d and "template_structure" not in d:
            d["template_structure"] = d["structure_template"]
        if "template_structure" in d and "structure_template" not in d:
            d["structure_template"] = d["template_structure"]
        if "applicable_scenarios" in d and "context_conditions" not in d:
            d["context_conditions"] = d["applicable_scenarios"]
        if "context_conditions" in d and "applicable_scenarios" not in d:
            d["applicable_scenarios"] = d["context_conditions"]
        return cls(**d)


# ---------------------------------------------------------------------------
# 4. Reflection Data Contracts
# ---------------------------------------------------------------------------

@dataclass
class ReflectionReport:
    """Structured report produced after reflecting on a task, sprint, release, or month."""
    id: str = field(default_factory=lambda: f"REF-{int(time.time() * 1000)}")
    reflection_id: str = ""
    scope: ReflectionScope = ReflectionScope.TASK
    target_id: str = ""
    entity_id: str = ""
    task_id: str = ""
    task: str = ""
    task_title: str = ""
    sprint_number: Optional[int] = None
    release_version: str = ""
    month_label: str = ""
    timestamp: float = field(default_factory=time.time)
    execution_success: bool = True
    success: bool = True
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    why_analysis: Any = field(default_factory=list)
    root_causes: List[str] = field(default_factory=list)
    how_to_improve: List[str] = field(default_factory=list)
    improvement_actions: List[str] = field(default_factory=list)
    key_takeaways: List[str] = field(default_factory=list)
    excessive_retries: bool = False
    retries_count: int = 0
    retry_count: int = 0
    planning_accurate: bool = True
    planning_accuracy: float = 1.0
    planning_accuracy_score: float = 90.0
    tests_sufficient: bool = True
    test_sufficiency: str = "HIGH"
    gate_pass_rate: float = 100.0
    prompts_oversized: bool = False
    prompt_too_large: bool = False
    prompt_bloated: bool = False
    prompt_tokens_estimate: int = 0
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    actionable_recommendations: List[str] = field(default_factory=list)
    summary: str = ""

    def __post_init__(self) -> None:
        if self.reflection_id:
            self.id = self.reflection_id
        elif self.id:
            self.reflection_id = self.id
        if self.entity_id:
            self.target_id = self.entity_id
        elif self.target_id:
            self.entity_id = self.target_id
        if self.task_id:
            self.task = self.task_id
        elif self.task:
            self.task_id = self.task
        if not self.target_id and self.task_id:
            self.target_id = self.task_id
            self.entity_id = self.task_id
        elif not self.task_id and self.target_id:
            self.task_id = self.target_id
            self.task = self.target_id
        if not self.root_causes and self.why_analysis:
            if isinstance(self.why_analysis, list):
                self.root_causes = list(self.why_analysis)
            else:
                self.root_causes = [str(self.why_analysis)]
        elif not self.why_analysis and self.root_causes:
            self.why_analysis = list(self.root_causes)
        if not self.improvement_actions and self.how_to_improve:
            self.improvement_actions = list(self.how_to_improve)
        elif not self.how_to_improve and self.improvement_actions:
            self.how_to_improve = list(self.improvement_actions)
        if not self.prompt_too_large and self.prompts_oversized:
            self.prompt_too_large = self.prompts_oversized
        elif not self.prompts_oversized and self.prompt_too_large:
            self.prompts_oversized = self.prompt_too_large
        if not self.prompt_bloated:
            self.prompt_bloated = bool(self.prompt_too_large or self.prompts_oversized)
        if not self.metrics and self.key_metrics:
            self.metrics = dict(self.key_metrics)
        elif not self.key_metrics and self.metrics:
            self.key_metrics = dict(self.metrics)
        if not self.success and self.execution_success:
            self.success = self.execution_success
        elif not self.execution_success and self.success:
            self.execution_success = self.success

    def __getitem__(self, item: str) -> Any:
        return self.to_dict()[item]

    def __contains__(self, item: str) -> bool:
        return item in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scope"] = self.scope.value if isinstance(self.scope, Enum) else str(self.scope)
        d["id"] = self.id or self.reflection_id
        d["reflection_id"] = self.reflection_id or self.id
        d["target_id"] = self.target_id
        d["entity_id"] = self.entity_id or self.target_id
        d["task_id"] = self.task_id or self.target_id
        d["task"] = self.task or self.task_id
        d["sprint_number"] = self.sprint_number
        d["release_version"] = self.release_version
        d["execution_success"] = self.execution_success
        d["success"] = self.success
        d["root_causes"] = self.root_causes or (self.why_analysis if isinstance(self.why_analysis, list) else [str(self.why_analysis)])
        d["why_analysis"] = self.why_analysis or self.root_causes
        d["improvement_actions"] = self.improvement_actions or self.how_to_improve
        d["how_to_improve"] = self.how_to_improve or self.improvement_actions
        d["prompt_too_large"] = self.prompt_too_large or self.prompts_oversized
        d["prompt_bloated"] = self.prompt_bloated or self.prompt_too_large
        d["metrics"] = self.metrics or self.key_metrics
        d["key_metrics"] = self.key_metrics or self.metrics
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReflectionReport:
        d = dict(data)
        if isinstance(d.get("scope"), str):
            d["scope"] = ReflectionScope(d["scope"])
        if "id" in d and "reflection_id" not in d:
            d["reflection_id"] = d["id"]
        if "reflection_id" in d and "id" not in d:
            d["id"] = d["reflection_id"]
        if "target_id" in d and "entity_id" not in d:
            d["entity_id"] = d["target_id"]
        if "entity_id" in d and "target_id" not in d:
            d["target_id"] = d["entity_id"]
        if "task" in d and "task_id" not in d:
            d["task_id"] = d["task"]
        if "task_id" in d and "task" not in d:
            d["task"] = d["task_id"]
        if "root_causes" in d and "why_analysis" not in d:
            d["why_analysis"] = d["root_causes"]
        if "why_analysis" in d and "root_causes" not in d:
            d["root_causes"] = d["why_analysis"] if isinstance(d["why_analysis"], list) else [str(d["why_analysis"])]
        if "improvement_actions" in d and "how_to_improve" not in d:
            d["how_to_improve"] = d["improvement_actions"]
        if "how_to_improve" in d and "improvement_actions" not in d:
            d["improvement_actions"] = d["how_to_improve"]
        if "prompt_too_large" in d and "prompts_oversized" not in d:
            d["prompts_oversized"] = d["prompt_too_large"]
        if "prompts_oversized" in d and "prompt_too_large" not in d:
            d["prompt_too_large"] = d["prompts_oversized"]
        if "metrics" in d and "key_metrics" not in d:
            d["key_metrics"] = d["metrics"]
        if "key_metrics" in d and "metrics" not in d:
            d["metrics"] = d["key_metrics"]
        return cls(**d)


# ---------------------------------------------------------------------------
# 5. Prompt Optimization Data Contracts
# ---------------------------------------------------------------------------

@dataclass
class PromptOptimizationRecord:
    """Tracks token efficiency, compression ratios, and quality scores for prompt templates."""
    template_id: str = field(default_factory=lambda: f"TPL-{int(time.time() * 1000)}")
    record_id: str = ""
    id: str = ""
    task_type: str = "coding"
    template_key: str = ""
    original_prompt: str = ""
    optimized_prompt: str = ""
    template_content: str = ""
    original_tokens: int = 0
    original_length: int = 0
    optimized_tokens: int = 0
    token_count_before: int = 0
    token_count_after: int = 0
    compressed_length: int = 0
    token_compression_ratio: float = 0.0
    compression_ratio: float = 0.0
    retry_count: int = 0
    retry_reduction_pct: float = 0.0
    success_rate: float = 1.0
    token_efficiency_score: float = 90.0
    measured_quality_score: float = 90.0
    discovered_rules: List[str] = field(default_factory=list)
    active_rules: List[str] = field(default_factory=list)
    patterns_applied: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.id:
            self.template_id = self.id
            self.record_id = self.id
        elif self.record_id:
            self.template_id = self.record_id
            self.id = self.record_id
        elif self.template_id:
            self.record_id = self.template_id
            self.id = self.template_id
        if not self.template_key and self.task_type:
            self.template_key = self.task_type
        elif not self.task_type and self.template_key:
            self.task_type = self.template_key
        if not self.template_content and self.optimized_prompt:
            self.template_content = self.optimized_prompt
        elif not self.optimized_prompt and self.template_content:
            self.optimized_prompt = self.template_content
        if not self.token_count_before and (self.original_tokens or self.original_length):
            self.token_count_before = self.original_tokens or self.original_length
        elif not self.original_tokens and self.token_count_before:
            self.original_tokens = self.token_count_before
        if not self.token_count_after and (self.optimized_tokens or self.compressed_length):
            self.token_count_after = self.optimized_tokens or self.compressed_length
        elif not self.optimized_tokens and self.token_count_after:
            self.optimized_tokens = self.token_count_after
        if not self.compression_ratio and self.token_compression_ratio:
            self.compression_ratio = self.token_compression_ratio
        elif not self.token_compression_ratio and self.compression_ratio:
            self.token_compression_ratio = self.compression_ratio
        if not self.measured_quality_score and self.token_efficiency_score:
            self.measured_quality_score = self.token_efficiency_score
        elif not self.token_efficiency_score and self.measured_quality_score:
            self.token_efficiency_score = self.measured_quality_score
        if not self.active_rules and self.discovered_rules:
            self.active_rules = list(self.discovered_rules)
        elif not self.discovered_rules and self.active_rules:
            self.discovered_rules = list(self.active_rules)

    def __getitem__(self, item: str) -> Any:
        return self.to_dict()[item]

    def __contains__(self, item: str) -> bool:
        return item in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["template_id"] = self.template_id
        d["record_id"] = self.record_id or self.template_id
        d["id"] = self.id or self.record_id or self.template_id
        d["task_type"] = self.task_type
        d["template_key"] = self.template_key or self.task_type
        d["optimized_prompt"] = self.optimized_prompt
        d["template_content"] = self.template_content or self.optimized_prompt
        d["token_compression_ratio"] = self.token_compression_ratio
        d["compression_ratio"] = self.compression_ratio or self.token_compression_ratio
        d["token_efficiency_score"] = self.token_efficiency_score
        d["measured_quality_score"] = self.measured_quality_score or self.token_efficiency_score
        d["token_count_before"] = self.token_count_before or self.original_tokens
        d["token_count_after"] = self.token_count_after or self.optimized_tokens
        d["discovered_rules"] = self.discovered_rules
        d["active_rules"] = self.active_rules or self.discovered_rules
        d["patterns_applied"] = self.patterns_applied
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromptOptimizationRecord:
        d = dict(data)
        if "template_id" in d and "record_id" not in d:
            d["record_id"] = d["template_id"]
        if "record_id" in d and "template_id" not in d:
            d["template_id"] = d["record_id"]
        if "task_type" in d and "template_key" not in d:
            d["template_key"] = d["task_type"]
        if "template_key" in d and "task_type" not in d:
            d["task_type"] = d["template_key"]
        return cls(**d)


# ---------------------------------------------------------------------------
# 6. Architecture Recommendation & Playbook Contracts
# ---------------------------------------------------------------------------

@dataclass
class ArchitectureRecommendation:
    """Prescriptive architecture design recommendations derived from historical successes."""
    recommendation_id: str = field(default_factory=lambda: f"REC-{int(time.time() * 1000)}")
    id: str = ""
    project_name: str = ""
    requirement_summary: str = ""
    archetype: Any = PlaybookArchetype.REST_API
    recommended_folder_structure: Any = field(default_factory=dict)
    folder_structure: Any = field(default_factory=dict)
    recommended_structure: Any = field(default_factory=list)
    structure: Any = field(default_factory=dict)
    design_patterns: List[str] = field(default_factory=list)
    recommended_patterns: List[str] = field(default_factory=list)
    database_recommendation: str = "PostgreSQL"
    database_choice: str = ""
    api_style: str = "RESTful JSON"
    testing_strategy: str = "Pytest"
    security_model: str = "JWT / TLS"
    confidence_score: float = 0.90
    confidence: float = 0.90
    rationale: str = ""
    historical_rationale: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.id:
            self.recommendation_id = self.id
        elif self.recommendation_id:
            self.id = self.recommendation_id
        if not self.project_name and self.requirement_summary:
            self.project_name = self.requirement_summary
        elif not self.requirement_summary and self.project_name:
            self.requirement_summary = self.project_name
        if not self.database_choice and self.database_recommendation:
            self.database_choice = self.database_recommendation
        elif not self.database_recommendation and self.database_choice:
            self.database_recommendation = self.database_choice
        if not self.confidence and self.confidence_score:
            self.confidence = self.confidence_score
        elif not self.confidence_score and self.confidence:
            self.confidence_score = self.confidence
        if not self.recommended_patterns and self.design_patterns:
            self.recommended_patterns = list(self.design_patterns)
        elif not self.design_patterns and self.recommended_patterns:
            self.design_patterns = list(self.recommended_patterns)
        if not self.folder_structure and self.recommended_folder_structure:
            self.folder_structure = dict(self.recommended_folder_structure) if isinstance(self.recommended_folder_structure, dict) else self.recommended_folder_structure
        elif not self.recommended_folder_structure and self.folder_structure:
            self.recommended_folder_structure = dict(self.folder_structure) if isinstance(self.folder_structure, dict) else self.folder_structure
        if not self.structure and self.folder_structure:
            self.structure = dict(self.folder_structure) if isinstance(self.folder_structure, dict) else self.folder_structure

    def __getitem__(self, item: str) -> Any:
        d = self.to_dict()
        return d[item]

    def __contains__(self, item: str) -> bool:
        return item in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        arch_val = self.archetype.value if isinstance(self.archetype, Enum) else str(self.archetype)
        d["archetype"] = arch_val
        d["id"] = self.id or self.recommendation_id
        d["recommendation_id"] = self.recommendation_id or self.id
        d["project_name"] = self.project_name
        d["requirement_summary"] = self.requirement_summary or self.project_name
        d["folder_structure"] = self.folder_structure or self.recommended_folder_structure
        d["recommended_folder_structure"] = self.recommended_folder_structure or self.folder_structure
        d["structure"] = self.structure or self.folder_structure
        d["design_patterns"] = self.design_patterns or self.recommended_patterns
        d["recommended_patterns"] = self.recommended_patterns or self.design_patterns
        d["database_choice"] = self.database_choice or self.database_recommendation
        d["database_recommendation"] = self.database_recommendation
        d["confidence"] = self.confidence or self.confidence_score
        d["confidence_score"] = self.confidence_score
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArchitectureRecommendation:
        d = dict(data)
        if isinstance(d.get("archetype"), str):
            arch_str = d["archetype"]
            if arch_str in PlaybookArchetype.__members__:
                d["archetype"] = PlaybookArchetype[arch_str]
            elif arch_str == "CRUD":
                d["archetype"] = PlaybookArchetype.CRUD_APPLICATION
            elif arch_str == "LLM_INTEGRATION":
                d["archetype"] = PlaybookArchetype.AI_AGENT
            elif arch_str == "EVENT_DRIVEN":
                d["archetype"] = PlaybookArchetype.EVENT_STREAMING
            else:
                d["archetype"] = PlaybookArchetype.REST_API
        if "id" in d and "recommendation_id" not in d:
            d["recommendation_id"] = d["id"]
        if "recommendation_id" in d and "id" not in d:
            d["id"] = d["recommendation_id"]
        if "folder_structure" in d and "recommended_folder_structure" not in d:
            d["recommended_folder_structure"] = d["folder_structure"]
        if "recommended_folder_structure" in d and "folder_structure" not in d:
            d["folder_structure"] = d["recommended_folder_structure"]
        return cls(**d)


@dataclass
class EngineeringPlaybook:
    """Pre-built or evolved engineering blueprint for software project archetypes."""
    playbook_id: str = field(default_factory=lambda: f"PB-{int(time.time() * 1000)}")
    id: str = ""
    archetype: PlaybookArchetype = PlaybookArchetype.REST_API
    title: str = ""
    name: str = ""
    description: str = ""
    recommended_sequence: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    estimated_effort_hours: float = 10.0
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    quality_threshold: float = 85.0
    sample_file_structure: List[str] = field(default_factory=list)
    usage_count: int = 1
    success_rate: float = 1.0
    version: str = "1.0.0"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.id:
            self.playbook_id = self.id
        elif self.playbook_id:
            self.id = self.playbook_id
        if self.name:
            self.title = self.name
        elif self.title:
            self.name = self.title

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["archetype"] = self.archetype.value if isinstance(self.archetype, Enum) else str(self.archetype)
        d["id"] = self.id or self.playbook_id
        d["playbook_id"] = self.playbook_id or self.id
        d["name"] = self.name or self.title
        d["title"] = self.title or self.name
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EngineeringPlaybook:
        d = dict(data)
        if isinstance(d.get("archetype"), str):
            arch_str = d["archetype"]
            if arch_str == "CRUD":
                d["archetype"] = PlaybookArchetype.CRUD_APPLICATION
            elif arch_str == "LLM_INTEGRATION":
                d["archetype"] = PlaybookArchetype.AI_AGENT
            elif arch_str == "EVENT_DRIVEN":
                d["archetype"] = PlaybookArchetype.EVENT_STREAMING
            elif arch_str in PlaybookArchetype.__members__:
                d["archetype"] = PlaybookArchetype[arch_str]
            else:
                d["archetype"] = PlaybookArchetype.REST_API
        if "id" in d and "playbook_id" not in d:
            d["playbook_id"] = d["id"]
        if "playbook_id" in d and "id" not in d:
            d["id"] = d["playbook_id"]
        if "name" in d and "title" not in d:
            d["title"] = d["name"]
        if "title" in d and "name" not in d:
            d["name"] = d["title"]
        return cls(**d)


# ---------------------------------------------------------------------------
# 7. Self-Improvement & Performance Contracts
# ---------------------------------------------------------------------------

@dataclass
class ImprovementRoadmapItem:
    """Actionable self-improvement milestone scheduled for internal system enhancement."""
    id: str = field(default_factory=lambda: f"RMAP-{int(time.time() * 1000)}")
    item_id: str = ""
    area: ImprovementArea = ImprovementArea.RETRY_ENGINE
    title: str = ""
    description: str = ""
    identified_weakness: str = ""
    action_plan: str = ""
    priority: str = "P1"              # "P0", "P1", "P2"
    estimated_roi: float = 80.0
    expected_roi_pct: float = 80.0
    effort_days: float = 3.0
    target_subsystem: str = "RetryEngine"
    scheduled_quarter: str = "2026-Q4"
    status: str = "PLANNED"           # PLANNED, IN_PROGRESS, COMPLETED
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.item_id:
            self.id = self.item_id
        elif self.id:
            self.item_id = self.id
        if not self.expected_roi_pct and self.estimated_roi:
            self.expected_roi_pct = self.estimated_roi
        elif not self.estimated_roi and self.expected_roi_pct:
            self.estimated_roi = self.expected_roi_pct

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["area"] = self.area.value if isinstance(self.area, Enum) else str(self.area)
        d["id"] = self.id
        d["item_id"] = self.item_id or self.id
        d["estimated_roi"] = self.estimated_roi
        d["expected_roi_pct"] = self.expected_roi_pct or self.estimated_roi
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ImprovementRoadmapItem:
        d = dict(data)
        if isinstance(d.get("area"), str):
            area_str = d["area"]
            if area_str in ("PROMPT_SYNTHESIS", "PROMPTS"):
                d["area"] = ImprovementArea.PROMPT_ENGINEERING
            elif area_str in ("TEST_COVERAGE", "TESTING"):
                d["area"] = ImprovementArea.TESTING_STRATEGY
            elif area_str == "ARCHITECTURE":
                d["area"] = ImprovementArea.ARCHITECTURE_MODELING
            elif area_str == "PERFORMANCE":
                d["area"] = ImprovementArea.PERFORMANCE_EFFICIENCY
            elif area_str == "RELIABILITY":
                d["area"] = ImprovementArea.RETRY_ENGINE
            else:
                try:
                    d["area"] = ImprovementArea(area_str)
                except Exception:
                    d["area"] = ImprovementArea.RETRY_ENGINE
        if "id" in d and "item_id" not in d:
            d["item_id"] = d["id"]
        if "item_id" in d and "id" not in d:
            d["id"] = d["item_id"]
        return cls(**d)


@dataclass
class SelfImprovementPlan:
    """Quarterly or monthly self-evaluation plan and upgrade roadmap."""
    plan_id: str = field(default_factory=lambda: f"PLAN-{int(time.time() * 1000)}")
    id: str = ""
    evaluation_period: str = "2026-10"
    weakest_subsystems: List[str] = field(default_factory=list)
    weakest_subsystem: str = "RETRY_ENGINE"
    subsystem_health_scores: Dict[str, float] = field(default_factory=dict)
    roadmap_items: List[ImprovementRoadmapItem] = field(default_factory=list)
    roadmap: List[ImprovementRoadmapItem] = field(default_factory=list)
    overall_health_score: float = 85.0
    executive_summary: str = ""
    improvement_summary: str = ""
    scheduled_upgrades: List[Dict[str, Any]] = field(default_factory=list)
    evaluated_at: float = field(default_factory=time.time)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.id:
            self.plan_id = self.id
        elif self.plan_id:
            self.id = self.plan_id
        if not self.timestamp and self.evaluated_at:
            self.timestamp = self.evaluated_at
        elif not self.evaluated_at and self.timestamp:
            self.evaluated_at = self.timestamp
        if not self.weakest_subsystem and self.weakest_subsystems:
            self.weakest_subsystem = self.weakest_subsystems[0]
        elif not self.weakest_subsystems and self.weakest_subsystem:
            self.weakest_subsystems = [self.weakest_subsystem]
        if not self.roadmap and self.roadmap_items:
            self.roadmap = list(self.roadmap_items)
        elif not self.roadmap_items and self.roadmap:
            self.roadmap_items = list(self.roadmap)
        if not self.improvement_summary and self.executive_summary:
            self.improvement_summary = self.executive_summary
        elif not self.executive_summary and self.improvement_summary:
            self.executive_summary = self.improvement_summary

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id or self.plan_id
        d["plan_id"] = self.plan_id or self.id
        d["roadmap_items"] = [item.to_dict() if isinstance(item, ImprovementRoadmapItem) else item for item in self.roadmap_items]
        d["roadmap"] = [item.to_dict() if isinstance(item, ImprovementRoadmapItem) else item for item in (self.roadmap or self.roadmap_items)]
        d["weakest_subsystem"] = self.weakest_subsystem
        d["weakest_subsystems"] = self.weakest_subsystems or [self.weakest_subsystem]
        d["executive_summary"] = self.executive_summary or self.improvement_summary
        d["improvement_summary"] = self.improvement_summary or self.executive_summary
        d["timestamp"] = self.timestamp
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SelfImprovementPlan:
        d = dict(data)
        items = d.get("roadmap_items") or d.get("roadmap") or []
        d["roadmap_items"] = [
            ImprovementRoadmapItem.from_dict(item) if isinstance(item, dict) else item
            for item in items
        ]
        d["roadmap"] = list(d["roadmap_items"])
        if "id" in d and "plan_id" not in d:
            d["plan_id"] = d["id"]
        if "plan_id" in d and "id" not in d:
            d["id"] = d["plan_id"]
        if "timestamp" not in d and "evaluated_at" in d:
            d["timestamp"] = d["evaluated_at"]
        return cls(**d)


@dataclass
class PerformanceEvolutionRecord:
    """Historical performance metrics tracking speed, latency, and resource efficiency across versions."""
    record_id: str = field(default_factory=lambda: f"PERF-{int(time.time() * 1000)}")
    id: str = ""
    version: str = "3.1.0"
    version_tag: str = "v3.1"
    benchmark_name: str = "DefaultBenchmark"
    stage: str = "task_execution"
    execution_time_seconds: float = 0.0
    duration_ms: float = 0.0
    memory_usage_mb: float = 0.0
    memory_kb: float = 0.0
    planning_latency_ms: float = 0.0
    review_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    speedup_vs_previous: float = 1.0
    memory_delta_vs_previous: float = 0.0
    throughput_ops_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id:
            self.record_id = self.id
        elif self.record_id:
            self.id = self.record_id
        if not self.version_tag and self.version:
            self.version_tag = self.version
        elif not self.version and self.version_tag:
            self.version = self.version_tag
        if not self.stage and self.benchmark_name:
            self.stage = self.benchmark_name
        elif not self.benchmark_name and self.stage:
            self.benchmark_name = self.stage
        if not self.duration_ms and self.execution_time_seconds:
            self.duration_ms = self.execution_time_seconds * 1000.0
        elif not self.execution_time_seconds and self.duration_ms:
            self.execution_time_seconds = self.duration_ms / 1000.0
        if not self.memory_kb and self.memory_usage_mb:
            self.memory_kb = self.memory_usage_mb * 1024.0
        elif not self.memory_usage_mb and self.memory_kb:
            self.memory_usage_mb = self.memory_kb / 1024.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id or self.record_id
        d["record_id"] = self.record_id or self.id
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PerformanceEvolutionRecord:
        d = dict(data)
        if "id" in d and "record_id" not in d:
            d["record_id"] = d["id"]
        if "record_id" in d and "id" not in d:
            d["id"] = d["record_id"]
        if "version" in d and "version_tag" not in d:
            d["version_tag"] = d["version"]
        if "version_tag" in d and "version" not in d:
            d["version"] = d["version_tag"]
        return cls(**d)
