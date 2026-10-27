import base64
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import ProviderEndpoint


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ImagePart:
    data: bytes
    mime: str = "image/png"

    @property
    def data_url(self) -> str:
        return f"data:{self.mime};base64,{base64.b64encode(self.data).decode('ascii')}"


Part = TextPart | ImagePart


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass
class Completion:
    text: str
    usage: Usage


class ProviderError(Exception):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class JsonProvider(Protocol):
    async def complete_json(
        self,
        *,
        model: str,
        instructions: str,
        parts: list[Part],
        schema_name: str,
        schema: dict[str, Any],
        reasoning: str,
        max_output_tokens: int,
    ) -> Completion: ...


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or err)[:300]
    return str(body)[:300]


class _HttpProvider:
    def __init__(self, endpoint: ProviderEndpoint, http: httpx.AsyncClient):
        self.endpoint = endpoint
        self.http = http

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.endpoint.api_key and self.endpoint.api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {self.endpoint.api_key.get_secret_value()}"
        return headers

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.endpoint.base_url}{path}"
        try:
            response = await self.http.post(url, json=body, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self.endpoint.name} timed out", retryable=True) from exc
        except httpx.TransportError as exc:
            raise ProviderError(f"{self.endpoint.name} unreachable: {exc}", retryable=True) from exc
        if not response.is_success:
            status = response.status_code
            raise ProviderError(
                f"{self.endpoint.name} HTTP {status}: {_error_detail(response)}",
                status=status,
                retryable=status == 429 or status >= 500,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError(f"{self.endpoint.name} returned non-JSON body") from exc


class ResponsesProvider(_HttpProvider):
    """Meta Model API Responses endpoint. store=False keeps every call ZDR-compatible."""

    async def complete_json(
        self,
        *,
        model: str,
        instructions: str,
        parts: list[Part],
        schema_name: str,
        schema: dict[str, Any],
        reasoning: str,
        max_output_tokens: int,
    ) -> Completion:
        content = [
            {"type": "input_text", "text": p.text}
            if isinstance(p, TextPart)
            else {"type": "input_image", "image_url": p.data_url}
            for p in parts
        ]
        body = {
            "model": model,
            "input": [
                {
                    "type": "message",
                    "role": "developer",
                    "content": [{"type": "input_text", "text": instructions}],
                },
                {"type": "message", "role": "user", "content": content},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
            "reasoning": {"effort": reasoning},
            "store": False,
            "max_output_tokens": max_output_tokens,
        }
        data = await self._post("/responses", body)
        status = data.get("status")
        if status not in (None, "completed"):
            details = data.get("incomplete_details") or data.get("error") or {}
            raise ProviderError(f"{self.endpoint.name} response {status}: {details}")
        text = "".join(
            part.get("text", "")
            for item in data.get("output", [])
            if item.get("type") == "message"
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        )
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            usage=Usage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                reasoning_tokens=(usage.get("output_tokens_details") or {}).get(
                    "reasoning_tokens", 0
                ),
            ),
        )


class ChatProvider(_HttpProvider):
    """OpenAI-compatible Chat Completions: hosted partners and self-hosted Glimmer."""

    async def complete_json(
        self,
        *,
        model: str,
        instructions: str,
        parts: list[Part],
        schema_name: str,
        schema: dict[str, Any],
        reasoning: str,
        max_output_tokens: int,
    ) -> Completion:
        content = [
            {"type": "text", "text": p.text}
            if isinstance(p, TextPart)
            else {"type": "image_url", "image_url": {"url": p.data_url}}
            for p in parts
        ]
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
            "max_tokens": max_output_tokens,
            **self.endpoint.extra_body,
        }
        data = await self._post("/chat/completions", body)
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(f"{self.endpoint.name} returned no choices")
        choice = choices[0]
        text = (choice.get("message") or {}).get("content") or ""
        if not text and choice.get("finish_reason") == "length":
            raise ProviderError(f"{self.endpoint.name} hit max_tokens before answering")
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            usage=Usage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                reasoning_tokens=(usage.get("completion_tokens_details") or {}).get(
                    "reasoning_tokens", 0
                ),
            ),
        )


def make_provider(endpoint: ProviderEndpoint, http: httpx.AsyncClient) -> JsonProvider:
    if endpoint.protocol == "responses":
        return ResponsesProvider(endpoint, http)
    return ChatProvider(endpoint, http)


async def probe(endpoint: ProviderEndpoint, http: httpx.AsyncClient) -> tuple[bool, str]:
    """Cheap reachability check: GET /models. Does not spend tokens."""
    headers = {}
    if endpoint.api_key and endpoint.api_key.get_secret_value():
        headers["Authorization"] = f"Bearer {endpoint.api_key.get_secret_value()}"
    try:
        response = await http.get(f"{endpoint.base_url}/models", headers=headers, timeout=6.0)
    except httpx.HTTPError as exc:
        return False, type(exc).__name__
    if response.is_success:
        return True, "ok"
    return False, f"HTTP {response.status_code}"
