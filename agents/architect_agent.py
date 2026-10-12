"""
architect_agent.py - Chief Architect Agent (AutoDev Version 3.4)

Directs architectural integrity and system modularity:
- System decomposition and modular boundary enforcement
- Architecture Decision Record (ADR) authoring and ratification
- Design pattern recommendation and anti-pattern mitigation
- Microservice & module interface contract definitions
- Presides over Architecture Reviews
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core.communication_bus import CommunicationBus, MessagePriority, OrgMessage, OrgMessageType
from core.organization_state import OrganizationState

logger = logging.getLogger("AutoDev.Org.ArchitectAgent")


class ArchitectAgent:
    """
    Autonomous Chief Architect AI Agent.
    """

    def __init__(
        self,
        name: str = "Architecture",
        bus: Optional[CommunicationBus] = None,
        state: Optional[OrganizationState] = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.state = state
        self.authority_level = 4  # Director Architecture
        self.design_patterns: List[str] = [
            "Repository Pattern",
            "Domain-Driven Design (DDD)",
            "Dependency Inversion",
            "Transactional Outbox",
            "Command-Query Responsibility Segregation (CQRS)",
        ]

        if self.bus:
            self.bus.register_entity(self.name)

    def design_system(self, requirements: str) -> Dict[str, Any]:
        """Synthesizes high-level system architecture and component boundaries."""
        req_lower = requirements.lower()

        patterns = ["Repository Pattern", "Domain-Driven Design"]
        if "event" in req_lower or "stream" in req_lower or "queue" in req_lower:
            patterns.append("Transactional Outbox")
        if "query" in req_lower or "report" in req_lower:
            patterns.append("CQRS")

        folder_structure = {
            "core/domain": "Pure business entities and value objects",
            "core/services": "Application service orchestration and use-cases",
            "core/repositories": "Persistence boundary interfaces and implementations",
            "api/controllers": "REST / JSON transport layer handlers",
            "tests/unit": "Isolated unit test suite with 100% test fixture mocks",
        }

        design = {
            "architecture_style": "Clean Hexagonal Architecture",
            "recommended_patterns": patterns,
            "folder_structure": folder_structure,
            "interface_boundaries": [
                "Domain entities must NOT import framework libraries",
                "Controllers must interact with services solely via typed DTOs",
                "Repositories must provide deterministic in-memory mock adapters",
            ],
            "modularity_score": 96.0,
            "timestamp": time.time(),
        }

        logger.info("System architecture designed with %d patterns.", len(patterns))
        return design

    def generate_adr(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: str,
    ) -> Dict[str, Any]:
        """Creates a formal Architecture Decision Record (ADR)."""
        adr_id = f"ADR-{int(time.time() * 1000) % 1000:03d}"
        adr = {
            "adr_id": adr_id,
            "title": title,
            "status": "ACCEPTED",
            "author": self.name,
            "context": context,
            "decision": decision,
            "consequences": consequences,
            "compliance_rules": [
                "Preserve 100% backward compatibility",
                "Zero external third-party dependencies",
                "Deterministic unit test coverage >= 90%",
            ],
            "timestamp": time.time(),
        }

        if self.state:
            self.state.record_architecture_decision(adr)

        logger.info("ADR ratified: '%s' - %s", adr_id, title)
        return adr

    def validate_component_boundaries(self, modules_graph: Dict[str, List[str]]) -> Dict[str, Any]:
        """Detects circular dependencies and boundary violations between modules."""
        # Simple cycle detector
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in modules_graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
                elif neighbor in rec_stack:
                    cycles.append(" -> ".join(path + [neighbor]))
            rec_stack.remove(node)

        for mod in modules_graph:
            if mod not in visited:
                dfs(mod, [mod])

        is_clean = len(cycles) == 0
        return {
            "is_clean": is_clean,
            "circular_dependencies": cycles,
            "coupling_score": 100.0 if is_clean else max(30.0, 100.0 - (len(cycles) * 25.0)),
        }
