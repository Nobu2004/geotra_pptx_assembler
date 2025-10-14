import os
from typing import Optional, Dict, Any, List
from openai import OpenAI
import json
from dotenv import load_dotenv
from ..data_classes import (
    BaseRequest, BaseResponse,
    WebSearchRequest, WebSearchResponse, Citation,
    StructuredOutputRequest, StructuredOutputResponse,
    FunctionCallingRequest, FunctionCallingResponse, FunctionDefinition, FunctionCall,
    ProviderConfig
)
from ..base import CallModel


class OpenAIModel(CallModel):
    """OpenAI API implementation of CallModel using data classes"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-5"):
        super().__init__(api_key=api_key, model_name=model_name)
    
    def _get_provider_config(self) -> ProviderConfig:
        return ProviderConfig(
            provider_name="OpenAI",
            model_name=self.model_name,
            supports_web_search=True,
            supports_structured_output=True,
            supports_function_calling=True,
            max_tokens_limit=128000,
            max_search_results_limit=50,
            max_allowed_domains=20
        )
    
    def setup_client(self):
        load_dotenv()
        api_key = self.api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Please set OPENAI_API_KEY in your .env file "
                "or pass it as api_key parameter to OpenAIModel constructor."
            )
        self.client = OpenAI(api_key=api_key)
    
    def generate_content(self, request: BaseRequest) -> BaseResponse:
        try:
            request_data: Dict[str, Any] = {
                "model": request.model_name or self.model_name,
                "input": request.prompt
            }
            response = self.client.responses.create(**request_data)
            return BaseResponse(
                text=getattr(response, 'output_text', ''),
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
        request_data: Dict[str, Any] = {
            "model": request.model_name or self.model_name,
            "input": request.prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": request.schema_name,
                    "schema": request.schema,
                    "strict": request.strict
                }
            }
        }
        if request.instructions:
            request_data["instructions"] = request.instructions
        try:
            response = self.client.responses.parse(**request_data)
            parsed = getattr(response, "output_parsed", None)
            serialized = json.dumps(parsed) if parsed is not None else ""
            return StructuredOutputResponse(
                text=serialized,
                parsed_output=parsed,
                model_used=request.model_name or self.model_name,
                raw_response=response,
            )
        except Exception as e:
            try:
                fallback_prompt = f"{request.prompt}\n\nPlease respond in JSON format matching this schema: {json.dumps(request.schema)}"
                fallback_response = self.client.responses.create(
                    model=request.model_name or self.model_name,
                    input=fallback_prompt
                )
                parsed = None
                try:
                    parsed = json.loads(getattr(fallback_response, 'output_text', '') or '{}')
                except Exception:
                    parsed = None
                return StructuredOutputResponse(
                    text=getattr(fallback_response, 'output_text', ''),
                    parsed_output=parsed,
                    model_used=request.model_name or self.model_name,
                    validation_error=f"Structured output parse failed: {str(e)}",
                    raw_response=fallback_response
                )
            except Exception as fallback_error:
                return StructuredOutputResponse(
                    text="",
                    model_used=request.model_name or self.model_name,
                    error=f"Structured output failed: {str(e)}, Fallback failed: {str(fallback_error)}"
                )
    
    def web_search(self, request: WebSearchRequest) -> WebSearchResponse:
        tool_config: Dict[str, Any] = {"type": "web_search"}
        if request.allowed_domains:
            tool_config["filters"] = {"allowed_domains": request.allowed_domains[:20]}
        if request.user_location:
            location_config = {"type": "approximate"}
            location_config.update(request.user_location)
            tool_config["user_location"] = location_config
        if request.search_context_size and self.model_name not in ["o3", "o3-pro", "o4-mini"] and "deep-research" not in self.model_name:
            tool_config["search_context_size"] = request.search_context_size
        include_params: List[str] = ["web_search_call.action.sources"]
        try:
            response = self.client.responses.create(
                model=request.model_name or self.model_name,
                tools=[tool_config],
                input=request.prompt,
                include=include_params
            )
            citations: List[Citation] = []
            sources: List[Dict[str, Any]] = []
            for output_item in getattr(response, 'output', []):
                if getattr(output_item, 'type', '') == "message":
                    if hasattr(output_item, 'content') and output_item.content:
                        for content_item in output_item.content:
                            if hasattr(content_item, 'annotations'):
                                for annotation in content_item.annotations:
                                    if getattr(annotation, 'type', '') == "url_citation":
                                        citations.append(Citation(
                                            url=getattr(annotation, 'url', ''),
                                            title=getattr(annotation, 'title', None),
                                            start_index=getattr(annotation, 'start_index', None),
                                            end_index=getattr(annotation, 'end_index', None)
                                        ))
                if getattr(output_item, 'type', '') == "web_search_call":
                    if hasattr(output_item, 'action') and hasattr(output_item.action, 'sources'):
                        sources.extend(output_item.action.sources)
            return WebSearchResponse(
                text=getattr(response, 'output_text', ''),
                model_used=request.model_name or self.model_name,
                citations=citations,
                raw_response=response,
                sources_used=len(sources)
            )
        except Exception as e:
            return WebSearchResponse(
                text="",
                model_used=request.model_name or self.model_name,
                error=str(e)
            )
    
    def function_calling(self, request: FunctionCallingRequest) -> FunctionCallingResponse:
        tools: List[Dict[str, Any]] = []
        for func in request.functions:
            tools.append({
                "type": "function",
                "function": {
                    "name": func.name,
                    "description": func.description,
                    "parameters": func.parameters,
                    "strict": func.strict
                }
            })
        request_data: Dict[str, Any] = {
            "model": request.model_name or self.model_name,
            "tools": tools,
            "input": request.prompt
        }
        if request.tool_choice == request.tool_choice.REQUIRED:
            request_data["tool_choice"] = "required"
        elif request.specific_function:
            request_data["tool_choice"] = {"type": "function", "name": request.specific_function}
        try:
            response = self.client.responses.create(**request_data)
            function_calls: List[FunctionCall] = []
            for output_item in getattr(response, 'output', []):
                if getattr(output_item, 'type', '') == "function_call":
                    function_calls.append(FunctionCall(
                        id=getattr(output_item, 'id', ''),
                        call_id=getattr(output_item, 'call_id', None),
                        name=getattr(output_item, 'name', ''),
                        arguments=getattr(output_item, 'arguments', {})
                    ))
            return FunctionCallingResponse(
                text=getattr(response, 'output_text', ''),
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


