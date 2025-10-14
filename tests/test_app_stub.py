from LLM_API.data_classes import StructuredOutputRequest

import app


def test_extract_request_excerpt_handles_missing_marker():
    prompt = "サンプルリクエスト"
    result = app._extract_request_excerpt(prompt, max_width=20)
    assert "サンプル" in result


def test_stub_structured_llm_returns_placeholders():
    schema = {
        "type": "object",
        "properties": {
            "placeholders": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "placeholder_name": {
                            "type": "string",
                            "enum": ["タイトル", "本文"],
                        }
                    },
                },
            }
        },
    }
    request = StructuredOutputRequest(
        prompt="[ユーザーからのリクエスト]\n進捗報告をまとめたい",
        schema=schema,
        schema_name="test",
    )
    llm = app.StubStructuredOutputLLM()
    response = llm.generate_structured_output(request)
    assert response.model_used == "stub-structured"
    parsed = response.parsed_output
    assert parsed is not None
    assert len(parsed["placeholders"]) == 2
    assert all(item["text"] for item in parsed["placeholders"])
