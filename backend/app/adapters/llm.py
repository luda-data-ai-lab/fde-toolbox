"""LLM adapter (Anthropic Messages API). Model and limits come from the tenant's activation config."""

import time
from collections.abc import Mapping
from typing import Protocol, TypeVar

from anthropic import Anthropic, APIError
from anthropic.types import TextBlock
from pydantic import BaseModel, Field, ValidationError

from app.adapters.base import (
    AdapterCallError,
    AdapterContext,
    ConfigField,
    EgressNotice,
    HealthResult,
    JsonScalar,
    invalid_config,
)
from app.core.errors import AppError
from app.core.prompting import ResultParseError, build_json_prompt, build_retry_prompt, parse_json_result

T = TypeVar("T", bound=BaseModel)

DESTINATION = "api.anthropic.com"


class LlmConfig(BaseModel):
    model: str = Field(min_length=1, max_length=100)
    max_tokens: int = Field(default=4096, ge=1, le=64000)
    timeout_seconds: int = Field(default=60, ge=1, le=600)


class LlmCredentials(BaseModel):
    api_key: str = Field(min_length=1, max_length=500)


class Transport(Protocol):
    def complete(self, prompt: str, *, config: LlmConfig, api_key: str) -> str: ...


class AnthropicTransport:
    def complete(self, prompt: str, *, config: LlmConfig, api_key: str) -> str:
        client = Anthropic(api_key=api_key, timeout=float(config.timeout_seconds), max_retries=0)
        try:
            message = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except APIError as exc:
            raise AdapterCallError("llm", type(exc).__name__) from exc
        return "".join(block.text for block in message.content if isinstance(block, TextBlock))


class LlmClient:
    def __init__(self, ctx: AdapterContext, transport: Transport, config: LlmConfig, api_key: str) -> None:
        self._ctx = ctx
        self._transport = transport
        self._config = config
        self._api_key = api_key

    def _call(self, prompt: str, feature: str, config: LlmConfig | None = None) -> str:
        started = time.monotonic()
        request_bytes = len(prompt.encode())
        try:
            text = self._transport.complete(prompt, config=config or self._config, api_key=self._api_key)
        except AppError as exc:
            self._ctx.record_call(
                feature,
                request_bytes=request_bytes,
                response_bytes=0,
                ok=False,
                duration_ms=int((time.monotonic() - started) * 1000),
                error=exc.code,
            )
            raise
        self._ctx.record_call(
            feature,
            request_bytes=request_bytes,
            response_bytes=len(text.encode()),
            ok=True,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return text

    def generate_markdown(self, prompt: str, *, feature: str) -> str:
        return self._call(prompt, feature)

    def generate_json(self, prompt: str, schema: type[T], *, feature: str) -> T:
        """Validate against `schema`; on mismatch retry once with the errors, then fail with 502."""
        full = build_json_prompt(prompt, schema)
        text = self._call(full, feature)
        try:
            return parse_json_result(text, schema)
        except ResultParseError as first:
            text = self._call(build_retry_prompt(full, text, first), feature)
            try:
                return parse_json_result(text, schema)
            except ResultParseError as second:
                raise AppError(
                    502, "llm_invalid_response", detail={"reason": second.reason, "errors": second.errors[:20]}
                ) from second

    def ping(self) -> str:
        return self._call("Reply with OK.", "health_check", self._config.model_copy(update={"max_tokens": 16}))


class LlmAdapter:
    key = "llm"
    display_name = "LLM (Anthropic)"
    implemented = True
    config_fields: tuple[ConfigField, ...] = (
        ConfigField("model", "text"),
        ConfigField("max_tokens", "int", required=False, default=4096),
        ConfigField("timeout_seconds", "int", required=False, default=60),
        ConfigField("api_key", "secret"),
    )

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport: Transport = transport or AnthropicTransport()

    def data_egress_notice(self) -> EgressNotice:
        return EgressNotice(
            destination=DESTINATION,
            data_kinds=("prompt_text", "source_excerpts", "glossary_terms"),
            features=("flowdesk_generate", "exmigrate_formula", "specforge_enrich", "ontomap_suggest"),
        )

    def validate_config(
        self, config: Mapping[str, JsonScalar], credentials: Mapping[str, str]
    ) -> tuple[dict[str, JsonScalar], dict[str, str]]:
        try:
            cfg = LlmConfig.model_validate({k: v for k, v in config.items() if v not in (None, "")})
        except ValidationError as exc:
            raise invalid_config(str(exc.errors()[0]["loc"][0])) from exc
        try:
            creds = LlmCredentials.model_validate(dict(credentials))
        except ValidationError as exc:
            raise invalid_config("api_key") from exc
        return dict(cfg.model_dump()), {"api_key": creds.api_key}

    def client(self, ctx: AdapterContext) -> LlmClient:
        cfg, creds = self.validate_config(ctx.config, ctx.credentials)
        return LlmClient(ctx, self.transport, LlmConfig.model_validate(cfg), creds["api_key"])

    def health_check(self, ctx: AdapterContext) -> HealthResult:
        started = time.monotonic()
        try:
            self.client(ctx).ping()
        except AppError as exc:
            return HealthResult(ok=False, message=exc.code, latency_ms=int((time.monotonic() - started) * 1000))
        return HealthResult(ok=True, latency_ms=int((time.monotonic() - started) * 1000))
