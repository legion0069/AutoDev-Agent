"""
image_build_spec.py - Validated Container Image Build Specifications & Provenance for AutoDev (v2.3)

Defines build specifications for dynamic container provisioning, reproducible base images,
context exclusions, supply-chain provenance tracking, and security policy validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("AutoDev.ImageBuildSpec")


class ImagePolicyViolationError(Exception):
    """Raised when an ImageBuildSpec violates container provisioning security policies."""
    pass


DEFAULT_APPROVED_BASE_IMAGES = {
    "python:3.12-slim",
    "python:3.11-slim",
    "python:3.10-slim",
    "node:20-slim",
    "node:18-slim",
    "maven:3.9-eclipse-temurin-17",
    "gradle:8.5-jdk17",
    "alpine:3.19",
}

DEFAULT_BUILD_EXCLUSIONS = [
    ".git",
    ".github",
    ".env*",
    "*.pem",
    "*.key",
    "*.pkcs12",
    "id_rsa*",
    "memory/execution_journal",
    "__pycache__",
    "*.pyc",
    "node_modules",
    "target",
    "build",
    ".venv",
    "venv",
]


@dataclass
class ImageBuildSpec:
    """Specification for building or resolving a reproducible container execution image."""
    base_image: str
    target_tag: str
    build_instructions: List[str] = field(default_factory=list)
    build_args: Dict[str, str] = field(default_factory=dict)
    context_exclusions: List[str] = field(default_factory=lambda: list(DEFAULT_BUILD_EXCLUSIONS))
    network_mode: str = "none"  # "none" | "bridge"
    cpu_limit: str = "2.0"
    memory_limit: str = "1g"
    timeout_seconds: float = 300.0
    labels: Dict[str, str] = field(default_factory=lambda: {"managed_by": "autodev-v2.3"})
    manifest_hashes: Dict[str, str] = field(default_factory=dict)
    spec_created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_cache_key(self) -> str:
        """
        Computes deterministic SHA-256 cache key based on base image,
        instructions, and manifest file hashes.
        """
        hasher = hashlib.sha256()
        hasher.update(self.base_image.encode("utf-8"))
        for inst in self.build_instructions:
            hasher.update(inst.encode("utf-8"))
        for k in sorted(self.manifest_hashes.keys()):
            hasher.update(f"{k}:{self.manifest_hashes[k]}".encode("utf-8"))
        return hasher.hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_image": self.base_image,
            "target_tag": self.target_tag,
            "build_instructions": self.build_instructions,
            "build_args": {k: "[REDACTED]" if any(s in k.lower() for s in ["key", "secret", "token", "pass"]) else v for k, v in self.build_args.items()},
            "context_exclusions": self.context_exclusions,
            "network_mode": self.network_mode,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "timeout_seconds": self.timeout_seconds,
            "labels": self.labels,
            "manifest_hashes": self.manifest_hashes,
            "cache_key": self.compute_cache_key(),
            "spec_created_at": self.spec_created_at,
        }


@dataclass
class ImageProvenance:
    """Cryptographic and supply-chain provenance metadata for a provisioned container image."""
    image_tag: str = "autodev-generated:latest"
    image_digest: str = ""
    cache_key: str = ""
    base_image: str = "python:3.12-slim"
    base_image_digest: str = ""
    built_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    build_duration_seconds: float = 0.0
    manifest_hashes: Dict[str, str] = field(default_factory=dict)
    builder_version: str = "autodev-2.3.0"
    is_cached: bool = False
    reproducible: bool = True
    build_spec_hash: str = ""

    def __post_init__(self) -> None:
        if self.build_spec_hash and not self.cache_key:
            self.cache_key = self.build_spec_hash
        elif self.cache_key and not self.build_spec_hash:
            self.build_spec_hash = self.cache_key

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ImageBuildSpecValidator:
    """
    Enforces security boundaries and approved base images on ImageBuildSpecs.
    """

    def __init__(
        self,
        approved_base_images: Optional[Set[str]] = None,
        allow_custom_registries: bool = False,
    ) -> None:
        self.approved_base_images = approved_base_images or set(DEFAULT_APPROVED_BASE_IMAGES)
        self.allow_custom_registries = allow_custom_registries

    def validate(self, spec: ImageBuildSpec) -> None:
        """
        Validates ImageBuildSpec against safety constraints.
        Raises ImagePolicyViolationError if invalid.
        """
        # 1. Base image validation
        base_clean = spec.base_image.split("@")[0].strip()
        if not self.allow_custom_registries and base_clean not in self.approved_base_images:
            raise ImagePolicyViolationError(
                f"Base image '{spec.base_image}' is not in approved image allowlist: {sorted(list(self.approved_base_images))}"
            )

        # 2. Build instructions validation - forbid dangerous commands
        forbidden_instruction_patterns = [
            re.compile(r"(?i)\bsudo\b"),
            re.compile(r"(?i)chmod\s+\+s"),
            re.compile(r"(?i)useradd.*--uid\s+0"),
            re.compile(r"(?i)/var/run/docker\.sock"),
            re.compile(r"(?i)curl.*\|\s*(ba)?sh"),
            re.compile(r"(?i)wget.*\|\s*(ba)?sh"),
        ]
        for inst in spec.build_instructions:
            for pat in forbidden_instruction_patterns:
                if pat.search(inst):
                    raise ImagePolicyViolationError(
                        f"Build instruction contains prohibited pattern '{pat.pattern}': '{inst}'"
                    )

        # 3. Context exclusion validation
        mandatory_exclusions = {".git", ".env*", "*.key", "*.pem"}
        current_excl = set(spec.context_exclusions)
        for mand in mandatory_exclusions:
            if not any(mand in e or e in mand for e in current_excl):
                spec.context_exclusions.append(mand)
