"""Helper stubs for simulating multi-stage LLM interactions in tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

DATA_CLASSES_PATH = Path(__file__).resolve().parents[1] / "LLM_API" / "data_classes.py"
spec = importlib.util.spec_from_file_location("LLM_API.data_classes", DATA_CLASSES_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
    raise RuntimeError("Failed to load LLM_API.data_classes module for tests")
data_classes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_classes)
StructuredOutputResponse = data_classes.StructuredOutputResponse
BaseResponse = data_classes.BaseResponse
WebSearchResponse = data_classes.WebSearchResponse


class MultiStageStubLLM:
    """LLM stub that returns predefined payloads for each pipeline stage."""

    model_name = "stub-multistage"

    def __init__(
        self,
        *,
        outline_payload: Dict[str, Any],
        placeholder_payloads: Iterable[Dict[str, Any]],
        structure_text: str = "構成案",
        web_search_text: str = "stub web search summary",
    ) -> None:
        self.outline_payload = outline_payload
        self.placeholder_payloads = list(placeholder_payloads)
        self.structure_text = structure_text
        self.web_search_text = web_search_text
        self.outline_requests: List[Any] = []
        self.placeholder_requests: List[Any] = []
        self.structure_requests: List[Any] = []
        self.web_search_requests: List[Any] = []

    # ------------------------------------------------------------------
    # Planner stage
    # ------------------------------------------------------------------
    def generate_content(self, request: Any) -> BaseResponse:
        self.structure_requests.append(request)
        return BaseResponse(text=self.structure_text, model_used="stub-text")

    # ------------------------------------------------------------------
    # Outline / placeholder generation
    # ------------------------------------------------------------------
    def generate_structured_output(self, request: Any) -> StructuredOutputResponse:
        if getattr(request, "schema_name", None) == "slide_outline":
            self.outline_requests.append(request)
            return StructuredOutputResponse(
                text=json.dumps(self.outline_payload, ensure_ascii=False),
                parsed_output=self.outline_payload,
                model_used="stub-structured",
            )

        if not self.placeholder_payloads:
            raise AssertionError("No placeholder payloads left for structured output request")

        payload = self.placeholder_payloads.pop(0)
        self.placeholder_requests.append(request)
        return StructuredOutputResponse(
            text=json.dumps(payload, ensure_ascii=False),
            parsed_output=payload,
            model_used="stub-structured",
        )

    # ------------------------------------------------------------------
    # Web search stage
    # ------------------------------------------------------------------
    def web_search(self, request: Any) -> WebSearchResponse:
        self.web_search_requests.append(request)
        return WebSearchResponse(text=self.web_search_text, model_used="stub-web")


__all__ = ["MultiStageStubLLM"]
