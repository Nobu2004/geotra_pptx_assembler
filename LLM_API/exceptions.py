from typing import Optional
from datetime import datetime


class LLMError(Exception):
    """Base exception for all LLM-related errors"""
    
    def __init__(
        self,
        message: str,
        provider: str = "",
        error_type: str = "general",
        retry_after: Optional[int] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.error_type = error_type
        self.retry_after = retry_after
        self.original_error = original_error
        self.timestamp = datetime.now()
    
    def __str__(self):
        return f"[{self.provider}] {self.error_type}: {self.message}"


class LLMAPIError(LLMError):
    """API request failed"""
    pass


class LLMAuthenticationError(LLMError):
    """Authentication failed (invalid API key)"""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded"""
    pass


class LLMValidationError(LLMError):
    """Request validation failed"""
    pass


class LLMTimeoutError(LLMError):
    """Request timed out"""
    pass


class LLMModelNotFoundError(LLMError):
    """Specified model not found"""
    pass


class LLMInsufficientQuotaError(LLMError):
    """Insufficient API quota"""
    pass