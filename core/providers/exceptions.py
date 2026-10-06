"""
exceptions.py - Standard Exception Hierarchy for AutoDev LLM Providers

Defines typed, structured exceptions for provider authentication, network connectivity,
and API response errors across all supported AI model providers.
"""

from __future__ import annotations

from typing import Optional


class ProviderError(Exception):
    """
    Base exception for all LLM provider-related errors in AutoDev.
    """

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider

    def __str__(self) -> str:
        if self.provider:
            return f"[{self.provider.upper()}] {self.message}"
        return self.message


class ProviderAuthenticationError(ProviderError):
    """
    Raised when API key is missing, invalid, expired, or rejected by the provider.
    """
    pass


class ProviderConnectionError(ProviderError):
    """
    Raised when a network error, socket timeout, or DNS failure prevents
    communicating with the provider's API endpoint.
    """
    pass


class ProviderResponseError(ProviderError):
    """
    Raised when the provider returns an HTTP error (e.g. 429 Rate Limit, 500 Server Error),
    malformed payload, blocked content filter, or empty completion.
    """
    pass
