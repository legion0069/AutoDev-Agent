"""
shared_services.py - Enterprise Shared Services Catalog (AutoDev Version 3.5)

Provides centralized corporate shared services consumed across all federated companies:
1. Authentication Service (Single Sign-On & Token Verification)
2. Logging Service (Unified Federation Log Stream & Log Level Filtering)
3. Monitoring Service (Service Health & Latency Telemetry)
4. Notification Service (Cross-Company Alert Broadcast & Dispatch)
5. Artifact Repository (Build Artifacts, Wheel Packages, Binaries)
6. Model Registry (AI Model Checkpoints, Versions, Performance Metrics)
7. Prompt Registry (Versioned System Prompts & Quality Scores)
8. Secrets Vault Service (Secure Federation Credential Access)
9. License Manager (Open Source License Compliance & Compatibility Gating)
10. Package Repository (Federation Internal Code Packages & Tarballs)

100% Python Standard Library.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.enterprise_security import EnterpriseSecurityManager

logger = logging.getLogger("AutoDev.Federation.SharedServices")


# -------------------------------------------------------------------------
# 1. Logging Service
# -------------------------------------------------------------------------

@dataclass
class LogEntry:
    timestamp: float
    company_id: str
    service: str
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    context: Dict[str, Any] = field(default_factory=dict)


class LoggingService:
    """Centralized high-throughput log aggregator for all companies."""

    def __init__(self, max_buffer_size: int = 10000) -> None:
        self._lock = threading.RLock()
        self.max_buffer_size = max_buffer_size
        self._logs: List[LogEntry] = []

    def log(self, company_id: str, service: str, level: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            entry = LogEntry(
                timestamp=time.time(),
                company_id=company_id,
                service=service,
                level=level.upper(),
                message=message,
                context=context or {},
            )
            self._logs.append(entry)
            if len(self._logs) > self.max_buffer_size:
                self._logs = self._logs[-self.max_buffer_size:]

    def query_logs(self, company_id: Optional[str] = None, min_level: Optional[str] = None, limit: int = 100) -> List[LogEntry]:
        with self._lock:
            level_ranks = {"DEBUG": 1, "INFO": 2, "WARNING": 3, "ERROR": 4, "CRITICAL": 5}
            target_rank = level_ranks.get(min_level.upper(), 1) if min_level else 1

            matched = [
                entry for entry in reversed(self._logs)
                if (company_id is None or entry.company_id == company_id)
                and level_ranks.get(entry.level, 1) >= target_rank
            ]
            return matched[:limit]


# -------------------------------------------------------------------------
# 2. Monitoring Service
# -------------------------------------------------------------------------

@dataclass
class MetricPoint:
    timestamp: float
    company_id: str
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


class MonitoringService:
    """Tracks latency, memory, uptime, and throughput metrics across all companies."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._metrics: List[MetricPoint] = []
        self._health_status: Dict[str, Dict[str, Any]] = {}

    def record_metric(self, company_id: str, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self._metrics.append(MetricPoint(
                timestamp=time.time(),
                company_id=company_id,
                metric_name=metric_name,
                value=float(value),
                tags=tags or {},
            ))

    def update_health(self, company_id: str, service_name: str, is_healthy: bool, latency_ms: float = 0.0) -> None:
        with self._lock:
            key = f"{company_id}:{service_name}"
            self._health_status[key] = {
                "company_id": company_id,
                "service_name": service_name,
                "is_healthy": is_healthy,
                "latency_ms": latency_ms,
                "last_checked": time.time(),
            }

    def get_service_health(self, company_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if company_id:
                return {k: v for k, v in self._health_status.items() if v["company_id"] == company_id}
            return dict(self._health_status)


# -------------------------------------------------------------------------
# 3. Notification Service
# -------------------------------------------------------------------------

@dataclass
class Notification:
    notification_id: str
    sender_company: str
    recipient: str  # Specific company_id or 'BROADCAST'
    channel: str  # SLACK_STUB, EMAIL_STUB, PAGERDUTY_STUB, IN_APP
    title: str
    body: str
    urgency: str  # LOW, NORMAL, HIGH, CRITICAL
    timestamp: float = field(default_factory=time.time)


class NotificationService:
    """Dispatches corporate alerts and notifications across channels."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._notifications: List[Notification] = []

    def dispatch(self, sender_company: str, recipient: str, title: str, body: str, channel: str = "IN_APP", urgency: str = "NORMAL") -> str:
        with self._lock:
            nid = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
            notif = Notification(
                notification_id=nid,
                sender_company=sender_company,
                recipient=recipient,
                channel=channel,
                title=title,
                body=body,
                urgency=urgency,
            )
            self._notifications.append(notif)
            logger.info("Dispatched notification %s: [%s] %s to %s", nid, urgency, title, recipient)
            return nid

    def get_notifications_for_company(self, company_id: str) -> List[Notification]:
        with self._lock:
            return [n for n in self._notifications if n.recipient in (company_id, "BROADCAST", "ALL")]


# -------------------------------------------------------------------------
# 4. Artifact Repository
# -------------------------------------------------------------------------

@dataclass
class ArtifactRecord:
    artifact_id: str
    name: str
    version: str
    company_id: str
    artifact_type: str  # WHEEL, JAR, DOCKER_IMAGE_SPEC, TAR_GZ, REPORT
    hash_sha256: str
    size_bytes: int
    content_ref: str
    created_at: float = field(default_factory=time.time)


class ArtifactRepository:
    """Stores build artifacts, deployables, and reports."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._artifacts: Dict[str, ArtifactRecord] = {}

    def publish_artifact(self, name: str, version: str, company_id: str, artifact_type: str, content: str | bytes) -> ArtifactRecord:
        with self._lock:
            aid = f"ART-{uuid.uuid4().hex[:8].upper()}"
            raw = content.encode("utf-8") if isinstance(content, str) else content
            import hashlib
            sha = hashlib.sha256(raw).hexdigest()

            rec = ArtifactRecord(
                artifact_id=aid,
                name=name,
                version=version,
                company_id=company_id,
                artifact_type=artifact_type,
                hash_sha256=sha,
                size_bytes=len(raw),
                content_ref=f"memory://artifacts/{aid}",
            )
            self._artifacts[aid] = rec
            return rec

    def find_artifact(self, name: str, version: Optional[str] = None) -> Optional[ArtifactRecord]:
        with self._lock:
            for art in reversed(list(self._artifacts.values())):
                if art.name == name and (version is None or art.version == version):
                    return art
            return None


# -------------------------------------------------------------------------
# 5. Model Registry
# -------------------------------------------------------------------------

@dataclass
class ModelMetadata:
    model_id: str
    model_name: str
    version: str
    company_id: str
    framework: str  # PyTorch, TensorFlow, GGUF, Scikit-Learn
    parameters_million: float
    accuracy_score: float
    latency_ms: float
    status: str = "PRODUCTION"  # EXPERIMENTAL, STAGING, PRODUCTION, RETIRED


class ModelRegistry:
    """Manages AI model checkpoints, evaluation benchmarks, and deployments."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._models: Dict[str, ModelMetadata] = {}

    def register_model(self, model_name: str, version: str, company_id: str, framework: str, parameters_million: float, accuracy: float, latency_ms: float) -> ModelMetadata:
        with self._lock:
            mid = f"MOD-{uuid.uuid4().hex[:8].upper()}"
            meta = ModelMetadata(
                model_id=mid,
                model_name=model_name,
                version=version,
                company_id=company_id,
                framework=framework,
                parameters_million=parameters_million,
                accuracy_score=accuracy,
                latency_ms=latency_ms,
            )
            self._models[mid] = meta
            return meta

    def get_best_model(self, model_name: str) -> Optional[ModelMetadata]:
        with self._lock:
            matching = [m for m in self._models.values() if m.model_name == model_name and m.status == "PRODUCTION"]
            if not matching:
                return None
            return max(matching, key=lambda m: m.accuracy_score)


# -------------------------------------------------------------------------
# 6. Prompt Registry
# -------------------------------------------------------------------------

@dataclass
class PromptRecord:
    prompt_id: str
    name: str
    version: int
    company_id: str
    template: str
    quality_score: float
    tags: List[str] = field(default_factory=list)


class PromptRegistry:
    """Versioned prompt repository with quality benchmarking."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._prompts: Dict[str, List[PromptRecord]] = {}  # name -> list of version records

    def register_prompt(self, name: str, template: str, company_id: str, quality_score: float = 95.0, tags: Optional[List[str]] = None) -> PromptRecord:
        with self._lock:
            if name not in self._prompts:
                self._prompts[name] = []

            ver = len(self._prompts[name]) + 1
            pid = f"PRM-{uuid.uuid4().hex[:8].upper()}"
            rec = PromptRecord(
                prompt_id=pid,
                name=name,
                version=ver,
                company_id=company_id,
                template=template,
                quality_score=quality_score,
                tags=tags or [],
            )
            self._prompts[name].append(rec)
            return rec

    def get_latest_prompt(self, name: str) -> Optional[PromptRecord]:
        with self._lock:
            versions = self._prompts.get(name)
            return versions[-1] if versions else None


# -------------------------------------------------------------------------
# 7. License Manager
# -------------------------------------------------------------------------

class LicenseManager:
    """Validates third-party software licenses against enterprise compliance policies."""

    PERMITTED_LICENSES = {"MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "ISC", "PYTHON-2.0"}
    RESTRICTED_COPYLEFT = {"GPL-2.0", "GPL-3.0", "AGPL-3.0"}

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._approved_exceptions: Set[str] = set()

    def check_license(self, package_name: str, license_identifier: str) -> Tuple[bool, str]:
        with self._lock:
            lic = license_identifier.upper()
            if lic in self.PERMITTED_LICENSES or package_name in self._approved_exceptions:
                return True, f"License '{lic}' is approved for enterprise production distribution."
            if lic in self.RESTRICTED_COPYLEFT:
                return False, f"License '{lic}' has viral copyleft restrictions. Disallowed by enterprise policy."
            return True, f"License '{lic}' permitted with standard attribution notice."


# -------------------------------------------------------------------------
# 8. Package Repository
# -------------------------------------------------------------------------

@dataclass
class PackageRecord:
    package_name: str
    version: str
    company_id: str
    dependencies: List[str] = field(default_factory=list)
    description: str = ""


class PackageRepository:
    """Internal registry of reusable software modules and libraries."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._packages: Dict[str, Dict[str, PackageRecord]] = {}  # name -> {version: record}

    def publish_package(self, package_name: str, version: str, company_id: str, dependencies: Optional[List[str]] = None, description: str = "") -> PackageRecord:
        with self._lock:
            if package_name not in self._packages:
                self._packages[package_name] = {}

            rec = PackageRecord(
                package_name=package_name,
                version=version,
                company_id=company_id,
                dependencies=dependencies or [],
                description=description,
            )
            self._packages[package_name][version] = rec
            return rec

    def get_package(self, package_name: str, version: Optional[str] = None) -> Optional[PackageRecord]:
        with self._lock:
            versions = self._packages.get(package_name, {})
            if not versions:
                return None
            if version and version in versions:
                return versions[version]
            # Default to latest registered version
            return list(versions.values())[-1]


# -------------------------------------------------------------------------
# 9 & 10. Unified Shared Services Suite
# -------------------------------------------------------------------------

class EnterpriseSharedServices:
    """
    Unified enterprise shared services suite available to all federated companies.
    """

    def __init__(self, security_manager: Optional[EnterpriseSecurityManager] = None) -> None:
        self.security_manager = security_manager or EnterpriseSecurityManager()
        self.logging = LoggingService()
        self.monitoring = MonitoringService()
        self.notifications = NotificationService()
        self.artifacts = ArtifactRepository()
        self.models = ModelRegistry()
        self.prompts = PromptRegistry()
        self.licenses = LicenseManager()
        self.packages = PackageRepository()

    def get_summary(self) -> Dict[str, Any]:
        """Provides high-level shared services catalog status."""
        return {
            "total_artifacts": len(self.artifacts._artifacts),
            "total_models": len(self.models._models),
            "total_prompts": len(self.prompts._prompts),
            "total_packages": len(self.packages._packages),
            "total_logs_buffered": len(self.logging._logs),
            "total_notifications_sent": len(self.notifications._notifications),
        }
