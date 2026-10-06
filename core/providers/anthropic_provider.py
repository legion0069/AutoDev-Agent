"""
anthropic_provider.py - Anthropic Claude LLM Provider for AutoDev

Integrates Anthropic Claude models (e.g. claude-3-5-sonnet, claude-3-opus, claude-3-5-haiku)
with comprehensive error mapping for authentication, connection, and API response issues.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from core.llm import BaseLLM
from core.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderResponseError,
)


class AnthropicProvider(BaseLLM):
    """
    Anthropic Claude LLM provider integration.
    """

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    API_URL = "https://api.anthropic.com/v1/messages"
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        client: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the AnthropicProvider.

        Args:
            model_name: Name of the Claude model (default: 'claude-3-5-sonnet-20241022').
            api_key: API key. If not provided, reads from ANTHROPIC_API_KEY env var.
            temperature: Sampling temperature between 0.0 and 1.0 (default: 0.7).
            max_tokens: Maximum output tokens (default: 4096).
            client: Optional pre-configured or mocked SDK client.
            **kwargs: Additional parameters passed to BaseLLM.

        Raises:
            ProviderAuthenticationError: If no API key is provided or found in the environment.
        """
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key or not resolved_key.strip():
            raise ProviderAuthenticationError(
                "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable.",
                provider="anthropic",
            )

        super().__init__(
            model_name=model_name or self.DEFAULT_MODEL,
            api_key=resolved_key.strip(),
            temperature=temperature,
            max_tokens=max_tokens or 4096,
            **kwargs,
        )
        self.client = client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a completion from Anthropic Claude.

        Args:
            prompt: The input prompt string.
            **kwargs: Generation overrides (e.g. temperature, max_tokens, model, system).

        Returns:
            The generated response string.

        Raises:
            ProviderAuthenticationError: On invalid API key or 401/403 status.
            ProviderConnectionError: On network or socket failure.
            ProviderResponseError: On bad status, rate limits, or malformed responses.
        """
        if not prompt or not prompt.strip():
            return ""

        model = kwargs.get("model") or kwargs.get("model_name") or self.model_name
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens or 4096)
        system_prompt = kwargs.get("system")

        # 1. If an injected SDK client exists, use it
        if self.client is not None:
            return self._generate_with_client(self.client, prompt, model, temperature, max_tokens, system_prompt, **kwargs)

        # 2. Check for official anthropic SDK
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)
            msg_kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                msg_kwargs["system"] = system_prompt

            response = client.messages.create(**msg_kwargs)
            if hasattr(response, "content") and response.content:
                block = response.content[0]
                if hasattr(block, "text"):
                    return str(block.text)
            raise ProviderResponseError(
                "Anthropic SDK returned empty or invalid content blocks in response.",
                provider="anthropic",
            )
        except ImportError:
            # Fall back to HTTP REST endpoint
            return self._generate_with_http(prompt, model, temperature, max_tokens, system_prompt)
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            self._handle_exception(exc)
            raise ProviderResponseError(f"Unexpected error communicating with Anthropic: {exc}", provider="anthropic")

    def _generate_with_client(
        self,
        client: Any,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        **kwargs: Any,
    ) -> str:
        """Executes generation using an injected client object."""
        try:
            # Check for messages.create (anthropic.Anthropic style)
            if hasattr(client, "messages") and hasattr(client.messages, "create"):
                msg_kwargs: Dict[str, Any] = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if system_prompt:
                    msg_kwargs["system"] = system_prompt
                resp = client.messages.create(**msg_kwargs)
                if hasattr(resp, "content") and resp.content:
                    block = resp.content[0]
                    if hasattr(block, "text"):
                        return str(block.text)
                return str(resp)

            # Check for callable client
            if callable(client):
                return str(client(prompt, **kwargs))

            raise ProviderResponseError(
                f"Injected client {type(client)} does not support messages.create.",
                provider="anthropic",
            )
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            self._handle_exception(exc)
            raise ProviderResponseError(f"Error from Anthropic client: {exc}", provider="anthropic")

    def _generate_with_http(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Executes generation using standard HTTP POST to Anthropic Messages REST API."""
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        req_data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": str(self.api_key),
            "anthropic-version": self.ANTHROPIC_VERSION,
        }

        req = urllib.request.Request(
            self.API_URL,
            data=req_data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                resp_data = resp.read().decode("utf-8")
                parsed = json.loads(resp_data)
                content_blocks = parsed.get("content", [])
                if not content_blocks:
                    raise ProviderResponseError("Anthropic returned no content blocks.", provider="anthropic")
                text = content_blocks[0].get("text", "")
                return str(text or "")
        except urllib.error.HTTPError as http_err:
            status = http_err.code
            body = ""
            try:
                body = http_err.read().decode("utf-8")
            except Exception:
                pass

            if status in (401, 403):
                raise ProviderAuthenticationError(
                    f"Anthropic authentication failed (HTTP {status}): {body or http_err.reason}",
                    provider="anthropic",
                )
            if status == 429:
                raise ProviderResponseError(
                    f"Anthropic rate limit exceeded (HTTP 429): {body or http_err.reason}",
                    provider="anthropic",
                )
            raise ProviderResponseError(
                f"Anthropic API returned error (HTTP {status}): {body or http_err.reason}",
                provider="anthropic",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as net_err:
            raise ProviderConnectionError(
                f"Failed to connect to Anthropic API endpoint: {net_err}",
                provider="anthropic",
            )
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            raise ProviderResponseError(f"Failed to process Anthropic response: {exc}", provider="anthropic")

    def _handle_exception(self, exc: Exception) -> None:
        """Maps third-party SDK exceptions to typed provider exceptions."""
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        if any(w in exc_str or w in exc_type for w in ("auth", "permission", "api_key", "401", "403", "unauthorized")):
            raise ProviderAuthenticationError(f"Anthropic authentication failed: {exc}", provider="anthropic")
        if any(w in exc_str or w in exc_type for w in ("connection", "timeout", "socket", "network", "unreachable", "dns")):
            raise ProviderConnectionError(f"Anthropic connection error: {exc}", provider="anthropic")
        if any(w in exc_str or w in exc_type for w in ("rate", "quota", "429", "500", "503", "overloaded")):
            raise ProviderResponseError(f"Anthropic rate limit or server error: {exc}", provider="anthropic")
