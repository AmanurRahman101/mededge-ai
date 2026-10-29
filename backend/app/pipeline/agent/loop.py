import json
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from app.config import Settings, Target
from app.models.providers import ProviderError
from app.pipeline.agent.prompts import AGENT_INSTRUCTIONS
from app.pipeline.agent.tools import ToolState, make_tools, tool_specs
from app.pipeline.schemas import EncounterFields, Extraction

Publish = Callable[..., None]


@dataclass
class AgentResult:
    bundle: dict | None
    state: ToolState
    target: str
    turns: int
    error: str | None = None
    trace: list[str] = field(default_factory=list)


def _output_text(data: dict) -> str:
    parts = []
    for item in data.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "output_text":
                parts.append(part.get("text") or "")
    return "".join(parts)


def _replay_item(item: dict) -> dict | None:
    kind = item.get("type")
    if kind == "function_call":
        return {
            "type": "function_call",
            "call_id": item.get("call_id"),
            "name": item.get("name"),
            "arguments": item.get("arguments") or "{}",
        }
    if kind == "reasoning" and item.get("encrypted_content"):
        replay = {
            "type": "reasoning",
            "summary": item.get("summary") or [],
            "encrypted_content": item["encrypted_content"],
        }
        if item.get("id"):
            replay["id"] = item["id"]
        return replay
    if kind == "message":
        content = [
            {"type": "output_text", "text": part.get("text") or ""}
            for part in item.get("content") or []
            if part.get("type") == "output_text"
        ]
        if content:
            replay = {"type": "message", "role": "assistant", "content": content}
            if item.get("phase"):
                replay["phase"] = item["phase"]
            return replay
    return None


async def run_agent(
    http: httpx.AsyncClient,
    settings: Settings,
    extraction: Extraction,
    encounter: EncounterFields,
    pseudonym: str,
    *,
    inject_fault: bool = False,
    max_turns: int = 8,
    publish: Publish | None = None,
) -> AgentResult:
    """Stateless Responses tool loop. store stays false, so the call is ZDR-compatible."""
    state = ToolState(extraction=extraction, inject_fault=inject_fault)
    for row in extraction.rows:
        from app.pipeline.units import normalize_unit

        unit = normalize_unit(row.unit)
        if unit:
            state.allowed_units.add(unit)
    tools = make_tools(http, state)
    target = _agent_target(settings)
    if target is None:
        return AgentResult(None, state, "none", 0, "agent provider is not configured")

    task = {
        "pseudonym": pseudonym,
        "encounter": encounter.model_dump(),
        "extraction": extraction.model_dump(),
    }
    conversation: list[dict] = [
        {
            "type": "message",
            "role": "developer",
            "content": [{"type": "input_text", "text": AGENT_INSTRUCTIONS}],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": json.dumps(task)}],
        },
    ]
    endpoint = settings.endpoint(target.provider)
    assert endpoint is not None
    headers = {"Content-Type": "application/json"}
    if endpoint.api_key and endpoint.api_key.get_secret_value():
        headers["Authorization"] = f"Bearer {endpoint.api_key.get_secret_value()}"

    for turn in range(1, max_turns + 1):
        body = {
            "model": target.model,
            "input": conversation,
            "tools": tool_specs(),
            "store": False,
            "include": ["reasoning.encrypted_content"],
            "reasoning": {"effort": "low"},
            "max_output_tokens": 16384,
        }
        try:
            response = await http.post(f"{endpoint.base_url}/responses", json=body, headers=headers)
        except httpx.HTTPError as exc:
            return AgentResult(None, state, str(target), turn, str(exc))
        if not response.is_success:
            return AgentResult(
                None,
                state,
                str(target),
                turn,
                f"HTTP {response.status_code}: {response.text[:300]}",
            )
        data = response.json()
        output = data.get("output") or []
        calls = [item for item in output if item.get("type") == "function_call"]
        for item in output:
            replay = _replay_item(item)
            if replay:
                conversation.append(replay)
        if not calls:
            if state.accepted_bundle is not None:
                return AgentResult(state.accepted_bundle, state, str(target), turn)
            return AgentResult(
                None,
                state,
                str(target),
                turn,
                _output_text(data)[:300] or "agent stopped without a bundle",
            )

        for call in calls:
            name = call.get("name") or ""
            try:
                args = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if publish:
                publish(name, args)
            fn = tools.get(name)
            if fn is None:
                result = {"error": f"unknown tool {name}"}
            else:
                try:
                    result = await fn(args if isinstance(args, dict) else {})
                except Exception as exc:  # noqa: BLE001 - return the failure to the model
                    result = {"error": str(exc)}
            if publish:
                publish(name, result, result=True)
            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": call.get("call_id"),
                    "output": json.dumps(result)[:12000],
                }
            )
        if state.accepted_bundle is not None:
            return AgentResult(state.accepted_bundle, state, str(target), turn)

    return AgentResult(None, state, str(target), max_turns, "turn limit reached")


def _agent_target(settings: Settings) -> Target | None:
    for target in settings.chain("agent"):
        endpoint = settings.endpoint(target.provider)
        if endpoint and endpoint.configured and endpoint.protocol == "responses":
            return target
    return None


class AgentError(ProviderError):
    pass
