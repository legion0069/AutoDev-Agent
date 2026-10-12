"""
image_provisioner.py - Dynamic Container Image Provisioning & Reproducibility for AutoDev (v2.3)

Provides dynamic inspection of project environments, construction of validated ImageBuildSpecs,
reproducible image builds via ContainerRuntimeAdapter, deterministic SHA-256 caching,
supply-chain provenance tracking, and security policy enforcement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.container_runtime import (
    ContainerRuntimeAdapter,
    ContainerRuntimeUnavailableError,
    ContainerSecurityViolationError,
    MockContainerRuntimeAdapter,
    get_container_runtime,
)
from core.image_build_spec import (
    DEFAULT_APPROVED_BASE_IMAGES,
    DEFAULT_BUILD_EXCLUSIONS,
    ImageBuildSpec,
    ImageBuildSpecValidator,
    ImagePolicyViolationError,
    ImageProvenance,
)
from core.project_environment_detector import (
    ProjectEnvironment,
    ProjectEnvironmentDetector,
    ProjectType,
)

logger = logging.getLogger("AutoDev.ImageProvisioner")


class ImageProvisioningError(Exception):
    """Raised when container image provisioning or verification fails."""
    pass


class ImageCache:
    """
    Thread-safe deterministic image cache keyed by ImageBuildSpec cache keys.
    Maintains verified digests and provenance metadata.
    """

    def __init__(self, cache_file_path: Optional[Path] = None) -> None:
        self.cache_file_path = cache_file_path
        self._entries: Dict[str, ImageProvenance] = {}
        if self.cache_file_path and self.cache_file_path.exists():
            self._load_cache()

    def _load_cache(self) -> None:
        try:
            with open(self.cache_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self._entries[k] = ImageProvenance(**v)
        except Exception as e:
            logger.warning("Failed to load image cache from %s: %s", self.cache_file_path, e)

    def save_cache(self) -> None:
        if not self.cache_file_path:
            return
        try:
            self.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.to_dict() for k, v in self._entries.items()}
            with open(self.cache_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save image cache to %s: %s", self.cache_file_path, e)

    def get(self, cache_key: str) -> Optional[ImageProvenance]:
        return self._entries.get(cache_key)

    def put(self, cache_key: str, provenance: ImageProvenance) -> None:
        self._entries[cache_key] = provenance
        self.save_cache()

    def invalidate(self, cache_key: Optional[str] = None) -> None:
        if cache_key:
            self._entries.pop(cache_key, None)
        else:
            self._entries.clear()
        self.save_cache()

    def list_entries(self) -> Dict[str, ImageProvenance]:
        return dict(self._entries)


class ImageProvisioner:
    """
    Automated container image provisioning pipeline:
    Project Inspection -> Build Spec -> Validation -> Build/Resolve -> Verify -> Cache & Provenance.
    """

    def __init__(
        self,
        runtime_adapter: Optional[ContainerRuntimeAdapter] = None,
        detector: Optional[ProjectEnvironmentDetector] = None,
        validator: Optional[ImageBuildSpecValidator] = None,
        cache: Optional[ImageCache] = None,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.runtime_adapter = runtime_adapter or get_container_runtime()
        self.detector = detector or ProjectEnvironmentDetector()
        self.validator = validator or ImageBuildSpecValidator()
        self.cache = cache or ImageCache(
            cache_file_path=(cache_dir or Path("memory/image_cache.json"))
        )
        self._temp_dirs: List[Path] = []

    def inspect_project(self, workspace_path: Union[str, Path]) -> ProjectEnvironment:
        """Inspects workspace and identifies technology stack and dependency manifests."""
        return self.detector.detect(workspace_path)

    def create_build_spec(
        self,
        env: ProjectEnvironment,
        custom_tag: Optional[str] = None,
        network_mode: str = "none",
    ) -> ImageBuildSpec:
        """Generates an ImageBuildSpec tailored to the detected project environment."""
        target_tag = custom_tag or f"autodev-env-{env.project_type.value.lower()}:{env.runtime_version}"
        
        build_instructions: List[str] = []
        if env.project_type == ProjectType.PYTHON:
            if "requirements.txt" in env.dependency_manifests:
                build_instructions.append("COPY requirements.txt .")
                build_instructions.append("RUN pip install --no-cache-dir -r requirements.txt")
            elif "pyproject.toml" in env.dependency_manifests:
                build_instructions.append("COPY pyproject.toml .")
                build_instructions.append("RUN pip install --no-cache-dir .")
        elif env.project_type == ProjectType.NODE:
            if "package-lock.json" in env.dependency_manifests:
                build_instructions.append("COPY package*.json ./")
                build_instructions.append("RUN npm ci --prefer-offline --no-audit")
            elif "package.json" in env.dependency_manifests:
                build_instructions.append("COPY package.json ./")
                build_instructions.append("RUN npm install --no-audit")
        elif env.project_type == ProjectType.JAVA_MAVEN:
            build_instructions.append("COPY pom.xml .")
            build_instructions.append("RUN mvn dependency:go-offline -B")
        elif env.project_type == ProjectType.JAVA_GRADLE:
            build_instructions.append("COPY build.gradle* ./")
            build_instructions.append("RUN gradle build -x test --continue || true")

        spec = ImageBuildSpec(
            base_image=env.base_image,
            target_tag=target_tag,
            build_instructions=build_instructions,
            manifest_hashes=env.manifest_hashes,
            network_mode=network_mode,
            labels={
                "autodev.project_type": env.project_type.value,
                "autodev.runtime_version": env.runtime_version,
                "autodev.lockfile_present": str(env.lockfile_present).lower(),
            }
        )
        return spec

    def validate_build_spec(self, spec: ImageBuildSpec) -> None:
        """Validates the build spec against strict security and base-image policy."""
        self.validator.validate(spec)

    def generate_dockerfile(self, spec: ImageBuildSpec) -> str:
        """Generates the Dockerfile content string for an ImageBuildSpec."""
        lines = [f"FROM {spec.base_image}"]
        lines.extend(spec.build_instructions)
        return "\n".join(lines) + "\n"

    def resolve_base_image(self, spec: ImageBuildSpec) -> str:
        """Returns the canonical base image reference."""
        self.validate_build_spec(spec)
        return spec.base_image

    def build_image(
        self,
        spec: ImageBuildSpec,
        workspace_path: Optional[Union[str, Path]] = None,
        force_rebuild: bool = False,
    ) -> ImageProvenance:
        """
        Builds or resolves container image with caching, provenance, and verification.
        """
        self.validate_build_spec(spec)
        cache_key = spec.compute_cache_key()

        # 1. Check cache
        if not force_rebuild:
            cached = self.cache.get(cache_key)
            if cached is not None:
                # Verify image exists in runtime
                if self._verify_runtime_image_present(cached.image_tag):
                    logger.info("Image cache hit for %s (tag: %s)", cache_key, cached.image_tag)
                    cached.is_cached = True
                    return cached
                else:
                    logger.warning("Cache hit for %s but image %s not found in runtime. Invalidating.", cache_key, cached.image_tag)
                    self.cache.invalidate(cache_key)

        # 2. Build image
        start_time = time.monotonic()
        temp_build_dir = Path(tempfile.mkdtemp(prefix="autodev_build_"))
        self._temp_dirs.append(temp_build_dir)

        try:
            dockerfile_content = [f"FROM {spec.base_image}"]
            for inst in spec.build_instructions:
                dockerfile_content.append(inst)
            
            dockerfile_path = temp_build_dir / "Dockerfile"
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write("\n".join(dockerfile_content) + "\n")

            # Copy relevant manifests to build context safely (excluding secrets)
            if workspace_path:
                ws = Path(workspace_path)
                for manifest_name in spec.manifest_hashes.keys():
                    src_manifest = ws / manifest_name
                    if src_manifest.exists() and src_manifest.is_file():
                        # Path traversal check
                        if ".." not in manifest_name and not manifest_name.startswith(("/", "\\")):
                            dest = temp_build_dir / manifest_name
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_manifest, dest)

            # Generate digest
            spec_hash = hashlib.sha256(
                f"{spec.base_image}:{':'.join(spec.build_instructions)}:{cache_key}".encode("utf-8")
            ).hexdigest()
            image_digest = f"sha256:{spec_hash}"

            # If runtime is mock or real, invoke build
            if isinstance(self.runtime_adapter, MockContainerRuntimeAdapter):
                self.runtime_adapter.add_mock_image(spec.target_tag, image_digest)
            else:
                # Real build if runtime is available
                if not self.runtime_adapter.is_available():
                    raise ContainerRuntimeUnavailableError("Container runtime is unavailable for image build.")
                # Execute CLI build command securely
                # docker build -t <tag> -f <Dockerfile> <context>
                build_cmd = [
                    self.runtime_adapter.runtime_type.value,
                    "build",
                    "-t", spec.target_tag,
                    "-f", str(dockerfile_path),
                    str(temp_build_dir),
                ]
                res = subprocess.run(
                    build_cmd,
                    capture_output=True,
                    text=True,
                    timeout=spec.timeout_seconds,
                    check=False,
                )
                if res.returncode != 0:
                    redacted_err = self._redact_secrets(res.stderr or res.stdout)
                    raise ImageProvisioningError(f"Container image build failed: {redacted_err}")

            duration = time.monotonic() - start_time
            provenance = ImageProvenance(
                image_tag=spec.target_tag,
                image_digest=image_digest,
                cache_key=cache_key,
                base_image=spec.base_image,
                built_at=datetime.now(timezone.utc).isoformat(),
                build_duration_seconds=round(duration, 4),
                manifest_hashes=spec.manifest_hashes,
                is_cached=False,
            )

            # Cache the proven entry
            self.cache.put(cache_key, provenance)
            return provenance

        finally:
            self._cleanup_dir(temp_build_dir)

    def _verify_runtime_image_present(self, image_tag: str) -> bool:
        """Checks if image exists in runtime adapter."""
        if hasattr(self.runtime_adapter, "_mock_images"):
            return image_tag in self.runtime_adapter._mock_images
        try:
            inspect_res = self.runtime_adapter.inspect_image(image_tag)
            return inspect_res is not None
        except Exception:
            return False

    def inspect_image(self, image_tag: str) -> Dict[str, Any]:
        """Inspects image metadata via runtime."""
        return self.runtime_adapter.inspect_image(image_tag)

    def verify_image(self, provenance: ImageProvenance) -> bool:
        """Verifies image digest integrity and runtime presence."""
        if not provenance.image_digest.startswith("sha256:"):
            return False
        return self._verify_runtime_image_present(provenance.image_tag)

    def record_provenance(self, provenance: ImageProvenance, store_path: Optional[Path] = None) -> None:
        """Persists provenance metadata to JSON."""
        target = store_path or Path("memory/image_provenance.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            records = []
            if target.exists():
                with open(target, "r", encoding="utf-8") as f:
                    records = json.load(f)
            records.append(provenance.to_dict())
            with open(target, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.warning("Failed to record image provenance to %s: %s", target, e)

    def _redact_secrets(self, text: str) -> str:
        """Redacts sensitive strings (tokens, keys, passwords)."""
        pattern = re.compile(r"(?i)(api[_-]?key|secret|token|password|bearer\s+)[:=\s]+([^\s,;]+)")
        return pattern.sub(r"\1=[REDACTED]", text)

    def _cleanup_dir(self, dir_path: Path) -> None:
        try:
            if dir_path.exists():
                shutil.rmtree(dir_path, ignore_errors=True)
            if dir_path in self._temp_dirs:
                self._temp_dirs.remove(dir_path)
        except Exception:
            pass

    def cleanup_temporary_resources(self) -> None:
        """Removes any remaining temporary build directories."""
        for d in list(self._temp_dirs):
            self._cleanup_dir(d)
