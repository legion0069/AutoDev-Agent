"""
mock_provider.py - Deterministic Mock LLM Provider for AutoDev Testing

Provides predictable, offline LLM responses for unit testing, integration workflows,
and offline local development without requiring external API keys or network access.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Union

from core.llm import BaseLLM


class MockProvider(BaseLLM):
    """
    Mock LLM provider implementation for local testing, dry runs, and unit testing
    without external API keys or network requests.
    """

    def __init__(
        self,
        model_name: str = "mock-model-v1",
        default_response: Optional[str] = None,
        responses: Optional[List[str]] = None,
        response_fn: Optional[Callable[[str, Any], str]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the MockProvider.

        Args:
            model_name: Identifier for the mock model (default: 'mock-model-v1').
            default_response: Static string returned when no specific response is provided.
            responses: Optional queue/list of responses returned sequentially per call.
            response_fn: Optional callable (prompt, **kwargs) -> str for dynamic mock generation.
            **kwargs: Extra parameters passed to BaseLLM.
        """
        super().__init__(model_name=model_name, **kwargs)
        self.default_response = default_response or (
            "# [MockLLM Response]\n"
            "# Autonomous code generation simulated successfully.\n"
            "def hello_autodev():\n"
            "    return 'AutoDev agent execution completed successfully.'"
        )
        self.responses: List[str] = list(responses) if responses is not None else []
        self.response_fn = response_fn
        self.last_prompt: Optional[str] = None
        self.prompt_history: List[str] = []
        self.call_count: int = 0

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a deterministic mock response.

        Args:
            prompt: The input prompt string.
            **kwargs: Optional generation overrides (e.g. response="...").

        Returns:
            The mock response string.
        """
        self.call_count += 1
        self.last_prompt = prompt
        self.prompt_history.append(prompt)

        # 1. Check for explicit keyword argument override
        if "response" in kwargs and kwargs["response"] is not None:
            return str(kwargs["response"])

        # 2. Check for dynamic response function
        if self.response_fn is not None:
            return str(self.response_fn(prompt, **kwargs))

        # 3. Check for sequential response queue
        if self.responses:
            return str(self.responses.pop(0))

        # 4. Fallback to default response
        return str(self.default_response)

    def reset(self) -> None:
        """Resets call counts, prompt history, and last prompt."""
        self.last_prompt = None
        self.prompt_history.clear()
        self.call_count = 0
