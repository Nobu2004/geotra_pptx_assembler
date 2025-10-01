from abc import ABC, abstractmethod
from typing import Optional
from .data_classes import (
    BaseRequest, BaseResponse,
    WebSearchRequest, WebSearchResponse,
    StructuredOutputRequest, StructuredOutputResponse,
    FunctionCallingRequest, FunctionCallingResponse,
    ProviderConfig
)


class CallModel(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.provider_config = self._get_provider_config()
        self.setup_client()
    
    @abstractmethod
    def setup_client(self):
        """Setup the provider's client"""
        pass
    
    @abstractmethod
    def _get_provider_config(self) -> ProviderConfig:
        """Get provider-specific configuration"""
        pass
    
    # Core methods - all providers must implement
    @abstractmethod
    def generate_content(self, request: BaseRequest) -> BaseResponse:
        """Generate basic text content"""
        pass
    
    @abstractmethod
    def generate_structured_output(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse:
        """Generate structured JSON output"""
        pass
    
    @abstractmethod
    def web_search(self, request: WebSearchRequest) -> WebSearchResponse:
        """Perform web search"""
        pass
    
    @abstractmethod
    def function_calling(
        self, request: FunctionCallingRequest
    ) -> FunctionCallingResponse:
        """Execute function calling"""
        pass
    
    # Utility methods
    def get_provider_name(self) -> str:
        """Get the provider name"""
        return self.provider_config.provider_name
    
    def supports_feature(self, feature: str) -> bool:
        """Check if provider supports a specific feature"""
        feature_map = {
            'web_search': self.provider_config.supports_web_search,
            'structured_output': self.provider_config.supports_structured_output,
            'function_calling': self.provider_config.supports_function_calling
        }
        return feature_map.get(feature, False)