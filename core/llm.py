"""
llm.py - Unified Large Language Model Interface for AutoDev

Acts as the single abstraction layer between AutoDev agents and
any Large Language Model provider (OpenAI, Anthropic Claude, Google Gemini,
or Mock providers for offline testing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type


class BaseLLM(ABC):
    """
    Abstract base class defining the contract for all LLM providers in AutoDev.
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


class MockLLM(BaseLLM):
    """
    Mock LLM implementation for local testing, unit tests, and dry runs
    without requiring API keys or network connectivity.
    """

    def __init__(
        self,
        model_name: str = "mock-model-v1",
        default_response: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, **kwargs)
        self.default_response = default_response or (
            "# [MockLLM Response]\n"
            "# Autonomous code generation simulated successfully.\n"
            "def hello_autodev():\n"
            "    return 'AutoDev agent execution completed successfully.'"
        )
        self.last_prompt: Optional[str] = None

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Returns a simulated mock response for testing.

        Args:
            prompt: The input prompt string.
            **kwargs: Optional overrides (e.g., custom response override).

        Returns:
            A deterministic mock response string.
        """
        self.last_prompt = prompt
        custom_response = kwargs.get("response", self.default_response)
        return str(custom_response)


class OpenAILLM(BaseLLM):
    """
    OpenAI LLM provider integration (e.g., GPT-4o, GPT-4 Turbo, o1).
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, api_key=api_key, **kwargs)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a completion using OpenAI's API.

        TODO: Implement OpenAI SDK client call (`openai.OpenAI()`),
              handle chat completions API, streaming, and token tracking.
        """
        raise NotImplementedError(
            f"OpenAILLM.generate() is not implemented yet. "
            f"Target model: '{self.model_name}'."
        )


class ClaudeLLM(BaseLLM):
    """
    Anthropic Claude LLM provider integration (e.g., Claude 3.5 Sonnet, Claude 3 Opus).
    """

    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, api_key=api_key, **kwargs)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a completion using Anthropic Claude API.

        TODO: Implement Anthropic SDK client call (`anthropic.Anthropic()`),
              handle messages API, system prompts, and tool use.
        """
        raise NotImplementedError(
            f"ClaudeLLM.generate() is not implemented yet. "
            f"Target model: '{self.model_name}'."
        )


class GeminiLLM(BaseLLM):
    """
    Google Gemini LLM provider integration (e.g., Gemini 1.5 Pro, Gemini 1.5 Flash).
    """

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro",
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, api_key=api_key, **kwargs)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a completion using Google GenAI SDK.

        TODO: Implement Google GenAI SDK client call (`google.generativeai.GenerativeModel`),
              handle contents generation, temperature, and safety settings.
        """
        raise NotImplementedError(
            f"GeminiLLM.generate() is not implemented yet. "
            f"Target model: '{self.model_name}'."
        )


class LLMFactory:
    """
    Factory class responsible for instantiating the appropriate BaseLLM
    provider based on configuration or provider name.
    """

    _registry: Dict[str, Type[BaseLLM]] = {
        "mock": MockLLM,
        "openai": OpenAILLM,
        "claude": ClaudeLLM,
        "anthropic": ClaudeLLM,
        "gemini": GeminiLLM,
        "google": GeminiLLM,
    }

    @classmethod
    def register_provider(cls, name: str, provider_cls: Type[BaseLLM]) -> None:
        """
        Extensible hook to register custom or third-party LLM providers.

        Args:
            name: Provider key identifier (case-insensitive).
            provider_cls: Subclass of BaseLLM.
        """
        cls._registry[name.strip().lower()] = provider_cls

    @classmethod
    def create(
        cls,
        provider: str = "mock",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseLLM:
        """
        Instantiates and returns the configured BaseLLM implementation.

        Args:
            provider: Provider name ('mock', 'openai', 'claude', 'gemini').
            model_name: Optional specific model identifier.
            api_key: Optional API key for authentication.
            **kwargs: Additional provider-specific keyword arguments.

        Returns:
            An instance of BaseLLM.

        Raises:
            ValueError: If the requested provider is not supported.
        """
        key = provider.strip().lower()
        provider_cls = cls._registry.get(key)

        if not provider_cls:
            available = ", ".join(sorted(set(cls._registry.keys())))
            raise ValueError(
                f"Unsupported LLM provider '{provider}'. Available providers: {available}"
            )

        init_kwargs: Dict[str, Any] = {**kwargs}
        if model_name:
            init_kwargs["model_name"] = model_name
        if api_key:
            init_kwargs["api_key"] = api_key

        return provider_cls(**init_kwargs)


if __name__ == "__main__":
    # Self-test / demonstration
    mock_llm = LLMFactory.create(provider="mock")
    response = mock_llm.generate("Write a starter function for AutoDev")
    print("MockLLM output:\n", response)
