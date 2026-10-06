"""
provider_factory.py - Provider Factory for AutoDev LLMs

Provides a unified factory interface to instantiate any supported LLM provider
(Mock, Gemini, OpenAI, Anthropic) or custom user-registered providers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from core.llm import BaseLLM
from core.providers.anthropic_provider import AnthropicProvider
from core.providers.gemini_provider import GeminiProvider
from core.providers.mock_provider import MockProvider
from core.providers.openai_provider import OpenAIProvider


class ProviderFactory:
    """
    Factory class responsible for instantiating and configuring BaseLLM providers.
    """

    _registry: Dict[str, Type[BaseLLM]] = {
        "mock": MockProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "openai": OpenAIProvider,
        "chatgpt": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider_cls: Type[BaseLLM]) -> None:
        """
        Registers a new or custom LLM provider in the factory registry.

        Args:
            name: Provider name identifier (case-insensitive).
            provider_cls: Subclass of BaseLLM.

        Raises:
            TypeError: If provider_cls is not a subclass of BaseLLM.
        """
        if not (isinstance(provider_cls, type) and issubclass(provider_cls, BaseLLM)):
            raise TypeError(f"Provider class {provider_cls} must inherit from BaseLLM.")
        cls._registry[name.strip().lower()] = provider_cls

    @classmethod
    def get_registered_providers(cls) -> List[str]:
        """Returns a sorted list of unique registered provider names."""
        return sorted(list(set(cls._registry.keys())))

    @classmethod
    def create(
        cls,
        provider: str = "mock",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> BaseLLM:
        """
        Instantiates and returns the configured BaseLLM implementation.

        Args:
            provider: Provider identifier ('mock', 'gemini', 'openai', 'anthropic').
            model_name: Optional specific model identifier (e.g. 'gpt-4o', 'gemini-1.5-pro').
            api_key: Optional API key override.
            temperature: Optional sampling temperature override.
            max_tokens: Optional token limit override.
            **kwargs: Additional provider-specific keyword arguments.

        Returns:
            An instance of BaseLLM corresponding to the chosen provider.

        Raises:
            ValueError: If the requested provider name is not recognized.
            ProviderAuthenticationError: If required API credentials are missing.
        """
        if not provider or not isinstance(provider, str):
            raise ValueError(f"Provider name must be a non-empty string. Got: {provider!r}")

        key = provider.strip().lower()
        provider_cls = cls._registry.get(key)

        if not provider_cls:
            available = ", ".join(cls.get_registered_providers())
            raise ValueError(
                f"Unsupported LLM provider '{provider}'. Available providers: {available}"
            )

        init_kwargs: Dict[str, Any] = {**kwargs}
        if model_name is not None:
            init_kwargs["model_name"] = model_name
        if api_key is not None:
            init_kwargs["api_key"] = api_key
        if temperature is not None:
            init_kwargs["temperature"] = temperature
        if max_tokens is not None:
            init_kwargs["max_tokens"] = max_tokens

        return provider_cls(**init_kwargs)
