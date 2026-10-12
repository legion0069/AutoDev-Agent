"""
release_intelligence.py - Release Intelligence & Semantic Version Analysis (v3.2)

Tracks external releases:
- Generates release summaries
- Assesses SemVer impact (Major breaking vs Minor feature vs Patch security)
- Identifies breaking change summaries
- Recommends adoption windows (IMMEDIATE, NEXT_SPRINT, ASSESS_QUARTERLY, HOLD)
- Calculates risk scores based on breaking change density
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from core.ecosystem.ecosystem_models import (
    PackageVersion,
    ReleaseAnalysis,
    ReleaseImpact,
)

logger = logging.getLogger("AutoDev.ReleaseIntelligence")


class ReleaseIntelligenceEngine:
    """
    Analyzes software releases and changesets to assess operational risk,
    breaking surface area, and appropriate corporate adoption schedules.
    """

    def analyze_release(
        self,
        package_name: str,
        current_version: str,
        new_version: str,
        release_notes: str = "",
        changelog_entries: Optional[List[str]] = None,
    ) -> ReleaseAnalysis:
        """Evaluates release delta between two semantic versions."""
        cur_v = PackageVersion(current_version)
        new_v = PackageVersion(new_version)

        # 1. Determine SemVer Impact Level
        if new_v.major > cur_v.major:
            impact = ReleaseImpact.MAJOR_BREAKING
            risk_score = 75.0
            adoption_window = "ASSESS_QUARTERLY"
        elif new_v.minor > cur_v.minor:
            impact = ReleaseImpact.MINOR_FEATURE
            risk_score = 30.0
            adoption_window = "NEXT_SPRINT"
        else:
            impact = ReleaseImpact.PATCH_SECURITY
            risk_score = 10.0
            adoption_window = "IMMEDIATE"

        # 2. Extract breaking changes and security fixes
        entries = changelog_entries or (release_notes.splitlines() if release_notes else [])
        breaking: List[str] = []
        security: List[str] = []
        features: List[str] = []

        for e in entries:
            clean = e.strip().lstrip("-*# ")
            if not clean:
                continue
            lower = clean.lower()
            if any(k in lower for k in ("breaking", "deprecated", "removed", "backward incompatible")):
                breaking.append(clean)
            elif any(k in lower for k in ("security", "cve", "vulnerability", "patch", "exploit")):
                security.append(clean)
            elif any(k in lower for k in ("feat", "feature", "add", "new", "support")):
                features.append(clean)

        # If breaking changes detected in minor release, elevate risk
        if breaking and impact != ReleaseImpact.MAJOR_BREAKING:
            risk_score += 25.0
            adoption_window = "NEXT_SPRINT"

        # If security fixes present in patch release, urge immediate adoption
        if security:
            adoption_window = "IMMEDIATE"
            risk_score = max(5.0, risk_score - 10.0)  # Lower operational hesitation due to security urgency

        summary = (
            f"Release {new_version} for {package_name} classified as {impact.value}. "
            f"Contains {len(breaking)} breaking changes, {len(security)} security fixes, and {len(features)} new features."
        )

        return ReleaseAnalysis(
            package_or_tool=package_name,
            version=new_version,
            release_date="2026-10",
            impact=impact,
            summary=summary,
            breaking_changes=breaking,
            security_fixes=security,
            new_features=features,
            recommended_adoption_window=adoption_window,
            risk_score=min(100.0, risk_score),
        )

    def generate_batch_release_report(
        self,
        updates: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Analyzes a batch of package updates and compiles a release intelligence report."""
        analyses: List[ReleaseAnalysis] = []
        for item in updates:
            analyses.append(self.analyze_release(
                package_name=item.get("package", "unknown"),
                current_version=item.get("current_version", "1.0.0"),
                new_version=item.get("new_version", "1.0.1"),
                release_notes=item.get("release_notes", ""),
            ))

        immediate = [a.to_dict() for a in analyses if a.recommended_adoption_window == "IMMEDIATE"]
        next_sprint = [a.to_dict() for a in analyses if a.recommended_adoption_window == "NEXT_SPRINT"]
        assess = [a.to_dict() for a in analyses if a.recommended_adoption_window == "ASSESS_QUARTERLY"]

        return {
            "total_releases_analyzed": len(analyses),
            "immediate_adoption_count": len(immediate),
            "next_sprint_adoption_count": len(next_sprint),
            "assess_quarterly_count": len(assess),
            "immediate_releases": immediate,
            "next_sprint_releases": next_sprint,
            "assess_releases": assess,
        }
