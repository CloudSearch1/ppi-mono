# `mom` 与 `pods` Python 接口草案

这份草案把 `mom` 和 `pods` 各自收敛成可实现的 Python `dataclass` / `Protocol` 接口。

它们的共同目标是：

- 保留现有行为语义
- 把 Slack / SSH / filesystem / remote process 这些外部依赖抽象出来
- 让核心编排层尽量纯净

---

## 1. `mom` 的设计目标

`mom` 的核心不是 Slack bot 本身，而是：

```text
Slack event -> channel state -> context sync -> agent run -> tool execution -> Slack response
```

要保留的语义包括：

- per-channel 独立上下文
- `log.jsonl` 作为历史事实
- `context.jsonl` 作为可喂给 LLM 的上下文
- attachment 下载与映射
- memory 文件合并
- sandbox 执行隔离
- thread reply 输出

---

## 2. `pods` 的设计目标

`pods` 的核心不是“部署脚本集合”，而是：

```text
local config -> SSH/SCP -> remote bootstrap -> vLLM process -> local state tracking
```

要保留的语义包括：

- local config 作为 source of truth
- remote start/stop/logs
- model capability selection
- GPU / vLLM compatibility
- OpenAI-compatible endpoint metadata

---

## 3. 公共基础类型

建议放在 `pimono.shared`，供 `mom` 和 `pods` 共用：

```python
from dataclasses import dataclass, field
from typing import Any


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
    stdout: str
    stderr: str
    exit_code: int
```

---

## 4. `mom` 的接口草案

### 4.1 Slack 相关模型

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
    channel: str
    user: str
    text: str
    ts: str
    thread_ts: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
```

### 4.2 channel store / log

```python
@runtime_checkable
class ChannelStore(Protocol):
    def get_channel_dir(self, channel_id: str) -> str: ...
    def process_attachments(self, channel_id: str, files: list[dict[str, Any]], timestamp: str) -> list[FileAttachment]: ...
    async def log_message(self, channel_id: str, message: LoggedMessage) -> bool: ...
    async def log_bot_response(self, channel_id: str, text: str, ts: str) -> None: ...
    def get_last_timestamp(self, channel_id: str) -> str | None: ...
```

### 4.3 context sync

```python
@runtime_checkable
class ContextSync(Protocol):
    def sync_log_to_session(self, channel_dir: str, exclude_slack_ts: str | None = None) -> int: ...
```

### 4.4 sandbox

```python
@dataclass(slots=True)
class SandboxConfig:
    type: str  # "host" | "docker"
    name: str | None = None


@runtime_checkable
class SandboxExecutor(Protocol):
    async def validate(self) -> None: ...
    async def exec(self, command: str, *, cwd: str | None = None) -> EnvResult: ...
    async def exec_stream(self, command: str, *, cwd: str | None = None) -> int: ...
```

### 4.5 agent runner

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
        ctx: "MomContext",
        store: ChannelStore,
        pending_messages: list[PendingMessage] | None = None,
    ) -> dict[str, Any]: ...

    def abort(self) -> None: ...
```

### 4.6 mom context

```python
@dataclass(slots=True)
class MomContext:
    message: SlackEvent
    channel_name: str | None
    store: ChannelStore
    channels: list[SlackChannel] = field(default_factory=list)
    users: list[SlackUser] = field(default_factory=list)

    async def respond(self, text: str, should_log: bool = True) -> None: ...
    async def replace_message(self, text: str) -> None: ...
    async def respond_in_thread(self, text: str) -> None: ...
    async def set_typing(self, is_typing: bool) -> None: ...
    async def upload_file(self, file_path: str, title: str | None = None) -> None: ...
    async def set_working(self, working: bool) -> None: ...
    async def delete_message(self) -> None: ...
```

### 4.7 event model

```python
@dataclass(slots=True)
class MomScheduledEvent:
    type: str  # "immediate" | "one-shot" | "periodic"
    channel_id: str
    text: str
    at: str | None = None
    schedule: str | None = None
    timezone: str | None = None
```

---

## 5. `mom` 的执行序列

```text
Slack event
  -> Slack adapter
  -> ChannelStore.log_message()
  -> sync_log_to_session()
  -> AgentRunner.run()
  -> agent tools / sandbox executor
  -> SlackContext.respond()/respond_in_thread()
```

### 5.1 需要拆开的职责

- Slack 适配器
- channel store
- context sync
- agent orchestration
- sandbox executor
- scheduler

---

## 6. `mom` 的 Python 选型建议

- `slack_bolt` 或 `slack_sdk`
- `asyncio`
- `pydantic`
- `watchdog`
- `apscheduler`
- `sqlite3` 或 JSONL

---

## 7. `pods` 的接口草案

### 7.1 基础配置

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
    gpus: list[GPU] = field(default_factory=list)
    models: dict[str, PodModel] = field(default_factory=dict)
    models_path: str | None = None
    vllm_version: str | None = None


@dataclass(slots=True)
class PodConfig:
    pods: dict[str, Pod] = field(default_factory=dict)
    active: str | None = None
```

### 7.2 model config

```python
@dataclass(slots=True)
class ModelConfig:
    gpu_count: int
    gpu_types: list[str] | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    notes: str | None = None


@dataclass(slots=True)
class ModelInfo:
    name: str
    configs: list[ModelConfig] = field(default_factory=list)
    notes: str | None = None
```

### 7.3 registry / resolver

```python
@runtime_checkable
class ModelRegistry(Protocol):
    def get_model_config(self, model_id: str, gpus: list[GPU], requested_gpu_count: int) -> dict[str, Any] | None: ...
    def is_known_model(self, model_id: str) -> bool: ...
    def get_known_models(self) -> list[str]: ...
    def get_model_name(self, model_id: str) -> str: ...
```

### 7.4 SSH / SCP

```python
@runtime_checkable
class SSHExecutor(Protocol):
    async def exec(self, ssh_cmd: str, command: str, *, keep_alive: bool = False) -> EnvResult: ...
    async def exec_stream(self, ssh_cmd: str, command: str, *, silent: bool = False, force_tty: bool = False) -> int: ...
    async def scp_file(self, ssh_cmd: str, local_path: str, remote_path: str) -> bool: ...
```

### 7.5 runtime manager

```python
@runtime_checkable
class PodRuntime(Protocol):
    async def setup_pod(self, name: str, ssh_cmd: str, *, mount: str | None = None, models_path: str | None = None, vllm: str | None = None) -> None: ...
    async def start_model(self, model_id: str, *, name: str, pod: str | None = None) -> None: ...
    async def stop_model(self, name: str | None = None) -> None: ...
    async def list_models(self) -> list[dict[str, Any]]: ...
    async def view_logs(self, name: str) -> None: ...
```

---

## 8. `pods` 的执行序列

### 8.1 `pi pods setup`

```text
CLI
  -> parse args
  -> load config
  -> sshExecStream(remote bootstrap)
  -> update local config
```

### 8.2 `pi start`

```text
CLI
  -> load config
  -> resolve model config
  -> pick pod / gpu allocation
  -> sshExecStream(start script)
  -> update local pod state
```

### 8.3 `pi agent`

```text
CLI
  -> resolve pod / endpoint
  -> create agent session
  -> use file tools
  -> optional interactive TUI
```

---

## 9. 推荐拆分顺序

### `mom`

1. `mom_storage`
2. `mom_platforms.slack`
3. `mom_core`
4. `mom_sandbox`
5. `mom_scheduler`

### `pods`

1. `pods_store`
2. `pods_ssh`
3. `pods_models`
4. `pods_setup`
5. `pods_runtime`
6. `pods_cli`

---

## 10. 关键风险点

### `mom`

- Slack message/thread 语义容易被简化过头
- `log.jsonl` 和 `context.jsonl` 必须分离
- attachment 下载和引用路径要稳定
- sandbox 必须是可替换的

### `pods`

- local config 与 remote state 容易不一致
- model config 规则会越来越多，必须模块化
- SSH / SCP / stream / TTY 三种执行路径要分开
- 运行日志和 PID 追踪要成为第一等数据
