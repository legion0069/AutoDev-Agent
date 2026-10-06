"""
test_coder_agent.py - Integration and Unit Tests for CoderAgent

Validates CoderAgent response parsing, schema verification, error handling,
and provider-independent BaseLLM execution.
"""

import json
import pytest
from agents.coder_agent import CoderAgent, CoderValidationError, GeneratedResult
from agents.task_planner_agent import Task
from core.llm import BaseLLM, MockLLM
from core.prompt_builder import PromptBuilder


class CustomTestLLM(BaseLLM):
    """Test LLM returning a programmable response."""
    def __init__(self, response_text: str):
        super().__init__(model_name="test-llm")
        self.response_text = response_text

    def generate(self, prompt: str, **kwargs) -> str:
        return self.response_text


@pytest.fixture
def sample_context():
    return {
        "project_name": "TestApp",
        "description": "A test application",
        "technology_stack": "Python, Pytest",
        "current_day": 1,
        "current_phase": {
            "day": 1,
            "phase_name": "Project Setup",
            "goals": ["Scaffold project"],
            "deliverables": ["src/main.py"],
            "testing_focus": "Unit tests",
        },
        "completed_phases": [],
        "directory_tree": [],
        "project_files": {},
    }


@pytest.fixture
def sample_task():
    return Task(
        id="TASK-01",
        title="Initialize setup",
        description="Create main.py entry point.",
        priority=1,
        dependencies=[],
        estimated_files=["src/main.py"],
    )


def test_coder_agent_successful_execution(sample_context, sample_task):
    """Tests that CoderAgent parses a standard valid JSON response correctly."""
    valid_payload = {
        "summary": "Created main.py and config.py",
        "files": [
            {"path": "src/main.py", "content": "print('hello')\n"},
            {"path": "src/config.py", "content": "DEBUG = True\n"},
        ],
        "explanation": "Implemented basic application modules.",
    }
    llm = CustomTestLLM(json.dumps(valid_payload))
    agent = CoderAgent(llm=llm)

    result = agent.execute(context=sample_context, task=sample_task)

    assert isinstance(result, GeneratedResult)
    assert result.summary == "Created main.py and config.py"
    assert len(result.files) == 2
    assert result.files[0].path == "src/main.py"
    assert result.files[0].content == "print('hello')\n"
    assert result.files[1].path == "src/config.py"
    assert result.explanation == "Implemented basic application modules."


def test_coder_agent_markdown_fence_stripping(sample_context, sample_task):
    """Tests that CoderAgent properly strips ```json markdown fences."""
    valid_payload = {
        "summary": "Created module",
        "files": [{"path": "src/app.py", "content": "pass\n"}],
        "explanation": "Clean module creation.",
    }
    raw_markdown = f"```json\n{json.dumps(valid_payload, indent=2)}\n```"
    llm = CustomTestLLM(raw_markdown)
    agent = CoderAgent(llm=llm)

    result = agent.execute(context=sample_context, task=sample_task)

    assert result.summary == "Created module"
    assert len(result.files) == 1
    assert result.files[0].path == "src/app.py"


def test_coder_agent_missing_summary_raises_error(sample_context, sample_task):
    """Tests that missing 'summary' field raises CoderValidationError."""
    invalid_payload = {
        "files": [{"path": "src/app.py", "content": "pass\n"}],
        "explanation": "No summary provided",
    }
    llm = CustomTestLLM(json.dumps(invalid_payload))
    agent = CoderAgent(llm=llm)

    with pytest.raises(CoderValidationError, match="Missing required field 'summary'"):
        agent.execute(context=sample_context, task=sample_task)


def test_coder_agent_missing_explanation_raises_error(sample_context, sample_task):
    """Tests that missing 'explanation' field raises CoderValidationError."""
    invalid_payload = {
        "summary": "Summary text",
        "files": [{"path": "src/app.py", "content": "pass\n"}],
    }
    llm = CustomTestLLM(json.dumps(invalid_payload))
    agent = CoderAgent(llm=llm)

    with pytest.raises(CoderValidationError, match="Missing required field 'explanation'"):
        agent.execute(context=sample_context, task=sample_task)


def test_coder_agent_missing_file_content_raises_error(sample_context, sample_task):
    """Tests that a file missing the 'content' field raises CoderValidationError."""
    invalid_payload = {
        "summary": "Summary text",
        "files": [{"path": "src/app.py"}],
        "explanation": "Missing file content",
    }
    llm = CustomTestLLM(json.dumps(invalid_payload))
    agent = CoderAgent(llm=llm)

    with pytest.raises(CoderValidationError, match="missing required 'content' field"):
        agent.execute(context=sample_context, task=sample_task)


def test_coder_agent_invalid_json_syntax_raises_error(sample_context, sample_task):
    """Tests that non-JSON syntax raises CoderValidationError."""
    llm = CustomTestLLM("This is not JSON text at all.")
    agent = CoderAgent(llm=llm)

    with pytest.raises(CoderValidationError, match="LLM response is not valid JSON"):
        agent.execute(context=sample_context, task=sample_task)
