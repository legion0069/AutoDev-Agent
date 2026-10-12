"""
certificate_manager.py - Mutual TLS (mTLS) Certificate Manager for AutoDev (v2.3)

Provides programmatic generation, validation, and SSLContext configuration for
coordinator and worker mutual authentication. Supports self-signed CAs for
development/testing, certificate expiration verification, and revocation tracking.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime as dt
from datetime import datetime, timezone
import hashlib
import ipaddress
import logging
import os
from pathlib import Path
import ssl
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    _HAS_CRYPTOGRAPHY = False

logger = logging.getLogger("AutoDev.CertificateManager")


class CertificateError(Exception):
    """Base exception for certificate operations."""
    pass


class CertificateValidationError(CertificateError):
    """Raised when certificate validation fails."""
    pass


class CertificateExpiredError(CertificateValidationError):
    """Raised when a certificate is expired."""
    pass


class CertificateUntrustedError(CertificateValidationError):
    """Raised when a certificate is not signed by trusted CA."""
    pass


class CertificateRevocationError(CertificateValidationError):
    """Raised when a certificate has been revoked."""
    pass


class CertificateRevokedError(CertificateRevocationError):
    """Alias for CertificateRevocationError."""
    pass


@dataclass
class CertificateAuthority:
    """Represents a Root or Intermediate Certificate Authority."""
    cert_path: str
    key_path: str
    common_name: str = "AutoDev Root CA"

    def __iter__(self):
        return iter((Path(self.cert_path), Path(self.key_path)))


@dataclass
class CertificateInfo:
    """Metadata describing a generated or inspected X.509 certificate."""
    cert_path: str
    key_path: Optional[str] = None
    common_name: str = "localhost"
    fingerprint_sha256: str = ""
    is_ca: bool = False
    not_valid_before: str = ""
    not_valid_after: str = ""
    is_expired: bool = False

    def __iter__(self):
        return iter((Path(self.cert_path), Path(self.key_path) if self.key_path else None))


class CertificateManager:
    """
    Manages generation, storage, and validation of mTLS certificates.
    """

    def __init__(self, cert_dir: Optional[Union[str, Path]] = None) -> None:
        self.cert_dir = Path(cert_dir).resolve() if cert_dir else Path("./certs").resolve()
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        self._crl_file = self.cert_dir / "crl.json"
        self._revoked_fingerprints: Set[str] = set()
        self._load_crl()

    def _load_crl(self) -> None:
        if self._crl_file.exists():
            try:
                import json
                data = json.loads(self._crl_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._revoked_fingerprints.update(fp.lower() for fp in data)
            except Exception as e:
                logger.warning("Failed to load CRL from %s: %s", self._crl_file, e)

    def _save_crl(self) -> None:
        try:
            import json
            self._crl_file.write_text(json.dumps(list(self._revoked_fingerprints), indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save CRL to %s: %s", self._crl_file, e)

    def revoke_certificate(self, fingerprint: str, reason: str = "") -> None:
        """Marks a certificate SHA-256 fingerprint as revoked."""
        self._revoked_fingerprints.add(fingerprint.lower())
        self._save_crl()
        logger.warning("Revoked certificate fingerprint %s (reason: %s)", fingerprint, reason)

    def revoke_fingerprint(self, fingerprint: str) -> None:
        """Alias for revoke_certificate."""
        self.revoke_certificate(fingerprint)

    def is_revoked(self, fingerprint: str) -> bool:
        """Returns True if the certificate fingerprint is revoked."""
        return fingerprint.lower() in self._revoked_fingerprints

    def generate_ca(
        self,
        common_name: str = "AutoDev Root CA",
        validity_days: int = 365,
    ) -> CertificateAuthority:
        """
        Generates a self-signed Root CA private key and certificate.
        """
        if not _HAS_CRYPTOGRAPHY:  # pragma: no cover
            raise CertificateError("The 'cryptography' library is required to generate certificates.")

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AutoDev System"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + dt.timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )

        cert_path = self.cert_dir / "ca.crt"
        key_path = self.cert_dir / "ca.key"

        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        logger.info("Generated Root CA at %s", cert_path)
        return CertificateAuthority(cert_path=str(cert_path), key_path=str(key_path), common_name=common_name)

    def get_or_create_ca(
        self,
        common_name: str = "AutoDev Root CA",
        validity_days: int = 365,
    ) -> CertificateAuthority:
        """Retrieves existing CA or generates a new one."""
        cert_path = self.cert_dir / "ca.crt"
        key_path = self.cert_dir / "ca.key"
        if cert_path.exists() and key_path.exists():
            return CertificateAuthority(cert_path=str(cert_path), key_path=str(key_path), common_name=common_name)
        return self.generate_ca(common_name=common_name, validity_days=validity_days)

    def generate_server_certificate(
        self,
        common_name: str = "localhost",
        dns_names: Optional[List[str]] = None,
        ip_addresses: Optional[List[str]] = None,
        validity_days: int = 90,
    ) -> CertificateInfo:
        """Generates a server certificate signed by Root CA."""
        ca = self.get_or_create_ca()
        san_hosts = (dns_names or []) + (ip_addresses or [])
        if not san_hosts:
            san_hosts = ["localhost", "127.0.0.1"]
        cert_path, key_path = self._generate_signed_cert(
            ca=ca,
            common_name=common_name,
            san_hosts=san_hosts,
            is_server=True,
            validity_days=validity_days,
            out_prefix="server",
        )
        fp = self.get_certificate_fingerprint(cert_path)
        return CertificateInfo(
            cert_path=str(cert_path),
            key_path=str(key_path),
            common_name=common_name,
            fingerprint_sha256=fp,
            is_ca=False,
        )

    def generate_server_cert(self, *args, **kwargs) -> Tuple[Path, Path]:
        """Legacy helper returning tuple."""
        info = self.generate_server_certificate(*args, **kwargs)
        return Path(info.cert_path), Path(info.key_path)

    def generate_client_certificate(
        self,
        worker_id: str,
        organization: str = "AutoDev Remote Worker",
        validity_days: int = 90,
    ) -> CertificateInfo:
        """Generates a worker client certificate signed by Root CA."""
        ca = self.get_or_create_ca()
        safe_id = "".join(c for c in worker_id if c.isalnum() or c in ("-", "_"))
        cert_path, key_path = self._generate_signed_cert(
            ca=ca,
            common_name=worker_id,
            san_hosts=[],
            is_server=False,
            validity_days=validity_days,
            out_prefix=f"worker_{safe_id}",
            org_name=organization,
        )
        fp = self.get_certificate_fingerprint(cert_path)
        return CertificateInfo(
            cert_path=str(cert_path),
            key_path=str(key_path),
            common_name=worker_id,
            fingerprint_sha256=fp,
            is_ca=False,
        )

    def generate_client_cert(self, *args, **kwargs) -> Tuple[Path, Path]:
        """Legacy helper returning tuple."""
        info = self.generate_client_certificate(*args, **kwargs)
        return Path(info.cert_path), Path(info.key_path)

    def _generate_signed_cert(
        self,
        ca: CertificateAuthority,
        common_name: str,
        san_hosts: List[str],
        is_server: bool,
        validity_days: int,
        out_prefix: str,
        org_name: str = "AutoDev Coordinator",
    ) -> Tuple[Path, Path]:
        if not _HAS_CRYPTOGRAPHY:  # pragma: no cover
            raise CertificateError("The 'cryptography' library is required.")

        ca_cert = x509.load_pem_x509_certificate(Path(ca.cert_path).read_bytes())
        ca_key = serialization.load_pem_private_key(Path(ca.key_path).read_bytes(), password=None)

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        now = datetime.now(timezone.utc)
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + dt.timedelta(days=validity_days))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        )

        if san_hosts:
            sans: List[x509.GeneralName] = []
            for host in san_hosts:
                try:
                    ip = ipaddress.ip_address(host)
                    sans.append(x509.IPAddress(ip))
                except ValueError:
                    sans.append(x509.DNSName(host))
            builder = builder.add_extension(x509.SubjectAlternativeName(sans), critical=False)

        cert = builder.sign(ca_key, hashes.SHA256())

        cert_path = self.cert_dir / f"{out_prefix}.crt"
        key_path = self.cert_dir / f"{out_prefix}.key"

        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        return cert_path, key_path

    def verify_certificate(
        self,
        cert_path: Union[str, Path],
        expected_common_name: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> CertificateInfo:
        """Verifies certificate validity, expiration, CA chain issuer, and revocation."""
        raw = Path(cert_path).read_bytes()
        cert = x509.load_pem_x509_certificate(raw)
        fp = cert.fingerprint(hashes.SHA256()).hex()

        if self.is_revoked(fp):
            raise CertificateRevocationError(f"Certificate {fp} has been revoked.")

        now = current_time or datetime.now(timezone.utc)
        if now > cert.not_valid_after_utc:
            raise CertificateExpiredError(f"Certificate expired at {cert.not_valid_after_utc.isoformat()}")
        if now < cert.not_valid_before_utc:
            raise CertificateValidationError(f"Certificate is not yet valid until {cert.not_valid_before_utc.isoformat()}")

        # Verify against local CA if present
        ca_cert_path = self.cert_dir / "ca.crt"
        if ca_cert_path.exists():
            ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
            if cert.issuer != ca_cert.subject:
                raise CertificateValidationError(f"Certificate issuer '{cert.issuer}' does not match CA subject '{ca_cert.subject}'.")

        cn = ""
        for attr in cert.subject:
            if attr.oid == NameOID.COMMON_NAME:
                cn = str(attr.value)

        if expected_common_name and cn != expected_common_name:
            raise CertificateValidationError(f"Certificate Common Name '{cn}' does not match expected '{expected_common_name}'.")

        return CertificateInfo(
            cert_path=str(cert_path),
            common_name=cn,
            fingerprint_sha256=fp,
            is_ca=False,
            not_valid_before=cert.not_valid_before_utc.isoformat(),
            not_valid_after=cert.not_valid_after_utc.isoformat(),
            is_expired=False,
        )

    @staticmethod
    def get_certificate_fingerprint(cert_path_or_bytes: Union[str, Path, bytes]) -> str:
        """Computes SHA-256 fingerprint hex of certificate DER bytes."""
        if isinstance(cert_path_or_bytes, (str, Path)):
            raw = Path(cert_path_or_bytes).read_bytes()
        else:
            raw = cert_path_or_bytes

        if b"-----BEGIN CERTIFICATE-----" in raw:
            cert = x509.load_pem_x509_certificate(raw)
            return cert.fingerprint(hashes.SHA256()).hex()
        return hashlib.sha256(raw).hexdigest()

    def create_server_ssl_context(
        self,
        server_info_or_ca_path: Union[CertificateInfo, str, Path],
        server_cert_path: Optional[Union[str, Path]] = None,
        server_key_path: Optional[Union[str, Path]] = None,
        require_client_cert: bool = True,
    ) -> ssl.SSLContext:
        """Creates server SSLContext."""
        ca = self.get_or_create_ca()
        if isinstance(server_info_or_ca_path, CertificateInfo):
            certfile = server_info_or_ca_path.cert_path
            keyfile = server_info_or_ca_path.key_path
            cafile = ca.cert_path
        else:
            cafile = str(server_info_or_ca_path)
            certfile = str(server_cert_path)
            keyfile = str(server_key_path)

        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        context.load_verify_locations(cafile=cafile)
        if require_client_cert:
            context.verify_mode = ssl.CERT_REQUIRED
        return context

    def create_client_ssl_context(
        self,
        client_info_or_ca_path: Union[CertificateInfo, str, Path],
        client_cert_path: Optional[Union[str, Path]] = None,
        client_key_path: Optional[Union[str, Path]] = None,
    ) -> ssl.SSLContext:
        """Creates client SSLContext."""
        ca = self.get_or_create_ca()
        if isinstance(client_info_or_ca_path, CertificateInfo):
            certfile = client_info_or_ca_path.cert_path
            keyfile = client_info_or_ca_path.key_path
            cafile = ca.cert_path
        else:
            cafile = str(client_info_or_ca_path)
            certfile = str(client_cert_path)
            keyfile = str(client_key_path)

        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=cafile)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        context.verify_mode = ssl.CERT_REQUIRED
        return context
