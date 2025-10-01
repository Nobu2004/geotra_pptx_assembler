from typing import Dict, Any, List
from .data_classes import (
    BaseRequest, WebSearchRequest, StructuredOutputRequest,
    FunctionCallingRequest, FunctionDefinition
)


class ClaudeConverter:
    """Convert data classes to Claude API format"""
    
    @staticmethod
    def convert_web_search_request(request: WebSearchRequest) -> Dict[str, Any]:
        """Convert WebSearchRequest to Claude's tool config"""
        tool_config = {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": request.max_uses
        }
        
        if request.allowed_domains:
            tool_config["allowed_domains"] = request.allowed_domains
        elif request.blocked_domains:
            tool_config["blocked_domains"] = request.blocked_domains
        
        if request.user_location:
            tool_config["user_location"] = request.user_location
        
        return tool_config
    
    @staticmethod
    def convert_function_definitions(
        functions: List[FunctionDefinition]
    ) -> List[Dict[str, Any]]:
        """Convert FunctionDefinition list to Claude's tool format"""
        return [
            {
                "name": func.name,
                "description": func.description,
                "input_schema": func.parameters
            }
            for func in functions
        ]


class GeminiConverter:
    """Convert data classes to Gemini API format"""
    
    @staticmethod
    def convert_web_search_request(request: WebSearchRequest) -> Dict[str, Any]:
        """Convert WebSearchRequest to Gemini's tool config"""
        # Gemini uses google_search tool
        return {
            "google_search": {}
        }
    
    @staticmethod
    def convert_function_definitions(
        functions: List[FunctionDefinition]
    ) -> List[Dict[str, Any]]:
        """Convert FunctionDefinition list to Gemini's format"""
        return [
            {
                "name": func.name,
                "description": func.description,
                "parameters": func.parameters
            }
            for func in functions
        ]


class OpenAIConverter:
    """Convert data classes to OpenAI API format"""
    
    @staticmethod
    def convert_web_search_request(request: WebSearchRequest) -> Dict[str, Any]:
        """Convert WebSearchRequest to OpenAI's tool config"""
        tool_config = {"type": "web_search"}
        
        if request.allowed_domains:
            tool_config["filters"] = {
                "allowed_domains": request.allowed_domains[:20]
            }
        
        if request.user_location:
            location_config = {"type": "approximate"}
            location_config.update(request.user_location)
            tool_config["user_location"] = location_config
        
        if request.search_context_size:
            tool_config["search_context_size"] = request.search_context_size
        
        return tool_config
    
    @staticmethod
    def convert_function_definitions(
        functions: List[FunctionDefinition]
    ) -> List[Dict[str, Any]]:
        """Convert FunctionDefinition list to OpenAI's format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": func.name,
                    "description": func.description,
                    "parameters": func.parameters,
                    "strict": func.strict
                }
            }
            for func in functions
        ]