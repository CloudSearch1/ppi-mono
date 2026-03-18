"""CLI entry point for pod management."""

from __future__ import annotations

import asyncio
import shlex
import sys
from pathlib import Path

import httpx

from .agent import prompt_model
from .config import JsonPodConfigStore, PodConfig
from .protocols import PodModel
from .remote import SubprocessSSHExecutor
from .vllm import VllmLaunchTemplate


def _usage() -> str:
    return (
        "Usage:\n"
        "  pi pods setup <name> <ssh> [--models-path PATH] [--vllm release|nightly|gpt-oss]\n"
        "  pi pods active <name>\n"
        "  pi pods list\n"
        "  pi pods remove <name>\n"
        "  pi start <model> --name <name> [--pod <pod>] [--memory <percent>] [--context <size>] [--gpus <count>]\n"
        "  pi stop [<name>] [--pod <pod>]\n"
        "  pi logs <name> [--pod <pod>]\n"
        "  pi agent <name> [--pod <pod>] [--api-key KEY] [prompt...]\n"
    )


def _parse_option(argv: list[str], name: str) -> str | None:
    if name in argv:
        idx = argv.index(name)
        if idx + 1 < len(argv):
            value = argv[idx + 1]
            del argv[idx : idx + 2]
            return value
    prefix = f"{name}="
    for idx, arg in enumerate(list(argv)):
        if arg.startswith(prefix):
            value = arg[len(prefix) :]
            del argv[idx]
            return value
    return None


def _next_port(pod: PodConfig) -> int:
    used = {model.port for model in pod.models.values()}
    port = 8001
    while port in used:
        port += 1
    return port


def _get_store(config_dir: str | None = None) -> JsonPodConfigStore:
    return JsonPodConfigStore(config_dir)


def _get_pod(store: JsonPodConfigStore, pod_override: str | None = None) -> tuple[str, PodConfig]:
    config = store.load()
    if pod_override:
        pod = config.pods.get(pod_override)
        if pod is None:
            raise KeyError(f"Pod '{pod_override}' not found")
        return pod_override, pod
    if config.active is None:
        raise KeyError("No active pod. Use `pi pods active <name>` first.")
    pod = config.pods.get(config.active)
    if pod is None:
        raise KeyError(f"Active pod '{config.active}' not found")
    return config.active, pod


def _ssh_target_from_cmd(ssh_cmd: str) -> str:
    parts = shlex.split(ssh_cmd)
    if not parts:
        raise ValueError("ssh_cmd cannot be empty")
    if parts[0] != "ssh":
        raise ValueError("ssh_cmd must start with 'ssh'")

    host = ""
    login_user: str | None = None
    i = 1
    while i < len(parts):
        part = parts[i]
        if part.startswith("-"):
            if part in {"-p", "-i", "-o", "-J"} and i + 1 < len(parts):
                i += 1
            elif part == "-l" and i + 1 < len(parts):
                login_user = parts[i + 1]
                i += 1
        else:
            host = part
            break
        i += 1

    if not host:
        raise ValueError("ssh_cmd must include a host")
    if login_user and "@" not in host:
        host = f"{login_user}@{host}"
    return host


def _model_path(pod: PodConfig, model_id: str) -> str:
    path = Path(model_id)
    if path.exists() or path.is_absolute() or any(sep in model_id for sep in ("/", "\\")):
        return str(path)
    if pod.models_path:
        return str(Path(pod.models_path) / model_id)
    return model_id


async def _probe_model_health(host: str, port: int, api_key: str | None = None) -> dict[str, object]:
    base_url = f"http://{host}:{port}/v1"
    headers = {}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    result: dict[str, object] = {"healthy": False, "health_status": None, "models_status": None}
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            health = await client.get(f"http://{host}:{port}/health", headers=headers)
            result["health_status"] = health.status_code
        except Exception as exc:
            result["health_error"] = str(exc)
            return result
        try:
            models = await client.get(f"{base_url}/models", headers=headers)
            result["models_status"] = models.status_code
            result["healthy"] = health.is_success and models.is_success
            try:
                result["models"] = models.json()
            except Exception:
                result["models"] = models.text
        except Exception as exc:
            result["models_error"] = str(exc)
    return result


async def _list_pods(config_dir: str | None = None) -> int:
    store = _get_store(config_dir)
    config = store.load()
    if not config.pods:
        print("No pods configured")
        return 0

    for name, pod in config.pods.items():
        active_marker = "*" if config.active == name else " "
        host = _ssh_target_from_cmd(pod.ssh).split("@", 1)[-1]
        print(f"{active_marker} {name} @ {host}")
        print(f"  models_path: {pod.models_path or '(unset)'}")
        print(f"  vllm_version: {pod.vllm_version}")
        if pod.models:
            for model_name, model in pod.models.items():
                status = f"pid={model.pid}" if model.pid else "stopped"
                health = await _probe_model_health(host, model.port)
                health_text = "healthy" if health.get("healthy") else "degraded"
                print(f"  - {model_name}: {model.model} port={model.port} {status} health={health_text}")
        else:
            print("  (no models)")
    return 0


async def setup_pod(
    name: str,
    ssh_cmd: str,
    *,
    models_path: str | None = None,
    vllm_version: str = "release",
    config_dir: str | None = None,
) -> int:
    store = _get_store(config_dir)
    executor = SubprocessSSHExecutor(ssh_cmd)

    print(f"Setting up pod '{name}'")
    test = await executor.exec("echo SSH_OK")
    if test.exit_code != 0:
        raise RuntimeError(test.stderr.strip() or "SSH connection test failed")

    pod = PodConfig(
        ssh=ssh_cmd,
        gpus=[],
        models={},
        models_path=models_path or "",
        vllm_version=vllm_version,
        metadata={},
    )
    store.add_pod(name, pod)
    print(f"✓ Pod '{name}' saved to config")
    return 0


async def start_model(
    model_id: str,
    name: str,
    *,
    pod_override: str | None = None,
    memory: str | None = None,
    context: str | None = None,
    gpus: int | None = None,
    config_dir: str | None = None,
) -> int:
    store = _get_store(config_dir)
    pod_name, pod = _get_pod(store, pod_override)
    if not pod.models_path:
        raise RuntimeError(f"Pod '{pod_name}' does not have models_path configured")
    if name in pod.models:
        raise RuntimeError(f"Model '{name}' already exists on pod '{pod_name}'")

    executor = SubprocessSSHExecutor(pod.ssh)
    port = _next_port(pod)
    model_path = _model_path(pod, model_id)
    gpu_indices = list(range(gpus)) if gpus and gpus > 0 else []
    template = VllmLaunchTemplate(
        model_path=model_path,
        name=name,
        port=port,
        memory=memory,
        context=context,
        gpus=gpus,
        extra_args=[
            "--trust-remote-code",
            "--disable-log-requests",
        ],
    )
    remote_script = template.render()
    result = await executor.exec(remote_script)
    if result.exit_code != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to start vLLM")

    pid_text = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    try:
        pid = int(pid_text)
    except ValueError as exc:
        raise RuntimeError(f"Could not parse remote pid from: {result.stdout!r}") from exc

    pod.models[name] = PodModel(model=model_id, port=port, gpu=gpu_indices, pid=pid)
    store.add_pod(pod_name, pod, set_active=False)

    host = _ssh_target_from_cmd(pod.ssh).split("@", 1)[-1]
    print(f"✓ Started model '{name}' on pod '{pod_name}'")
    print(f"  URL: http://{host}:{port}/v1")
    print(f"  PID: {pid}")
    return 0


async def stop_model(
    name: str,
    *,
    pod_override: str | None = None,
    config_dir: str | None = None,
) -> int:
    store = _get_store(config_dir)
    pod_name, pod = _get_pod(store, pod_override)
    model = pod.models.get(name)
    if model is None:
        raise RuntimeError(f"Model '{name}' not found on pod '{pod_name}'")

    executor = SubprocessSSHExecutor(pod.ssh)
    await executor.exec(f"pkill -TERM -P {model.pid} 2>/dev/null || true; kill {model.pid} 2>/dev/null || true")
    del pod.models[name]
    store.add_pod(pod_name, pod, set_active=False)
    print(f"✓ Stopped model '{name}' on pod '{pod_name}'")
    return 0


async def stop_all_models(
    *,
    pod_override: str | None = None,
    config_dir: str | None = None,
) -> int:
    store = _get_store(config_dir)
    pod_name, pod = _get_pod(store, pod_override)
    if not pod.models:
        print(f"No models running on pod '{pod_name}'")
        return 0

    executor = SubprocessSSHExecutor(pod.ssh)
    for model in list(pod.models.values()):
        await executor.exec(f"pkill -TERM -P {model.pid} 2>/dev/null || true; kill {model.pid} 2>/dev/null || true")
    pod.models.clear()
    store.add_pod(pod_name, pod, set_active=False)
    print(f"✓ Stopped all models on pod '{pod_name}'")
    return 0


async def view_logs(
    name: str,
    *,
    pod_override: str | None = None,
    config_dir: str | None = None,
) -> int:
    store = _get_store(config_dir)
    pod_name, pod = _get_pod(store, pod_override)
    if name not in pod.models:
        raise RuntimeError(f"Model '{name}' not found on pod '{pod_name}'")

    executor = SubprocessSSHExecutor(pod.ssh)
    print(f"Streaming logs for '{name}' on pod '{pod_name}'")
    return await executor.exec_stream(f"tail -f ~/.vllm_logs/{name}/server.log", force_tty=True)


async def run_agent(
    name: str,
    *,
    pod_override: str | None = None,
    api_key: str | None = None,
    prompt: str | None = None,
    config_dir: str | None = None,
) -> int:
    user_args = [prompt] if prompt else []
    if prompt is None:
        user_args = []
    await prompt_model(name, user_args, pod_override=pod_override, api_key=api_key, config_dir=config_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if not args:
        print(_usage())
        return 1

    try:
        if args[0] == "pods":
            if len(args) < 2:
                print(_usage())
                return 1
            subcommand = args[1]
            if subcommand == "setup":
                if len(args) < 4:
                    print(_usage())
                    return 1
                name = args[2]
                ssh_cmd = args[3]
                models_path = _parse_option(args[4:], "--models-path")
                vllm = _parse_option(args[4:], "--vllm") or "release"
                return asyncio.run(
                    setup_pod(name, ssh_cmd, models_path=models_path, vllm_version=vllm)
                )
            if subcommand == "active":
                if len(args) < 3:
                    print(_usage())
                    return 1
                store = _get_store()
                store.set_active_pod(args[2])
                print(f"✓ Switched active pod to '{args[2]}'")
                return 0
            if subcommand == "list":
                return asyncio.run(_list_pods())
            if subcommand == "remove":
                if len(args) < 3:
                    print(_usage())
                    return 1
                store = _get_store()
                store.remove_pod(args[2])
                print(f"✓ Removed pod '{args[2]}'")
                return 0
            print(_usage())
            return 1

        if args[0] == "start":
            if len(args) < 2:
                print(_usage())
                return 1
            model_id = args[1]
            name = _parse_option(args[2:], "--name")
            if not name:
                raise RuntimeError("--name is required")
            pod_override = _parse_option(args[2:], "--pod")
            memory = _parse_option(args[2:], "--memory")
            context = _parse_option(args[2:], "--context")
            gpus_text = _parse_option(args[2:], "--gpus")
            gpus = int(gpus_text) if gpus_text else None
            return asyncio.run(
                start_model(
                    model_id,
                    name,
                    pod_override=pod_override,
                    memory=memory,
                    context=context,
                    gpus=gpus,
                )
            )

        if args[0] == "stop":
            name = args[1] if len(args) > 1 and not args[1].startswith("-") else None
            pod_override = _parse_option(args[1:], "--pod")
            if name:
                return asyncio.run(stop_model(name, pod_override=pod_override))
            return asyncio.run(stop_all_models(pod_override=pod_override))

        if args[0] == "logs":
            if len(args) < 2:
                print(_usage())
                return 1
            name = args[1]
            pod_override = _parse_option(args[2:], "--pod")
            return asyncio.run(view_logs(name, pod_override=pod_override))

        if args[0] == "agent":
            if len(args) < 2:
                print(_usage())
                return 1
            name = args[1]
            tail = list(args[2:])
            pod_override = _parse_option(tail, "--pod")
            api_key = _parse_option(tail, "--api-key")
            prompt = " ".join(tail).strip() or None
            return asyncio.run(
                run_agent(
                    name,
                    pod_override=pod_override,
                    api_key=api_key,
                    prompt=prompt,
                )
            )

        print(_usage())
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
