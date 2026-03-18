"""Utilities for building vLLM launch commands."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Protocol

from .models import ModelPlan, RunningModel


class VllmLauncher(Protocol):
    def start(self, plan: ModelPlan) -> RunningModel:
        ...

    def stop(self, name: str | None = None) -> None:
        ...


@dataclass(slots=True)
class VllmLaunchTemplate:
    """Render a shell command that launches vLLM in the background."""

    model_path: str
    name: str
    port: int
    host: str = "0.0.0.0"
    memory: str | None = None
    context: str | None = None
    gpus: int | None = None
    extra_args: list[str] = field(default_factory=list)

    def render(self) -> str:
        args: list[str] = [
            "python -m vllm.entrypoints.openai.api_server",
            f'--host "{self.host}"',
            f"--port {self.port}",
            f'--model "{self.model_path}"',
            f'--served-model-name "{self.name}"',
        ]
        if self.context:
            args.append(f"--max-model-len {self.context}")
        if self.memory:
            args.append(f"--gpu-memory-utilization {self.memory}")
        if self.extra_args:
            args.extend(self.extra_args)

        env_prefix = []
        if self.gpus is not None and self.gpus > 0:
            env_prefix.append(f"CUDA_VISIBLE_DEVICES={','.join(str(i) for i in range(self.gpus))}")
        env = " ".join(env_prefix)
        command = " ".join(args)
        log_dir = f"~/.vllm_logs/{self.name}"
        return (
            "set -e\n"
            f"mkdir -p {log_dir}\n"
            f"nohup {env} {command} > {log_dir}/server.log 2>&1 < /dev/null &\n"
            "echo $!\n"
        )
