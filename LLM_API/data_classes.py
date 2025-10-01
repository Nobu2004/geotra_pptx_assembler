from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ========== Enums ==========

class SearchMode(Enum):
    """Web検索モード"""
    AUTO = "auto"
    ON = "on"
    OFF = "off"


class ToolChoice(Enum):
    """Tool使用の選択肢"""
    AUTO = "auto"
    REQUIRED = "required"
    NONE = "none"


# ========== Base Classes ==========

@dataclass
class BaseRequest:
    """全てのリクエストの基底クラス"""
    prompt: str = ""
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（APIリクエスト用）"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class BaseResponse:
    """全てのレスポンスの基底クラス"""
    text: str = ""
    model_used: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None
    raw_response: Optional[Any] = None

    @property
    def success(self) -> bool:
        """リクエストが成功したか"""
        return self.error is None


# ========== Web Search ==========

@dataclass
class Citation:
    """引用情報"""
    url: str = ""
    title: Optional[str] = None
    text: Optional[str] = None
    start_index: Optional[int] = None
    end_index: Optional[int] = None
    page_age: Optional[str] = None
    encrypted_index: Optional[str] = None


@dataclass
class SearchResult:
    """検索結果の個別アイテム"""
    url: str = ""
    title: Optional[str] = None
    snippet: Optional[str] = None
    page_age: Optional[str] = None
    encrypted_content: Optional[str] = None


@dataclass
class WebSearchRequest(BaseRequest):
    """Web検索リクエスト（全プロバイダー統一）"""
    # 共通パラメータ
    search_mode: SearchMode = SearchMode.AUTO
    max_search_results: int = 20

    # ドメインフィルター（allowed/blockedは排他的）
    allowed_domains: Optional[List[str]] = None
    blocked_domains: Optional[List[str]] = None

    # 日付フィルター
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    recency_filter: Optional[str] = None  # Perplexity用

    # 位置情報
    user_location: Optional[Dict[str, str]] = None  # country, city, region等

    # プロバイダー固有
    search_context_size: str = "medium"  # OpenAI用
    max_uses: int = 5  # Claude用
    sources: Optional[List[Dict]] = None  # Grok用

    def __post_init__(self):
        """バリデーション"""
        if self.allowed_domains and self.blocked_domains:
            raise ValueError("allowed_domainsとblocked_domainsは同時に指定できません")


@dataclass
class WebSearchResponse(BaseResponse):
    """Web検索レスポンス（全プロバイダー統一）"""
    citations: List[Citation] = field(default_factory=list)
    search_results: List[SearchResult] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    sources_used: int = 0
    web_search_requests: int = 0

    # プロバイダー固有のメタデータ
    grounding_metadata: Optional[Any] = None  # Gemini用
    search_entry_point: Optional[Dict] = None  # Gemini用

    @property
    def has_citations(self) -> bool:
        """引用が存在するか"""
        return len(self.citations) > 0

    @property
    def citation_urls(self) -> List[str]:
        """全引用URLのリスト"""
        return [c.url for c in self.citations]


# ========== Structured Output ==========

@dataclass
class StructuredOutputRequest(BaseRequest):
    """構造化出力リクエスト"""
    schema: Dict[str, Any] = field(default_factory=dict)  # JSON Schema
    schema_name: str = "response"
    schema_description: Optional[str] = None
    strict: bool = True  # OpenAI用
    instructions: Optional[str] = None


@dataclass
class StructuredOutputResponse(BaseResponse):
    """構造化出力レスポンス"""
    parsed_output: Optional[Dict[str, Any]] = None
    validation_error: Optional[str] = None

    @property
    def success(self) -> bool:
        """パースが成功したか"""
        return self.error is None and self.validation_error is None and self.parsed_output is not None


# ========== Function Calling ==========

@dataclass
class FunctionDefinition:
    """関数定義"""
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)  # JSON Schema形式
    strict: bool = True  # OpenAI用


@dataclass
class FunctionCall:
    """関数呼び出し情報"""
    id: str = ""
    name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    call_id: Optional[str] = None  # OpenAI用


@dataclass
class FunctionCallingRequest(BaseRequest):
    """関数呼び出しリクエスト"""
    functions: List[FunctionDefinition] = field(default_factory=list)
    tool_choice: ToolChoice = ToolChoice.AUTO
    specific_function: Optional[str] = None  # 特定の関数を指定する場合
    instructions: Optional[str] = None
    parallel_tool_calls: bool = True


@dataclass
class FunctionCallingResponse(BaseResponse):
    """関数呼び出しレスポンス"""
    function_calls: List[FunctionCall] = field(default_factory=list)
    stop_reason: Optional[str] = None

    @property
    def has_function_calls(self) -> bool:
        """関数呼び出しが発生したか"""
        return len(self.function_calls) > 0

    @property
    def function_names(self) -> List[str]:
        """呼び出された関数名のリスト"""
        return [fc.name for fc in self.function_calls]


# ========== Provider-Specific Conversion Helpers ==========

@dataclass
class ProviderConfig:
    """プロバイダー固有の設定"""
    provider_name: str = ""
    model_name: str = ""
    supports_web_search: bool = True
    supports_structured_output: bool = True
    supports_function_calling: bool = True

    # プロバイダー固有の制限
    max_tokens_limit: Optional[int] = None
    max_search_results_limit: Optional[int] = None
    max_allowed_domains: Optional[int] = None


# ========== Error Classes ==========

@dataclass
class LLMError:
    """LLMエラー情報"""
    error_type: str = ""
    message: str = ""
    provider: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    retry_after: Optional[int] = None  # リトライまでの秒数

    def __str__(self) -> str:
        return f"[{self.provider}] {self.error_type}: {self.message}"


# ========== Utility Functions ==========

def create_web_search_request(
    prompt: str,
    allowed_domains: Optional[List[str]] = None,
    max_results: int = 20,
    **kwargs
) -> WebSearchRequest:
    """Web検索リクエストの便利な生成関数"""
    return WebSearchRequest(
        prompt=prompt,
        allowed_domains=allowed_domains,
        max_search_results=max_results,
        **kwargs
    )


def create_structured_output_request(
    prompt: str,
    schema: Dict[str, Any],
    schema_name: str = "response",
    **kwargs
) -> StructuredOutputRequest:
    """構造化出力リクエストの便利な生成関数"""
    return StructuredOutputRequest(
        prompt=prompt,
        schema=schema,
        schema_name=schema_name,
        **kwargs
    )


def create_function_calling_request(
    prompt: str,
    functions: List[FunctionDefinition],
    **kwargs
) -> FunctionCallingRequest:
    """関数呼び出しリクエストの便利な生成関数"""
    return FunctionCallingRequest(
        prompt=prompt,
        functions=functions,
        **kwargs
    )
