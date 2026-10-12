"""
test_shared_services.py - Unit Tests for EnterpriseSharedServices Suite (AutoDev Version 3.5)
"""

import pytest

from core.shared_services import (
    ArtifactRecord,
    ArtifactRepository,
    EnterpriseSharedServices,
    LicenseManager,
    LoggingService,
    ModelRegistry,
    MonitoringService,
    NotificationService,
    PackageRepository,
    PromptRegistry,
)


def test_logging_service():
    logs = LoggingService(max_buffer_size=10)
    for i in range(15):
        logs.log("COMP-A", "Service1", "INFO", f"Message {i}")

    # Should cap at 10
    results = logs.query_logs()
    assert len(results) == 10

    # Query with min_level
    logs.log("COMP-A", "Service1", "ERROR", "Something broke")
    err_logs = logs.query_logs(min_level="ERROR")
    assert len(err_logs) == 1
    assert err_logs[0].message == "Something broke"


def test_monitoring_service():
    mon = MonitoringService()
    mon.record_metric("COMP-A", "cpu_percent", 42.5)
    mon.record_metric("COMP-A", "memory_mb", 1024.0)

    mon.update_health("COMP-A", "AuthService", is_healthy=True, latency_ms=12.4)
    health = mon.get_service_health("COMP-A")
    assert "COMP-A:AuthService" in health
    assert health["COMP-A:AuthService"]["is_healthy"] is True


def test_notification_service():
    notifs = NotificationService()
    nid = notifs.dispatch(
        sender_company="COMP-OPS",
        recipient="COMP-A",
        title="Scheduled Maintenance",
        body="Sunday 02:00 UTC",
        urgency="HIGH",
    )
    assert nid.startswith("NOTIF-")

    inbox_a = notifs.get_notifications_for_company("COMP-A")
    assert len(inbox_a) == 1
    assert inbox_a[0].title == "Scheduled Maintenance"


def test_artifact_repository():
    repo = ArtifactRepository()
    art = repo.publish_artifact(
        name="autodev-core",
        version="3.5.0",
        company_id="COMP-A",
        artifact_type="WHEEL",
        content="FAKE_BINARY_CONTENT_2026",
    )
    assert art.artifact_id.startswith("ART-")
    assert len(art.hash_sha256) == 64

    found = repo.find_artifact("autodev-core", "3.5.0")
    assert found is not None
    assert found.artifact_id == art.artifact_id


def test_model_registry():
    mr = ModelRegistry()
    m1 = mr.register_model("CodeLlama-FineTune", "1.0", "COMP-C", "PyTorch", 7000.0, accuracy=92.5, latency_ms=45.0)
    m2 = mr.register_model("CodeLlama-FineTune", "2.0", "COMP-C", "PyTorch", 7000.0, accuracy=96.8, latency_ms=38.0)

    best = mr.get_best_model("CodeLlama-FineTune")
    assert best is not None
    assert best.version == "2.0"
    assert best.accuracy_score == 96.8


def test_prompt_registry():
    pr = PromptRegistry()
    p1 = pr.register_prompt("RefactoringPrompt", "Analyze {code}", "COMP-A", quality_score=90.0)
    p2 = pr.register_prompt("RefactoringPrompt", "Carefully analyze {code} preserving invariants", "COMP-A", quality_score=98.5)

    assert p1.version == 1
    assert p2.version == 2

    latest = pr.get_latest_prompt("RefactoringPrompt")
    assert latest.version == 2
    assert latest.quality_score == 98.5


def test_license_manager():
    lm = LicenseManager()
    ok_mit, _ = lm.check_license("requests", "MIT")
    assert ok_mit is True

    ok_apache, _ = lm.check_license("tensorflow", "Apache-2.0")
    assert ok_apache is True

    # Copyleft GPL should be blocked
    ok_gpl, reason = lm.check_license("viral-lib", "GPL-3.0")
    assert ok_gpl is False
    assert "viral copyleft" in reason


def test_package_repository():
    pkg_repo = PackageRepository()
    rec = pkg_repo.publish_package(
        package_name="enterprise-utils",
        version="1.2.0",
        company_id="COMP-A",
        dependencies=["json", "hashlib"],
        description="Core utility helpers",
    )
    assert rec.package_name == "enterprise-utils"

    retrieved = pkg_repo.get_package("enterprise-utils", "1.2.0")
    assert retrieved is not None
    assert retrieved.dependencies == ["json", "hashlib"]


def test_enterprise_shared_services_facade():
    services = EnterpriseSharedServices()
    summary = services.get_summary()
    assert "total_artifacts" in summary
    assert "total_models" in summary
    assert "total_prompts" in summary
    assert "total_packages" in summary
