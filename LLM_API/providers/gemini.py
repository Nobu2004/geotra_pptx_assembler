import os
import io
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
import httpx
import json
from dotenv import load_dotenv
from ..data_classes import (
    BaseRequest, BaseResponse,
    WebSearchRequest, WebSearchResponse, Citation, SearchResult,
    StructuredOutputRequest, StructuredOutputResponse,
    FunctionCallingRequest, FunctionCallingResponse, FunctionCall,
    ProviderConfig
)
from ..base import CallModel


class GeminiModel(CallModel):
    """Gemini API implementation of CallModel using data classes"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        super().__init__(api_key=api_key, model_name=model_name)
    
    def _get_provider_config(self) -> ProviderConfig:
        """Get Gemini provider configuration"""
        return ProviderConfig(
            provider_name="Gemini",
            model_name=self.model_name or "gemini-2.5-flash",
            supports_web_search=True,
            supports_structured_output=True,
            supports_function_calling=True,
            max_tokens_limit=8192,
            max_search_results_limit=50,
            max_allowed_domains=10
        )
    
    def setup_client(self):
        """Setup Gemini client"""
        load_dotenv()
        api_key = self.api_key or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError(
                "Gemini API key is required. Please set GEMINI_API_KEY in your .env file "
                "or pass it as api_key parameter to GeminiModel constructor."
            )
        self.client = genai.Client(api_key=api_key)
    
    def generate_content(self, request: BaseRequest) -> BaseResponse:
        """Generate content using data classes"""
        try:
            response = self.client.models.generate_content(
                model=request.model_name or self.model_name,
                contents=request.prompt
            )
            return BaseResponse(
                text=getattr(response, 'text', '') or "",
                model_used=request.model_name or self.model_name,
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
            response = self.client.models.generate_content(
                model=request.model_name or self.model_name,
                contents=request.prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=request.schema,
                )
            )
            return StructuredOutputResponse(
                text=str(getattr(response, 'parsed', None)) if hasattr(response, 'parsed') else getattr(response, 'text', ''),
                parsed_output=getattr(response, 'parsed', None),
                model_used=request.model_name or self.model_name,
                raw_response=response
            )
        except Exception as e:
            # Fallback to JSON generation and parse
            try:
                json_prompt = f"{request.prompt}\n\nPlease respond in JSON format matching this schema: {json.dumps(request.schema)}"
                fallback_response = self.client.models.generate_content(
                    model=request.model_name or self.model_name,
                    contents=json_prompt
                )
                parsed_json = json.loads(getattr(fallback_response, 'text', '') or '{}') if getattr(fallback_response, 'text', '') else None
                return StructuredOutputResponse(
                    text=getattr(fallback_response, 'text', '') or "",
                    parsed_output=parsed_json,
                    model_used=request.model_name or self.model_name,
                    validation_error=f"Schema validation bypassed due to: {str(e)}",
                    raw_response=fallback_response
                )
            except Exception as fallback_error:
                return StructuredOutputResponse(
                    text="",
                    model_used=request.model_name or self.model_name,
                    error=f"Structured output failed: {str(e)}, Fallback failed: {str(fallback_error)}"
                )
    
    def web_search(self, request: WebSearchRequest) -> WebSearchResponse:
        """Perform web search using data classes"""
        try:
            grounding_tool = types.Tool(google_search=types.GoogleSearch())
            config = types.GenerateContentConfig(tools=[grounding_tool])
            response = self.client.models.generate_content(
                model=request.model_name or self.model_name,
                contents=request.prompt,
                config=config,
            )
            citations: List[Citation] = []
            search_results: List[SearchResult] = []
            search_queries: List[str] = []
            grounding_metadata = None
            if (hasattr(response, 'candidates') and len(response.candidates) > 0 and 
                hasattr(response.candidates[0], 'grounding_metadata')):
                grounding_metadata = response.candidates[0].grounding_metadata
                if hasattr(grounding_metadata, 'web_search_queries'):
                    search_queries = grounding_metadata.web_search_queries
                if hasattr(grounding_metadata, 'grounding_chunks'):
                    for chunk in grounding_metadata.grounding_chunks:
                        if hasattr(chunk, 'web'):
                            citations.append(Citation(
                                url=getattr(chunk.web, 'uri', '') or "",
                                title=getattr(chunk.web, 'title', None)
                            ))
                            search_results.append(SearchResult(
                                url=getattr(chunk.web, 'uri', '') or "",
                                title=getattr(chunk.web, 'title', None)
                            ))
            return WebSearchResponse(
                text=getattr(response, 'text', '') or "",
                model_used=request.model_name or self.model_name,
                citations=citations,
                search_results=search_results,
                search_queries=search_queries,
                grounding_metadata=grounding_metadata,
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
            function_declarations = []
            for func_def in request.functions:
                function_declarations.append({
                    "name": func_def.name,
                    "description": func_def.description,
                    "parameters": func_def.parameters
                })
            tools = types.Tool(function_declarations=function_declarations)
            config = types.GenerateContentConfig(tools=[tools])
            response = self.client.models.generate_content(
                model=request.model_name or self.model_name,
                contents=request.prompt,
                config=config,
            )
            function_calls: List[FunctionCall] = []
            if hasattr(response, 'candidates') and len(response.candidates) > 0:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call'):
                        function_calls.append(FunctionCall(
                            id=getattr(part.function_call, 'id', f"call_{part.function_call.name}"),
                            name=part.function_call.name,
                            arguments=dict(getattr(part.function_call, 'args', {}))
                        ))
            return FunctionCallingResponse(
                text=getattr(response, 'text', '') or "",
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


