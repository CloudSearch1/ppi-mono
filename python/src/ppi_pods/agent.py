"""`pi agent` command implementation."""

from __future__ import annotations

import asyncio
import json
import shlex
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from ppi_ai import AssistantMessage, Context, Model, SimpleStreamOptions, TextContent, UserMessage, stream

from .config import JsonPodConfigStore
from .protocols import Pod, PodModel
from ppi_coding_agent.core.providers import ensure_provider_registered


@dataclass(slots=True)
class PodEndpoint:
    pod_name: str
    selection_name: str
    base_url: str
    model_name: str
    host: str
    port: int


def _ssh_target_from_cmd(ssh_cmd: str) -> str:
    parts = shlex.split(ssh_cmd)
    if not parts:
        raise ValueError("ssh_cmd cannot be empty")
    if parts[0] != "ssh":
        raise ValueError("ssh_cmd must start with ssh")
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


def _resolve_endpoint(store: JsonPodConfigStore, model_name: str, pod_override: str | None = None) -> PodEndpoint:
    registry = store.load()
    pod_name, pod = _select_pod(registry, pod_override)
    model = pod.models.get(model_name)
    if model is None:
        raise KeyError(f"Model '{model_name}' not found on pod '{pod_name}'")
    host = _ssh_target_from_cmd(pod.ssh).split("@", 1)[-1]
    return PodEndpoint(
        pod_name=pod_name,
        selection_name=model_name,
        base_url=f"http://{host}:{model.port}/v1",
        model_name=model.model,
        host=host,
        port=model.port,
    )


def _load_pod(store: JsonPodConfigStore, pod_name: str) -> Pod:
    registry = store.load()
    pod = registry.pods.get(pod_name)
    if pod is None:
        raise KeyError(f"Pod '{pod_name}' not found")
    return pod


def _describe_endpoint(endpoint: PodEndpoint) -> str:
    return (
        f"{endpoint.selection_name} -> {endpoint.model_name} "
        f"@ {endpoint.host}:{endpoint.port} ({endpoint.pod_name})"
    )


def _format_help() -> str:
    return (
        "Commands:\n"
        "  :help          Show this help\n"
        "  :model         Show the current model and pod\n"
        "  :model list    List models on the current pod\n"
        "  :model next    Switch to the next model on the current pod\n"
        "  :model prev    Switch to the previous model on the current pod\n"
        "  :model <name>  Switch to another model on the current pod\n"
        "  :retry [keep|clear]  Retry the last prompt and keep/clear context\n"
        "  :stop          Exit the chat REPL\n"
        "\n"
        "Notes:\n"
        "  - Plain text is sent as a user message.\n"
        "  - Ctrl+C cancels the current response and returns to the prompt.\n"
        "  - exit / quit also leave the REPL.\n"
    )


def _format_model_list(store: JsonPodConfigStore, endpoint: PodEndpoint) -> str:
    pod = _load_pod(store, endpoint.pod_name)
    if not pod.models:
        return f"[pods] no models registered on pod '{endpoint.pod_name}'"
    lines = [f"[pods] models on pod '{endpoint.pod_name}':"]
    for name in sorted(pod.models):
        model = pod.models[name]
        marker = "*" if name == endpoint.selection_name else " "
        lines.append(f"  {marker} {name} -> {model.model} (port {model.port}, pid {model.pid})")
    return "\n".join(lines)


def _switch_model(
    store: JsonPodConfigStore,
    endpoint: PodEndpoint,
    selection: str,
) -> PodEndpoint:
    return _resolve_endpoint(store, selection, pod_override=endpoint.pod_name)


def _switch_model_relative(
    store: JsonPodConfigStore,
    endpoint: PodEndpoint,
    direction: str,
) -> PodEndpoint:
    pod = _load_pod(store, endpoint.pod_name)
    model_names = sorted(pod.models)
    if not model_names:
        raise KeyError(f"Pod '{endpoint.pod_name}' has no models")
    try:
        current_index = model_names.index(endpoint.selection_name)
    except ValueError:
        current_index = -1 if direction == "next" else 0
    if direction == "next":
        next_index = (current_index + 1) % len(model_names)
    elif direction == "prev":
        next_index = (current_index - 1) % len(model_names)
    else:
        raise ValueError(f"Unknown direction '{direction}'")
    return _resolve_endpoint(store, model_names[next_index], pod_override=endpoint.pod_name)


def _retry_mode_from_args(parts: list[str]) -> str:
    if len(parts) == 1:
        return "keep"
    mode = parts[1].lower()
    if mode in {"keep", "clear"}:
        return mode
    raise ValueError("retry mode must be 'keep' or 'clear'")


def _select_pod(registry: Any, pod_override: str | None = None) -> tuple[str, Pod]:
    if pod_override:
        pod = registry.pods.get(pod_override)
        if pod is None:
            raise KeyError(f"Pod '{pod_override}' not found")
        return pod_override, pod
    if registry.active is None:
        raise KeyError("No active pod. Use `pi pods active <name>` first.")
    pod = registry.pods.get(registry.active)
    if pod is None:
        raise KeyError(f"Active pod '{registry.active}' not found")
    return registry.active, pod


def _extract_prompt(user_args: list[str]) -> str:
    prompt = " ".join(arg for arg in user_args if not arg.startswith("--"))
    return prompt.strip()


async def _chat_once(
    endpoint: PodEndpoint,
    prompt: str,
    api_key: str | None = None,
    *,
    messages: list[object] | None = None,
) -> str:
    model = Model(
        provider="openai",
        api="openai-completions",
        id=endpoint.model_name,
        base_url=endpoint.base_url,
    )
    bootstrap = ensure_provider_registered(model)
    if bootstrap.resolved_model is not None:
        model = bootstrap.resolved_model
    if api_key is None:
        api_key = bootstrap.api_key

    request_messages = list(messages or [])
    if not request_messages:
        request_messages = [UserMessage(content=prompt)]
    context = Context(messages=request_messages)

    try:
        assistant_stream = await stream(
            model,
            context,
            SimpleStreamOptions(api_key=api_key),
        )
        text = await _render_stream(assistant_stream)
        return text
    except Exception:
        payload = {
            "model": endpoint.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        headers = {"content-type": "application/json"}
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(f"{endpoint.base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            print(content)
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict):
                    texts.append(str(block.get("text", "")))
            output = "".join(texts)
            print(output)
            return output
        output = json.dumps(data, ensure_ascii=False, indent=2)
        print(output)
        return output


async def _render_stream(assistant_stream: Any) -> str:
    chunks: list[str] = []
    try:
        async for event in assistant_stream:
            delta = getattr(event, "delta", None)
            if delta:
                text = str(delta)
                chunks.append(text)
                print(text, end="", flush=True)
                continue
            message = getattr(event, "message", None)
            if message is not None:
                chunks.append(_message_text(message))
    except asyncio.CancelledError:
        print()
        raise
    print()
    if chunks:
        return "".join(chunks)
    result = await assistant_stream.result()
    return _message_text(result)


def _message_text(message: Any) -> str:
    content = getattr(message, "content", [])
    if isinstance(content, str):
        return content
    texts: list[str] = []
    for block in content or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(str(text))
    return "".join(texts)


async def _health_check(endpoint: PodEndpoint, api_key: str | None = None) -> dict[str, Any]:
    headers = {}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        health = await client.get(f"{endpoint.base_url.rsplit('/v1', 1)[0]}/health", headers=headers)
        models = await client.get(f"{endpoint.base_url}/models", headers=headers)
    payload: dict[str, Any] = {
        "health_status": health.status_code,
        "models_status": models.status_code,
        "healthy": health.is_success and models.is_success,
    }
    try:
        payload["models"] = models.json()
    except Exception:
        payload["models"] = models.text
    return payload


async def prompt_model(
    model_name: str,
    user_args: list[str],
    *,
    pod_override: str | None = None,
    api_key: str | None = None,
    config_dir: str | None = None,
) -> None:
    store = JsonPodConfigStore(config_dir)
    endpoint = _resolve_endpoint(store, model_name, pod_override=pod_override)
    health = await _health_check(endpoint, api_key=api_key)
    status = "healthy" if health.get("healthy") else "degraded"
    print(f"[pods] endpoint {_describe_endpoint(endpoint)} status={status}")
    if not health.get("healthy"):
        print(f"[pods] health={health.get('health_status')} models={health.get('models_status')}")

    history: list[object] = []
    last_prompt: str | None = None
    last_prompt_completed = False
    last_turn_start: int | None = None
    prompt_label = model_name

    def _update_last_turn_state(turn_start: int | None, prompt_text: str, *, completed: bool) -> None:
        nonlocal last_prompt, last_prompt_completed, last_turn_start
        last_prompt = prompt_text
        last_prompt_completed = completed
        last_turn_start = turn_start

    prompt = _extract_prompt(user_args)
    if prompt:
        await _submit_prompt(
            endpoint,
            history,
            prompt,
            api_key=api_key,
            on_success=lambda turn_start: _update_last_turn_state(turn_start, prompt, completed=True),
            on_interrupt=lambda: _update_last_turn_state(None, prompt, completed=False),
            on_error=lambda: _update_last_turn_state(None, prompt, completed=False),
        )

    while True:
        try:
            line = await asyncio.to_thread(input, f"{prompt_label}> ")
        except EOFError:
            break
        except KeyboardInterrupt:
            print()
            continue

        line = line.strip()
        if not line or line.lower() in {"exit", "quit"}:
            break
        if line.startswith(":"):
            command = line[1:].strip()
            if not command:
                print(_format_help())
                continue
            parts = shlex.split(command)
            if not parts:
                print(_format_help())
                continue
            op = parts[0].lower()
            if op == "help":
                print(_format_help())
                continue
            if op == "stop":
                print("[pods] chat session stopped")
                break
            if op == "model":
                if len(parts) == 1:
                    print(f"[pods] current model: {_describe_endpoint(endpoint)}")
                    continue
                if parts[1].lower() == "list":
                    print(_format_model_list(store, endpoint))
                    continue
                if parts[1].lower() in {"next", "prev"}:
                    try:
                        endpoint = _switch_model_relative(store, endpoint, parts[1].lower())
                        prompt_label = endpoint.selection_name
                        health = await _health_check(endpoint, api_key=api_key)
                        status = "healthy" if health.get("healthy") else "degraded"
                        print(f"[pods] switched to {_describe_endpoint(endpoint)} status={status}")
                        if not health.get("healthy"):
                            print(
                                f"[pods] health={health.get('health_status')} models={health.get('models_status')}"
                            )
                    except Exception as exc:
                        print(f"[pods] model switch failed: {exc}")
                    continue
                try:
                    endpoint = _switch_model(store, endpoint, parts[1])
                    prompt_label = endpoint.selection_name
                    health = await _health_check(endpoint, api_key=api_key)
                    status = "healthy" if health.get("healthy") else "degraded"
                    print(f"[pods] switched to {_describe_endpoint(endpoint)} status={status}")
                    if not health.get("healthy"):
                        print(f"[pods] health={health.get('health_status')} models={health.get('models_status')}")
                except Exception as exc:
                    print(f"[pods] model switch failed: {exc}")
                continue
            if op == "retry":
                if last_prompt is None:
                    print("[pods] no previous prompt to retry")
                    continue
                retry_mode = "keep"
                try:
                    retry_mode = _retry_mode_from_args(parts)
                except ValueError as exc:
                    print(f"[pods] retry failed: {exc}")
                    continue
                if retry_mode == "clear":
                    history.clear()
                elif last_prompt_completed and last_turn_start is not None:
                    del history[last_turn_start:]
                await _submit_prompt(
                    endpoint,
                    history,
                    last_prompt,
                    api_key=api_key,
                    on_success=lambda turn_start: _update_last_turn_state(turn_start, last_prompt, completed=True),
                    on_interrupt=lambda: _update_last_turn_state(None, last_prompt, completed=False),
                    on_error=lambda: _update_last_turn_state(None, last_prompt, completed=False),
                )
                continue
            print(f"[pods] unknown command: :{command}")
            print(_format_help())
            continue

        last_prompt = line
        await _submit_prompt(
            endpoint,
            history,
            line,
            api_key=api_key,
            on_success=lambda turn_start: _update_last_turn_state(turn_start, line, completed=True),
            on_interrupt=lambda: _update_last_turn_state(None, line, completed=False),
            on_error=lambda: _update_last_turn_state(None, line, completed=False),
        )


async def _submit_prompt(
    endpoint: PodEndpoint,
    history: list[object],
    prompt: str,
    *,
    api_key: str | None = None,
    on_success: Callable[[int], None] | None = None,
    on_interrupt: Callable[[], None] | None = None,
    on_error: Callable[[], None] | None = None,
) -> None:
    try:
        _, turn_start = await _run_chat_turn(endpoint, history, prompt, api_key=api_key)
        if on_success is not None:
            on_success(turn_start)
    except KeyboardInterrupt:
        print("\n[pods] cancelled current response, ready for next prompt")
        if on_interrupt is not None:
            on_interrupt()
    except Exception as exc:
        print(f"[pods] error: {exc}")
        if on_error is not None:
            on_error()


async def _run_chat_turn(
    endpoint: PodEndpoint,
    history: list[object],
    prompt: str,
    *,
    api_key: str | None = None,
) -> tuple[str, int]:
    start_len = len(history)
    history.append(UserMessage(content=prompt))
    try:
        output = await _chat_once(endpoint, prompt, api_key=api_key, messages=history)
        history.append(
            AssistantMessage(
                content=[TextContent(text=output)],
                provider="openai",
                api="openai-completions",
                model=endpoint.model_name,
            )
        )
        return output, start_len
    except BaseException:
        del history[start_len:]
        raise
