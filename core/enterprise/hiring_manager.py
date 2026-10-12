"""
hiring_manager.py - HR, Talent Acquisition & Performance Management for AutoDev (v3.0)

Handles enterprise headcount planning, job requisitions, candidate interview scoring,
offer letters, employee performance reviews, and promotion tracking.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.enterprise.enterprise_models import (
    CandidateProfile,
    DepartmentType,
    EmployeeProfile,
    JobPosting,
    TeamType,
)

logger = logging.getLogger("AutoDev.Enterprise.Hiring")


class HiringManager:
    """
    Human Resources & Talent Management Engine.
    Executes hiring pipelines, candidate evaluations, employee records, and promotion reviews.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._job_postings: Dict[str, JobPosting] = {}
        self._candidates: Dict[str, CandidateProfile] = {}
        self._employees: Dict[str, EmployeeProfile] = {}

        self._init_default_employees()

    def _init_default_employees(self) -> None:
        """Seeds initial core technical staff."""
        initial_staff = [
            ("EMP-001", "Liam O'Connor", "Staff Backend Engineer", DepartmentType.ENGINEERING, TeamType.BACKEND, 180000.0),
            ("EMP-002", "Aria Stark", "Senior Frontend Engineer", DepartmentType.ENGINEERING, TeamType.FRONTEND, 160000.0),
            ("EMP-003", "Dr. Alan Turing", "Principal AI Research Engineer", DepartmentType.ENGINEERING, TeamType.AI_ML, 220000.0),
            ("EMP-004", "Agent Smith", "Senior Security Operations Engineer", DepartmentType.SECURITY, TeamType.SECURITY_OPS, 175000.0),
        ]

        for eid, name, title, dept, team, salary in initial_staff:
            self._employees[eid] = EmployeeProfile(
                employee_id=eid,
                name=name,
                role_title=title,
                department=dept,
                team=team,
                manager_id="emp_vpeng",
                skills=["Python", "Enterprise Architecture", "Testing"],
                performance_rating=4.8,
                salary_usd=salary,
            )

    def create_job_posting(
        self,
        title: str,
        department: DepartmentType,
        team: TeamType,
        required_skills: List[str],
        salary_range_usd: Optional[Tuple[float, float]] = None,
        salary_range: Optional[Tuple[float, float]] = None,
        headcount: int = 1,
    ) -> JobPosting:
        """Publishes an open job requisition."""
        with self._lock:
            j_id = f"JOB-{int(time.time()*1000)}-{len(self._job_postings)+1:03d}"
            effective_range = salary_range_usd or salary_range or (130000.0, 180000.0)
            posting = JobPosting(
                job_id=j_id,
                title=title,
                department=department,
                team=team,
                required_skills=list(required_skills),
                salary_range_usd=effective_range,
                headcount=headcount,
                status="OPEN",
            )
            self._job_postings[j_id] = posting
            logger.info("Created Job Posting %s: '%s' in %s (%d openings)", j_id, title, department.value, headcount)
            return copy.deepcopy(posting)

    def apply_candidate(
        self,
        job_id: str,
        name: str,
        skills: List[str],
        experience_years: float,
    ) -> CandidateProfile:
        """Submits a candidate application into the hiring funnel."""
        with self._lock:
            c_id = f"CAND-{int(time.time()*1000)}-{len(self._candidates)+1:03d}"
            posting = self._job_postings.get(job_id)
            
            # Compute match score
            req_skills = set(posting.required_skills) if posting else set()
            match_count = len(set(skills).intersection(req_skills))
            score = min(100.0, (match_count / max(1, len(req_skills))) * 80.0 + min(20.0, experience_years * 2.5))

            cand = CandidateProfile(
                candidate_id=c_id,
                job_id=job_id,
                name=name,
                skills=list(skills),
                experience_years=experience_years,
                interview_score=round(score, 2),
                cultural_fit_score=90.0,
                status="APPLIED",
            )
            self._candidates[c_id] = cand
            logger.info("Candidate %s ('%s') applied for %s with score %.1f", c_id, name, job_id, score)
            return copy.deepcopy(cand)

    def conduct_interview(
        self,
        candidate_id: str,
        interview_score: float = 85.0,
        cultural_fit_score: float = 90.0,
    ) -> CandidateProfile:
        """Conducts candidate interview and updates scoring."""
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                raise KeyError(f"Candidate {candidate_id} not found")
            cand.interview_score = interview_score
            cand.cultural_fit_score = cultural_fit_score
            cand.status = "INTERVIEWED"
            logger.info("Interview conducted for %s (Score: %.1f)", candidate_id, interview_score)
            return copy.deepcopy(cand)

    def extend_offer_and_hire(
        self,
        candidate_id: str,
        salary_usd: Optional[float] = None,
    ) -> EmployeeProfile:
        """
        Extends offer and onboards hired candidate into employee registry.
        """
        with self._lock:
            cand = self._candidates.get(candidate_id)
            if not cand:
                raise KeyError(f"Candidate {candidate_id} not found")

            posting = self._job_postings.get(cand.job_id)
            dept = posting.department if posting else DepartmentType.ENGINEERING
            team = posting.team if posting else TeamType.BACKEND
            salary = salary_usd or (posting.salary_range_usd[0] if posting else 140000.0)

            emp_id = f"EMP-{int(time.time()*1000)}-{len(self._employees)+1:03d}"
            emp = EmployeeProfile(
                employee_id=emp_id,
                name=cand.name,
                role_title=posting.title if posting else "Software Engineer",
                department=dept,
                team=team,
                manager_id="emp_vpeng",
                skills=cand.skills,
                salary_usd=salary,
            )

            cand.status = "HIRED"
            if posting:
                posting.filled += 1
                if posting.filled >= posting.headcount:
                    posting.status = "FILLED"

            self._employees[emp_id] = emp
            logger.info("Hired candidate %s as %s (%s) with salary $%.2f", candidate_id, emp_id, emp.name, salary)
            return copy.deepcopy(emp)

    hire_candidate = extend_offer_and_hire

    def conduct_performance_review(
        self,
        employee_id: str,
        performance_rating: Optional[float] = None,
        rating: Optional[float] = None,
        feedback: str = "",
    ) -> EmployeeProfile:
        """Records performance review rating."""
        eff_rating = performance_rating if performance_rating is not None else (rating if rating is not None else 4.0)
        with self._lock:
            emp = self._employees.get(employee_id)
            if not emp:
                raise KeyError(f"Employee {employee_id} not found")
            emp.performance_rating = max(1.0, min(5.0, round(eff_rating, 2)))
            logger.info("Performance review for %s (%s): Rating %.2f/5.0", employee_id, emp.name, emp.performance_rating)
            return copy.deepcopy(emp)

    def promote_employee(
        self,
        employee_id: str,
        new_title: str,
        new_salary_usd: Optional[float] = None,
        salary_increase_usd: float = 20000.0,
    ) -> EmployeeProfile:
        """Promotes an employee with a title change and compensation adjustment."""
        with self._lock:
            emp = self._employees.get(employee_id)
            if not emp:
                raise KeyError(f"Employee {employee_id} not found")

            old_title = emp.role_title
            emp.role_title = new_title
            if new_salary_usd is not None:
                emp.salary_usd = new_salary_usd
            else:
                emp.salary_usd += salary_increase_usd

            emp.promotion_history.append({
                "from_title": old_title,
                "to_title": new_title,
                "salary_usd": emp.salary_usd,
                "promoted_at": time.time(),
            })

            logger.info("Promoted %s (%s) to %s (New Salary: $%.2f)", employee_id, emp.name, new_title, emp.salary_usd)
            return copy.deepcopy(emp)

    def get_job_posting(self, job_id: str) -> Optional[JobPosting]:
        with self._lock:
            j = self._job_postings.get(job_id)
            return copy.deepcopy(j) if j else None

    def get_candidate(self, candidate_id: str) -> Optional[CandidateProfile]:
        with self._lock:
            c = self._candidates.get(candidate_id)
            return copy.deepcopy(c) if c else None

    def get_employee(self, employee_id: str) -> Optional[EmployeeProfile]:
        with self._lock:
            e = self._employees.get(employee_id)
            return copy.deepcopy(e) if e else None

    def list_employees(self) -> List[EmployeeProfile]:
        with self._lock:
            return [copy.deepcopy(e) for e in self._employees.values()]

    def list_job_postings(self) -> List[JobPosting]:
        with self._lock:
            return [copy.deepcopy(j) for j in self._job_postings.values()]
