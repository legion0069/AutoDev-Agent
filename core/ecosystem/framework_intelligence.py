"""
framework_intelligence.py - Framework Lifecycle, Breaking Changes & Deprecations (v3.2)

Maintains structured knowledge about:
- Spring Boot
- React
- Angular
- Vue
- FastAPI
- Flask
- Django
- Node.js
- Express
- MongoDB
- PostgreSQL
- Redis
- Docker
- Kubernetes

Tracks new releases, breaking changes, deprecated APIs, migration guides, and recommended versions.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from core.ecosystem.ecosystem_models import FrameworkRelease, PackageVersion

logger = logging.getLogger("AutoDev.FrameworkIntelligence")


class FrameworkIntelligenceEngine:
    """
    Catalog of enterprise framework releases, lifecycle status (LTS/EOL),
    deprecated APIs, breaking changes, and migration prerequisites.
    """

    def __init__(self) -> None:
        self._frameworks: Dict[str, List[FrameworkRelease]] = {}
        self._load_framework_database()

    def _load_framework_database(self) -> None:
        catalog = [
            # FastAPI
            FrameworkRelease(
                framework="FastAPI",
                version="0.115.0",
                release_date="2024-09-18",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["Requires Pydantic v2.0+ for strict validation modes"],
                deprecated_apis=["@app.on_event('startup') replaced by lifespan context managers"],
                recommended_min_python_or_node=">=3.8",
                migration_guide_summary="Migrate from on_event to asynccontextmanager lifespan handler.",
            ),
            FrameworkRelease(
                framework="FastAPI",
                version="0.95.0",
                release_date="2023-04-03",
                is_lts=False,
                is_deprecated=False,
                breaking_changes=[],
                deprecated_apis=[],
                recommended_min_python_or_node=">=3.7",
            ),
            # React
            FrameworkRelease(
                framework="React",
                version="19.0.0",
                release_date="2024-04-25",
                is_lts=False,
                is_deprecated=False,
                breaking_changes=[
                    "Removal of deprecated String Refs",
                    "Removal of Legacy Context API (contextTypes)",
                    "useActionState and useFormStatus replacing manual form states",
                ],
                deprecated_apis=["ReactDOM.render (completely removed)", "defaultProps on functional components"],
                recommended_min_python_or_node="Node >=18.17.0",
                migration_guide_summary="Use createRoot instead of ReactDOM.render; migrate defaultProps to ES6 default params.",
            ),
            FrameworkRelease(
                framework="React",
                version="18.3.1",
                release_date="2024-04-26",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=[],
                deprecated_apis=[],
                recommended_min_python_or_node="Node >=16.0.0",
            ),
            # Spring Boot
            FrameworkRelease(
                framework="Spring Boot",
                version="3.3.0",
                release_date="2024-05-23",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=[
                    "Requires Java 17 as baseline minimum",
                    "Namespace migration from javax.* to jakarta.* across Servlets and Persistence",
                ],
                deprecated_apis=["WebSecurityConfigurerAdapter removed in Spring Security 6"],
                recommended_min_python_or_node="Java >=17",
                migration_guide_summary="Replace javax imports with jakarta; configure SecurityFilterChain bean.",
            ),
            FrameworkRelease(
                framework="Spring Boot",
                version="2.7.18",
                release_date="2023-11-23",
                is_lts=False,
                is_deprecated=True,
                breaking_changes=[],
                deprecated_apis=[],
                recommended_min_python_or_node="Java 8 or 11",
                migration_guide_summary="Spring Boot 2.x OSS support ended Nov 2023. Migrate to 3.x.",
            ),
            # Django
            FrameworkRelease(
                framework="Django",
                version="5.1.0",
                release_date="2024-08-07",
                is_lts=False,
                is_deprecated=False,
                breaking_changes=["OS-level authentication changes in admin"],
                deprecated_apis=["django.utils.timezone.utc deprecated in favor of datetime.timezone.utc"],
                recommended_min_python_or_node="Python >=3.10",
            ),
            FrameworkRelease(
                framework="Django",
                version="4.2.16",
                release_date="2024-09-04",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=[],
                deprecated_apis=[],
                recommended_min_python_or_node="Python >=3.8",
            ),
            # Node.js
            FrameworkRelease(
                framework="Node",
                version="20.17.0",
                release_date="2024-08-21",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["Built-in fetch enabled natively", "Stable test runner available via node:test"],
                deprecated_apis=[],
                recommended_min_python_or_node="N/A",
            ),
            FrameworkRelease(
                framework="Node",
                version="16.20.2",
                release_date="2023-08-08",
                is_lts=False,
                is_deprecated=True,
                breaking_changes=[],
                deprecated_apis=[],
                recommended_min_python_or_node="N/A",
                migration_guide_summary="Node 16 End-of-Life reached September 2023. Upgrade to Node 20 LTS.",
            ),
            # Kubernetes
            FrameworkRelease(
                framework="Kubernetes",
                version="1.31.0",
                release_date="2024-08-13",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["Removal of in-tree cloud providers"],
                deprecated_apis=["FlowSchema and PriorityLevelConfiguration v1beta3 removed"],
                recommended_min_python_or_node="Go >=1.22",
            ),
            # PostgreSQL
            FrameworkRelease(
                framework="PostgreSQL",
                version="16.4",
                release_date="2024-08-08",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["pg_hba.conf regex matching changes"],
                deprecated_apis=[],
                recommended_min_python_or_node="N/A",
            ),
            # Flask
            FrameworkRelease(
                framework="Flask",
                version="3.0.3",
                release_date="2024-04-07",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["Werkzeug 3.0+ required; legacy app.json_encoder removed"],
                deprecated_apis=["app.json_encoder (use json.provider instead)"],
                recommended_min_python_or_node="Python >=3.8",
            ),
            # Angular
            FrameworkRelease(
                framework="Angular",
                version="18.2.0",
                release_date="2024-08-14",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["Zoneless change detection preview", "Standalone components default"],
                deprecated_apis=["NgModules optional; legacy factory apis deprecated"],
                recommended_min_python_or_node="Node >=18.19.0",
            ),
            # Vue
            FrameworkRelease(
                framework="Vue",
                version="3.5.10",
                release_date="2024-09-27",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=[],
                deprecated_apis=["Vue 2 Options API lifecycle events in legacy compat mode"],
                recommended_min_python_or_node="Node >=18.0.0",
            ),
            # Express
            FrameworkRelease(
                framework="Express",
                version="4.21.0",
                release_date="2024-09-11",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=[],
                deprecated_apis=[],
                recommended_min_python_or_node="Node >=18.0.0",
            ),
            # MongoDB
            FrameworkRelease(
                framework="MongoDB",
                version="7.0.12",
                release_date="2024-07-16",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["Query settings persistence format changes"],
                deprecated_apis=[],
                recommended_min_python_or_node="N/A",
            ),
            # Redis
            FrameworkRelease(
                framework="Redis",
                version="7.2.5",
                release_date="2024-05-02",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=[],
                deprecated_apis=[],
                recommended_min_python_or_node="N/A",
            ),
            # Docker
            FrameworkRelease(
                framework="Docker",
                version="27.2.0",
                release_date="2024-08-27",
                is_lts=True,
                is_deprecated=False,
                breaking_changes=["BuildKit default builder v2 engine"],
                deprecated_apis=["Legacy v1 builder deprecated"],
                recommended_min_python_or_node="N/A",
            ),
        ]
        for rel in catalog:
            self._frameworks.setdefault(rel.framework.lower(), []).append(rel)

    def get_latest_version(self, framework_name: str) -> Optional[str]:
        """Returns the latest release version for a framework."""
        releases = self._frameworks.get(framework_name.lower())
        if not releases:
            return None
        # Return first or highest version
        return releases[0].version

    def get_recommended_lts_version(self, framework_name: str) -> Optional[str]:
        """Returns the recommended Long-Term Support (LTS) version."""
        releases = self._frameworks.get(framework_name.lower(), [])
        for rel in releases:
            if rel.is_lts and not rel.is_deprecated:
                return rel.version
        return releases[0].version if releases else None

    def evaluate_framework(self, framework_name: str, current_version: str) -> Dict[str, Any]:
        """Evaluates a framework version against current ecosystem knowledge."""
        name_key = framework_name.lower()
        releases = self._frameworks.get(name_key, [])
        if not releases:
            return {
                "framework": framework_name,
                "current_version": current_version,
                "status": "UNKNOWN",
                "is_supported": True,
                "recommended_version": current_version,
                "breaking_changes_ahead": [],
                "deprecated_apis_ahead": [],
            }

        cur_v = PackageVersion(current_version)
        recommended_lts = self.get_recommended_lts_version(framework_name) or releases[0].version
        rec_v = PackageVersion(recommended_lts)

        is_deprecated = any(r.is_deprecated for r in releases if PackageVersion(r.version) == cur_v)
        
        # Check breaking changes in versions higher than current
        breaking_changes = []
        deprecated_apis = []
        for rel in releases:
            if PackageVersion(rel.version) > cur_v:
                breaking_changes.extend(rel.breaking_changes)
                deprecated_apis.extend(rel.deprecated_apis)

        return {
            "framework": framework_name,
            "current_version": current_version,
            "status": "DEPRECATED" if is_deprecated else ("OUTDATED" if cur_v < rec_v else "CURRENT"),
            "is_supported": not is_deprecated,
            "recommended_version": recommended_lts,
            "breaking_changes_ahead": list(set(breaking_changes)),
            "deprecated_apis_ahead": list(set(deprecated_apis)),
            "migration_recommended": (cur_v < rec_v or is_deprecated),
        }
