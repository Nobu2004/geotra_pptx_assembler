"""
LLM API Package - Unified interface for multiple LLM providers
"""

from .base import CallModel
from .data_classes import (
    BaseRequest, BaseResponse,
    WebSearchRequest, WebSearchResponse,
    StructuredOutputRequest, StructuredOutputResponse,
    FunctionCallingRequest, FunctionCallingResponse,
    FunctionDefinition, FunctionCall,
    Citation, SearchResult,
    SearchMode, ToolChoice,
    ProviderConfig
)
from .exceptions import (
    LLMError, LLMAPIError, LLMValidationError,
    LLMRateLimitError, LLMAuthenticationError
)
# Provider imports are optional because some dependencies may not be installed
try:  # pragma: no cover - optional dependency
    from .providers.claude import ClaudeModel
except ModuleNotFoundError:  # pragma: no cover - dependency not available
    ClaudeModel = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from .providers.gemini import GeminiModel
except ModuleNotFoundError:  # pragma: no cover - dependency not available
    GeminiModel = None  # type: ignore

try:
    from .providers.openai import OpenAIModel
except ModuleNotFoundError:  # pragma: no cover - dependency not available
    OpenAIModel = None  # type: ignore

__version__ = "1.0.0"
__all__ = [
    # Base
    'CallModel',
    # Data Classes
    'BaseRequest', 'BaseResponse',
    'WebSearchRequest', 'WebSearchResponse',
    'StructuredOutputRequest', 'StructuredOutputResponse',
    'FunctionCallingRequest', 'FunctionCallingResponse',
    'FunctionDefinition', 'FunctionCall',
    'Citation', 'SearchResult',
    'SearchMode', 'ToolChoice',
    'ProviderConfig',
    # Exceptions
    'LLMError', 'LLMAPIError', 'LLMValidationError',
    'LLMRateLimitError', 'LLMAuthenticationError',
    # Providers (optional)
    'ClaudeModel', 'GeminiModel', 'OpenAIModel'
]