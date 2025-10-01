import os
from typing import Optional, Dict, Any, List
import time
import json
import anthropic
from dotenv import load_dotenv
from ..data_classes import (
    BaseRequest, BaseResponse,
    WebSearchRequest, WebSearchResponse,
    StructuredOutputRequest, StructuredOutputResponse,
    FunctionCallingRequest, FunctionCallingResponse,
    FunctionDefinition, FunctionCall,
    ProviderConfig, ToolChoice, Citation, SearchResult
)
from ..base import CallModel


class ClaudeModel(CallModel):
    """Enhanced Anthropic Claude API implementation using data classes"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key=api_key, model_name=model_name)
    
    def _get_provider_config(self) -> ProviderConfig:
        """Get Claude provider configuration"""
        return ProviderConfig(
            provider_name="Claude",
            model_name=self.model_name or "claude-3-5-sonnet-20241022",
            supports_web_search=True,
            supports_structured_output=True,
            supports_function_calling=True,
            max_tokens_limit=200000,
            max_search_results_limit=20,
            max_allowed_domains=5
        )
    
    def setup_client(self):
        """Setup Anthropic client"""
        load_dotenv()
        api_key = self.api_key or os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            raise ValueError(
                "Anthropic API key is required. Please set ANTHROPIC_API_KEY in your .env file "
                "or pass it as api_key parameter to ClaudeModel constructor."
            )
        
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def generate_content(self, request: BaseRequest) -> BaseResponse:
        """Generate content using data classes"""
        try:
            messages = [{"role": "user", "content": request.prompt}]
            
            request_params: Dict[str, Any] = {
                "model": request.model_name or self.model_name,
                "max_tokens": request.max_tokens or 1024,
                "messages": messages
            }
            
            if request.temperature is not None:
                request_params["temperature"] = request.temperature
            
            response = self.client.messages.create(**request_params)
            
            # Extract text from response
            text_content = ""
            for content in response.content:
                if content.type == "text":
                    text_content += content.text
            
            # Extract usage information
            usage = None
            if hasattr(response, 'usage'):
                usage = {
                    "prompt_tokens": getattr(response.usage, 'input_tokens', 0),
                    "completion_tokens": getattr(response.usage, 'output_tokens', 0),
                    "total_tokens": getattr(response.usage, 'input_tokens', 0) + getattr(response.usage, 'output_tokens', 0)
                }
            
            return BaseResponse(
                text=text_content,
                model_used=request.model_name or self.model_name,
                usage=usage,
                raw_response=response
            )
            
        except Exception as e:
            return BaseResponse(
                text="",
                model_used=request.model_name or self.model_name,
                error=str(e)
            )
    
    def generate_structured_output(self, request: StructuredOutputRequest) -> StructuredOutputResponse:
        """Generate structured output using data classes"""
        try:
            tools = [{
                "name": request.schema_name,
                "description": request.schema_description or f"Structured output for {request.schema_name}",
                "input_schema": request.schema
            }]
            
            messages = [{"role": "user", "content": request.prompt}]
            
            response = self.client.messages.create(
                model=request.model_name or self.model_name,
                max_tokens=request.max_tokens or 1024,
                tools=tools,
                tool_choice={"type": "tool", "name": request.schema_name},
                messages=messages
            )
            
            # Extract structured output from tool use
            parsed_output: Optional[Dict[str, Any]] = None
            text_content = ""
            
            for content in response.content:
                if content.type == "text":
                    text_content += content.text
                elif content.type == "tool_use" and content.name == request.schema_name:
                    parsed_output = content.input
            
            return StructuredOutputResponse(
                text=text_content,
                parsed_output=parsed_output,
                model_used=request.model_name or self.model_name,
                raw_response=response
            )
            
        except Exception as e:
            return StructuredOutputResponse(
                text="",
                model_used=request.model_name or self.model_name,
                error=str(e)
            )
    
    def web_search(self, request: WebSearchRequest) -> WebSearchResponse:
        """Perform web search using data classes"""
        try:
            tool_config: Dict[str, Any] = {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": request.max_uses or 5
            }
            
            # Add domain filtering (cannot use both allowed and blocked)
            if request.allowed_domains and request.blocked_domains:
                raise ValueError("Cannot specify both allowed_domains and blocked_domains")
            
            if request.allowed_domains:
                tool_config["allowed_domains"] = request.allowed_domains
            elif request.blocked_domains:
                tool_config["blocked_domains"] = request.blocked_domains
            
            # Add user location if provided
            if request.user_location:
                tool_config["user_location"] = request.user_location
            
            messages = [{"role": "user", "content": request.prompt}]
            
            response = self.client.messages.create(
                model=request.model_name or self.model_name,
                max_tokens=request.max_tokens or 4096,
                tools=[tool_config],
                messages=messages
            )
            
            # Extract search information
            text_content = ""
            citations: List[Citation] = []
            search_results: List[SearchResult] = []
            search_queries: List[str] = []
            web_search_requests = 0
            
            for content in response.content:
                if content.type == "text":
                    text_content += content.text
                elif content.type == "tool_use" and content.name == "web_search":
                    web_search_requests += 1
            
            return WebSearchResponse(
                text=text_content,
                model_used=request.model_name or self.model_name,
                citations=citations,
                search_results=search_results,
                search_queries=search_queries,
                web_search_requests=web_search_requests,
                raw_response=response
            )
            
        except Exception as e:
            return WebSearchResponse(
                text="",
                model_used=request.model_name or self.model_name,
                error=str(e)
            )
    
    def function_calling(self, request: FunctionCallingRequest) -> FunctionCallingResponse:
        """Perform function calling using data classes"""
        try:
            # Convert function definitions to Claude's tool format
            tools: List[Dict[str, Any]] = []
            for func_def in request.functions:
                tool = {
                    "name": func_def.name,
                    "description": func_def.description,
                    "input_schema": func_def.parameters
                }
                tools.append(tool)
            
            messages = [{"role": "user", "content": request.prompt}]
            
            # Set tool choice based on request
            tool_choice: Dict[str, Any] = {"type": "auto"}
            if request.tool_choice == ToolChoice.REQUIRED:
                tool_choice = {"type": "any"}
            elif request.specific_function:
                tool_choice = {"type": "tool", "name": request.specific_function}
            
            response = self.client.messages.create(
                model=request.model_name or self.model_name,
                max_tokens=request.max_tokens or 1024,
                tools=tools,
                tool_choice=tool_choice,
                messages=messages
            )
            
            # Extract function calls and text content
            text_content = ""
            function_calls: List[FunctionCall] = []
            
            for content in response.content:
                if content.type == "text":
                    text_content += content.text
                elif content.type == "tool_use":
                    function_call = FunctionCall(
                        id=content.id,
                        name=content.name,
                        arguments=content.input
                    )
                    function_calls.append(function_call)
            
            return FunctionCallingResponse(
                text=text_content,
                model_used=request.model_name or self.model_name,
                function_calls=function_calls,
                raw_response=response
            )
            
        except Exception as e:
            return FunctionCallingResponse(
                text="",
                model_used=request.model_name or self.model_name,
                error=str(e)
            )


