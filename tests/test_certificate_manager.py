"""
test_certificate_manager.py - Unit tests for CertificateManager & mTLS Infrastructure (v2.3)
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import ssl
import tempfile
import pytest

from core.certificate_manager import (
    CertificateAuthority,
    CertificateExpiredError,
    CertificateInfo,
    CertificateManager,
    CertificateRevocationError,
    CertificateValidationError,
)


@pytest.fixture
def cert_dir(tmp_path):
    d = tmp_path / "certs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_ca_generation(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    ca = manager.generate_ca(common_name="AutoDev-Test-CA", validity_days=10)
    assert Path(ca.cert_path).exists()
    assert Path(ca.key_path).exists()
    assert ca.common_name == "AutoDev-Test-CA"

    # Verify reload of existing CA
    ca2 = manager.get_or_create_ca()
    assert ca2.cert_path == ca.cert_path


def test_server_certificate_generation(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    server_info = manager.generate_server_certificate(
        common_name="localhost",
        dns_names=["localhost", "coordinator.internal"],
        ip_addresses=["127.0.0.1"],
    )
    assert Path(server_info.cert_path).exists()
    assert Path(server_info.key_path).exists()
    assert server_info.common_name == "localhost"
    assert len(server_info.fingerprint_sha256) == 64

    # Verify certificate content
    validated = manager.verify_certificate(server_info.cert_path)
    assert validated.common_name == "localhost"


def test_client_certificate_generation(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    client_info = manager.generate_client_certificate(
        worker_id="worker-node-01",
        organization="AutoDev Distributed Fleet",
    )
    assert Path(client_info.cert_path).exists()
    assert Path(client_info.key_path).exists()
    assert client_info.common_name == "worker-node-01"


def test_certificate_revocation(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    client_info = manager.generate_client_certificate(worker_id="revoked-worker")
    assert not manager.is_revoked(client_info.fingerprint_sha256)

    # Revoke certificate
    manager.revoke_certificate(client_info.fingerprint_sha256, reason="Compromised key")
    assert manager.is_revoked(client_info.fingerprint_sha256)

    with pytest.raises(CertificateRevocationError):
        manager.verify_certificate(client_info.cert_path)


def test_ssl_context_creation(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    server_info = manager.generate_server_certificate(common_name="localhost")
    client_info = manager.generate_client_certificate(worker_id="worker-ssl")

    # Server SSL context
    server_ctx = manager.create_server_ssl_context(server_info)
    assert isinstance(server_ctx, ssl.SSLContext)
    assert server_ctx.verify_mode == ssl.CERT_REQUIRED

    # Client SSL context
    client_ctx = manager.create_client_ssl_context(client_info)
    assert isinstance(client_ctx, ssl.SSLContext)
    assert client_ctx.verify_mode == ssl.CERT_REQUIRED


def test_certificate_fingerprint_computation(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    info = manager.generate_server_certificate(common_name="127.0.0.1")
    fp1 = CertificateManager.get_certificate_fingerprint(info.cert_path)
    fp2 = CertificateManager.get_certificate_fingerprint(Path(info.cert_path).read_bytes())
    assert fp1 == fp2
    assert len(fp1) == 64


def test_certificate_authority_tuple_unpacking(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    ca = manager.generate_ca(common_name="Test-Unpack-CA")
    cert_p, key_p = ca
    assert cert_p.exists()
    assert key_p.exists()


def test_verify_certificate_with_expected_cn(cert_dir):
    manager = CertificateManager(cert_dir=cert_dir)
    info = manager.generate_client_certificate(worker_id="worker-expected-cn")
    
    # Valid CN match
    validated = manager.verify_certificate(info.cert_path, expected_common_name="worker-expected-cn")
    assert validated.common_name == "worker-expected-cn"

    # Mismatch CN raises CertificateValidationError
    with pytest.raises(CertificateValidationError, match="does not match expected"):
        manager.verify_certificate(info.cert_path, expected_common_name="different-worker")


def test_untrusted_certificate_verification(tmp_path):
    dir1 = tmp_path / "ca1"
    dir2 = tmp_path / "ca2"
    m1 = CertificateManager(cert_dir=dir1)
    m2 = CertificateManager(cert_dir=dir2)

    m1.generate_ca(common_name="CA1")
    cert_from_m2 = m2.generate_client_certificate(worker_id="foreign-worker")

    # m1 CA should reject certificate issued by m2 CA
    with pytest.raises(CertificateValidationError):
        m1.verify_certificate(cert_from_m2.cert_path)


def test_revocation_list_persistence(cert_dir):
    manager1 = CertificateManager(cert_dir=cert_dir)
    cert_info = manager1.generate_client_certificate(worker_id="worker-persist-rev")
    manager1.revoke_certificate(cert_info.fingerprint_sha256, reason="Revoked on day 1")

    # Create a fresh manager instance pointing to the same directory
    manager2 = CertificateManager(cert_dir=cert_dir)
    assert manager2.is_revoked(cert_info.fingerprint_sha256)
    with pytest.raises(CertificateRevocationError):
        manager2.verify_certificate(cert_info.cert_path)


def test_expired_certificate_handling(cert_dir, monkeypatch):
    manager = CertificateManager(cert_dir=cert_dir)
    # Generate cert with valid_days=1
    cert_info = manager.generate_client_certificate(worker_id="worker-expiry-test", validity_days=1)
    
    # Simulate time jumping ahead 2 days
    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    
    with pytest.raises(CertificateExpiredError):
        manager.verify_certificate(cert_info.cert_path, current_time=future_time)

