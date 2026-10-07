"""Adapters whose interface and activation settings exist but whose transport is not implemented yet."""

from collections.abc import Mapping

from app.adapters.base import AdapterContext, ConfigField, EgressNotice, HealthResult, JsonScalar
from app.core.errors import AppError


class _NotImplementedAdapter:
    key = ""
    display_name = ""
    implemented = False
    config_fields: tuple[ConfigField, ...] = ()
    _notice = EgressNotice(destination="", data_kinds=(), features=())

    def data_egress_notice(self) -> EgressNotice:
        return self._notice

    def validate_config(
        self, config: Mapping[str, JsonScalar], credentials: Mapping[str, str]
    ) -> tuple[dict[str, JsonScalar], dict[str, str]]:
        raise AppError(422, "adapter_not_implemented", detail={"adapter": self.key})

    def health_check(self, ctx: AdapterContext) -> HealthResult:
        return HealthResult(ok=False, message="not_implemented")


class AgentRuntimeAdapter(_NotImplementedAdapter):
    key = "agent_runtime"
    display_name = "Agent runtime"
    config_fields: tuple[ConfigField, ...] = (ConfigField("endpoint", "text"), ConfigField("token", "secret"))
    _notice = EgressNotice(
        destination="agent runtime endpoint",
        data_kinds=("agent_task", "agent_context"),
        features=("agenthub_run",),
    )


class GitAdapter(_NotImplementedAdapter):
    key = "git"
    display_name = "Git"
    config_fields: tuple[ConfigField, ...] = (ConfigField("remote_url", "text"), ConfigField("token", "secret"))
    _notice = EgressNotice(
        destination="git remote",
        data_kinds=("generated_documents", "generated_code"),
        features=("specforge_push", "devtracker_repo"),
    )
