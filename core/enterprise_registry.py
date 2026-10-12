"""
enterprise_registry.py - Enterprise Federation Directory & Registry (AutoDev Version 3.5)

Maintains the master enterprise registry:
- Organizations & Companies (metadata, domain, executives, capacity, budgets, health, status)
- Business Units / Divisions (multi-company hierarchical groupings)
- Capability Catalogs (cross-company discoverable skills, offerings, and SLAs)
- Dynamic health tracking, status lifecycle, and capability-based lookup
- 100% Python Standard Library.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("AutoDev.Federation.Registry")


class OrganizationStatus(str, enum.Enum):
    """Operational status of a federated organization or company."""
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"
    SUSPENDED = "SUSPENDED"


@dataclass
class CapabilityOffering:
    """A distinct capability or service offered by a company."""
    capability_name: str
    category: str  # e.g., "ENGINEERING", "AI_RESEARCH", "SECURITY", "CLOUD", "QA"
    description: str
    capacity_units: float = 100.0
    utilized_units: float = 0.0
    sla_hours: float = 24.0
    cost_per_unit_usd: float = 150.0

    @property
    def available_units(self) -> float:
        return max(0.0, self.capacity_units - self.utilized_units)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompanyProfile:
    """Complete profile of an autonomous company within the enterprise federation."""
    company_id: str
    company_name: str
    domain: str  # e.g., "Backend Platform", "Frontend Products", "AI Research", "Security"
    business_unit: str = "Core Technologies"
    ceo_name: str = "CEO Agent"
    cto_name: str = "CTO Agent"
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    headcount: int = 100
    allocated_budget_usd: float = 1000000.0
    spent_budget_usd: float = 0.0
    health_score: float = 100.0
    performance_score: float = 100.0
    capabilities: Dict[str, CapabilityOffering] = field(default_factory=dict)
    departments: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if hasattr(self.status, "value") else self.status
        d["tags"] = list(self.tags)
        return d


class EnterpriseRegistry:
    """
    Central registry for the entire multi-company enterprise ecosystem.
    Thread-safe discovery, health monitoring, and capability indexing.
    """

    def __init__(self, enterprise_name: str = "AutoDev Global Enterprise") -> None:
        self._lock = threading.RLock()
        self.enterprise_name = enterprise_name
        self._companies: Dict[str, CompanyProfile] = {}
        self._business_units: Dict[str, Set[str]] = {}  # BU name -> set of company_ids
        self._capability_index: Dict[str, Set[str]] = {}  # capability_name -> set of company_ids

    def register_company(
        self,
        company_id: str,
        company_name: str,
        domain: str,
        business_unit: str = "Core Technologies",
        ceo_name: str = "CEO Agent",
        cto_name: str = "CTO Agent",
        headcount: int = 100,
        budget_usd: float = 1000000.0,
        departments: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CompanyProfile:
        """Registers a new company in the enterprise federation."""
        with self._lock:
            prof = CompanyProfile(
                company_id=company_id,
                company_name=company_name,
                domain=domain,
                business_unit=business_unit,
                ceo_name=ceo_name,
                cto_name=cto_name,
                headcount=headcount,
                allocated_budget_usd=budget_usd,
                departments=departments or [
                    "CEO", "CTO", "EngineeringManager", "Architecture",
                    "Backend", "Frontend", "QA", "Security", "DevOps",
                ],
                tags=set(tags or [domain.lower().replace(" ", "_")]),
                metadata=metadata or {},
            )
            self._companies[company_id] = prof

            # Index business unit
            if business_unit not in self._business_units:
                self._business_units[business_unit] = set()
            self._business_units[business_unit].add(company_id)

            logger.info("Registered company '%s' (%s) in unit '%s'", company_name, company_id, business_unit)
            return prof

    def add_capability(
        self,
        company_id: str,
        capability_name: str,
        category: str,
        description: str,
        capacity_units: float = 100.0,
        sla_hours: float = 24.0,
        cost_per_unit_usd: float = 150.0,
    ) -> bool:
        """Adds or updates a capability offering for a company."""
        with self._lock:
            prof = self._companies.get(company_id)
            if not prof:
                logger.warning("Company '%s' not found for capability addition.", company_id)
                return False

            cap = CapabilityOffering(
                capability_name=capability_name,
                category=category,
                description=description,
                capacity_units=capacity_units,
                sla_hours=sla_hours,
                cost_per_unit_usd=cost_per_unit_usd,
            )
            prof.capabilities[capability_name] = cap

            # Index capability
            if capability_name not in self._capability_index:
                self._capability_index[capability_name] = set()
            self._capability_index[capability_name].add(company_id)

            return True

    def find_companies_by_capability(self, capability_name: str) -> List[CompanyProfile]:
        """Discovers companies offering a specific capability."""
        with self._lock:
            company_ids = self._capability_index.get(capability_name, set())
            return [
                self._companies[cid]
                for cid in company_ids
                if cid in self._companies and self._companies[cid].status == OrganizationStatus.ACTIVE
            ]

    def find_companies_by_domain(self, domain_substring: str) -> List[CompanyProfile]:
        """Finds companies matching a domain string."""
        with self._lock:
            sub = domain_substring.lower()
            return [
                prof for prof in self._companies.values()
                if sub in prof.domain.lower() and prof.status == OrganizationStatus.ACTIVE
            ]

    def find_companies_by_business_unit(self, business_unit: str) -> List[CompanyProfile]:
        """Finds all companies belonging to a business unit."""
        with self._lock:
            company_ids = self._business_units.get(business_unit, set())
            return [self._companies[cid] for cid in company_ids if cid in self._companies]

    def get_company(self, company_id: str) -> Optional[CompanyProfile]:
        """Retrieves profile of a company by ID."""
        with self._lock:
            return self._companies.get(company_id)

    def list_companies(self, status: Optional[OrganizationStatus] = None) -> List[CompanyProfile]:
        """Lists all registered companies, optionally filtered by status."""
        with self._lock:
            if status is None:
                return list(self._companies.values())
            return [p for p in self._companies.values() if p.status == status]

    def update_company_status(
        self,
        company_id: str,
        status: OrganizationStatus | str,
        health_score: Optional[float] = None,
    ) -> bool:
        """Updates health or operational status of a company."""
        with self._lock:
            prof = self._companies.get(company_id)
            if not prof:
                return False

            if isinstance(status, str):
                status = OrganizationStatus(status)
            prof.status = status
            prof.last_heartbeat = time.time()
            if health_score is not None:
                prof.health_score = max(0.0, min(100.0, float(health_score)))
            return True

    def record_heartbeat(self, company_id: str) -> bool:
        """Records a heartbeat timestamp from an active company."""
        with self._lock:
            prof = self._companies.get(company_id)
            if prof:
                prof.last_heartbeat = time.time()
                return True
            return False

    def get_registry_summary(self) -> Dict[str, Any]:
        """Generates comprehensive enterprise registry overview."""
        with self._lock:
            total_companies = len(self._companies)
            active_companies = sum(1 for c in self._companies.values() if c.status == OrganizationStatus.ACTIVE)
            total_budget = sum(c.allocated_budget_usd for c in self._companies.values())
            total_spent = sum(c.spent_budget_usd for c in self._companies.values())
            total_headcount = sum(c.headcount for c in self._companies.values())
            avg_health = (
                sum(c.health_score for c in self._companies.values()) / max(1, total_companies)
                if total_companies > 0 else 100.0
            )

            return {
                "enterprise_name": self.enterprise_name,
                "total_companies": total_companies,
                "active_companies": active_companies,
                "business_units_count": len(self._business_units),
                "total_capabilities_indexed": len(self._capability_index),
                "total_headcount": total_headcount,
                "total_budget_usd": total_budget,
                "total_spent_usd": total_spent,
                "average_company_health": round(avg_health, 2),
                "business_units": {bu: list(cids) for bu, cids in self._business_units.items()},
            }
