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
from .providers.claude import ClaudeModel
from .providers.gemini import GeminiModel
from .providers.openai import OpenAIModel

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
    # Providers
    'ClaudeModel', 'GeminiModel', 'OpenAIModel'
]