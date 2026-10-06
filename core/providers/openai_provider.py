"""
openai_provider.py - OpenAI LLM Provider for AutoDev

Integrates OpenAI models (e.g. gpt-4o, gpt-4o-mini, gpt-4-turbo, o1)
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


class OpenAIProvider(BaseLLM):
    """
    OpenAI LLM provider integration.
    """

    DEFAULT_MODEL = "gpt-4o"
    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        client: Optional[Any] = None,
        organization: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the OpenAIProvider.

        Args:
            model_name: Name of the OpenAI model (default: 'gpt-4o').
            api_key: API key. If not provided, reads from OPENAI_API_KEY env var.
            temperature: Sampling temperature between 0.0 and 2.0 (default: 0.7).
            max_tokens: Maximum output tokens.
            client: Optional pre-configured or mocked SDK client.
            organization: Optional OpenAI organization ID.
            **kwargs: Additional parameters passed to BaseLLM.

        Raises:
            ProviderAuthenticationError: If no API key is provided or found in the environment.
        """
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key or not resolved_key.strip():
            raise ProviderAuthenticationError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable.",
                provider="openai",
            )

        super().__init__(
            model_name=model_name or self.DEFAULT_MODEL,
            api_key=resolved_key.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self.client = client
        self.organization = organization or os.environ.get("OPENAI_ORG_ID")

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a completion from OpenAI.

        Args:
            prompt: The input prompt string.
            **kwargs: Generation overrides (e.g. temperature, max_tokens, model).

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
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        # 1. If an injected SDK client exists, use it
        if self.client is not None:
            return self._generate_with_client(self.client, prompt, model, temperature, max_tokens, **kwargs)

        # 2. Check for official openai SDK
        try:
            import openai

            client_kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.organization:
                client_kwargs["organization"] = self.organization

            client = openai.OpenAI(**client_kwargs)
            completion_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            if max_tokens is not None:
                completion_kwargs["max_tokens"] = max_tokens

            response = client.chat.completions.create(**completion_kwargs)
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    return str(choice.message.content or "")
            raise ProviderResponseError(
                "OpenAI SDK returned empty or invalid choices in response.",
                provider="openai",
            )
        except ImportError:
            # Fall back to HTTP REST endpoint
            return self._generate_with_http(prompt, model, temperature, max_tokens)
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            self._handle_exception(exc)
            raise ProviderResponseError(f"Unexpected error communicating with OpenAI: {exc}", provider="openai")

    def _generate_with_client(
        self,
        client: Any,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs: Any,
    ) -> str:
        """Executes generation using an injected client object."""
        try:
            # Check for chat.completions.create (openai.OpenAI style)
            if hasattr(client, "chat") and hasattr(client.chat, "completions"):
                completion_kwargs: Dict[str, Any] = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    completion_kwargs["max_tokens"] = max_tokens
                resp = client.chat.completions.create(**completion_kwargs)
                if hasattr(resp, "choices") and resp.choices:
                    choice = resp.choices[0]
                    if hasattr(choice, "message") and hasattr(choice.message, "content"):
                        return str(choice.message.content or "")
                return str(resp)

            # Check for callable client
            if callable(client):
                return str(client(prompt, **kwargs))

            raise ProviderResponseError(
                f"Injected client {type(client)} does not support chat completions.",
                provider="openai",
            )
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            self._handle_exception(exc)
            raise ProviderResponseError(f"Error from OpenAI client: {exc}", provider="openai")

    def _generate_with_http(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """Executes generation using standard HTTP POST to OpenAI REST API."""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        req_data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization

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
                choices = parsed.get("choices", [])
                if not choices:
                    raise ProviderResponseError("OpenAI returned no response choices.", provider="openai")
                message = choices[0].get("message", {})
                content = message.get("content", "")
                return str(content or "")
        except urllib.error.HTTPError as http_err:
            status = http_err.code
            body = ""
            try:
                body = http_err.read().decode("utf-8")
            except Exception:
                pass

            if status in (401, 403):
                raise ProviderAuthenticationError(
                    f"OpenAI authentication failed (HTTP {status}): {body or http_err.reason}",
                    provider="openai",
                )
            if status == 429:
                raise ProviderResponseError(
                    f"OpenAI rate limit exceeded (HTTP 429): {body or http_err.reason}",
                    provider="openai",
                )
            raise ProviderResponseError(
                f"OpenAI API returned error (HTTP {status}): {body or http_err.reason}",
                provider="openai",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as net_err:
            raise ProviderConnectionError(
                f"Failed to connect to OpenAI API endpoint: {net_err}",
                provider="openai",
            )
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            raise ProviderResponseError(f"Failed to process OpenAI response: {exc}", provider="openai")

    def _handle_exception(self, exc: Exception) -> None:
        """Maps third-party SDK exceptions to typed provider exceptions."""
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        if any(w in exc_str or w in exc_type for w in ("auth", "permission", "api_key", "401", "403", "unauthorized")):
            raise ProviderAuthenticationError(f"OpenAI authentication failed: {exc}", provider="openai")
        if any(w in exc_str or w in exc_type for w in ("connection", "timeout", "socket", "network", "unreachable", "dns")):
            raise ProviderConnectionError(f"OpenAI connection error: {exc}", provider="openai")
        if any(w in exc_str or w in exc_type for w in ("rate", "quota", "429", "500", "503", "overloaded")):
            raise ProviderResponseError(f"OpenAI rate limit or server error: {exc}", provider="openai")
