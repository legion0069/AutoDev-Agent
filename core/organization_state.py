"""
organization_state.py - Enterprise Organizational Memory & State (AutoDev Version 3.4)

Maintains comprehensive, searchable organizational history:
- Department history
- Meeting minutes and action items
- Architecture Decision Records (ADRs)
- Release trains and historical release artifacts
- Incident reports & 5-Whys postmortems
- Customer feedback and feature requests
- Financial reports, budgets, and burn rate telemetry
- Product roadmaps and strategic goals
- Cryptographic SHA-256 tamper-evident audit log
- 100% Python Standard Library
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("AutoDev.Org.OrganizationState")


class OrganizationState:
    """
    Central, thread-safe organizational memory bank and state coordinator.
    Provides persistence, full-text search, and tamper-evident audit log.
    """

    def __init__(self, storage_dir: Optional[str | Path] = None, auto_persist: bool = True) -> None:
        self._lock = threading.RLock()
        self.storage_dir = Path(storage_dir) if storage_dir else Path("memory/organization")
        self.auto_persist = auto_persist

        # In-memory organizational memory collections
        self.department_history: Dict[str, List[Dict[str, Any]]] = {}
        self.meeting_history: List[Dict[str, Any]] = []
        self.architecture_decisions: List[Dict[str, Any]] = []
        self.release_history: List[Dict[str, Any]] = []
        self.incidents: List[Dict[str, Any]] = []
        self.postmortems: List[Dict[str, Any]] = []
        self.customer_requests: List[Dict[str, Any]] = []
        self.financial_reports: List[Dict[str, Any]] = []
        self.roadmaps: Dict[str, Any] = {"quarters": {}, "milestones": []}
        self.audit_trail: List[Dict[str, Any]] = []

        if self.auto_persist:
            self._ensure_storage()
            self._load_state()

    def _ensure_storage(self) -> None:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create organization state directory '%s': %s", self.storage_dir, e)

    # -------------------------------------------------------------------------
    # Audit Trail & Cryptographic Verification
    # -------------------------------------------------------------------------

    def record_audit_event(self, actor: str, action: str, details: Dict[str, Any]) -> str:
        """Records an immutable audit event with SHA-256 chain verification."""
        with self._lock:
            prev_hash = self.audit_trail[-1]["hash"] if self.audit_trail else "0" * 64
            event_id = f"AUDIT-{int(time.time() * 1000)}-{len(self.audit_trail)}"
            ts = time.time()

            raw_str = f"{event_id}:{actor}:{action}:{ts}:{prev_hash}:{json.dumps(details, sort_keys=True)}"
            digest = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

            event = {
                "event_id": event_id,
                "actor": actor,
                "action": action,
                "timestamp": ts,
                "previous_hash": prev_hash,
                "hash": digest,
                "details": details,
            }
            self.audit_trail.append(event)
            if self.auto_persist:
                self._save_state()
            return event_id

    def verify_audit_trail_integrity(self) -> bool:
        """Verifies that the audit chain is unbroken and unmodified."""
        with self._lock:
            for i, evt in enumerate(self.audit_trail):
                expected_prev = self.audit_trail[i - 1]["hash"] if i > 0 else "0" * 64
                if evt.get("previous_hash") != expected_prev:
                    return False
                raw_str = f"{evt['event_id']}:{evt['actor']}:{evt['action']}:{evt['timestamp']}:{evt['previous_hash']}:{json.dumps(evt['details'], sort_keys=True)}"
                expected_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
                if evt.get("hash") != expected_hash:
                    return False
            return True

    # -------------------------------------------------------------------------
    # Organizational Collections Mutations
    # -------------------------------------------------------------------------

    def record_department_snapshot(self, department_name: str, snapshot: Dict[str, Any]) -> None:
        """Records a timestamped telemetry snapshot of a department."""
        with self._lock:
            if department_name not in self.department_history:
                self.department_history[department_name] = []
            entry = dict(snapshot)
            entry["timestamp"] = entry.get("timestamp", time.time())
            self.department_history[department_name].append(entry)
            self.record_audit_event(
                actor=department_name,
                action="RECORD_SNAPSHOT",
                details={"health": entry.get("health_score"), "performance": entry.get("performance_score")},
            )

    def record_meeting(self, meeting_minutes: Dict[str, Any]) -> str:
        """Archives meeting minutes and action items."""
        with self._lock:
            mid = meeting_minutes.get("meeting_id") or f"MEET-{int(time.time() * 1000)}"
            entry = dict(meeting_minutes)
            entry["meeting_id"] = mid
            entry["timestamp"] = entry.get("timestamp", time.time())
            self.meeting_history.append(entry)
            self.record_audit_event(
                actor=entry.get("host", "MeetingEngine"),
                action="RECORD_MEETING",
                details={"meeting_id": mid, "type": entry.get("type"), "title": entry.get("title")},
            )
            return mid

    def record_architecture_decision(self, adr: Dict[str, Any]) -> str:
        """Records a ratified Architecture Decision Record (ADR)."""
        with self._lock:
            aid = adr.get("decision_id") or f"ADR-{len(self.architecture_decisions) + 1:03d}"
            entry = dict(adr)
            entry["decision_id"] = aid
            entry["timestamp"] = entry.get("timestamp", time.time())
            self.architecture_decisions.append(entry)
            self.record_audit_event(
                actor=entry.get("author", "ChiefArchitect"),
                action="RATIFY_ADR",
                details={"decision_id": aid, "title": entry.get("title"), "status": entry.get("status", "ACCEPTED")},
            )
            return aid

    def record_release(self, release_info: Dict[str, Any]) -> str:
        """Records a formal release record."""
        with self._lock:
            rid = release_info.get("release_id") or f"REL-{release_info.get('version', 'vNext')}"
            entry = dict(release_info)
            entry["release_id"] = rid
            entry["timestamp"] = entry.get("timestamp", time.time())
            self.release_history.append(entry)
            self.record_audit_event(
                actor=entry.get("release_manager", "ReleaseManager"),
                action="PUBLISH_RELEASE",
                details={"release_id": rid, "version": entry.get("version"), "status": entry.get("status", "SUCCESS")},
            )
            return rid

    def record_incident(self, incident_data: Dict[str, Any]) -> str:
        """Records an active incident ticket."""
        with self._lock:
            inc_id = incident_data.get("incident_id") or f"INC-{int(time.time() * 1000) % 100000}"
            entry = dict(incident_data)
            entry["incident_id"] = inc_id
            entry["created_at"] = entry.get("created_at", time.time())
            entry["status"] = entry.get("status", "ACTIVE")
            self.incidents.append(entry)
            self.record_audit_event(
                actor=entry.get("reporter", "Operations"),
                action="CREATE_INCIDENT",
                details={"incident_id": inc_id, "severity": entry.get("severity", "SEV-2"), "title": entry.get("title")},
            )
            return inc_id

    def resolve_incident(self, incident_id: str, resolution: str, root_cause: str) -> bool:
        """Marks an incident as resolved."""
        with self._lock:
            for inc in self.incidents:
                if inc.get("incident_id") == incident_id:
                    inc["status"] = "RESOLVED"
                    inc["resolved_at"] = time.time()
                    inc["resolution"] = resolution
                    inc["root_cause"] = root_cause
                    self.record_audit_event(
                        actor="Operations",
                        action="RESOLVE_INCIDENT",
                        details={"incident_id": incident_id, "resolution": resolution},
                    )
                    return True
            return False

    def record_postmortem(self, postmortem: Dict[str, Any]) -> str:
        """Records a blameless 5-Whys postmortem report."""
        with self._lock:
            pm_id = postmortem.get("postmortem_id") or f"PM-{int(time.time() * 1000) % 100000}"
            entry = dict(postmortem)
            entry["postmortem_id"] = pm_id
            entry["timestamp"] = entry.get("timestamp", time.time())
            self.postmortems.append(entry)
            self.record_audit_event(
                actor=entry.get("author", "Operations"),
                action="RECORD_POSTMORTEM",
                details={"postmortem_id": pm_id, "incident_id": entry.get("incident_id")},
            )
            return pm_id

    def record_customer_request(self, request_data: Dict[str, Any]) -> str:
        """Stores customer request, ticket, or feature inquiry."""
        with self._lock:
            req_id = request_data.get("request_id") or f"REQ-{int(time.time() * 1000) % 100000}"
            entry = dict(request_data)
            entry["request_id"] = req_id
            entry["timestamp"] = entry.get("timestamp", time.time())
            entry["status"] = entry.get("status", "SUBMITTED")
            self.customer_requests.append(entry)
            self.record_audit_event(
                actor=entry.get("source", "CustomerFeedback"),
                action="INGEST_CUSTOMER_REQUEST",
                details={"request_id": req_id, "category": entry.get("category", "FEATURE_REQUEST")},
            )
            return req_id

    def record_financial_report(self, report_data: Dict[str, Any]) -> str:
        """Records financial statement or budget audit report."""
        with self._lock:
            fin_id = report_data.get("report_id") or f"FIN-{int(time.time() * 1000) % 100000}"
            entry = dict(report_data)
            entry["report_id"] = fin_id
            entry["timestamp"] = entry.get("timestamp", time.time())
            self.financial_reports.append(entry)
            self.record_audit_event(
                actor="FinanceManager",
                action="RECORD_FINANCIAL_REPORT",
                details={"report_id": fin_id, "burn_rate": entry.get("monthly_burn_rate", 0.0)},
            )
            return fin_id

    def update_roadmap(self, quarter: str, milestones: List[Dict[str, Any]]) -> None:
        """Updates product milestones for a specific quarter."""
        with self._lock:
            self.roadmaps["quarters"][quarter] = milestones
            self.roadmaps["milestones"].extend(milestones)
            self.record_audit_event(
                actor="ProductManager",
                action="UPDATE_ROADMAP",
                details={"quarter": quarter, "milestones_count": len(milestones)},
            )

    # -------------------------------------------------------------------------
    # Search & Memory Querying
    # -------------------------------------------------------------------------

    def search_memory(self, query: str, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Searches across all organizational memory collections using keyword matching.
        """
        with self._lock:
            results = []
            q = query.lower()

            target_domains = [domain.lower()] if domain else [
                "adr", "meetings", "incidents", "postmortems", "requests", "releases", "financials", "audit"
            ]

            if "adr" in target_domains or "architecture" in target_domains:
                for adr in self.architecture_decisions:
                    if q in str(adr.get("title", "")).lower() or q in str(adr.get("decision", "")).lower():
                        results.append({"domain": "architecture_decisions", "item": adr})

            if "meetings" in target_domains:
                for m in self.meeting_history:
                    if q in str(m.get("title", "")).lower() or q in str(m.get("decisions", "")).lower():
                        results.append({"domain": "meeting_history", "item": m})

            if "incidents" in target_domains:
                for inc in self.incidents:
                    if q in str(inc.get("title", "")).lower() or q in str(inc.get("root_cause", "")).lower():
                        results.append({"domain": "incidents", "item": inc})

            if "postmortems" in target_domains:
                for pm in self.postmortems:
                    if q in str(pm.get("root_cause", "")).lower() or q in str(pm.get("lessons_learned", "")).lower():
                        results.append({"domain": "postmortems", "item": pm})

            if "requests" in target_domains:
                for req in self.customer_requests:
                    if q in str(req.get("description", "")).lower() or q in str(req.get("title", "")).lower():
                        results.append({"domain": "customer_requests", "item": req})

            if "releases" in target_domains:
                for rel in self.release_history:
                    if q in str(rel.get("version", "")).lower() or q in str(rel.get("notes", "")).lower():
                        results.append({"domain": "release_history", "item": rel})

            if "audit" in target_domains:
                for aud in self.audit_trail:
                    if q in str(aud.get("action", "")).lower() or q in str(aud.get("actor", "")).lower():
                        results.append({"domain": "audit_trail", "item": aud})

            return results

    # -------------------------------------------------------------------------
    # JSON Persistence
    # -------------------------------------------------------------------------

    def _save_state(self) -> None:
        try:
            self._ensure_storage()
            data = {
                "department_history": self.department_history,
                "meeting_history": self.meeting_history,
                "architecture_decisions": self.architecture_decisions,
                "release_history": self.release_history,
                "incidents": self.incidents,
                "postmortems": self.postmortems,
                "customer_requests": self.customer_requests,
                "financial_reports": self.financial_reports,
                "roadmaps": self.roadmaps,
                "audit_trail": self.audit_trail,
            }
            out_file = self.storage_dir / "organization_state.json"
            out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save organization state: %s", e)

    def _load_state(self) -> None:
        state_file = self.storage_dir / "organization_state.json"
        if not state_file.is_file():
            return
        try:
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            self.department_history = raw.get("department_history", {})
            self.meeting_history = raw.get("meeting_history", [])
            self.architecture_decisions = raw.get("architecture_decisions", [])
            self.release_history = raw.get("release_history", [])
            self.incidents = raw.get("incidents", [])
            self.postmortems = raw.get("postmortems", [])
            self.customer_requests = raw.get("customer_requests", [])
            self.financial_reports = raw.get("financial_reports", [])
            self.roadmaps = raw.get("roadmaps", {"quarters": {}, "milestones": []})
            self.audit_trail = raw.get("audit_trail", [])
            logger.info("Loaded organization state with %d audit events.", len(self.audit_trail))
        except Exception as e:
            logger.warning("Could not load organization state: %s", e)

    def export_full_memory_dump(self) -> Dict[str, Any]:
        """Returns deep snapshot of all organizational memory collections."""
        with self._lock:
            return {
                "total_meetings": len(self.meeting_history),
                "total_adrs": len(self.architecture_decisions),
                "total_releases": len(self.release_history),
                "total_incidents": len(self.incidents),
                "total_customer_requests": len(self.customer_requests),
                "total_financial_reports": len(self.financial_reports),
                "audit_trail_events": len(self.audit_trail),
                "audit_integrity_verified": self.verify_audit_trail_integrity(),
            }
