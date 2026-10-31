from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

Role = Literal["extractor", "structurer", "agent"]
ROLES: tuple[Role, ...] = ("extractor", "structurer", "agent")
Protocol = Literal["responses", "chat"]


class Target(BaseModel):
    """One provider:model hop in a role's fallback chain."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


class ProviderEndpoint(BaseModel):
    name: str
    protocol: Protocol
    base_url: str
    api_key: SecretStr | None = None
    key_required: bool = True
    extra_body: dict[str, Any] = {}

    @property
    def configured(self) -> bool:
        if not self.base_url:
            return False
        return bool(self.api_key and self.api_key.get_secret_value()) or not self.key_required


def parse_chain(spec: str) -> list[Target]:
    targets: list[Target] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        provider, sep, model = part.partition(":")
        provider, model = provider.strip().lower(), model.strip()
        if not sep or not provider or not model:
            raise ValueError(f"Invalid role target {part!r}; expected provider:model")
        targets.append(Target(provider=provider, model=model))
    if not targets:
        raise ValueError("Role chain is empty")
    return targets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    model_api_key: SecretStr | None = None
    meta_base_url: str = "https://api.meta.ai/v1"

    role_extractor: str = "meta:muse-spark-1.3"
    role_structurer: str = "meta:muse-spark-1.3"
    role_agent: str = "meta:muse-spark-1.3"

    glimmer_base_url: str = ""
    glimmer_api_key: SecretStr | None = None
    glimmer_reasoning_strength: Literal["low", "medium", "high", "xhigh"] = "low"

    fireworks_base_url: str = "https://api.fireworks.ai/inference/v1"
    fireworks_api_key: SecretStr | None = None
    baseten_base_url: str = "https://inference.baseten.co/v1"
    baseten_api_key: SecretStr | None = None
    modal_base_url: str = ""
    modal_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr | None = None

    sam_provider: Literal["meta", "local"] = "meta"
    sam_model: str = "sam-3.1"
    voice_model: str = "muse-voice-transcribe-1.0"

    daily_budget_usd: float = 8.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    enable_dev_routes: bool = False
    request_timeout_s: float = 180.0
    database_url: str = "sqlite:///var/mededge.db"
    database_url_unpooled: str = ""
    runs_dir: str = "var/runs"
    hapi_base_url: str = "https://hapi.fhir.org/baseR4"
    rate_limit: str = "30/minute"
    pseudonym_salt: str = "mededge"
    sam_local_checkpoint: str = ""
    app_env: Literal["development", "production", "test"] = "development"
    trust_render_proxy: bool = False
    app_base_url: str = "http://localhost:5173"
    resend_api_key: SecretStr | None = None
    resend_from_email: str = ""
    demo_patient_email: str = ""
    demo_doctor_email: str = ""
    demo_password: SecretStr | None = None
    auth_email_daily_limit: int = 90
    auth_email_monthly_limit: int = 2500

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def chain(self, role: Role) -> list[Target]:
        return parse_chain(getattr(self, f"role_{role}"))

    def endpoint(self, provider: str) -> ProviderEndpoint | None:
        return self.endpoints().get(provider)

    def endpoints(self) -> dict[str, ProviderEndpoint]:
        glimmer_url = self.glimmer_base_url.rstrip("/")
        return {
            "meta": ProviderEndpoint(
                name="meta",
                protocol="responses",
                base_url=self.meta_base_url.rstrip("/"),
                api_key=self.model_api_key,
            ),
            "glimmer": ProviderEndpoint(
                name="glimmer",
                protocol="chat",
                base_url=glimmer_url,
                api_key=self.glimmer_api_key,
                key_required=False,
                # llama.cpp ignores reasoning_effort; Glimmer's template reads this instead.
                extra_body={
                    "chat_template_kwargs": {"reasoning_strength": self.glimmer_reasoning_strength}
                },
            ),
            "fireworks": ProviderEndpoint(
                name="fireworks",
                protocol="chat",
                base_url=self.fireworks_base_url.rstrip("/"),
                api_key=self.fireworks_api_key,
            ),
            "baseten": ProviderEndpoint(
                name="baseten",
                protocol="chat",
                base_url=self.baseten_base_url.rstrip("/"),
                api_key=self.baseten_api_key,
            ),
            "modal": ProviderEndpoint(
                name="modal",
                protocol="chat",
                base_url=self.modal_base_url.rstrip("/"),
                api_key=self.modal_api_key,
            ),
            "openrouter": ProviderEndpoint(
                name="openrouter",
                protocol="chat",
                base_url=self.openrouter_base_url.rstrip("/"),
                api_key=self.openrouter_api_key,
            ),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
