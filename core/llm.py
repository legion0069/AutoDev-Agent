"""
llm.py - Unified Large Language Model Interface for AutoDev

Acts as the single abstraction layer between AutoDev agents and
any Large Language Model provider (OpenAI, Anthropic Claude, Google Gemini,
or Mock providers for offline testing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type


class BaseLLM(ABC):
    """
    Abstract base class defining the contract for all LLM providers in AutoDev.
    All agents must interact with LLMs exclusively through this interface.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_kwargs = kwargs

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a text completion response from the language model.

        Args:
            prompt: The input prompt string.
            **kwargs: Provider-specific inference overrides.

        Returns:
            The generated response string.
        """
        pass


# Import concrete providers and exceptions
from core.providers.anthropic_provider import AnthropicProvider
from core.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderResponseError,
)
from core.providers.gemini_provider import GeminiProvider
from core.providers.mock_provider import MockProvider
from core.providers.openai_provider import OpenAIProvider
from core.providers.provider_factory import ProviderFactory

# Backward compatibility aliases
MockLLM = MockProvider
OpenAILLM = OpenAIProvider
ClaudeLLM = AnthropicProvider
GeminiLLM = GeminiProvider
LLMFactory = ProviderFactory

__all__ = [
    "BaseLLM",
    "MockLLM",
    "MockProvider",
    "OpenAILLM",
    "OpenAIProvider",
    "ClaudeLLM",
    "AnthropicProvider",
    "GeminiLLM",
    "GeminiProvider",
    "LLMFactory",
    "ProviderFactory",
    "ProviderError",
    "ProviderAuthenticationError",
    "ProviderConnectionError",
    "ProviderResponseError",
]


if __name__ == "__main__":
    # Self-test / demonstration
    mock_llm = ProviderFactory.create(provider="mock")
    response = mock_llm.generate("Write a starter function for AutoDev")
    print("MockLLM output:\n", response)
