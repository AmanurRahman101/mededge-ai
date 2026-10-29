import json

import httpx

from app.config import Settings
from app.pipeline.agent.loop import run_agent
from app.pipeline.schemas import EncounterFields, Extraction


async def test_meta_agent_replays_encrypted_reasoning_and_commentary(monkeypatch):
    requests = []

    async def lookup(arguments):
        return {"value": arguments["value"]}

    monkeypatch.setattr(
        "app.pipeline.agent.loop.make_tools", lambda http, state: {"lookup": lookup}
    )

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "reasoning",
                            "id": "rs_test",
                            "summary": [],
                            "encrypted_content": "opaque-test-value",
                        },
                        {
                            "type": "message",
                            "phase": "commentary",
                            "content": [{"type": "output_text", "text": "Checking."}],
                        },
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "lookup",
                            "arguments": '{"value":"test"}',
                        },
                    ]
                },
            )
        return httpx.Response(200, json={"output": []})

    settings = Settings(_env_file=None, model_api_key="fixture-key")
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await run_agent(
            http,
            settings,
            Extraction(document_type="other"),
            EncounterFields(),
            "PT-ANON-TEST",
        )

    assert result.turns == 2
    assert len(requests) == 2
    assert all(body["store"] is False for body in requests)
    assert all(body["include"] == ["reasoning.encrypted_content"] for body in requests)
    reasoning, commentary, call, output = requests[1]["input"][-4:]
    assert reasoning == {
        "type": "reasoning",
        "id": "rs_test",
        "summary": [],
        "encrypted_content": "opaque-test-value",
    }
    assert commentary["phase"] == "commentary"
    assert call["call_id"] == output["call_id"] == "call_1"
    assert json.loads(output["output"]) == {"value": "test"}
