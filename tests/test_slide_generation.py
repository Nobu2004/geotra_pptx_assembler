import json
import importlib.util
import sys
from pathlib import Path

import pytest

DATA_CLASSES_PATH = Path(__file__).resolve().parents[1] / "LLM_API" / "data_classes.py"
spec = importlib.util.spec_from_file_location("LLM_API.data_classes", DATA_CLASSES_PATH)
data_classes = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(data_classes)
StructuredOutputResponse = data_classes.StructuredOutputResponse

sys.path.append(str(Path(__file__).resolve().parents[1]))

from geotra_slide.slide_document import SlideDocumentStore
from geotra_slide.slide_generation import GenerationContext, SlideContentGenerator
from geotra_slide.slide_library import SlideLibrary
from geotra_slide.slide_models import SlideDocument, SlidePage


class StubLLM:
    def __init__(self, parsed_output):
        self.parsed_output = parsed_output
        self.requests = []

    def generate_structured_output(self, request):
        self.requests.append(request)
        return StructuredOutputResponse(
            text=json.dumps(self.parsed_output, ensure_ascii=False),
            parsed_output=self.parsed_output,
            model_used="stub-model",
        )


@pytest.fixture(scope="module")
def slide_library():
    return SlideLibrary(Path("assets"))


def test_generate_cover_slide_with_structured_output(tmp_path, slide_library):
    slide = SlidePage(
        slide_id="slide_01",
        page_number=1,
        asset_id="cover_regular_001",
        asset_file="cover_regular.pptx",
        title="定例進捗報告",
    )
    document = SlideDocument(slides=[slide])

    parsed_output = {
        "placeholders": [
            {
                "placeholder_name": "テキスト プレースホルダー 3",
                "text": "JKAに関する業務進捗報告資料",
                "references": ["internal_report.md"],
            }
        ],
        "slide_summary": "JKA向け定例報告の概要",
        "citations": ["internal_report.md"],
    }
    stub_llm = StubLLM(parsed_output)
    generator = SlideContentGenerator(
        slide_library,
        llm_client=stub_llm,
        internal_document_path=Path("data/internal_report.md"),
    )

    context = GenerationContext(
        user_request="JKA向けの進捗報告資料を作りたい",
        target_company="JKA",
    )

    updated_document = generator.generate_for_slide(
        document,
        slide_id="slide_01",
        context=context,
    )

    assert updated_document.metadata["references"] == ["internal_report.md"]

    updated_slide = updated_document.get_slide("slide_01")
    assert updated_slide is not None
    assert updated_slide.notes["summary"] == "JKA向け定例報告の概要"
    assert updated_slide.notes["citations"] == ["internal_report.md"]

    placeholder_map = {item.name: item for item in updated_slide.placeholders}
    assert placeholder_map["テキスト プレースホルダー 2"].text == "JKA"
    assert placeholder_map["テキスト プレースホルダー 1"].text == "定例進捗"
    assert (
        placeholder_map["テキスト プレースホルダー 3"].text
        == "JKAに関する業務進捗報告資料"
    )
    assert placeholder_map["テキスト プレースホルダー 3"].references == [
        "internal_report.md"
    ]


def test_slide_document_store_roundtrip(tmp_path):
    slide = SlidePage(
        slide_id="slide_99",
        page_number=1,
        asset_id="dummy",
        asset_file="dummy.pptx",
        title="テスト",
    )
    document = SlideDocument(slides=[slide], metadata={"references": []})

    path = tmp_path / "slide.json"
    store = SlideDocumentStore(path)
    store.save(document)

    loaded = store.load()
    assert loaded.to_dict() == document.to_dict()
