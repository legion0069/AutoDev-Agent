"""
test_security_intelligence.py - Comprehensive Unit & Stress Tests for Subsystem 2: Security Intelligence Engine
Covers:
- SecurityAdvisoryDatabase: known CVEs catalog, retrieval, addition, filtering
- CVEAnalyzer: version range matching (<, <=, ==, >, >=), CVSS scoring, severity classification
- VulnerabilityScanner: static code analysis for hardcoded secrets, deprecated crypto (MD5, SHA1, DES, RC4), unsafe APIs (eval, exec, pickle, shell=True), weak randomness
- RiskAssessment & SecurityIntelligenceEngine: risk score computation, mitigation plans, edge cases, clean code
"""

import copy
import pytest

from core.ecosystem.security_intelligence import (
    CVEAnalyzer,
    SecurityAdvisoryDatabase,
    SecurityIntelligenceEngine,
    VulnerabilityScanner,
)
from core.ecosystem.ecosystem_models import (
    CVEAdvisory,
    DependencyEcosystem,
    DependencyNode,
    PackageVersion,
    SeverityLevel,
    VulnerabilityFinding,
)


# ============================================================================
# SecurityAdvisoryDatabase Unit Tests
# ============================================================================

class TestSecurityAdvisoryDatabase:
    @pytest.fixture
    def db(self):
        return SecurityAdvisoryDatabase()

    def test_default_advisories_loaded(self, db):
        advisories = db.get_all_advisories()
        assert len(advisories) >= 6
        cve_ids = {a.cve_id for a in advisories}
        assert "CVE-2023-32681" in cve_ids
        assert "CVE-2024-21503" in cve_ids
        assert "CVE-2021-44228" in cve_ids  # Log4Shell

    def test_get_advisory_by_id(self, db):
        adv = db.get_advisory("CVE-2023-32681")
        assert adv is not None
        assert adv.package_name == "requests"
        assert adv.severity == SeverityLevel.HIGH
        assert adv.cvss_score == 7.5

    def test_get_nonexistent_advisory(self, db):
        assert db.get_advisory("CVE-9999-99999") is None

    def test_find_advisories_for_package(self, db):
        advs = db.find_advisories_for_package("requests")
        assert len(advs) >= 1
        assert advs[0].package_name == "requests"

    def test_find_advisories_case_insensitive(self, db):
        advs = db.find_advisories_for_package("REQUESTS")
        assert len(advs) >= 1

    def test_find_advisories_filtered_by_ecosystem(self, db):
        advs_py = db.find_advisories_for_package("requests", DependencyEcosystem.PYTHON)
        assert len(advs_py) >= 1
        advs_npm = db.find_advisories_for_package("requests", DependencyEcosystem.NPM)
        assert len(advs_npm) == 0

    def test_add_custom_advisory(self, db):
        custom = CVEAdvisory(
            cve_id="CVE-2026-0001",
            package_name="custom-sec-pkg",
            ecosystem=DependencyEcosystem.PYTHON,
            affected_version_spec="<1.5.0",
            patched_versions=["1.5.0"],
            severity=SeverityLevel.CRITICAL,
            cvss_score=9.9,
            title="Custom RCE Vulnerability",
            description="Remote code execution in custom-sec-pkg.",
            remediation="Upgrade to 1.5.0 immediately.",
            published_date="2026-01-01",
        )
        db.add_advisory(custom)
        found = db.get_advisory("CVE-2026-0001")
        assert found is not None
        assert found.package_name == "custom-sec-pkg"
        assert found.severity == SeverityLevel.CRITICAL


# ============================================================================
# CVEAnalyzer Unit Tests
# ============================================================================

class TestCVEAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return CVEAnalyzer()

    def test_detect_vulnerable_requests_version(self, analyzer):
        node = DependencyNode(name="requests", current_version="2.28.0", ecosystem=DependencyEcosystem.PYTHON)
        vulns = analyzer.check_dependency(node)
        assert len(vulns) >= 1
        assert any(v.cve_id == "CVE-2023-32681" for v in vulns)

    def test_safe_requests_version_not_flagged(self, analyzer):
        node = DependencyNode(name="requests", current_version="2.32.3", ecosystem=DependencyEcosystem.PYTHON)
        vulns = analyzer.check_dependency(node)
        assert len(vulns) == 0

    def test_detect_pycrypto_critical(self, analyzer):
        node = DependencyNode(name="pycrypto", current_version="2.6.1", ecosystem=DependencyEcosystem.PYTHON)
        vulns = analyzer.check_dependency(node)
        assert len(vulns) >= 1
        cve = vulns[0]
        assert cve.cve_id == "CVE-2024-21503"
        assert cve.severity == SeverityLevel.CRITICAL
        assert cve.cvss_score >= 9.0

    def test_detect_log4shell_in_maven(self, analyzer):
        node = DependencyNode(
            name="org.apache.logging.log4j:log4j-core",
            current_version="2.14.1",
            ecosystem=DependencyEcosystem.MAVEN,
        )
        vulns = analyzer.check_dependency(node)
        assert len(vulns) >= 1
        assert any(v.cve_id == "CVE-2021-44228" for v in vulns)

    def test_safe_log4j_version(self, analyzer):
        node = DependencyNode(
            name="org.apache.logging.log4j:log4j-core",
            current_version="2.17.1",
            ecosystem=DependencyEcosystem.MAVEN,
        )
        vulns = analyzer.check_dependency(node)
        assert len(vulns) == 0

    def test_detect_axios_redos(self, analyzer):
        node = DependencyNode(name="axios", current_version="0.21.1", ecosystem=DependencyEcosystem.NPM)
        vulns = analyzer.check_dependency(node)
        assert len(vulns) >= 1
        assert any(v.cve_id == "CVE-2021-3749" for v in vulns)

    def test_safe_axios_version(self, analyzer):
        node = DependencyNode(name="axios", current_version="1.7.0", ecosystem=DependencyEcosystem.NPM)
        vulns = analyzer.check_dependency(node)
        assert len(vulns) == 0

    def test_unaffected_package_returns_empty(self, analyzer):
        node = DependencyNode(name="safelib", current_version="1.0.0", ecosystem=DependencyEcosystem.PYTHON)
        vulns = analyzer.check_dependency(node)
        assert vulns == []


# ============================================================================
# VulnerabilityScanner Unit Tests (Static Code Analysis)
# ============================================================================

class TestVulnerabilityScanner:
    @pytest.fixture
    def scanner(self):
        return VulnerabilityScanner()

    def test_detect_hardcoded_api_key(self, scanner):
        code = "api_key = 'abcdef1234567890abcdef1234567890'\n"
        findings = scanner.scan_code("config.py", code)
        assert len(findings) == 1
        assert findings[0].category == "HARDCODED_SECRET"
        assert findings[0].severity == SeverityLevel.CRITICAL
        assert findings[0].line_number == 1

    def test_detect_hardcoded_jwt_token(self, scanner):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        code = f"token = '{jwt}'"
        findings = scanner.scan_code("auth.py", code)
        assert any(f.category == "HARDCODED_SECRET" for f in findings)

    def test_detect_hardcoded_private_key(self, scanner):
        code = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        findings = scanner.scan_code("server.key", code)
        assert any(f.category == "HARDCODED_SECRET" for f in findings)

    def test_detect_deprecated_md5_hash(self, scanner):
        code = "import hashlib\ndef hash_pw(pw):\n    return hashlib.md5(pw.encode()).hexdigest()\n"
        findings = scanner.scan_code("crypto.py", code)
        assert len(findings) >= 1
        assert findings[0].category == "DEPRECATED_CRYPTO"
        assert findings[0].severity == SeverityLevel.HIGH
        assert findings[0].line_number == 3

    def test_detect_deprecated_sha1_hash(self, scanner):
        code = "import hashlib\nsig = hashlib.sha1(data).digest()"
        findings = scanner.scan_code("sign.py", code)
        assert any(f.category == "DEPRECATED_CRYPTO" for f in findings)

    def test_detect_eval_execution(self, scanner):
        code = "user_input = request.args.get('expr')\nresult = eval(user_input)\n"
        findings = scanner.scan_code("handler.py", code)
        assert len(findings) >= 1
        assert findings[0].category == "UNSAFE_API"
        assert findings[0].severity == SeverityLevel.HIGH
        assert findings[0].line_number == 2

    def test_detect_exec_execution(self, scanner):
        code = "exec(dynamic_code)"
        findings = scanner.scan_code("runner.py", code)
        assert any(f.category == "UNSAFE_API" for f in findings)

    def test_detect_insecure_pickle_load(self, scanner):
        code = "import pickle\ndata = pickle.loads(raw_bytes)"
        findings = scanner.scan_code("cache.py", code)
        assert any(f.category == "UNSAFE_API" for f in findings)

    def test_detect_subprocess_shell_true(self, scanner):
        code = "import subprocess\nsubprocess.run(cmd, shell=True)"
        findings = scanner.scan_code("cli.py", code)
        assert any(f.category == "UNSAFE_API" for f in findings)

    def test_detect_unsafe_random_in_security_context(self, scanner):
        code = "import random\ndef generate_session_token():\n    return str(random.random())\n"
        findings = scanner.scan_code("tokens.py", code)
        assert any(f.category == "UNSAFE_RANDOMNESS" for f in findings)

    def test_safe_random_in_non_security_context_not_flagged(self, scanner):
        code = "import random\ndef roll_dice():\n    return random.randint(1, 6)\n"
        findings = scanner.scan_code("game.py", code)
        assert len(findings) == 0

    def test_clean_secure_code_has_no_findings(self, scanner):
        code = """
import os
import secrets
import hashlib

def generate_secure_token():
    return secrets.token_hex(32)

def hash_data(data: bytes):
    return hashlib.sha256(data).hexdigest()

def get_db_password():
    return os.environ.get("DB_PASSWORD", "")
"""
        findings = scanner.scan_code("secure_app.py", code)
        assert len(findings) == 0


# ============================================================================
# SecurityIntelligenceEngine Integration & Scoring Tests
# ============================================================================

class TestSecurityIntelligenceEngine:
    @pytest.fixture
    def engine(self):
        return SecurityIntelligenceEngine()

    def test_scan_clean_project(self, engine):
        deps = [
            DependencyNode(name="fastapi", current_version="0.115.0"),
            DependencyNode(name="requests", current_version="2.32.3"),
        ]
        files = {
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "utils.py": "def add(a, b): return a + b\n",
        }
        report = engine.scan_project(deps, files)
        assert report["is_secure"] is True
        assert report["security_score"] == 100.0
        assert report["total_vulnerabilities"] == 0
        assert len(report["mitigation_plan"]) == 0

    def test_scan_vulnerable_project_computes_score_penalty(self, engine):
        deps = [
            DependencyNode(name="pycrypto", current_version="2.6.1"),  # CRITICAL CVE
            DependencyNode(name="requests", current_version="2.28.0"),  # HIGH CVE
        ]
        files = {
            "auth.py": "api_key = 'abcdef1234567890abcdef1234567890'\n",  # CRITICAL SECRET
            "calc.py": "result = eval(user_input)\n",  # HIGH API
        }
        report = engine.scan_project(deps, files)
        assert report["is_secure"] is False
        assert report["security_score"] < 50.0
        assert report["critical_count"] >= 2
        assert report["high_count"] >= 2
        assert len(report["mitigation_plan"]) >= 4

    def test_mitigation_plan_includes_actionable_advice(self, engine):
        deps = [DependencyNode(name="pycrypto", current_version="2.6.1")]
        files = {"leak.py": "jwt_secret = 'abcdef1234567890abcdef1234567890'\n"}
        report = engine.scan_project(deps, files)
        plan_text = " ".join(report["mitigation_plan"])
        assert "pycrypto" in plan_text
        assert "leak.py" in plan_text

    def test_empty_project_inputs(self, engine):
        report = engine.scan_project([], {})
        assert report["is_secure"] is True
        assert report["security_score"] == 100.0
        assert report["total_vulnerabilities"] == 0

    def test_vulnerability_finding_serialization(self):
        finding = VulnerabilityFinding(
            finding_id="FIND-1",
            category="UNSAFE_API",
            target="src/main.py",
            severity=SeverityLevel.HIGH,
            description="Use of eval",
            line_number=42,
            snippet="eval(x)",
            remediation_advice="Do not use eval",
        )
        d = finding.to_dict()
        assert d["category"] == "UNSAFE_API"
        assert d["severity"] == "HIGH"
        assert d["line_number"] == 42
