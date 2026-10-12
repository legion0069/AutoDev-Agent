"""
test_worker_auth.py - Unit tests for Worker Authentication & Authorization (v2.3)
"""

import pytest
from core.worker_auth import (
    AuthenticatedWorkerIdentity,
    WorkerAuthorizationError,
    WorkerAuthorizer,
    WorkerSecurityScope,
)


def test_worker_identity_creation():
    identity = AuthenticatedWorkerIdentity(
        worker_id="remote-node-99",
        cert_fingerprint="a" * 64,
        organization="AutoDev",
    )
    assert identity.worker_id == "remote-node-99"
    assert identity.is_authenticated


def test_worker_authorizer_default_scope():
    authorizer = WorkerAuthorizer()
    identity = AuthenticatedWorkerIdentity(worker_id="worker-default")

    # Registration
    assert authorizer.authorize_registration(identity)

    # Allowed operations
    assert authorizer.authorize_operation(identity, "CREATE_FILE", "projects/p1/file.py", "restricted")
    assert authorizer.authorize_operation(identity, "RUN_TESTS", "tests/test_foo.py", "restricted")


def test_worker_authorizer_custom_scope_restrictions():
    scope = WorkerSecurityScope(
        worker_id="worker-restricted",
        allowed_operation_types={"CREATE_FILE", "MODIFY_FILE"},
        allowed_path_prefixes={"src/", "tests/"},
        allowed_runtime_profiles={"restricted"},
    )
    authorizer = WorkerAuthorizer(scopes={"worker-restricted": scope})
    identity = AuthenticatedWorkerIdentity(worker_id="worker-restricted")

    # Allowed operation and path
    assert authorizer.authorize_operation(identity, "CREATE_FILE", "src/module.py", "restricted")

    # Forbidden operation (DELETE_FILE)
    with pytest.raises(WorkerAuthorizationError, match="Operation type 'DELETE_FILE' not permitted"):
        authorizer.authorize_operation(identity, "DELETE_FILE", "src/module.py", "restricted")

    # Forbidden path (outside src/ and tests/)
    with pytest.raises(WorkerAuthorizationError, match="Target path 'config/settings.py' outside allowed prefixes"):
        authorizer.authorize_operation(identity, "CREATE_FILE", "config/settings.py", "restricted")

    # Forbidden runtime profile
    with pytest.raises(WorkerAuthorizationError, match="Runtime profile 'privileged' not permitted"):
        authorizer.authorize_operation(identity, "CREATE_FILE", "src/module.py", "privileged")


def test_unregistered_worker_scope_denial():
    authorizer = WorkerAuthorizer(require_explicit_scope=True)
    identity = AuthenticatedWorkerIdentity(worker_id="unknown-worker")

    with pytest.raises(WorkerAuthorizationError, match="No authorization scope configured"):
        authorizer.authorize_registration(identity)


def test_unauthenticated_identity_rejection():
    authorizer = WorkerAuthorizer()
    identity = AuthenticatedWorkerIdentity(worker_id="")
    assert not identity.is_authenticated

    with pytest.raises(WorkerAuthorizationError, match="Unauthenticated identity"):
        authorizer.authorize_registration(identity)


def test_worker_authorizer_protected_path_denial():
    authorizer = WorkerAuthorizer()
    identity = AuthenticatedWorkerIdentity(worker_id="worker-default")

    protected_targets = [
        ".git/config",
        ".env",
        ".env.production",
        "certs/ca.key",
        "secrets/id_rsa",
    ]
    for target in protected_targets:
        with pytest.raises(WorkerAuthorizationError, match="protected"):
            authorizer.authorize_operation(identity, "MODIFY_FILE", target, "restricted")


def test_worker_authorizer_path_traversal_rejection():
    authorizer = WorkerAuthorizer()
    identity = AuthenticatedWorkerIdentity(worker_id="worker-default")

    traversal_targets = [
        "../outside.py",
        "src/../../etc/passwd",
        "/etc/shadow",
        "C:\\Windows\\System32\\cmd.exe",
    ]
    for target in traversal_targets:
        with pytest.raises(WorkerAuthorizationError):
            authorizer.authorize_operation(identity, "CREATE_FILE", target, "restricted")


def test_worker_authorizer_artifact_count_quota():
    scope = WorkerSecurityScope(worker_id="worker-quota", max_submitted_artifacts=2)
    authorizer = WorkerAuthorizer(scopes={"worker-quota": scope})
    identity = AuthenticatedWorkerIdentity(worker_id="worker-quota")

    assert authorizer.authorize_artifact_submission(identity, "artifact-1")
    assert authorizer.authorize_artifact_submission(identity, "artifact-2")
    with pytest.raises(WorkerAuthorizationError, match="Artifact quota exceeded"):
        authorizer.authorize_artifact_submission(identity, "artifact-3")

