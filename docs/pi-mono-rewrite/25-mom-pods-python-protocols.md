# `mom` / `pods` Python `Protocol` 草案

这份文档把 `mom` 和 `pods` 进一步收敛成类和方法签名级别的接口草案。

目标是让 Python 重写时可以直接从协议层开工，而不是先在具体实现里反复试错。

---

## 1. 共享基础类型

建议先定义共享数据结构，再在 `mom` / `pods` 里复用。

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(slots=True)
class FileAttachment:
    original: str
    local: str


@dataclass(slots=True)
class LoggedMessage:
    date: str
    ts: str
    user: str
    text: str
    attachments: list[FileAttachment] = field(default_factory=list)
    is_bot: bool = False


@dataclass(slots=True)
class EnvResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
```

---

## 2. `mom` 相关协议

### 2.1 Slack 数据模型

```python
@dataclass(slots=True)
class SlackUser:
    id: str
    user_name: str
    display_name: str | None = None


@dataclass(slots=True)
class SlackChannel:
    id: str
    name: str


@dataclass(slots=True)
class SlackEvent:
    type: Literal["mention", "dm"]
    channel: str
    ts: str
    user: str
    text: str
    files: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[FileAttachment] = field(default_factory=list)
```

### 2.2 Channel store

```python
@runtime_checkable
class ChannelStore(Protocol):
    def get_channel_dir(self, channel_id: str) -> str: ...

    def process_attachments(
        self,
        channel_id: str,
        files: list[dict[str, Any]],
        timestamp: str,
    ) -> list[FileAttachment]: ...

    async def log_message(self, channel_id: str, message: LoggedMessage) -> bool: ...

    async def log_bot_response(self, channel_id: str, text: str, ts: str) -> None: ...

    def get_last_timestamp(self, channel_id: str) -> str | None: ...
```

### 2.3 Session sync

```python
@runtime_checkable
class ContextSync(Protocol):
    def sync_log_to_session_manager(self, channel_dir: str, exclude_slack_ts: str | None = None) -> int: ...
```

### 2.4 Sandbox executor

```python
@dataclass(slots=True)
class SandboxConfig:
    type: Literal["host", "docker"]
    name: str | None = None


@runtime_checkable
class SandboxExecutor(Protocol):
    async def validate(self) -> None: ...

    async def exec(self, command: str, *, cwd: str | None = None) -> EnvResult: ...

    async def exec_stream(self, command: str, *, cwd: str | None = None) -> int: ...

    def get_workspace_path(self, host_path: str) -> str: ...
```

### 2.5 Slack context

```python
@runtime_checkable
class SlackContext(Protocol):
    message: Any
    channel_name: str | None
    store: ChannelStore
    channels: list[SlackChannel]
    users: list[SlackUser]

    async def respond(self, text: str, should_log: bool = True) -> None: ...
    async def replace_message(self, text: str) -> None: ...
    async def respond_in_thread(self, text: str) -> None: ...
    async def set_typing(self, is_typing: bool) -> None: ...
    async def upload_file(self, file_path: str, title: str | None = None) -> None: ...
    async def set_working(self, working: bool) -> None: ...
    async def delete_message(self) -> None: ...
```

### 2.6 Agent runner

```python
@dataclass(slots=True)
class PendingMessage:
    user_name: str
    text: str
    attachments: list[FileAttachment] = field(default_factory=list)
    timestamp: int = 0


@runtime_checkable
class AgentRunner(Protocol):
    async def run(
        self,
        ctx: SlackContext,
        store: ChannelStore,
        pending_messages: list[PendingMessage] | None = None,
    ) -> dict[str, Any]: ...

    def abort(self) -> None: ...
```

### 2.7 Scheduler

```python
@dataclass(slots=True)
class MomScheduledEvent:
    type: Literal["immediate", "one-shot", "periodic"]
    channel_id: str
    text: str
    at: str | None = None
    schedule: str | None = None
    timezone: str | None = None


@runtime_checkable
class EventScheduler(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def register_file(self, filename: str) -> None: ...

    def cancel(self, filename: str) -> None: ...
```

### 2.8 Slack bot adapter

```python
@runtime_checkable
class MomHandler(Protocol):
    def is_running(self, channel_id: str) -> bool: ...

    async def handle_event(self, event: SlackEvent, slack: "SlackBot", is_event: bool = False) -> None: ...

    async def handle_stop(self, channel_id: str, slack: "SlackBot") -> None: ...


@runtime_checkable
class SlackBot(Protocol):
    async def start(self) -> None: ...

    def get_user(self, user_id: str) -> SlackUser | None: ...

    def get_channel(self, channel_id: str) -> SlackChannel | None: ...

    def get_all_users(self) -> list[SlackUser]: ...

    def get_all_channels(self) -> list[SlackChannel]: ...

    async def post_message(self, channel: str, text: str) -> str: ...

    async def update_message(self, channel: str, ts: str, text: str) -> None: ...

    async def delete_message(self, channel: str, ts: str) -> None: ...

    async def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str: ...

    async def upload_file(self, channel: str, file_path: str, title: str | None = None) -> None: ...

    def log_to_file(self, channel: str, entry: object) -> None: ...

    def log_bot_response(self, channel: str, text: str, ts: str) -> None: ...

    def enqueue_event(self, event: SlackEvent) -> bool: ...
```

---

## 3. `pods` 相关协议

### 3.1 基础数据模型

```python
@dataclass(slots=True)
class GPU:
    id: int
    name: str
    memory: str


@dataclass(slots=True)
class PodModel:
    model: str
    port: int
    gpu: list[int]
    pid: int


@dataclass(slots=True)
class Pod:
    ssh: str
    gpus: list[GPU]
    models: dict[str, PodModel] = field(default_factory=dict)
    models_path: str | None = None
    vllm_version: str | None = None


@dataclass(slots=True)
class PodConfig:
    active: str | None
    pods: dict[str, Pod] = field(default_factory=dict)
```

### 3.2 Config storage

```python
@runtime_checkable
class PodConfigStore(Protocol):
    def load(self) -> PodConfig: ...

    def save(self, config: PodConfig) -> None: ...

    def get_active_pod(self) -> tuple[str, Pod] | None: ...

    def set_active_pod(self, name: str) -> None: ...

    def add_pod(self, name: str, pod: Pod) -> None: ...

    def remove_pod(self, name: str) -> None: ...
```

### 3.3 SSH / SCP

```python
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
```

### 3.4 Model registry / planning

```python
@dataclass(slots=True)
class ModelConfig:
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    notes: str | None = None
    gpu_count: int = 1


@runtime_checkable
class ModelRegistry(Protocol):
    def is_known_model(self, model_id: str) -> bool: ...

    def get_known_models(self) -> list[str]: ...

    def get_model_name(self, model_id: str) -> str: ...

    def get_model_config(self, model_id: str, gpus: list[GPU], requested_gpu_count: int) -> ModelConfig | None: ...
```

### 3.5 Runtime

```python
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
```

### 3.6 Agent command bridge

```python
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
```

---

## 4. 组合层协议

建议把 `mom` 和 `pods` 的运行入口再包一层，以便测试和注入。

```python
@runtime_checkable
class MomApp(Protocol):
    async def run(self) -> None: ...

    async def stop(self) -> None: ...


@runtime_checkable
class PodsApp(Protocol):
    async def run(self, argv: list[str]) -> int: ...
```

这样 CLI 可以只依赖 `MomApp` / `PodsApp`，而不是直接依赖具体实现类。

---

## 5. 设计取舍

### `mom`

- `SlackBot` 和 `MomHandler` 必须分开
- `ChannelStore` 必须独立出来，否则日志和附件处理会耦合进 handler
- `EventScheduler` 应该可替换，避免把文件监听写死在 Slack runtime 里

### `pods`

- `PodConfigStore` 必须是唯一的状态持有者
- `SSHExecutor` 和 `ModelRegistry` 要可 mock，便于单测启动 / 停止路径
- `PodRuntime` 不要直接和 CLI 绑死，否则 `setup/start/stop/logs` 会难以复用

