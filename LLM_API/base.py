"""Abstract base class that normalises the provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .data_classes import (
    BaseRequest,
    BaseResponse,
    FunctionCallingRequest,
    FunctionCallingResponse,
    ProviderConfig,
    StructuredOutputRequest,
    StructuredOutputResponse,
    WebSearchRequest,
    WebSearchResponse,
)


class CallModel(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self.provider_config = self._get_provider_config()
        self.setup_client()

    @abstractmethod
    def setup_client(self) -> None:
        """Initialise the provider client."""

    @abstractmethod
    def _get_provider_config(self) -> ProviderConfig:
        """Return provider specific configuration metadata."""

    # ------------------------------------------------------------------
    # Core API methods that providers must implement
    # ------------------------------------------------------------------
    @abstractmethod
    def generate_content(self, request: BaseRequest) -> BaseResponse:
        """Generate basic text content."""

    @abstractmethod
    def generate_structured_output(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse:
        """Generate structured JSON output."""

    @abstractmethod
    def web_search(self, request: WebSearchRequest) -> WebSearchResponse:
        """Perform a web search request."""

    @abstractmethod
    def function_calling(
        self, request: FunctionCallingRequest
    ) -> FunctionCallingResponse:
        """Execute function calling."""

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def get_provider_name(self) -> str:
        """Return the provider name."""

        return self.provider_config.provider_name

    def supports_feature(self, feature: str) -> bool:
        """Check if provider supports a specific feature."""

        feature_map = {
            "web_search": self.provider_config.supports_web_search,
            "structured_output": self.provider_config.supports_structured_output,
            "function_calling": self.provider_config.supports_function_calling,
        }
        return feature_map.get(feature, False)
