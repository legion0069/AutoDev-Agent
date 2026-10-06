"""
gemini_provider.py - Google Gemini LLM Provider for AutoDev

Integrates Google's Gemini models (e.g. gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash)
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


class GeminiProvider(BaseLLM):
    """
    Google Gemini LLM provider integration.
    """

    DEFAULT_MODEL = "gemini-1.5-pro"
    API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        client: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the GeminiProvider.

        Args:
            model_name: Name of the Gemini model (default: 'gemini-1.5-pro').
            api_key: API key. If not provided, reads from GEMINI_API_KEY or GOOGLE_API_KEY env vars.
            temperature: Sampling temperature between 0.0 and 2.0 (default: 0.7).
            max_tokens: Maximum output tokens.
            client: Optional pre-configured or mocked SDK client.
            **kwargs: Additional parameters passed to BaseLLM.

        Raises:
            ProviderAuthenticationError: If no API key is provided or found in the environment.
        """
        resolved_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        if not resolved_key or not resolved_key.strip():
            raise ProviderAuthenticationError(
                "Gemini API key is required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.",
                provider="gemini",
            )

        super().__init__(
            model_name=model_name or self.DEFAULT_MODEL,
            api_key=resolved_key.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self.client = client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates a completion from Google Gemini.

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

        # 2. Check for official google.genai SDK
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            if hasattr(response, "text") and response.text is not None:
                return str(response.text)
            raise ProviderResponseError(
                "Gemini SDK returned an empty or invalid content response.",
                provider="gemini",
            )
        except ImportError:
            # Fall back to HTTP REST endpoint
            return self._generate_with_http(prompt, model, temperature, max_tokens)
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            self._handle_exception(exc)
            raise ProviderResponseError(f"Unexpected error communicating with Gemini: {exc}", provider="gemini")

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
            # Check for models.generate_content (google.genai style)
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                resp = client.models.generate_content(model=model, contents=prompt, **kwargs)
                if hasattr(resp, "text"):
                    return str(resp.text)
                return str(resp)

            # Check for generate_content (google.generativeai GenerativeModel style)
            if hasattr(client, "generate_content"):
                resp = client.generate_content(prompt, **kwargs)
                if hasattr(resp, "text"):
                    return str(resp.text)
                return str(resp)

            # Check for callable client
            if callable(client):
                return str(client(prompt, **kwargs))

            raise ProviderResponseError(
                f"Injected client {type(client)} does not support generate_content.",
                provider="gemini",
            )
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            self._handle_exception(exc)
            raise ProviderResponseError(f"Error from Gemini client: {exc}", provider="gemini")

    def _generate_with_http(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """Executes generation using standard HTTP POST to Gemini REST API."""
        url = self.API_URL_TEMPLATE.format(model=model) + f"?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                resp_data = resp.read().decode("utf-8")
                parsed = json.loads(resp_data)
                candidates = parsed.get("candidates", [])
                if not candidates:
                    raise ProviderResponseError("Gemini returned no response candidates.", provider="gemini")
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise ProviderResponseError("Gemini response missing text in candidate parts.", provider="gemini")
                return str(parts[0]["text"])
        except urllib.error.HTTPError as http_err:
            status = http_err.code
            body = ""
            try:
                body = http_err.read().decode("utf-8")
            except Exception:
                pass

            if status in (401, 403):
                raise ProviderAuthenticationError(
                    f"Gemini authentication failed (HTTP {status}): {body or http_err.reason}",
                    provider="gemini",
                )
            if status == 429:
                raise ProviderResponseError(
                    f"Gemini rate limit exceeded (HTTP 429): {body or http_err.reason}",
                    provider="gemini",
                )
            raise ProviderResponseError(
                f"Gemini API returned error (HTTP {status}): {body or http_err.reason}",
                provider="gemini",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as net_err:
            raise ProviderConnectionError(
                f"Failed to connect to Gemini API endpoint: {net_err}",
                provider="gemini",
            )
        except (ProviderAuthenticationError, ProviderConnectionError, ProviderResponseError):
            raise
        except Exception as exc:
            raise ProviderResponseError(f"Failed to process Gemini response: {exc}", provider="gemini")

    def _handle_exception(self, exc: Exception) -> None:
        """Maps third-party SDK exceptions to typed provider exceptions."""
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        if any(w in exc_str or w in exc_type for w in ("auth", "permission", "api_key", "401", "403", "unauthenticated", "unauthorized")):
            raise ProviderAuthenticationError(f"Gemini authentication failed: {exc}", provider="gemini")
        if any(w in exc_str or w in exc_type for w in ("connection", "timeout", "socket", "network", "unreachable", "dns")):
            raise ProviderConnectionError(f"Gemini connection error: {exc}", provider="gemini")
        if any(w in exc_str or w in exc_type for w in ("rate", "quota", "429", "500", "503", "overloaded")):
            raise ProviderResponseError(f"Gemini rate limit or server error: {exc}", provider="gemini")
