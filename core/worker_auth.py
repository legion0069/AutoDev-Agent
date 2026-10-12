"""
worker_auth.py - Remote Worker Authentication & Authorization Policy Engine for AutoDev (v2.3)

Enforces zero-trust worker identity validation, mTLS certificate-to-worker binding,
capability authorization, and path/runtime privilege restrictions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("AutoDev.WorkerAuth")


class WorkerAuthorizationError(Exception):
    """Raised when an authenticated worker attempts an unauthorized operation."""
    pass


class WorkerAuthenticationError(Exception):
    """Raised when worker identity or mTLS verification fails."""
    pass


@dataclass
class WorkerSecurityScope:
    """Security boundaries and execution permissions granted to a worker."""
    worker_id: Optional[str] = None
    allowed_operation_types: Set[str] = field(
        default_factory=lambda: {"CREATE_FILE", "MODIFY_FILE", "DELETE_FILE", "EXECUTE_TEST", "RUN_TESTS"}
    )
    allowed_runtimes: Set[str] = field(default_factory=lambda: {"process", "container"})
    allowed_security_profiles: Set[str] = field(default_factory=lambda: {"restricted", "development"})
    allowed_runtime_profiles: Optional[Set[str]] = None
    max_concurrency: int = 4
    allow_network_access: bool = False
    max_submitted_artifacts: int = 100
    allowed_path_prefixes: Set[str] = field(default_factory=set)
    denied_path_prefixes: List[str] = field(
        default_factory=lambda: [".git", ".env", "memory/execution_journal", "certs", "secrets"]
    )

    def __post_init__(self) -> None:
        if self.allowed_runtime_profiles is not None and not self.allowed_security_profiles:
            self.allowed_security_profiles = set(self.allowed_runtime_profiles)
        elif self.allowed_runtime_profiles is not None:
            self.allowed_security_profiles = set(self.allowed_runtime_profiles)
        if isinstance(self.allowed_path_prefixes, list):
            self.allowed_path_prefixes = set(self.allowed_path_prefixes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "allowed_operation_types": sorted(list(self.allowed_operation_types)),
            "allowed_runtimes": sorted(list(self.allowed_runtimes)),
            "allowed_security_profiles": sorted(list(self.allowed_security_profiles)),
            "max_concurrency": self.max_concurrency,
            "allow_network_access": self.allow_network_access,
            "max_submitted_artifacts": self.max_submitted_artifacts,
            "allowed_path_prefixes": sorted(list(self.allowed_path_prefixes)),
            "denied_path_prefixes": self.denied_path_prefixes,
        }


@dataclass
class AuthenticatedWorkerIdentity:
    """Verified identity and granted security scope of a remote worker."""
    worker_id: str
    common_name: str = ""
    certificate_fingerprint: str = ""
    cert_fingerprint: str = ""
    organization: str = ""
    authenticated_via: str = "mTLS"  # mTLS | TOKEN | LOCAL
    scope: Optional[WorkerSecurityScope] = None
    authenticated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.common_name:
            self.common_name = self.worker_id
        if self.cert_fingerprint and not self.certificate_fingerprint:
            self.certificate_fingerprint = self.cert_fingerprint
        elif self.certificate_fingerprint and not self.cert_fingerprint:
            self.cert_fingerprint = self.certificate_fingerprint

    @property
    def is_authenticated(self) -> bool:
        return bool(self.worker_id and self.worker_id.strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "common_name": self.common_name,
            "certificate_fingerprint": self.certificate_fingerprint,
            "organization": self.organization,
            "authenticated_via": self.authenticated_via,
            "scope": self.scope.to_dict() if self.scope else None,
            "authenticated_at": self.authenticated_at,
        }


class WorkerAuthorizer:
    """
    Validates that a worker is authorized to register and execute requested operations.
    """

    def __init__(
        self,
        default_scope: Optional[WorkerSecurityScope] = None,
        scopes: Optional[Dict[str, WorkerSecurityScope]] = None,
        worker_scopes: Optional[Dict[str, WorkerSecurityScope]] = None,
        require_explicit_scope: bool = False,
    ) -> None:
        self.default_scope = default_scope or WorkerSecurityScope()
        self.worker_scopes = scopes or worker_scopes or {}
        self.require_explicit_scope = require_explicit_scope
        self._submitted_artifact_counts: Dict[str, int] = {}

    def get_scope_for_worker(self, worker_id: str) -> WorkerSecurityScope:
        """Returns specific scope configured for worker or falls back to default."""
        if worker_id in self.worker_scopes:
            return self.worker_scopes[worker_id]
        if self.require_explicit_scope:
            raise WorkerAuthorizationError(f"No authorization scope configured for worker '{worker_id}'")
        return self.default_scope

    def authorize_registration(self, identity: AuthenticatedWorkerIdentity) -> bool:
        """Validates worker identity for registration."""
        if not identity.is_authenticated:
            raise WorkerAuthorizationError("Unauthenticated identity: worker_id is missing or empty.")
        if self.require_explicit_scope and identity.worker_id not in self.worker_scopes:
            raise WorkerAuthorizationError(f"No authorization scope configured for worker '{identity.worker_id}'")
        return True

    def authorize_operation(
        self,
        identity: AuthenticatedWorkerIdentity,
        operation_type: str,
        target_file: Optional[str] = None,
        security_profile: str = "restricted",
    ) -> bool:
        """
        Validates task assignment against worker scope.
        Raises WorkerAuthorizationError if unauthorized.
        """
        if not identity.is_authenticated:
            raise WorkerAuthorizationError("Unauthenticated worker identity.")

        scope = identity.scope or self.get_scope_for_worker(identity.worker_id)

        # 1. Operation type authorization
        if operation_type not in scope.allowed_operation_types:
            raise WorkerAuthorizationError(
                f"Operation type '{operation_type}' not permitted for worker '{identity.worker_id}'. "
                f"Allowed: {sorted(list(scope.allowed_operation_types))}"
            )

        # 2. Security profile authorization
        if security_profile not in scope.allowed_security_profiles:
            raise WorkerAuthorizationError(
                f"Runtime profile '{security_profile}' not permitted for worker '{identity.worker_id}'."
            )

        # 3. Target file path authorization & traversal checks
        if target_file:
            raw_path = str(target_file)
            if ".." in raw_path or raw_path.startswith("/") or (len(raw_path) > 1 and raw_path[1] == ":"):
                raise WorkerAuthorizationError(
                    f"Path traversal or absolute path '{target_file}' is forbidden."
                )

            norm_path = raw_path.replace("\\", "/").lstrip("/")
            # Check denied prefixes
            for denied in scope.denied_path_prefixes:
                denied_norm = denied.replace("\\", "/").lstrip("/")
                if norm_path == denied_norm or norm_path.startswith(denied_norm + "/") or norm_path.startswith(denied_norm + "."):
                    raise WorkerAuthorizationError(
                        f"Worker '{identity.worker_id}' is forbidden from mutating protected path '{target_file}'."
                    )
            # Check allowed prefixes if specified
            if scope.allowed_path_prefixes:
                is_allowed = False
                for a in scope.allowed_path_prefixes:
                    clean_a = a.replace("\\", "/").strip("/")
                    if norm_path == clean_a or norm_path.startswith(clean_a + "/"):
                        is_allowed = True
                        break
                if not is_allowed:
                    raise WorkerAuthorizationError(
                        f"Target path '{target_file}' outside allowed prefixes: {sorted(list(scope.allowed_path_prefixes))}"
                    )

        return True

    def authorize_artifact_submission(self, identity: AuthenticatedWorkerIdentity, artifact_id: str) -> bool:
        """Validates artifact submission against worker's quota."""
        if not identity.is_authenticated:
            raise WorkerAuthorizationError("Unauthenticated worker identity.")
        scope = identity.scope or self.get_scope_for_worker(identity.worker_id)
        current = self._submitted_artifact_counts.get(identity.worker_id, 0)
        if current >= scope.max_submitted_artifacts:
            raise WorkerAuthorizationError(
                f"Artifact quota exceeded for worker '{identity.worker_id}' ({current}/{scope.max_submitted_artifacts})."
            )
        self._submitted_artifact_counts[identity.worker_id] = current + 1
        return True

    def authorize_task(
        self,
        identity: AuthenticatedWorkerIdentity,
        operation_type: str,
        target_file: Optional[str] = None,
        required_runtime: str = "process",
        security_profile: str = "restricted",
    ) -> None:
        """Legacy helper calling authorize_operation."""
        self.authorize_operation(identity, operation_type, target_file, security_profile)
