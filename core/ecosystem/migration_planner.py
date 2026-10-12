"""
migration_planner.py - Automated Ecosystem Migration Planner (v3.2)

Synthesizes step-by-step, actionable migration plans for major ecosystem transitions:
- Python 3.10 → 3.13
- Spring Boot 2 → 3
- React 17/18 → 19
- Angular upgrades
- Java 17 → 21

Generates breaking API lists, regex code modifications, test verification suites, and rollback strategies.
"""

from __future__ import annotations

import copy
import logging
import time
from typing import Any, Dict, List, Optional

from core.ecosystem.ecosystem_models import MigrationPlan, MigrationStep

logger = logging.getLogger("AutoDev.MigrationPlanner")


class MigrationPlanner:
    """
    Generates structured, automated migration blueprints with code modifications,
    testing requirements, and rollback procedures.
    """

    MIGRATION_TEMPLATES: Dict[str, Dict[str, Any]] = {
        "python_3.10_to_3.13": {
            "source": "Python",
            "from_ver": "3.10",
            "to_ver": "3.13",
            "title": "Python 3.10 to 3.13 Runtime & Deprecation Migration",
            "summary": "Upgrades interpreter baseline to Python 3.13, removes dead stdlib modules (cgi, telnetlib, crypt), and leverages GIL-free multi-threading.",
            "breaking_apis": [
                "cgi module removed (PEP 594)",
                "crypt module removed (PEP 594)",
                "telnetlib and pipes modules removed",
                "Py_TRACEREFS build changes",
            ],
            "code_modifications": [
                "Replace 'import cgi' with multipart or email.message",
                "Replace 'import crypt' with hashlib or bcrypt",
                "Update typing.get_type_hints with include_extras=True",
            ],
            "steps": [
                MigrationStep(
                    step_number=1,
                    title="Audit Dead Standard Library Imports",
                    target_component="requirements & core codebase",
                    action_type="CODE_REFACTOR",
                    instructions="Scan all files for cgi, crypt, pipes, telnetlib and replace with modern libraries.",
                    code_modification_example="- import cgi\n+ import urllib.parse",
                    verification_check="python -c 'import cgi' fails on 3.13",
                ),
                MigrationStep(
                    step_number=2,
                    title="Update CI/CD Environment Matrix",
                    target_component="Dockerfile & GitHub Actions",
                    action_type="CONFIG_UPDATE",
                    instructions="Bump python:3.10-slim to python:3.13-slim in Dockerfile and CI matrix.",
                    code_modification_example="- image: python:3.10\n+ image: python:3.13",
                    verification_check="docker build -t app:v3.13 . succeeds",
                ),
                MigrationStep(
                    step_number=3,
                    title="Execute Full Regression Test Suite",
                    target_component="tests/",
                    action_type="TEST_VALIDATION",
                    instructions="Run pytest with -W error::DeprecationWarning to catch runtime deprecations.",
                    verification_check="pytest tests/ exits with 0",
                ),
            ],
            "testing_requirements": [
                "Run test suite across Python 3.13 environment",
                "Validate C-extension builds and binary wheel compatibility",
                "Inspect performance benchmarks under tiered JIT",
            ],
            "rollback_plan": [
                "Revert Dockerfile base image to python:3.10-slim",
                "Revert pyproject.toml python_requires constraint to '>=3.10'",
                "Deploy previous container image tag from registry",
            ],
            "estimated_hours": 12.0,
            "risk_level": "LOW",
        },
        "spring_boot_2_to_3": {
            "source": "Spring Boot",
            "from_ver": "2.7",
            "to_ver": "3.3",
            "title": "Spring Boot 2.x to 3.x Enterprise Migration",
            "summary": "Upgrades Spring Boot baseline to Java 17+, completes Jakarta EE 9/10 namespace migration, and updates Spring Security 6.",
            "breaking_apis": [
                "javax.persistence.* -> jakarta.persistence.*",
                "javax.servlet.* -> jakarta.servlet.*",
                "WebSecurityConfigurerAdapter removed",
            ],
            "code_modifications": [
                "Sed/Regex replace all javax.servlet with jakarta.servlet",
                "Sed/Regex replace all javax.persistence with jakarta.persistence",
                "Declare SecurityFilterChain @Bean replacing WebSecurityConfigurerAdapter",
            ],
            "steps": [
                MigrationStep(
                    step_number=1,
                    title="Upgrade Java Baseline to JDK 17+",
                    target_component="pom.xml / build.gradle",
                    action_type="CONFIG_UPDATE",
                    instructions="Set <java.version>17</java.version> in Maven POM.",
                    code_modification_example="- <java.version>11</java.version>\n+ <java.version>17</java.version>",
                    verification_check="mvn compile --version prints JDK 17",
                ),
                MigrationStep(
                    step_number=2,
                    title="Jakarta EE Namespace Replacement",
                    target_component="src/main/java",
                    action_type="CODE_REFACTOR",
                    instructions="Replace javax.* imports with jakarta.* throughout entities, servlets, and controllers.",
                    code_modification_example="- import javax.persistence.Entity;\n+ import jakarta.persistence.Entity;",
                    verification_check="Grep for javax.servlet returns 0 matches",
                ),
                MigrationStep(
                    step_number=3,
                    title="Modernize Spring Security Configuration",
                    target_component="SecurityConfig.java",
                    action_type="CODE_REFACTOR",
                    instructions="Refactor configure(HttpSecurity http) to return SecurityFilterChain bean.",
                    verification_check="Application starts and authenticates cleanly",
                ),
            ],
            "testing_requirements": [
                "Execute JPA entity mapping tests",
                "Validate Spring Security filter chain endpoints",
                "Run contract tests against client APIs",
            ],
            "rollback_plan": [
                "Checkout previous git branch with Spring Boot 2.7.x",
                "Revert JDK runtime setting to 11 in deployment manifests",
            ],
            "estimated_hours": 24.0,
            "risk_level": "HIGH",
        },
        "react_18_to_19": {
            "source": "React",
            "from_ver": "18.3",
            "to_ver": "19.0",
            "title": "React 18 to 19 Core Framework Migration",
            "summary": "Adopts React 19 compiler enhancements, replaces manual form action state with useActionState, removes legacy ReactDOM.render and String Refs.",
            "breaking_apis": [
                "ReactDOM.render completely removed",
                "String refs removed",
                "Legacy contextTypes removed",
            ],
            "code_modifications": [
                "Replace ReactDOM.render(component, container) with createRoot(container).render(component)",
                "Replace defaultProps with ES6 default function parameter values",
            ],
            "steps": [
                MigrationStep(
                    step_number=1,
                    title="Upgrade package.json React and React-DOM",
                    target_component="package.json",
                    action_type="DEPENDENCY_UPGRADE",
                    instructions="Update react and react-dom to ^19.0.0.",
                    code_modification_example="- \"react\": \"^18.3.1\"\n+ \"react\": \"^19.0.0\"",
                    verification_check="npm ls react shows 19.0.0",
                ),
                MigrationStep(
                    step_number=2,
                    title="Eliminate defaultProps on Functional Components",
                    target_component="src/components/",
                    action_type="CODE_REFACTOR",
                    instructions="Convert Component.defaultProps to parameter defaults in function signature.",
                    code_modification_example="- Button.defaultProps = { color: 'blue' };\n+ function Button({ color = 'blue' })",
                    verification_check="npm run build succeeds without warnings",
                ),
                MigrationStep(
                    step_number=3,
                    title="Migrate Legacy ReactDOM.render to createRoot",
                    target_component="src/index.js / src/main.tsx",
                    action_type="CODE_REFACTOR",
                    instructions="Replace legacy ReactDOM.render(element, container) with createRoot(container).render(element).",
                    code_modification_example="- ReactDOM.render(<App />, el);\n+ createRoot(el).render(<App />);",
                    verification_check="Application mounts cleanly without legacy render warnings",
                ),
            ],
            "testing_requirements": [
                "Run React Testing Library suites",
                "Verify E2E Cypress or Playwright browser flows",
            ],
            "rollback_plan": [
                "Run npm install react@18.3.1 react-dom@18.3.1",
                "Revert git commit and rollback frontend bundle",
            ],
            "estimated_hours": 16.0,
            "risk_level": "MEDIUM",
        },
        "java_17_to_21": {
            "source": "Java",
            "from_ver": "17",
            "to_ver": "21",
            "title": "Java 17 to 21 LTS Platform Migration",
            "summary": "Adopts Java 21 LTS features including Virtual Threads (Project Loom), Sequenced Collections, and Record Patterns.",
            "breaking_apis": [
                "Generational ZGC enabled by default",
                "Dynamic agent loading warnings",
            ],
            "code_modifications": [
                "Adopt Executors.newVirtualThreadPerTaskExecutor() for high-concurrency tasks",
                "Use SequencedCollection (reversed(), getFirst(), getLast())",
            ],
            "steps": [
                MigrationStep(
                    step_number=1,
                    title="Update Compiler & Runtime Source Compatibility",
                    target_component="pom.xml / build.gradle",
                    action_type="CONFIG_UPDATE",
                    instructions="Update Java compiler target and release version from 17 to 21 in build manifests.",
                    code_modification_example="- <java.version>17</java.version>\n+ <java.version>21</java.version>",
                    verification_check="mvn compile succeeds with JDK 21",
                ),
                MigrationStep(
                    step_number=2,
                    title="Leverage Virtual Threads for Concurrent Workloads",
                    target_component="Concurrency configuration",
                    action_type="CODE_REFACTOR",
                    instructions="Refactor thread pools to use Virtual Threads for I/O-intensive task execution.",
                    code_modification_example="- Executors.newFixedThreadPool(200)\n+ Executors.newVirtualThreadPerTaskExecutor()",
                    verification_check="Virtual thread throughput verified",
                ),
                MigrationStep(
                    step_number=3,
                    title="Execute Full Regression & Performance Testing",
                    target_component="Test suites",
                    action_type="TEST_VALIDATION",
                    instructions="Run test suite and benchmark memory usage under Generational ZGC runtime.",
                    verification_check="All integration tests pass",
                ),
            ],
            "testing_requirements": [
                "Execute JVM garbage collection telemetry tests",
                "Validate virtual thread deadlock diagnostics",
            ],
            "rollback_plan": [
                "Revert build manifest java.version back to 17",
                "Revert deployment container JDK image to 17-slim",
            ],
            "estimated_hours": 12.0,
            "risk_level": "LOW",
        },
    }

    def plan_migration(
        self,
        technology: str,
        from_version: str,
        to_version: str,
    ) -> MigrationPlan:
        """Generates a complete migration plan."""
        tech_clean = technology.lower().replace(" ", "_")
        key = f"{tech_clean}_{from_version[:3]}_to_{to_version[:3]}"

        template = None
        for k, tmpl in self.MIGRATION_TEMPLATES.items():
            if tech_clean in k:
                template = tmpl
                break

        now = time.time()
        plan_id = f"MIG-{tech_clean.upper()}-{int(now * 1000)}"

        if from_version.strip() == to_version.strip():
            return MigrationPlan(
                plan_id=plan_id,
                source_technology=technology,
                from_version=from_version,
                to_version=to_version,
                title=f"No-Op Migration: {technology} {from_version}",
                summary=f"Source and target versions are identical ({from_version}). No migration actions required.",
                breaking_apis=[],
                code_modifications=[],
                steps=[],
                testing_requirements=[],
                rollback_plan=[],
                estimated_hours=0.0,
                risk_level="NONE",
                created_at=now,
            )

        if template:
            return MigrationPlan(
                plan_id=plan_id,
                source_technology=technology,
                from_version=from_version,
                to_version=to_version,
                title=template["title"],
                summary=template["summary"],
                breaking_apis=list(template["breaking_apis"]),
                code_modifications=list(template["code_modifications"]),
                steps=copy.deepcopy(template["steps"]),
                testing_requirements=list(template["testing_requirements"]),
                rollback_plan=list(template["rollback_plan"]),
                estimated_hours=template["estimated_hours"],
                risk_level=template["risk_level"],
                created_at=now,
            )

        # Dynamic fallback plan for unspecified migrations
        generic_steps = [
            MigrationStep(
                step_number=1,
                title=f"Review Release Notes & Changelogs for {technology}",
                target_component="manifests & documentation",
                action_type="CONFIG_UPDATE",
                instructions=f"Analyze differences between {from_version} and {to_version}.",
                verification_check="Verify deprecation notices in build output",
            ),
            MigrationStep(
                step_number=2,
                title=f"Update Manifest Version Constraints",
                target_component="build manifests",
                action_type="DEPENDENCY_UPGRADE",
                instructions=f"Bump {technology} from {from_version} to {to_version}.",
                verification_check="Build/compile passes",
            ),
            MigrationStep(
                step_number=3,
                title="Execute Comprehensive Regression Testing",
                target_component="test suite",
                action_type="TEST_VALIDATION",
                instructions="Run automated test suite to verify backward compatibility.",
                verification_check="All unit and integration tests pass",
            ),
        ]

        return MigrationPlan(
            plan_id=plan_id,
            source_technology=technology,
            from_version=from_version,
            to_version=to_version,
            title=f"Automated Migration: {technology} {from_version} → {to_version}",
            summary=f"Automated plan to migrate {technology} from version {from_version} to {to_version}.",
            breaking_apis=[f"Verify {technology} {to_version} breaking changelog."],
            code_modifications=[f"Refactor any deprecated {technology} APIs used in codebase."],
            steps=generic_steps,
            testing_requirements=["Run full test suite", "Validate performance benchmarks"],
            rollback_plan=[f"Revert manifest version to {from_version}", "Redeploy last stable build"],
            estimated_hours=8.0,
            risk_level="MEDIUM",
            created_at=now,
        )
