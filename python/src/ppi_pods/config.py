"""Pod configuration storage for the pods runtime."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .protocols import GPU, PodModel


@dataclass(slots=True)
class PodConfig:
    ssh: str
    gpus: list[GPU] = field(default_factory=list)
    models: dict[str, PodModel] = field(default_factory=dict)
    models_path: str = ""
    vllm_version: str = "release"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PodRegistry:
    pods: dict[str, PodConfig] = field(default_factory=dict)
    active: str | None = None


class JsonPodConfigStore:
    """Persist pod registry to a JSON file on disk."""

    def __init__(self, config_dir: str | None = None) -> None:
        base_dir = config_dir or os.getenv("PI_CONFIG_DIR") or str(Path.home() / ".pi")
        self.config_dir = Path(base_dir)
        self.config_path = self.config_dir / "pods.json"

    def load(self) -> PodRegistry:
        if not self.config_path.exists():
            return PodRegistry()

        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return PodRegistry()

        pods: dict[str, PodConfig] = {}
        for name, data in raw.get("pods", {}).items():
            if not isinstance(data, dict):
                continue
            pods[name] = self._decode_pod(data)

        active = raw.get("active")
        if active not in pods:
            active = None
        return PodRegistry(pods=pods, active=active)

    def save(self, config: PodRegistry) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "active": config.active,
            "pods": {name: self._encode_pod(pod) for name, pod in config.pods.items()},
        }
        self.config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def get_active_pod(self) -> tuple[str, PodConfig] | None:
        config = self.load()
        if not config.active:
            return None
        pod = config.pods.get(config.active)
        if pod is None:
            return None
        return config.active, pod

    def set_active_pod(self, name: str) -> None:
        config = self.load()
        if name not in config.pods:
            raise KeyError(f"Pod '{name}' not found")
        config.active = name
        self.save(config)

    def add_pod(self, name: str, pod: PodConfig, *, set_active: bool = True) -> None:
        config = self.load()
        config.pods[name] = pod
        if set_active:
            config.active = name
        self.save(config)

    def remove_pod(self, name: str) -> None:
        config = self.load()
        if name not in config.pods:
            raise KeyError(f"Pod '{name}' not found")
        del config.pods[name]
        if config.active == name:
            config.active = next(iter(config.pods), None)
        self.save(config)

    def _encode_pod(self, pod: PodConfig) -> dict[str, Any]:
        return {
            "ssh": pod.ssh,
            "gpus": [
                {"id": gpu.id, "name": gpu.name, "memory": gpu.memory}
                for gpu in pod.gpus
            ],
            "models": {
                name: {
                    "model": model.model,
                    "port": model.port,
                    "gpu": list(model.gpu),
                    "pid": model.pid,
                }
                for name, model in pod.models.items()
            },
            "models_path": pod.models_path,
            "vllm_version": pod.vllm_version,
            "metadata": pod.metadata,
        }

    def _decode_pod(self, data: dict[str, Any]) -> PodConfig:
        gpus = [
            GPU(
                id=int(item.get("id", 0)),
                name=str(item.get("name", "")),
                memory=str(item.get("memory", "")),
            )
            for item in data.get("gpus", [])
            if isinstance(item, dict)
        ]
        models = {}
        for name, item in data.get("models", {}).items():
            if not isinstance(item, dict):
                continue
            models[name] = PodModel(
                model=str(item.get("model", "")),
                port=int(item.get("port", 0)),
                gpu=[int(v) for v in item.get("gpu", []) if isinstance(v, int) or str(v).isdigit()],
                pid=int(item.get("pid", 0)),
            )
        return PodConfig(
            ssh=str(data.get("ssh", "")),
            gpus=gpus,
            models=models,
            models_path=str(data.get("models_path", "")),
            vllm_version=str(data.get("vllm_version", "release")),
            metadata=dict(data.get("metadata", {})),
        )


def load_config(config_dir: str | None = None) -> PodRegistry:
    return JsonPodConfigStore(config_dir).load()


def save_config(config: PodRegistry, config_dir: str | None = None) -> None:
    JsonPodConfigStore(config_dir).save(config)


def get_active_pod(config_dir: str | None = None) -> tuple[str, PodConfig] | None:
    return JsonPodConfigStore(config_dir).get_active_pod()


def add_pod(name: str, pod: PodConfig, config_dir: str | None = None, *, set_active: bool = True) -> None:
    JsonPodConfigStore(config_dir).add_pod(name, pod, set_active=set_active)


def remove_pod(name: str, config_dir: str | None = None) -> None:
    JsonPodConfigStore(config_dir).remove_pod(name)


def set_active_pod(name: str, config_dir: str | None = None) -> None:
    JsonPodConfigStore(config_dir).set_active_pod(name)
