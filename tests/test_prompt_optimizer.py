"""
test_prompt_optimizer.py - AutoDev Version 3.1
Unit and integration tests for PromptOptimizationEngine, token estimation,
line deduplication, pattern injection, and token efficiency score calculation.
"""

from pathlib import Path
import pytest
from core.learning.learning_models import EngineeringPattern, PatternCategory
from core.learning.prompt_optimizer import PromptOptimizationEngine


@pytest.fixture
def prompt_optimizer(tmp_path: Path):
    storage_dir = tmp_path / "prompts"
    return PromptOptimizationEngine(storage_dir=str(storage_dir), auto_persist=True)


def test_estimate_tokens(prompt_optimizer: PromptOptimizationEngine):
    text = "Hello world! This is a test prompt with several words."
    tokens = prompt_optimizer.estimate_tokens(text)
    assert tokens > 0
    assert tokens == max(1, len(text) // 4)


def test_compress_and_deduplicate_lines(prompt_optimizer: PromptOptimizationEngine):
    bloated_prompt = (
        "Line 1: Implement feature.\n"
        "Line 1: Implement feature.\n"
        "Line 2: Ensure type safety.\n\n\n"
        "Line 3: Write tests.\n"
        "Line 2: Ensure type safety.\n"
    )
    compressed = prompt_optimizer.compress_prompt(bloated_prompt)
    lines = [line.strip() for line in compressed.split("\n") if line.strip()]
    assert len(lines) == 3
    assert "Line 1: Implement feature." in lines
    assert "Line 2: Ensure type safety." in lines
    assert "Line 3: Write tests." in lines


def test_optimize_prompt_with_rules_and_patterns(prompt_optimizer: PromptOptimizationEngine):
    pattern = EngineeringPattern(
        name="Use Context Managers",
        category=PatternCategory.BUG_FIX,
        description="Always use context managers for file and socket I/O.",
    )

    raw_prompt = (
        "Please generate a Python script that parses CSV files.\n"
        "Please generate a Python script that parses CSV files.\n"
        "Make sure to follow best practices.\n"
    )

    rec = prompt_optimizer.optimize_prompt(
        raw_prompt=raw_prompt,
        task_type="coding",
        discovered_patterns=[pattern],
        target_tokens=500,
    )

    assert rec.task_type == "coding"
    assert rec.original_tokens >= rec.optimized_tokens
    assert rec.token_compression_ratio >= 0.0
    assert rec.token_efficiency_score >= 80.0
    assert "Use Context Managers" in rec.optimized_prompt


def test_register_and_get_template(prompt_optimizer: PromptOptimizationEngine):
    rec = prompt_optimizer.optimize_prompt(
        raw_prompt="Standard test generation prompt for unit tests.",
        task_type="test_generation",
    )

    tpl = prompt_optimizer.get_template(rec.template_id)
    assert tpl is not None
    assert tpl.template_id == rec.template_id
    assert tpl.task_type == "test_generation"


def test_default_templates_available(prompt_optimizer: PromptOptimizationEngine):
    templates = prompt_optimizer.get_all_templates()
    assert len(templates) >= 3
    task_types = {t.task_type for t in templates}
    assert "CODER_SYNTHESIS" in task_types
    assert "PLANNER_DECOMPOSITION" in task_types
    assert "REVIEWER_AUDIT" in task_types
