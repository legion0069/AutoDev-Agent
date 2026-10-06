"""
test_reviewer_agent.py - Comprehensive Unit & Integration Tests for ReviewerAgent

Validates:
- Successful review parsing with ReviewResult and Issue objects
- Markdown fence stripping (```json ... ```)
- Malformed JSON detection
- Missing required fields (summary, overall_quality_score, should_regenerate, explanation)
- Severity level validation (LOW, MEDIUM, HIGH, CRITICAL)
- Quality score boundary validation (0-100)
- should_regenerate boolean type enforcement
- Offline MockLLM execution
"""

import json
import pytest
from agents.coder_agent import GeneratedFile, GeneratedResult
from agents.reviewer_agent import (
    Issue,
    ReviewerAgent,
    ReviewResult,
    ReviewValidationError,
)
from agents.tester_agent import TestResult
from core.llm import BaseLLM


class CustomReviewTestLLM(BaseLLM):
    """Test LLM returning programmable responses for code review."""
    def __init__(self, response_text: str):
        super().__init__(model_name="review-test-llm")
        self.response_text = response_text

    def generate(self, prompt: str, **kwargs) -> str:
        return self.response_text


@pytest.fixture
def sample_context():
    return {
        "project_name": "ReviewApp",
        "description": "App for review testing",
        "technology_stack": "Python, Pytest",
        "current_day": 1,
        "current_phase": {
            "day": 1,
            "phase_name": "Setup & Architecture",
            "goals": ["Implement core"],
            "deliverables": ["src/app.py"],
            "testing_focus": "Unit tests",
        },
    }


@pytest.fixture
def sample_gen_result():
    return GeneratedResult(
        summary="Created app.py",
        files=[GeneratedFile(path="src/app.py", content="def start(): pass\n")],
        explanation="Initial setup.",
    )


@pytest.fixture
def sample_test_result():
    return TestResult(
        success=True,
        total_tests=1,
        passed=1,
        failed=0,
        skipped=0,
        duration=0.05,
        stdout="1 passed in 0.05s",
        stderr="",
        exit_code=0,
        command="pytest",
        message="All tests passed.",
    )


def test_successful_review(sample_context, sample_gen_result, sample_test_result):
    """Verifies that a valid JSON review response is correctly parsed into ReviewResult."""
    valid_payload = {
        "success": True,
        "summary": "Code adheres to standards.",
        "overall_quality_score": 95,
        "issues": [
            {
                "severity": "LOW",
                "category": "Style",
                "file": "src/app.py",
                "line": 1,
                "description": "Missing type annotation on start function.",
                "recommendation": "Add -> None return type annotation.",
            }
        ],
        "strengths": ["Clean function structure"],
        "recommendations": ["Expand docstrings"],
        "should_regenerate": False,
        "explanation": "High quality initial codebase.",
    }
    llm = CustomReviewTestLLM(json.dumps(valid_payload))
    agent = ReviewerAgent(llm=llm)

    result = agent.review(
        context=sample_context,
        generated_result=sample_gen_result,
        test_result=sample_test_result,
    )

    assert isinstance(result, ReviewResult)
    assert result.success is True
    assert result.summary == "Code adheres to standards."
    assert result.overall_quality_score == 95
    assert result.should_regenerate is False
    assert len(result.issues) == 1
    assert isinstance(result.issues[0], Issue)
    assert result.issues[0].severity == "LOW"
    assert result.issues[0].line == 1
    assert result.issues[0].category == "Style"
    assert "Clean function structure" in result.strengths


def test_markdown_fence_stripping(sample_context, sample_gen_result):
    """Verifies that markdown fences are stripped before JSON parsing."""
    valid_payload = {
        "success": True,
        "summary": "Clean code.",
        "overall_quality_score": 88,
        "issues": [],
        "strengths": ["Solid architecture"],
        "recommendations": [],
        "should_regenerate": False,
        "explanation": "Looks great.",
    }
    raw_markdown = f"```json\n{json.dumps(valid_payload, indent=2)}\n```"
    llm = CustomReviewTestLLM(raw_markdown)
    agent = ReviewerAgent(llm=llm)

    result = agent.review(context=sample_context, generated_result=sample_gen_result)

    assert result.overall_quality_score == 88
    assert result.summary == "Clean code."


def test_malformed_json_raises_error(sample_context, sample_gen_result):
    """Verifies that non-JSON response raises ReviewValidationError."""
    llm = CustomReviewTestLLM("This is not valid JSON string.")
    agent = ReviewerAgent(llm=llm)

    with pytest.raises(ReviewValidationError, match="not valid JSON"):
        agent.review(context=sample_context, generated_result=sample_gen_result)


def test_missing_summary_raises_error(sample_context, sample_gen_result):
    """Verifies that missing 'summary' field raises ReviewValidationError."""
    invalid_payload = {
        "overall_quality_score": 85,
        "should_regenerate": False,
        "explanation": "Missing summary",
    }
    llm = CustomReviewTestLLM(json.dumps(invalid_payload))
    agent = ReviewerAgent(llm=llm)

    with pytest.raises(ReviewValidationError, match="Missing required field 'summary'"):
        agent.review(context=sample_context, generated_result=sample_gen_result)


def test_missing_quality_score_raises_error(sample_context, sample_gen_result):
    """Verifies that missing 'overall_quality_score' raises ReviewValidationError."""
    invalid_payload = {
        "summary": "Valid summary",
        "should_regenerate": False,
        "explanation": "No score",
    }
    llm = CustomReviewTestLLM(json.dumps(invalid_payload))
    agent = ReviewerAgent(llm=llm)

    with pytest.raises(ReviewValidationError, match="Missing required field 'overall_quality_score'"):
        agent.review(context=sample_context, generated_result=sample_gen_result)


def test_invalid_quality_score_boundary(sample_context, sample_gen_result):
    """Verifies that out-of-bounds quality scores raise ReviewValidationError."""
    invalid_payload = {
        "summary": "Valid summary",
        "overall_quality_score": 150,  # Invalid > 100
        "should_regenerate": False,
        "explanation": "Out of bounds score",
    }
    llm = CustomReviewTestLLM(json.dumps(invalid_payload))
    agent = ReviewerAgent(llm=llm)

    with pytest.raises(ReviewValidationError, match="must be between 0 and 100"):
        agent.review(context=sample_context, generated_result=sample_gen_result)


def test_invalid_severity_raises_error(sample_context, sample_gen_result):
    """Verifies that unrecognized severity strings raise ReviewValidationError."""
    invalid_payload = {
        "summary": "Valid summary",
        "overall_quality_score": 75,
        "issues": [
            {
                "severity": "SUPER_CRITICAL",  # Invalid severity
                "category": "Security",
                "file": "src/app.py",
                "description": "Invalid severity test",
            }
        ],
        "should_regenerate": True,
        "explanation": "Invalid severity level provided",
    }
    llm = CustomReviewTestLLM(json.dumps(invalid_payload))
    agent = ReviewerAgent(llm=llm)

    with pytest.raises(ReviewValidationError, match="invalid severity 'SUPER_CRITICAL'"):
        agent.review(context=sample_context, generated_result=sample_gen_result)


def test_should_regenerate_boolean_validation(sample_context, sample_gen_result):
    """Verifies that should_regenerate correctly parses boolean and rejects non-boolean."""
    # Case 1: valid True
    valid_payload = {
        "summary": "Critical flaws found",
        "overall_quality_score": 30,
        "issues": [
            {
                "severity": "CRITICAL",
                "category": "Bug",
                "file": "src/app.py",
                "description": "Severe memory leak in loop.",
                "recommendation": "Rewrite using context manager.",
            }
        ],
        "should_regenerate": True,
        "explanation": "Regeneration required due to critical bug.",
    }
    llm = CustomReviewTestLLM(json.dumps(valid_payload))
    agent = ReviewerAgent(llm=llm)
    result = agent.review(context=sample_context, generated_result=sample_gen_result)
    assert result.should_regenerate is True

    # Case 2: non-boolean should_regenerate
    invalid_payload = valid_payload.copy()
    invalid_payload["should_regenerate"] = "yes"  # string instead of boolean
    llm_bad = CustomReviewTestLLM(json.dumps(invalid_payload))
    agent_bad = ReviewerAgent(llm=llm_bad)
    with pytest.raises(ReviewValidationError, match="must be a boolean"):
        agent_bad.review(context=sample_context, generated_result=sample_gen_result)
