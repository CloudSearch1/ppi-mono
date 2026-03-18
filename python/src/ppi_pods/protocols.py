"""Protocol and shared dataclass definitions for the pods runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class GPU:
    id: int
    name: str
    memory: str


@dataclass(slots=True)
class PodModel:
    model: str
    port: int
    gpu: list[int] = field(default_factory=list)
    pid: int = 0


@dataclass(slots=True)
class Pod:
    ssh: str
    gpus: list[GPU] = field(default_factory=list)
    models: dict[str, PodModel] = field(default_factory=dict)
    models_path: str | None = None
    vllm_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PodConfig:
    active: str | None
    pods: dict[str, Pod] = field(default_factory=dict)


@dataclass(slots=True)
class ModelConfig:
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    notes: str | None = None
    gpu_count: int = 1


@dataclass(slots=True)
class EnvResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


@runtime_checkable
class PodConfigStore(Protocol):
    def load(self) -> PodConfig: ...

    def save(self, config: PodConfig) -> None: ...

    def get_active_pod(self) -> tuple[str, Pod] | None: ...

    def set_active_pod(self, name: str) -> None: ...

    def add_pod(self, name: str, pod: Pod) -> None: ...

    def remove_pod(self, name: str) -> None: ...


@runtime_checkable
class SSHExecutor(Protocol):
    async def exec(self, ssh_cmd: str, command: str) -> EnvResult: ...

    async def exec_stream(
        self,
        ssh_cmd: str,
        command: str,
        *,
        force_tty: bool = False,
    ) -> int: ...

    async def scp_file(self, ssh_cmd: str, local_path: str, remote_path: str) -> bool: ...


@runtime_checkable
class ModelRegistry(Protocol):
    def is_known_model(self, model_id: str) -> bool: ...

    def get_known_models(self) -> list[str]: ...

    def get_model_name(self, model_id: str) -> str: ...

    def get_model_config(self, model_id: str, gpus: list[GPU], requested_gpu_count: int) -> ModelConfig | None: ...


@runtime_checkable
class PodRuntime(Protocol):
    async def setup_pod(
        self,
        name: str,
        ssh_cmd: str,
        *,
        mount: str | None = None,
        models_path: str | None = None,
        vllm: str = "release",
    ) -> None: ...

    async def start_model(
        self,
        model_id: str,
        name: str,
        *,
        pod_override: str | None = None,
        vllm_args: list[str] | None = None,
        memory: str | None = None,
        context: str | None = None,
        gpus: int | None = None,
    ) -> None: ...

    async def stop_model(self, name: str, *, pod_override: str | None = None) -> None: ...

    async def stop_all_models(self, *, pod_override: str | None = None) -> None: ...

    async def view_logs(self, name: str, *, pod_override: str | None = None) -> None: ...


@runtime_checkable
class AgentCommandBridge(Protocol):
    async def prompt_model(
        self,
        model_name: str,
        user_args: list[str],
        *,
        pod_override: str | None = None,
        api_key: str | None = None,
    ) -> None: ...

