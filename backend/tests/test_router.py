import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from app.config import Settings
from app.models.providers import TextPart
from app.models.router import ModelRouter, NoProviderAvailable, strict_json_schema

META_URL = "https://api.meta.ai/v1/responses"
GLIMMER_URL = "https://glimmer.test/v1/chat/completions"


class Echo(BaseModel):
    status: str
    count: int


class Row(BaseModel):
    title: str
    unit: str | None = None


class Table(BaseModel):
    rows: list[Row]
    note: str = "none"


def meta_body(text: str) -> dict:
    return {
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": text}]},
        ],
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 2},
        },
    }


def chat_body(text: str) -> dict:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3},
    }


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        model_api_key="meta-key",
        glimmer_base_url="https://glimmer.test/v1",
        role_extractor="glimmer:muse-glimmer,meta:muse-spark-1.3",
    )


async def run(settings: Settings, role: str = "extractor", schema=Echo):
    async with httpx.AsyncClient() as http:
        router = ModelRouter(settings, http, retry_backoff_s=0)
        return await router.structured(
            role, instructions="Return JSON.", parts=[TextPart("hi")], schema=schema
        )


@respx.mock
async def test_meta_request_is_stateless_and_schema_constrained(settings):
    route = respx.post(META_URL).mock(
        return_value=httpx.Response(200, json=meta_body('{"status":"ok","count":3}'))
    )
    result = await run(settings, role="agent")

    assert result.value == Echo(status="ok", count=3)
    assert result.usage.reasoning_tokens == 2
    request = route.calls[0].request
    body = json.loads(request.content)
    assert body["store"] is False
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["input"][0]["role"] == "developer"
    assert request.headers["Authorization"] == "Bearer meta-key"


@respx.mock
async def test_falls_back_to_meta_when_glimmer_is_down(settings):
    glimmer = respx.post(GLIMMER_URL).mock(return_value=httpx.Response(503))
    respx.post(META_URL).mock(
        return_value=httpx.Response(200, json=meta_body('{"status":"ok","count":1}'))
    )
    result = await run(settings)

    assert result.target.provider == "meta"
    assert result.fell_back
    assert glimmer.call_count == 2
    assert [a.ok for a in result.attempts] == [False, False, True]
    glimmer_body = json.loads(glimmer.calls[0].request.content)
    assert glimmer_body["chat_template_kwargs"] == {"reasoning_strength": "low"}
    assert glimmer_body["response_format"]["type"] == "json_schema"


@respx.mock
async def test_glimmer_serves_when_up(settings):
    respx.post(GLIMMER_URL).mock(
        return_value=httpx.Response(200, json=chat_body('```json\n{"status":"ok","count":2}\n```'))
    )
    result = await run(settings)
    assert result.target.provider == "glimmer"
    assert not result.fell_back
    assert result.value.count == 2


@respx.mock
async def test_unconfigured_target_is_skipped_without_a_request():
    settings = Settings(
        _env_file=None,
        model_api_key="meta-key",
        role_extractor="glimmer:muse-glimmer,meta:muse-spark-1.3",
    )
    respx.post(META_URL).mock(
        return_value=httpx.Response(200, json=meta_body('{"status":"ok","count":1}'))
    )
    result = await run(settings)
    assert result.attempts[0].error == "not configured"
    assert result.target.provider == "meta"


@respx.mock
async def test_schema_mismatch_gets_one_repair_turn(settings):
    route = respx.post(META_URL).mock(
        side_effect=[
            httpx.Response(200, json=meta_body('{"status":"ok"}')),
            httpx.Response(200, json=meta_body('{"status":"ok","count":4}')),
        ]
    )
    result = await run(settings, role="agent")

    assert result.value.count == 4
    repair_request = json.loads(route.calls[1].request.content)
    user_texts = [part["text"] for part in repair_request["input"][1]["content"]]
    assert any("count" in text and "Validation errors" in text for text in user_texts)


@respx.mock
async def test_client_error_moves_on_without_retrying(settings):
    glimmer = respx.post(GLIMMER_URL).mock(return_value=httpx.Response(400, json={}))
    respx.post(META_URL).mock(
        return_value=httpx.Response(200, json=meta_body('{"status":"ok","count":1}'))
    )
    await run(settings)
    assert glimmer.call_count == 1


@respx.mock
async def test_raises_with_every_attempt_when_chain_is_exhausted(settings):
    respx.post(META_URL).mock(
        return_value=httpx.Response(401, json={"error": {"message": "bad key"}})
    )
    with pytest.raises(NoProviderAvailable) as excinfo:
        await run(settings, role="agent")
    assert "bad key" in str(excinfo.value)
    assert len(excinfo.value.attempts) == 1


def test_strict_schema_inlines_refs_and_closes_objects():
    schema = strict_json_schema(Table)

    assert "$defs" not in json.dumps(schema)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["rows", "note"]
    row = schema["properties"]["rows"]["items"]
    assert row["additionalProperties"] is False
    assert row["required"] == ["title", "unit"]
    assert "title" in row["properties"]
    assert "default" not in json.dumps(schema)
