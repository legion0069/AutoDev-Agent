"""
test_providers.py - Comprehensive Unit Tests for AutoDev LLM Providers & Plugin Architecture

Tests all provider implementations (Mock, Gemini, OpenAI, Anthropic), ProviderFactory,
exception mapping, and dependency injection into Orchestrator using mocked responses.
No real network calls or API requests are performed.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from core.llm import (
    BaseLLM,
    ClaudeLLM,
    GeminiLLM,
    MockLLM,
    OpenAILLM,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderResponseError,
)
from core.orchestrator import Orchestrator
from core.providers import (
    AnthropicProvider,
    GeminiProvider,
    MockProvider,
    OpenAIProvider,
    ProviderFactory,
)


# =============================================================================
# 1. MockProvider Tests
# =============================================================================

def test_mock_provider_default_response():
    """Verifies that MockProvider returns its default simulated response."""
    provider = MockProvider()
    response = provider.generate("Implement user authentication")
    assert "def hello_autodev" in response
    assert provider.call_count == 1
    assert provider.last_prompt == "Implement user authentication"
    assert len(provider.prompt_history) == 1


def test_mock_provider_override_in_generate():
    """Verifies that response keyword argument overrides default response."""
    provider = MockProvider(default_response="Default")
    response = provider.generate("prompt", response="Custom override")
    assert response == "Custom override"
    assert provider.call_count == 1


def test_mock_provider_sequential_responses():
    """Verifies that MockProvider returns queued responses in sequence."""
    provider = MockProvider(responses=["First Response", "Second Response"])
    r1 = provider.generate("p1")
    r2 = provider.generate("p2")
    r3 = provider.generate("p3")  # Falls back to default

    assert r1 == "First Response"
    assert r2 == "Second Response"
    assert "hello_autodev" in r3
    assert provider.call_count == 3


def test_mock_provider_dynamic_function():
    """Verifies that MockProvider can use a dynamic response function."""
    def custom_fn(prompt: str, **kwargs: Any) -> str:
        return f"Echo: {prompt.upper()}"

    provider = MockProvider(response_fn=custom_fn)
    assert provider.generate("hello world") == "Echo: HELLO WORLD"


def test_mock_provider_reset():
    """Verifies that reset clears call statistics."""
    provider = MockProvider()
    provider.generate("test prompt")
    assert provider.call_count == 1

    provider.reset()
    assert provider.call_count == 0
    assert provider.last_prompt is None
    assert provider.prompt_history == []


# =============================================================================
# 2. ProviderFactory Tests
# =============================================================================

def test_provider_factory_create_mock():
    """Verifies factory creation of MockProvider."""
    provider = ProviderFactory.create("mock", default_response="Factory Mock")
    assert isinstance(provider, MockProvider)
    assert isinstance(provider, BaseLLM)
    assert provider.generate("test") == "Factory Mock"


def test_provider_factory_case_insensitivity():
    """Verifies case-insensitive provider lookup."""
    p1 = ProviderFactory.create("MOCK")
    p2 = ProviderFactory.create("Mock")
    assert isinstance(p1, MockProvider)
    assert isinstance(p2, MockProvider)


def test_provider_factory_create_with_api_key():
    """Verifies creating real providers with explicitly supplied API keys."""
    gemini = ProviderFactory.create("gemini", api_key="test-gemini-key")
    assert isinstance(gemini, GeminiProvider)
    assert gemini.api_key == "test-gemini-key"

    openai = ProviderFactory.create("openai", api_key="test-openai-key")
    assert isinstance(openai, OpenAIProvider)
    assert openai.api_key == "test-openai-key"

    anthropic = ProviderFactory.create("anthropic", api_key="test-anthropic-key")
    assert isinstance(anthropic, AnthropicProvider)
    assert anthropic.api_key == "test-anthropic-key"


def test_provider_factory_aliases():
    """Verifies provider aliases (google, chatgpt, claude)."""
    p_google = ProviderFactory.create("google", api_key="gkey")
    assert isinstance(p_google, GeminiProvider)

    p_chatgpt = ProviderFactory.create("chatgpt", api_key="okey")
    assert isinstance(p_chatgpt, OpenAIProvider)

    p_claude = ProviderFactory.create("claude", api_key="ckey")
    assert isinstance(p_claude, AnthropicProvider)


def test_provider_factory_unsupported_provider():
    """Verifies that an unsupported provider name raises a descriptive ValueError."""
    with pytest.raises(ValueError) as exc_info:
        ProviderFactory.create("quantum-ai")
    assert "Unsupported LLM provider 'quantum-ai'" in str(exc_info.value)
    assert "Available providers:" in str(exc_info.value)


def test_provider_factory_empty_provider_name():
    """Verifies that empty provider string raises ValueError."""
    with pytest.raises(ValueError):
        ProviderFactory.create("")


def test_provider_factory_register_custom_provider():
    """Verifies registering a custom BaseLLM subclass in the factory."""
    class CustomEchoProvider(BaseLLM):
        def generate(self, prompt: str, **kwargs: Any) -> str:
            return f"Custom: {prompt}"

    ProviderFactory.register_provider("custom_echo", CustomEchoProvider)
    instance = ProviderFactory.create("custom_echo")
    assert isinstance(instance, CustomEchoProvider)
    assert instance.generate("ping") == "Custom: ping"


def test_provider_factory_register_invalid_provider():
    """Verifies that registering a non-BaseLLM class raises TypeError."""
    class NotAnLLM:
        pass

    with pytest.raises(TypeError):
        ProviderFactory.register_provider("invalid", NotAnLLM)  # type: ignore


# =============================================================================
# 3. GeminiProvider Tests
# =============================================================================

def test_gemini_missing_api_key_raises_auth_error(monkeypatch):
    """Verifies that missing API key raises ProviderAuthenticationError."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        GeminiProvider()
    assert "Gemini API key is required" in str(exc_info.value)
    assert exc_info.value.provider == "gemini"


def test_gemini_reads_env_vars(monkeypatch):
    """Verifies that Gemini reads GEMINI_API_KEY and GOOGLE_API_KEY from env."""
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
    p1 = GeminiProvider()
    assert p1.api_key == "env-gemini-key"

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "env-google-key")
    p2 = GeminiProvider()
    assert p2.api_key == "env-google-key"


def test_gemini_injected_client_generation():
    """Verifies generation using an injected mock SDK client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"files": [{"path": "auth.py", "content": "# auth code"}]}'
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="mock-key", client=mock_client)
    result = provider.generate("Generate auth module")

    assert result == '{"files": [{"path": "auth.py", "content": "# auth code"}]}'
    mock_client.models.generate_content.assert_called_once()


def test_gemini_http_mocked_success():
    """Verifies successful HTTP generation when SDK is not present."""
    fake_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "class Database:\n    pass"}]
                }
            }
        ]
    }
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(fake_payload).encode("utf-8")
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = None

    provider = GeminiProvider(api_key="test-key")
    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        result = provider._generate_with_http("Write DB class", "gemini-1.5-pro", 0.7, None)
        assert result == "class Database:\n    pass"
        mock_urlopen.assert_called_once()


def test_gemini_http_401_raises_auth_error():
    """Verifies that HTTP 401 error is converted to ProviderAuthenticationError."""
    http_err = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore
        fp=io.BytesIO(b'{"error": {"message": "API key not valid"}}'),
    )

    provider = GeminiProvider(api_key="invalid-key")
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(ProviderAuthenticationError) as exc_info:
            provider._generate_with_http("Prompt", "gemini-1.5-pro", 0.7, None)
        assert "401" in str(exc_info.value)


def test_gemini_http_connection_error():
    """Verifies that URLError/connection error is converted to ProviderConnectionError."""
    url_err = urllib.error.URLError("Connection refused")
    provider = GeminiProvider(api_key="test-key")
    with patch("urllib.request.urlopen", side_effect=url_err):
        with pytest.raises(ProviderConnectionError):
            provider._generate_with_http("Prompt", "gemini-1.5-pro", 0.7, None)


def test_gemini_http_429_rate_limit_error():
    """Verifies that HTTP 429 is converted to ProviderResponseError."""
    http_err = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com",
        code=429,
        msg="Too Many Requests",
        hdrs={},  # type: ignore
        fp=io.BytesIO(b'{"error": {"message": "Resource exhausted"}}'),
    )

    provider = GeminiProvider(api_key="test-key")
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(ProviderResponseError) as exc_info:
            provider._generate_with_http("Prompt", "gemini-1.5-pro", 0.7, None)
        assert "429" in str(exc_info.value)


# =============================================================================
# 4. OpenAIProvider Tests
# =============================================================================

def test_openai_missing_api_key_raises_auth_error(monkeypatch):
    """Verifies that missing OPENAI_API_KEY raises ProviderAuthenticationError."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        OpenAIProvider()
    assert "OpenAI API key is required" in str(exc_info.value)
    assert exc_info.value.provider == "openai"


def test_openai_reads_env_var(monkeypatch):
    """Verifies that OpenAI reads OPENAI_API_KEY from environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    provider = OpenAIProvider()
    assert provider.api_key == "env-openai-key"


def test_openai_injected_client_generation():
    """Verifies generation using an injected mock OpenAI client."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "def calculate_total(): return 42"
    mock_response = MagicMock(choices=[mock_choice])
    mock_client.chat.completions.create.return_value = mock_response

    provider = OpenAIProvider(api_key="mock-key", client=mock_client)
    result = provider.generate("Generate function")

    assert result == "def calculate_total(): return 42"
    mock_client.chat.completions.create.assert_called_once()


def test_openai_http_mocked_success():
    """Verifies successful HTTP generation when SDK is not present."""
    fake_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "class UserModel:\n    pass",
                }
            }
        ]
    }
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(fake_payload).encode("utf-8")
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = None

    provider = OpenAIProvider(api_key="test-key")
    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        result = provider._generate_with_http("Write User model", "gpt-4o", 0.7, None)
        assert result == "class UserModel:\n    pass"
        mock_urlopen.assert_called_once()


def test_openai_http_401_raises_auth_error():
    """Verifies that HTTP 401 raises ProviderAuthenticationError."""
    http_err = urllib.error.HTTPError(
        url="https://api.openai.com",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore
        fp=io.BytesIO(b'{"error": {"message": "Incorrect API key provided"}}'),
    )

    provider = OpenAIProvider(api_key="bad-key")
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(ProviderAuthenticationError):
            provider._generate_with_http("Prompt", "gpt-4o", 0.7, None)


def test_openai_http_connection_error():
    """Verifies that network error raises ProviderConnectionError."""
    url_err = urllib.error.URLError("Temporary failure in name resolution")
    provider = OpenAIProvider(api_key="test-key")
    with patch("urllib.request.urlopen", side_effect=url_err):
        with pytest.raises(ProviderConnectionError):
            provider._generate_with_http("Prompt", "gpt-4o", 0.7, None)


# =============================================================================
# 5. AnthropicProvider Tests
# =============================================================================

def test_anthropic_missing_api_key_raises_auth_error(monkeypatch):
    """Verifies that missing ANTHROPIC_API_KEY raises ProviderAuthenticationError."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        AnthropicProvider()
    assert "Anthropic API key is required" in str(exc_info.value)
    assert exc_info.value.provider == "anthropic"


def test_anthropic_reads_env_var(monkeypatch):
    """Verifies that Anthropic reads ANTHROPIC_API_KEY from environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-anthropic-key")
    provider = AnthropicProvider()
    assert provider.api_key == "env-anthropic-key"


def test_anthropic_injected_client_generation():
    """Verifies generation using an injected mock Anthropic client."""
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "class ClaudeService:\n    pass"
    mock_response = MagicMock(content=[mock_block])
    mock_client.messages.create.return_value = mock_response

    provider = AnthropicProvider(api_key="mock-key", client=mock_client)
    result = provider.generate("Generate Claude service")

    assert result == "class ClaudeService:\n    pass"
    mock_client.messages.create.assert_called_once()


def test_anthropic_http_mocked_success():
    """Verifies successful HTTP generation for Anthropic."""
    fake_payload = {
        "content": [
            {
                "type": "text",
                "text": "import sys\nprint('Anthropic response')",
            }
        ]
    }
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(fake_payload).encode("utf-8")
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = None

    provider = AnthropicProvider(api_key="test-key")
    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        result = provider._generate_with_http("Prompt", "claude-3-5-sonnet-20241022", 0.7, 4096)
        assert "Anthropic response" in result
        mock_urlopen.assert_called_once()


def test_anthropic_http_401_raises_auth_error():
    """Verifies that HTTP 401 raises ProviderAuthenticationError."""
    http_err = urllib.error.HTTPError(
        url="https://api.anthropic.com",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore
        fp=io.BytesIO(b'{"error": {"type": "authentication_error", "message": "invalid x-api-key"}}'),
    )

    provider = AnthropicProvider(api_key="invalid-key")
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(ProviderAuthenticationError):
            provider._generate_with_http("Prompt", "claude-3-5-sonnet-20241022", 0.7, 4096)


def test_anthropic_http_connection_error():
    """Verifies that network error raises ProviderConnectionError."""
    url_err = urllib.error.URLError("Network unreachable")
    provider = AnthropicProvider(api_key="test-key")
    with patch("urllib.request.urlopen", side_effect=url_err):
        with pytest.raises(ProviderConnectionError):
            provider._generate_with_http("Prompt", "claude-3-5-sonnet-20241022", 0.7, 4096)


# =============================================================================
# 6. Backward Compatibility & Orchestrator Dependency Injection Tests
# =============================================================================

def test_backward_compatibility_aliases():
    """Verifies that old imports and aliases in core.llm work seamlessly."""
    mock_llm = MockLLM()
    assert isinstance(mock_llm, BaseLLM)
    assert isinstance(mock_llm, MockProvider)


def test_orchestrator_receives_provider_via_dependency_injection(tmp_path):
    """Verifies that Orchestrator accepts any BaseLLM provider via llm parameter."""
    custom_mock = MockProvider(
        default_response=json.dumps({
            "files": [{"path": "module.py", "content": "# Generated by custom provider"}],
            "summary": "Generated by custom provider",
        })
    )

    orchestrator = Orchestrator(
        project_root=tmp_path,
        llm=custom_mock,
    )

    assert orchestrator.llm is custom_mock
    assert orchestrator.coder_agent.llm is custom_mock
    assert orchestrator.reviewer_agent.llm is custom_mock
    assert orchestrator.task_planner.llm is custom_mock
