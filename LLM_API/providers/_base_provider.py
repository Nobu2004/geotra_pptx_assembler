import os
from typing import Optional
from ..base import CallModel
from ..exceptions import LLMAuthenticationError


class BaseProvider(CallModel):
    """Base class with common provider functionality"""
    
    def _get_api_key(self, env_var_name: str) -> str:
        """Get API key from environment or instance variable"""
        api_key = self.api_key or os.getenv(env_var_name)
        
        if not api_key:
            raise LLMAuthenticationError(
                message=f"API key required. Set {env_var_name} or pass api_key parameter",
                provider=self.__class__.__name__,
                error_type="missing_api_key"
            )
        
        return api_key
    
    def _validate_request(self, request):
        """Common request validation"""
        if not request.prompt and not hasattr(request, 'messages'):
            raise ValueError("Request must have a prompt or messages")
        
        if request.max_tokens and request.max_tokens > self.provider_config.max_tokens_limit:
            raise ValueError(
                f"max_tokens exceeds limit: {self.provider_config.max_tokens_limit}"
            )