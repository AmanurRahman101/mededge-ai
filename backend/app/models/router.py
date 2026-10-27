import asyncio
import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Role, Settings, Target
from app.models.providers import (
    Completion,
    Part,
    ProviderError,
    TextPart,
    Usage,
    make_provider,
)

T = TypeVar("T", bound=BaseModel)

_SCHEMA_KEYWORDS_TO_DROP = {"default", "title"}
_MAX_SCHEMA_DEPTH = 48


@dataclass
class Attempt:
    target: str
    ok: bool
    latency_ms: int
    error: str | None = None


@dataclass
class StructuredResult(Generic[T]):
    value: T
    target: Target
    usage: Usage
    latency_ms: int
    attempts: list[Attempt]

    @property
    def fell_back(self) -> bool:
        return any(a.target != str(self.target) for a in self.attempts)


class NoProviderAvailable(Exception):
    def __init__(self, role: str, attempts: list[Attempt]):
        self.role = role
        self.attempts = attempts
        tried = "; ".join(f"{a.target} ({a.error})" for a in attempts) or "empty chain"
        super().__init__(f"No provider could serve role {role!r}: {tried}")


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic schema rewritten for constrained decoding: refs inlined, closed objects."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    return _resolve(schema, defs, 0)


def _resolve(node: Any, defs: dict[str, Any], depth: int) -> Any:
    if depth > _MAX_SCHEMA_DEPTH:
        raise ValueError("Recursive schemas are not supported by structured output")
    if isinstance(node, list):
        return [_resolve(item, defs, depth + 1) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return _resolve(defs[node["$ref"].rsplit("/", 1)[-1]], defs, depth + 1)
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _SCHEMA_KEYWORDS_TO_DROP:
            continue
        if key == "properties":
            out[key] = {name: _resolve(sub, defs, depth + 1) for name, sub in value.items()}
        else:
            out[key] = _resolve(value, defs, depth + 1)
    if out.get("type") == "object" and "properties" in out:
        out["additionalProperties"] = False
        out["required"] = list(out["properties"])
    return out


def _json_body(text: str) -> str:
    text = text.strip()
    if text.startswith("{"):
        return text
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def _repair_note(previous: str, exc: ValidationError) -> str:
    problems = "\n".join(
        f"- {'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}"
        for err in exc.errors(include_url=False)[:20]
    )
    return (
        "Your previous reply did not match the required JSON schema.\n"
        f"Validation errors:\n{problems}\n"
        f"Previous reply (truncated):\n{previous[:2000]}\n"
        "Return only the corrected JSON object."
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


class ModelRouter:
    """Resolves a role to its provider chain and returns schema-validated output.

    Each target gets one backoff retry on transient errors (429, 5xx, network) and one
    repair turn on schema errors before the router moves to the next target.
    """

    def __init__(self, settings: Settings, http: httpx.AsyncClient, retry_backoff_s: float = 1.5):
        self.settings = settings
        self.http = http
        self.retry_backoff_s = retry_backoff_s

    async def structured(
        self,
        role: Role,
        *,
        instructions: str,
        parts: list[Part],
        schema: type[T],
        name: str | None = None,
        reasoning: str = "low",
        max_output_tokens: int = 16384,
    ) -> StructuredResult[T]:
        json_schema = strict_json_schema(schema)
        schema_name = name or schema.__name__
        attempts: list[Attempt] = []

        for target in self.settings.chain(role):
            endpoint = self.settings.endpoint(target.provider)
            if endpoint is None or not endpoint.configured:
                reason = "unknown provider" if endpoint is None else "not configured"
                attempts.append(Attempt(str(target), False, 0, reason))
                continue

            provider = make_provider(endpoint, self.http)
            request_parts = list(parts)
            transient_retry_used = False
            schema_repair_used = False

            while True:
                started = time.perf_counter()
                try:
                    completion: Completion = await provider.complete_json(
                        model=target.model,
                        instructions=instructions,
                        parts=request_parts,
                        schema_name=schema_name,
                        schema=json_schema,
                        reasoning=reasoning,
                        max_output_tokens=max_output_tokens,
                    )
                except ProviderError as exc:
                    attempts.append(Attempt(str(target), False, _elapsed_ms(started), str(exc)))
                    if exc.retryable and not transient_retry_used:
                        transient_retry_used = True
                        await asyncio.sleep(self.retry_backoff_s)
                        continue
                    break

                try:
                    value = schema.model_validate_json(_json_body(completion.text))
                except ValidationError as exc:
                    attempts.append(
                        Attempt(
                            str(target),
                            False,
                            _elapsed_ms(started),
                            f"schema mismatch ({exc.error_count()} errors)",
                        )
                    )
                    if schema_repair_used:
                        break
                    schema_repair_used = True
                    request_parts = [*parts, TextPart(_repair_note(completion.text, exc))]
                    continue

                latency = _elapsed_ms(started)
                attempts.append(Attempt(str(target), True, latency))
                return StructuredResult(value, target, completion.usage, latency, attempts)

        raise NoProviderAvailable(role, attempts)
