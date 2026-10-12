"""
test_hiring_manager.py - Unit and Integration Tests for HR & Talent Engine (v3.0)
"""

import pytest
from core.enterprise.enterprise_models import DepartmentType, TeamType
from core.enterprise.hiring_manager import HiringManager


@pytest.fixture
def hm():
    return HiringManager()


class TestHiringManager:
    def test_default_employees_initialized(self, hm: HiringManager):
        employees = hm.list_employees()
        assert len(employees) >= 4
        names = {e.name for e in employees}
        assert "Liam O'Connor" in names
        assert "Aria Stark" in names

    def test_create_job_posting(self, hm: HiringManager):
        posting = hm.create_job_posting(
            title="Senior Distributed Systems Engineer",
            department=DepartmentType.ENGINEERING,
            team=TeamType.INFRASTRUCTURE,
            required_skills=["Python", "Raft", "Distributed Consensus"],
            salary_range_usd=(160000.0, 210000.0),
            headcount=2,
        )
        assert posting.job_id.startswith("JOB-")
        assert posting.status == "OPEN"
        assert posting.headcount == 2

    def test_full_hiring_pipeline(self, hm: HiringManager):
        posting = hm.create_job_posting(
            title="Senior AI Engineer",
            department=DepartmentType.ENGINEERING,
            team=TeamType.AI_ML,
            required_skills=["Python", "LLMs", "Embeddings"],
            salary_range_usd=(170000.0, 220000.0),
        )

        # 1. Apply
        cand = hm.apply_candidate(
            job_id=posting.job_id,
            name="Grace Hopper",
            skills=["Python", "LLMs", "Embeddings", "Compilers"],
            experience_years=10.0,
        )
        assert cand.status == "APPLIED"

        # 2. Interview
        interviewed = hm.conduct_interview(cand.candidate_id, interview_score=96.0, cultural_fit_score=94.0)
        assert interviewed.status == "INTERVIEWED"
        assert interviewed.interview_score == 96.0

        # 3. Extend Offer and Hire
        emp = hm.extend_offer_and_hire(cand.candidate_id, salary_usd=195000.0)
        assert emp.employee_id.startswith("EMP-")
        assert emp.name == "Grace Hopper"
        assert emp.salary_usd == 195000.0

        # Verify job posting headcount updated
        updated_job = hm.get_job_posting(posting.job_id)
        assert updated_job.filled == 1
        assert updated_job.status == "FILLED"

    def test_conduct_performance_review_and_promotion(self, hm: HiringManager):
        employees = hm.list_employees()
        emp = employees[0]

        reviewed = hm.conduct_performance_review(emp.employee_id, performance_rating=4.9)
        assert reviewed.performance_rating == 4.9

        # Promotion
        promoted = hm.promote_employee(
            emp.employee_id,
            new_title="Principal Engineer",
            new_salary_usd=emp.salary_usd + 30000.0,
        )
        assert promoted.role_title == "Principal Engineer"
        assert len(promoted.promotion_history) >= 1
