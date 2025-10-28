"""Custom exceptions for the estimate automation package."""

from __future__ import annotations


class EstimateAutomationError(Exception):
    """Base class for domain-specific exceptions."""


class ValidationError(EstimateAutomationError):
    """Raised when provided data cannot be parsed or validated."""


class SecurityError(EstimateAutomationError):
    """Raised when authentication or authorization fails."""
